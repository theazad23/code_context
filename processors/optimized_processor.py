import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import aiofiles
from rich.progress import Progress
from config import ProcessorConfig
from .code_analyzer import CodeAnalyzer
from utils import read_file_safely, calculate_file_hash
import traceback

class OptimizedContentProcessor:
    """Processes source code files with optimized performance and memory usage."""
    
    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.analyzer = CodeAnalyzer()
        self.logger = logging.getLogger(__name__)
        if config.verbose:
            self.logger.setLevel(logging.DEBUG)
        self.stats = {
            'processed_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'total_raw_size': 0,
            'total_cleaned_size': 0,
            'processing_time': 0,
            'total_files': 0,
            'file_types': {},
            'failed_files_info': []  # New field to track failed files
        }
    
    async def should_process_file(self, file_path: Path) -> bool:
        """Determine if a file should be processed."""
        try:
            if not file_path.is_file():
                self.logger.debug(f'Skipping {file_path}: not a file')
                return False
                
            # Check file size
            size = file_path.stat().st_size
            if size > self.config.max_file_size:
                self.logger.debug(f'Skipping {file_path}: size {size} exceeds limit {self.config.max_file_size}')
                return False
                
            # Check extension
            if file_path.suffix.lower() not in self.config.included_extensions:
                self.logger.debug(f'Skipping {file_path}: extension {file_path.suffix} not in {self.config.included_extensions}')
                return False
                
            # Check excluded patterns
            rel_path = str(file_path.relative_to(self.config.target_dir))
            if any(pattern in rel_path for pattern in self.config.excluded_patterns):
                self.logger.debug(f'Skipping {file_path}: matches excluded pattern')
                return False
                
            self.logger.debug(f'Will process {file_path}')
            return True
            
        except Exception as e:
            self.logger.warning(f'Error checking file {file_path}: {e}')
            return False
    
    async def process_file(self, file_path: Path) -> Optional[Dict]:
        """Process a single file."""
        try:
            if not await self.should_process_file(file_path):
                self.stats['skipped_files'] += 1
                return None
            
            self.logger.debug(f'Starting to process {file_path}')
            
            # Check if file is empty
            raw_size = file_path.stat().st_size
            if raw_size == 0:
                self.logger.debug(f'Skipping empty file: {file_path}')
                self.stats['skipped_files'] += 1
                return None
            
            self.stats['total_raw_size'] += raw_size
            
            content = read_file_safely(file_path, self.logger)
            if not content or not content.strip():
                self.logger.debug(f'Skipping empty file: {file_path}')
                self.stats['skipped_files'] += 1
                return None
            
            # Rest of the processing remains the same...
            file_type = file_path.suffix.lstrip('.')
            try:
                cleaned_content = self.analyzer.clean_content(content, file_type)
                if not cleaned_content.strip():
                    self.logger.debug(f'Skipping {file_path}: empty after cleaning')
                    self.stats['skipped_files'] += 1
                    return None
            except Exception as e:
                self.logger.error(f'Failed to clean content of {file_path}: {e}')
                self.stats['failed_files'] += 1
                self.stats['failed_files_info'].append({
                    'file': str(file_path),
                    'error': f'Content cleaning error: {str(e)}',
                    'traceback': traceback.format_exc()
                })
                return None
            
            # Update statistics
            cleaned_size = len(cleaned_content.encode('utf-8'))
            self.stats['total_cleaned_size'] += cleaned_size
            self.stats['file_types'][file_type] = self.stats['file_types'].get(file_type, 0) + 1
            
            # Analyze code
            try:
                analysis = self.analyzer.analyze_code(cleaned_content, file_type)
                if not analysis.get('success', False):
                    error_msg = analysis.get('error', 'Unknown analysis error')
                    self.logger.error(f'Analysis failed for {file_path}: {error_msg}')
                    self.stats['failed_files'] += 1
                    self.stats['failed_files_info'].append({
                        'file': str(file_path),
                        'error': f'Analysis error: {error_msg}'
                    })
                    return None
            except Exception as e:
                self.logger.error(f'Exception during analysis of {file_path}: {e}')
                self.stats['failed_files'] += 1
                self.stats['failed_files_info'].append({
                    'file': str(file_path),
                    'error': f'Analysis exception: {str(e)}',
                    'traceback': traceback.format_exc()
                })
                return None

            self.stats['processed_files'] += 1
            self.logger.debug(f'Successfully processed {file_path}')
            
            # Return results
            return {
                'path': str(file_path.relative_to(self.config.target_dir)),
                'type': file_type,
                'analysis': analysis,
                'size': cleaned_size,
                'content': cleaned_content,
                'hash': calculate_file_hash(file_path)
            }
            
        except Exception as e:
            self.logger.error(f'Unexpected error processing {file_path}: {e}')
            self.logger.error(traceback.format_exc())
            self.stats['failed_files'] += 1
            self.stats['failed_files_info'].append({
                'file': str(file_path),
                'error': f'Unexpected error: {str(e)}',
                'traceback': traceback.format_exc()
            })
            return None
    
    async def process(self) -> dict:
        """Process all files in the target directory."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info(f'Starting processing of {self.config.target_dir}')
            
            # Collect all files
            files = [f for f in self.config.target_dir.rglob('*')
                    if f.is_file() and await self.should_process_file(f)]
            self.stats['total_files'] = len(files)
            
            # Process files with progress bar
            results = []
            with Progress() as progress:
                task = progress.add_task("[cyan]Processing files...", total=len(files))
                
                for file_path in files:
                    result = await self.process_file(file_path)
                    if result:
                        results.append(result)
                    progress.update(task, advance=1)
            
            # Write results
            output_file = self.config.output_file or f'{self.config.target_dir.name}_context.{self.config.output_format}'
            
            if self.config.output_format == 'jsonl':
                async with aiofiles.open(output_file, 'w') as f:
                    metadata = {
                        'timestamp': datetime.now().isoformat(),
                        'repository_root': str(self.config.target_dir),
                        'total_files': len(results),
                        'statistics': self.stats
                    }
                    await f.write(json.dumps(metadata) + '\n')
                    for result in results:
                        await f.write(json.dumps(result) + '\n')
            else:
                output = {
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'repository_root': str(self.config.target_dir),
                        'statistics': self.stats
                    },
                    'files': results
                }
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write(json.dumps(output, indent=2))
            
            # Update final statistics
            end_time = asyncio.get_event_loop().time()
            self.stats['processing_time'] = end_time - start_time
            
            # Log failed files if any
            if self.stats['failed_files'] > 0:
                self.logger.error("\nFailed files details:")
                for fail_info in self.stats['failed_files_info']:
                    self.logger.error(f"\nFile: {fail_info['file']}")
                    self.logger.error(f"Error: {fail_info['error']}")
                    if 'traceback' in fail_info:
                        self.logger.error(f"Traceback: {fail_info['traceback']}")
            
            return self.stats
            
        except Exception as e:
            self.logger.error(f'Error during processing: {e}')
            self.logger.error(traceback.format_exc())
            raise