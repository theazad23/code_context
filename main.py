import asyncio
import os
import sys
import argparse
import logging
from pathlib import Path

from code_context.config import ProcessorConfig
from code_context.processors.async_processor import AsyncContentProcessor
from processors.content_processor import ContentProcessor
from utils.file_utils import setup_logging

def generate_context(
    directory: str,
    output_file: str = None,
    include_tests: bool = False,
    format: str = "jsonl",
    verbose: bool = False
) -> str:
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    if not output_file:
        output_file = f"{Path(directory).name}_context.{format}"
    
    try:
        processor = ContentProcessor(
            target_dir=directory,
            include_tests=include_tests,
            output_format=format
        )
        processor.process(output_file)
        logger.info(f"\nGenerated context file: {output_file}")
        
        if include_tests:
            logger.info("Test files were included in the generated context")
        else:
            logger.info("Test files were excluded from the generated context")
            
        return output_file
            
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    
async def main():
    config = ProcessorConfig(
        target_dir="path/to/your/code",
        include_tests=True,
        output_format='jsonl',
        cache_enabled=True,
        verbose=True
    )
    
    processor = AsyncContentProcessor(config)
    await processor.process()

if __name__ == '__main__':
    asyncio.run(main())    