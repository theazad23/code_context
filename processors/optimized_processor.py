from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any
import json
import asyncio
import aiofiles
import logging
import gzip
import os
from datetime import datetime
from processors.content_processor import ContentProcessor
from config import ProcessorConfig

@dataclass
class DescriptiveKeys:
    """Fully descriptive keys for maximum LLM context understanding"""
    # File level keys
    PATH = 'file_path'
    TYPE = 'file_type'
    ANALYSIS = 'analysis'
    SIZE = 'size'
    CONTENT = 'content'
    HASH = 'content_hash'
    
    # Analysis keys
    METRICS = 'metrics'
    IMPORTS = 'imports'
    FUNCTIONS = 'functions'
    CLASSES = 'classes'
    SUCCESS = 'success'
    
    # Metric keys
    LINES_OF_CODE = 'lines_of_code'
    COMMENT_LINES = 'comment_lines'
    BLANK_LINES = 'blank_lines'
    COMPLEXITY = 'complexity'
    MAINTAINABILITY = 'maintainability_index'
    MAX_DEPTH = 'max_depth'
    
    # Function/Method keys
    NAME = 'name'
    ARGS = 'arguments'
    DECORATORS = 'decorators'
    IS_ASYNC = 'is_async'
    IS_PRIVATE = 'is_private'
    BASES = 'base_classes'
    METHODS = 'methods'

class ContentOptimizer:
    """Processes file analysis output with LLM-friendly descriptive keys"""
    
    def __init__(self):
        self.keys = DescriptiveKeys()
    
    def optimize_metrics(self, metrics: Dict) -> Dict:
        """Format metrics with descriptive keys"""
        return {k: v for k, v in {
            self.keys.LINES_OF_CODE: metrics.get('lines_of_code'),
            self.keys.COMMENT_LINES: metrics.get('comment_lines'),
            self.keys.BLANK_LINES: metrics.get('blank_lines'),
            self.keys.COMPLEXITY: metrics.get('complexity'),
            self.keys.MAINTAINABILITY: round(metrics.get('maintainability_index', 0), 2),
            self.keys.MAX_DEPTH: metrics.get('max_depth')
        }.items() if v is not None}
    
    def optimize_function(self, func: Dict) -> Dict:
        """Format function data with descriptive keys"""
        return {k: v for k, v in {
            self.keys.NAME: func['name'],
            self.keys.ARGS: func.get('args'),
            self.keys.DECORATORS: func.get('decorators'),
            self.keys.IS_ASYNC: func.get('is_async')
        }.items() if v is not None}
    
    def optimize_class(self, cls: Dict) -> Dict:
        """Format class data with descriptive keys"""
        methods = [{k: v for k, v in {
            self.keys.NAME: m['name'],
            self.keys.IS_PRIVATE: m.get('is_private'),
            self.keys.IS_ASYNC: m.get('is_async')
        }.items() if v is not None} for m in cls['methods']]
        
        return {k: v for k, v in {
            self.keys.NAME: cls['name'],
            self.keys.BASES: cls.get('bases'),
            self.keys.METHODS: methods,
            self.keys.DECORATORS: cls.get('decorators')
        }.items() if v is not None and (not isinstance(v, list) or len(v) > 0)}
    
    def optimize_analysis(self, analysis: Dict) -> Dict:
        """Format analysis data with descriptive keys"""
        if not analysis.get('success', False):
            return {self.keys.SUCCESS: False}
        
        result = {self.keys.SUCCESS: True}
        
        if metrics := analysis.get('metrics'):
            result[self.keys.METRICS] = self.optimize_metrics(metrics)
        
        if imports := analysis.get('imports'):
            result[self.keys.IMPORTS] = imports
        
        if functions := analysis.get('functions'):
            result[self.keys.FUNCTIONS] = [
                self.optimize_function(f) for f in functions
            ]
        
        if classes := analysis.get('classes'):
            result[self.keys.CLASSES] = [
                self.optimize_class(c) for c in classes
            ]
        
        return {k: v for k, v in result.items() if v is not None}
    
    def optimize_file_entry(self, entry: Dict) -> Dict:
        """Format file entry with descriptive keys"""
        return {k: v for k, v in {
            self.keys.PATH: entry['path'],
            self.keys.TYPE: entry['type'],
            self.keys.ANALYSIS: self.optimize_analysis(entry['analysis']),
            self.keys.SIZE: entry['size'],
            self.keys.CONTENT: entry['content'],
            self.keys.HASH: entry['hash']
        }.items() if v is not None}

class OptimizedContentProcessor(ContentProcessor):
    """ContentProcessor with LLM-optimized output format"""
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self.optimizer = ContentOptimizer()
    
    async def process_file(self, file_path: Path):
        """Process a single file with LLM-friendly output."""
        result = await super().process_file(file_path)
        if result:
            return self.optimizer.optimize_file_entry(result)
        return None

    async def process(self) -> dict:
        """Process files with LLM-friendly output format"""
        start_time = asyncio.get_event_loop().time()
        try:
            self.logger.info(f'Starting processing of {self.config.target_dir}')
            results = await self.process_directory()
            
            output_file = self.config.output_file or f'{self.config.target_dir.name}_context.{self.config.output_format}'
            
            if self.config.output_format == 'jsonl':
                content = []
                
                # Add descriptive metadata
                metadata = {
                    'timestamp': datetime.now().isoformat(),
                    'repository_root': str(self.config.target_dir),
                    'total_files': len(results),
                    'statistics': {k: v for k, v in self.stats.items() if v is not None}
                }
                content.append(json.dumps(metadata))
                
                # Add file entries
                for result in results:
                    if result:
                        content.append(json.dumps(result))
                
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write('\n'.join(content))
            else:
                output = {
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'repository_root': str(self.config.target_dir),
                        'statistics': {k: v for k, v in self.stats.items() if v is not None}
                    },
                    'files': [r for r in results if r]
                }
                
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write(json.dumps(output))
            
            end_time = asyncio.get_event_loop().time()
            self.stats['processing_time'] = end_time - start_time
            
            # Calculate size reduction from removing nulls
            raw_size = sum(len(str(r).encode('utf-8')) for r in results if r)
            final_size = os.path.getsize(output_file)
            reduction = (1 - final_size / raw_size) * 100
            
            self.logger.info(
                f"Output written to {output_file} "
                f"(Size reduction from null removal: {reduction:.1f}%)"
            )
            
            return self.stats
            
        except Exception as e:
            self.logger.error(f'Error during processing: {e}')
            raise