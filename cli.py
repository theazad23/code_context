import asyncio
import argparse
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def format_size(size_in_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f'{size_in_bytes:.2f} {unit}'
        size_in_bytes /= 1024
    return f'{size_in_bytes:.2f} TB'

def parse_args():
    parser = argparse.ArgumentParser(description='Code Context Generator')
    parser.add_argument('path', type=str, help='Path to code directory')
    parser.add_argument('-o', '--output', type=str, help='Output file path')
    parser.add_argument('-f', '--format', choices=['jsonl', 'json'], default='jsonl')
    parser.add_argument('--include-tests', action='store_true')
    parser.add_argument('--max-size', type=int, default=1024*1024)
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    
    path = Path(args.path)
    if not path.exists() or not path.is_dir():
        console.print(f'[red]Error:[/red] Invalid directory: {path}')
        sys.exit(1)
    return args

def display_summary(stats: dict):
    table = Table(title='Processing Summary', show_header=True, header_style='bold blue')
    table.add_column('Metric', style='cyan')
    table.add_column('Value', justify='right', style='green')
    
    metrics = [
        ('Files Processed', stats['processed_files']),
        ('Files Skipped', stats['skipped_files']),
        ('Files Failed', stats['failed_files']),
        ('Total Files', stats['total_files']),
        ('Original Size', format_size(stats['total_raw_size'])),
        ('Cleaned Size', format_size(stats['total_cleaned_size'])),
        ('Processing Time', f"{stats['processing_time']:.2f} seconds")
    ]
    
    for label, value in metrics:
        table.add_row(label, str(value))
        
    if stats['total_raw_size'] > 0:
        reduction = (1 - stats['total_cleaned_size'] / stats['total_raw_size']) * 100
        table.add_row('Size Reduction', f'{reduction:.2f}%')
        
    console.print('\n')
    console.print(table)
    console.print('\n')

async def main():
    try:
        console.print(Panel.fit('[bold blue]Code Context Generator[/bold blue]', border_style='blue'))
        args = parse_args()
        
        from config import ProcessorConfig
        from processors.optimized_processor import OptimizedContentProcessor
        
        config = ProcessorConfig(
            target_dir=args.path,
            output_file=args.output,
            output_format=args.format,
            include_tests=args.include_tests,
            max_file_size=args.max_size,
            verbose=args.verbose
        )
        
        processor = OptimizedContentProcessor(config)
        with console.status('[bold green]Processing files...') as status:
            stats = await processor.process()
            
        display_summary(stats)
        
        if config.output_file:
            console.print(f'Results written to: [bold]{config.output_file}[/bold]')
            
    except KeyboardInterrupt:
        console.print('\n[yellow]Process interrupted by user[/yellow]')
        sys.exit(1)
    except Exception as e:
        console.print(f'\n[red]Error:[/red] {str(e)}')
        if args.verbose:
            console.print_exception()
        sys.exit(1)

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())