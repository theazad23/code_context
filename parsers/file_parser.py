from pathlib import Path
from fnmatch import fnmatch
import logging
from parsers.gitignore_parser import GitignoreParser

logger = logging.getLogger(__name__)

class FileParser:
    def __init__(self, include_tests: bool = False):
        self.include_tests = include_tests
        
        self.test_patterns = {
            '**/test_*.py',
            '**/tests/*.py',
            '**/tests/**/*.py',
            '**/*_test.py',
            '**/test/*.py',
            '**/test/**/*.py',
            '**/*.spec.js',
            '**/*.test.js',
            '**/test/*.js',
            '**/tests/*.js',
            '**/__tests__/**'
        }
        
        self.ignore_patterns = {
            'node_modules', '.git', 'venv', '__pycache__',
            'dist', 'build', '.min.', 'vendor/',
            '.DS_Store', '.env', '.coverage', 'bundle.',
            'package-lock.json', 'README.md',
            '.pytest_cache', 'htmlcov', '.coverage',
            'test-results', '*.pyc', '*.pyo'
        }
        
        self.file_categories = {
            'source': {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rb'},
            'config': {'.json', '.yaml', '.yml', '.toml', '.ini', '.xml'},
            'doc': {'.md', '.rst', '.txt'},
            'style': {'.css', '.scss', '.sass', '.less'},
            'template': {'.html', '.jinja', '.jinja2', '.tmpl'},
            'shell': {'.sh', '.bash', '.zsh', '.fish'}
        }

    def is_test_file(self, file_path: str) -> bool:
        normalized_path = str(file_path).replace('\\', '/')
        return any(fnmatch(normalized_path, pattern) for pattern in self.test_patterns)

    def should_process_file(self, file_path: Path, gitignore_parser) -> bool:
        try:
            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return False
                
            rel_path = str(file_path)
            rel_path_str = rel_path.replace('\\', '/')
            
            # Check gitignore
            if gitignore_parser and gitignore_parser.is_ignored(rel_path_str):
                return False
            
            # Check standard ignore patterns
            if any(p in rel_path for p in self.ignore_patterns):
                return False
            
            # Handle test files based on include_tests flag
            is_test = self.is_test_file(rel_path_str)
            if is_test and not self.include_tests:
                return False
            
            # Check file extensions
            valid_extensions = {ext for exts in self.file_categories.values() for ext in exts}
            if file_path.suffix.lower() not in valid_extensions:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking file {file_path}: {e}")
            return False

    def get_file_type(self, file_path: Path) -> str:
        """Get the category of the file based on its extension."""
        ext = file_path.suffix.lower()
        for category, extensions in self.file_categories.items():
            if ext in extensions:
                return category
        return "unknown"