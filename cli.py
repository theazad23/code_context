# cli.py
import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.panel import Panel
from config import ProcessorConfig
from processors.optimized_processor import OptimizedContentProcessor
import aiofiles
from datetime import datetime

console = Console()

def format_size(size_in_bytes: int) -> str:
    """Format size in bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f'{size_in_bytes:.2f} {unit}'
        size_in_bytes /= 1024
    return f'{size_in_bytes:.2f} TB'

def parse_args() -> ProcessorConfig:
    """Parse command line arguments and return ProcessorConfig."""
    parser = argparse.ArgumentParser(
        description='Code Context Generator - Analyze and process code repositories',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('path', type=str, help='Path to the code directory to analyze')
    parser.add_argument('-o', '--output', type=str, help='Output file path (default: <directory_name>_context.<format>)')
    parser.add_argument('-f', '--format', choices=['jsonl', 'json'], default='jsonl', help='Output format')
    parser.add_argument('--include-tests', action='store_true', help='Include test files in analysis')
    parser.add_argument('--max-size', type=int, default=1024 * 1024, help='Maximum file size to process in bytes')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker processes')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching of analysis results')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--optimize', action='store_true', help='Use optimized output format', default=True)  
    
    args = parser.parse_args()
    
    path = Path(args.path)
    if not path.exists():
        console.print(f'[red]Error:[/red] Path does not exist: {path}')
        sys.exit(1)
    if not path.is_dir():
        console.print(f'[red]Error:[/red] Path is not a directory: {path}')
        sys.exit(1)
        
    config = ProcessorConfig(
        target_dir=path,
        output_file=args.output,
        output_format=args.format,
        include_tests=args.include_tests,
        max_file_size=args.max_size,
        worker_count=args.workers,
        cache_enabled=not args.no_cache,
        verbose=args.verbose,
        optimize=args.optimize  
    )
    
    return config

def setup_logging(verbose: bool):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
def display_summary(stats: dict):
    """Display a formatted summary of the processing results."""
    table = Table(title='Processing Summary', show_header=True, header_style='bold blue')
    table.add_column('Metric', style='cyan')
    table.add_column('Value', justify='right', style='green')
    
    table.add_row('Files Processed', str(stats['processed_files']))
    table.add_row('Files Skipped', str(stats['skipped_files']))
    table.add_row('Files Failed', str(stats['failed_files']))
    table.add_row('Cache Hits', str(stats['cache_hits']))
    table.add_row('Total Files', str(stats['total_files']))
    table.add_row('Original Size', format_size(stats['total_raw_size']))
    table.add_row('Cleaned Size', format_size(stats['total_cleaned_size']))
    
    if stats['total_raw_size'] > 0:
        reduction = (1 - stats['total_cleaned_size'] / stats['total_raw_size']) * 100
        table.add_row('Size Reduction', f'{reduction:.2f}%')
        
    table.add_row('Processing Time', f"{stats['processing_time']:.2f} seconds")
    
    if stats['processed_files'] > 0:
        avg_time = stats['processing_time'] / stats['processed_files']
        table.add_row('Average Time per File', f'{avg_time:.3f} seconds')
        
    if stats.get('file_types'):
        table.add_row('File Types', ', '.join((f'{k}: {v}' for (k, v) in stats['file_types'].items())))
        
    console.print('\n')
    console.print(table)
    console.print('\n')

async def main():
    try:
        console.print(Panel.fit(
            '[bold blue]Code Context Generator[/bold blue]\n[dim]Analyzing your code repository...[/dim]',
            border_style='blue'
        ))
        
        config = parse_args()
        setup_logging(config.verbose)  # Setup logging before creating processor
        
        processor = OptimizedContentProcessor(config)
        
        with console.status('[bold green]Processing files...') as status:
            stats = await processor.process()
            
        display_summary(stats)
        
        if config.output_file:
            console.print(f'Results written to: [bold]{config.output_file}[/bold]')
            
        if config.verbose:
            console.print('\n[bold]Additional Information:[/bold]')
            if hasattr(processor, 'cache'):
                console.print(f'• Cache directory: {processor.cache.cache_dir}')
            console.print(f"• Excluded patterns: {', '.join(config.excluded_patterns)}")
            console.print(f"• Included extensions: {', '.join(config.included_extensions)}")
            
    except KeyboardInterrupt:
        console.print('\n[yellow]Process interrupted by user[/yellow]')
        sys.exit(1)
    except Exception as e:
        console.print(f'\n[red]Error:[/red] {str(e)}')
        if config.verbose:
            console.print_exception()
        sys.exit(1)

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())