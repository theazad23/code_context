from dataclasses import dataclass
from typing import Set, Dict, Optional, List
from pathlib import Path

@dataclass
class ProcessorConfig:
    target_dir: Path
    output_file: Optional[str] = None
    include_tests: bool = False
    output_format: str = 'jsonl'
    max_file_size: int = 1024 * 1024  # 1MB
    worker_count: int = 4
    cache_enabled: bool = True
    verbose: bool = False
    optimize: bool = True  # Add this line
    excluded_patterns: Set[str] = None
    included_extensions: Set[str] = None
    
    def __post_init__(self):
        self.target_dir = Path(self.target_dir)
        if self.excluded_patterns is None:
            self.excluded_patterns = {
                'node_modules', '.git', 'venv', '__pycache__', 
                'dist', 'build', '.env', '.pytest_cache'
            }
        if self.included_extensions is None:
            self.included_extensions = {
                '.py', '.js', '.jsx', '.ts', '.tsx', '.java', 
                '.cpp', '.c', '.h', '.cs', '.go', '.rb'
            }