import json
import os
from datetime import datetime
from pathlib import Path
import logging
from parsers.gitignore_parser import GitignoreParser
from parsers.file_parser import FileParser
from processors.code_analyzer import CodeAnalyzer
from config import ProcessorConfig

class ContentProcessor:
    @staticmethod
    def format_size(size_in_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f'{size_in_bytes:.2f} {unit}'
            size_in_bytes /= 1024
        return f'{size_in_bytes:.2f} TB'
    
    def __init__(self, config: ProcessorConfig):
        self.target_dir = config.target_dir
        self.gitignore = GitignoreParser(self.target_dir / '.gitignore')
        self.file_parser = FileParser(config.include_tests)
        self.code_analyzer = CodeAnalyzer()
        self.output_format = config.output_format
        self.config = config
        self.seen_contents = set()
        self.logger = logging.getLogger('code_context.processor')
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
        self.ignored_prefixes = {
            '.git',
            '.cache',
            '__pycache__',
            'node_modules',
            'venv',
            'dist',
            'build'
        }
        self.ignored_extensions = {
            '.pyc',
            '.pyo',
            '.pyd',
            '.so',
            '.dll',
            '.dylib',
            '.pickle',
            '.pkl',
            '.log',
            '.cache',
            '.jsonl'  # Ignore output files
        }


    async def should_process_file(self, file_path: Path) -> bool:
        """Determine if a file should be processed with improved filtering."""
        try:
            if not file_path.is_file():
                return False
                
            # Quick check for ignored files using parts
            parts = file_path.parts
            if any(part.startswith('.') for part in parts):  # Hidden files/directories
                return False
                
            if any(part in self.ignored_prefixes for part in parts):
                return False
                
            # Check extension
            if file_path.suffix.lower() in self.ignored_extensions:
                return False
                
            if file_path.suffix.lower() not in self.config.included_extensions:
                if self.config.verbose:
                    rel_path = file_path.relative_to(self.config.target_dir)
                    self.logger.debug(f'Ignoring {rel_path}: unsupported extension {file_path.suffix}')
                return False

            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.config.max_file_size:
                if self.config.verbose:
                    self.logger.debug(f'Ignoring {file_path.name}: exceeds size limit')
                return False
                
            # Check excluded patterns last (most expensive check)
            rel_path = str(file_path.relative_to(self.config.target_dir))
            if any(pattern in rel_path for pattern in self.config.excluded_patterns):
                if self.config.verbose:
                    self.logger.debug(f'Ignoring {rel_path}: matches excluded pattern')
                return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f'Error checking file {file_path}: {e}')
            return False
        
    async def process_file(self, file_path: Path):
        """Process a single file with improved handling."""
        try:
            if not await self.should_process_file(file_path):
                self.stats['skipped_files'] += 1
                return None

            # Track original file size
            raw_size = os.path.getsize(file_path)
            self.stats['total_raw_size'] += raw_size

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                self.logger.warning(f"Failed to read {file_path} with UTF-8 encoding")
                self.stats['failed_files'] += 1
                return None

            if not content.strip():
                self.stats['skipped_files'] += 1
                return None

            file_type = self.file_parser.get_file_type(file_path)
            cleaned_content = self.code_analyzer.clean_content(content, file_path.suffix.lstrip('.'))
            
            # Track cleaned content size
            cleaned_size = len(cleaned_content.encode('utf-8'))
            self.stats['total_cleaned_size'] += cleaned_size
            
            # Update file type statistics
            extension = file_path.suffix.lstrip('.')
            self.stats['file_types'][extension] = self.stats['file_types'].get(extension, 0) + 1

            # Skip duplicate content
            content_hash = hash(cleaned_content)
            if content_hash in self.seen_contents:
                self.stats['skipped_files'] += 1
                return None
            self.seen_contents.add(content_hash)

            analysis = self.code_analyzer.analyze_code(cleaned_content, file_path.suffix.lstrip('.'))
            
            self.stats['processed_files'] += 1
            
            if self.config.verbose:
                self.logger.info(
                    f"Processed {file_path.name} "
                    f"({self.format_size(raw_size)} -> {self.format_size(cleaned_size)})"
                )
            
            return {
                'path': str(file_path.relative_to(self.config.target_dir)),
                'type': file_type,
                'analysis': analysis,
                'size': cleaned_size,
                'content': cleaned_content,
                'hash': content_hash
            }
            
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            self.stats['failed_files'] += 1
            return None

    async def process_directory(self):
        """Process all files in the directory."""
        files = [f for f in self.target_dir.rglob('*') if f.is_file()]
        self.stats['total_files'] = len(files)
        results = []
        
        for file_path in files:
            result = await self.process_file(file_path)
            if result:
                results.append(result)
                
        return results

    async def process(self) -> dict:
        start_time = datetime.now()
        try:
            self.logger.info(f'Starting processing of {self.target_dir}')
            results = await self.process_directory()
            
            output_file = self.config.output_file or f'{self.target_dir.name}_context.{self.output_format}'
            
            if self.output_format == 'jsonl':
                async with aiofiles.open(output_file, 'w') as f:
                    metadata = {
                        'timestamp': datetime.now().isoformat(),
                        'root': str(self.target_dir),
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
                        'root': str(self.target_dir),
                        'stats': self.stats
                    },
                    'files': results
                }
                
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write(json.dumps(output, indent=2))
            
            end_time = datetime.now()
            self.stats['processing_time'] = (end_time - start_time).total_seconds()
            return self.stats
            
        except Exception as e:
            self.logger.error(f'Error during processing: {e}')
            raise