import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Set
import json
from tqdm import tqdm
import logging
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from datetime import datetime

from utils.cache_utils import FileAnalysisCache
from utils.file_utils import calculate_file_hash, read_file_safely
from processors.code_analyzer import CodeAnalyzer
from config import ProcessorConfig
from exceptions import FileProcessingError

class AsyncContentProcessor:
    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.logger = logging.getLogger('code_context.processor')
        self.cache = FileAnalysisCache(Path('.cache'))
        self.code_analyzer = CodeAnalyzer()
        self.seen_contents: Set[str] = set()
        self.stats = {
            'processed_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'total_raw_size': 0,
            'total_cleaned_size': 0,
            'cache_hits': 0,
            'processing_time': 0,
            'total_files': 0,
            'file_types': {}
        }

    async def should_process_file(self, file_path: Path) -> bool:
        """Determine if a file should be processed based on configuration."""
        try:
            if not file_path.is_file():
                return False
                
            # Check file size
            if file_path.stat().st_size > self.config.max_file_size:
                self.logger.debug(f"Skipping {file_path}: exceeds size limit")
                return False

            # Check file extension
            if file_path.suffix.lower() not in self.config.included_extensions:
                return False

            # Check excluded patterns
            rel_path = str(file_path.relative_to(self.config.target_dir))
            if any(pattern in rel_path for pattern in self.config.excluded_patterns):
                return False

            return True
        except Exception as e:
            self.logger.warning(f"Error checking file {file_path}: {e}")
            return False

    async def process_file(self, file_path: Path) -> Optional[Dict]:
        """Process a single file asynchronously."""
        try:
            if not await self.should_process_file(file_path):
                self.stats['skipped_files'] += 1
                return None

            # Get original file size and update stats
            raw_size = file_path.stat().st_size
            self.stats['total_raw_size'] += raw_size
            
            # Update file type stats
            file_type = file_path.suffix.lstrip('.')
            self.stats['file_types'][file_type] = self.stats['file_types'].get(file_type, 0) + 1

            # Calculate file hash for caching
            file_hash = calculate_file_hash(file_path)
            
            # Check cache
            cached_result = self.cache.get(file_hash)
            if cached_result is not None:
                self.stats['cache_hits'] += 1
                self.stats['total_cleaned_size'] += len(cached_result.get('content', ''))
                self.stats['processed_files'] += 1
                return cached_result

            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    self.logger.error(f"Error reading file {file_path}: {e}")
                    self.stats['failed_files'] += 1
                    return None

            if not content:
                self.stats['skipped_files'] += 1
                return None

            # Process content in a separate process pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor() as pool:
                analysis_func = partial(
                    self.code_analyzer.analyze_code,
                    content,
                    file_type
                )
                analysis = await loop.run_in_executor(pool, analysis_func)

            # Clean content using code analyzer
            cleaned_content = self.code_analyzer.clean_content(content, file_type)

            result = {
                'path': str(file_path.relative_to(self.config.target_dir)),
                'type': file_type,
                'analysis': analysis,
                'size': len(cleaned_content),
                'content': cleaned_content,
                'hash': file_hash
            }

            # Update statistics
            self.stats['total_cleaned_size'] += len(cleaned_content)
            self.stats['processed_files'] += 1

            # Cache the result
            if self.config.cache_enabled:
                self.cache.set(file_hash, result)
            
            return result

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            self.stats['failed_files'] += 1
            return None

    async def process_directory(self) -> List[Dict]:
        """Process all files in the directory asynchronously."""
        files = [f for f in self.config.target_dir.rglob('*') 
                if await self.should_process_file(f)]
        
        results = []
        with tqdm(total=len(files), desc="Processing files") as pbar:
            # Process files in chunks to avoid memory issues
            chunk_size = 100
            for i in range(0, len(files), chunk_size):
                chunk = files[i:i + chunk_size]
                chunk_tasks = [self.process_file(f) for f in chunk]
                chunk_results = await asyncio.gather(*chunk_tasks)
                
                # Filter out None results and update progress
                valid_results = [r for r in chunk_results if r is not None]
                results.extend(valid_results)
                pbar.update(len(chunk))

        return results

    async def process(self) -> dict:
        """Main processing method."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info(f"Starting processing of {self.config.target_dir}")
            
            # Get total files before processing
            all_files = list(self.config.target_dir.rglob('*'))
            self.stats['total_files'] = len([f for f in all_files if f.is_file()])
            
            results = await self.process_directory()
            
            # Write results based on format
            output_file = self.config.output_file or f"{self.config.target_dir.name}_context.{self.config.output_format}"
            
            if self.config.output_format == 'jsonl':
                async with aiofiles.open(output_file, 'w') as f:
                    metadata = {
                        'timestamp': datetime.now().isoformat(),
                        'root': str(self.config.target_dir),
                        'file_count': len(results),
                        'stats': self.stats
                    }
                    await f.write(json.dumps(metadata) + '\n')
                    for result in results:
                        await f.write(json.dumps(result) + '\n')
            else:
                output = {
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'root': str(self.config.target_dir),
                        'stats': self.stats
                    },
                    'files': results
                }
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write(json.dumps(output, indent=2))

            # Calculate final stats
            end_time = asyncio.get_event_loop().time()
            self.stats['processing_time'] = end_time - start_time
            
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Error during processing: {e}")
            raise