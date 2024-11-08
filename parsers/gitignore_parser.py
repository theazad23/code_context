import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class GitignorePattern:
    def __init__(self, pattern: str):
        self.raw_pattern = pattern
        self.is_negated = pattern.startswith('!')
        self.is_directory_only = pattern.endswith('/')
        
        pattern = pattern[1:] if self.is_negated else pattern
        pattern = pattern.rstrip('/')
        self.regex = self._glob_to_regex(pattern)

    def _glob_to_regex(self, pattern: str) -> re.Pattern:
        regex = ''
        if not pattern.startswith('/'):
            regex = '(?:.+/)?'
        for c in pattern:
            if c == '*':
                regex += '[^/]*'
            elif c == '?':
                regex += '[^/]'
            elif c in '.[]()+^${}|':
                regex += f'\\{c}'
            else:
                regex += c
        regex = f'^{regex}(?:/.*)?$' if self.is_directory_only else f'^{regex}$'
        return re.compile(regex)

    def matches(self, path: str) -> bool:
        return bool(self.regex.match(path))

class GitignoreParser:
    def __init__(self, gitignore_path: Path):
        self.patterns = []
        self.negated_patterns = []
        
        if not gitignore_path.exists():
            logger.warning(f"No .gitignore found at {gitignore_path}")
            return
            
        with open(gitignore_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    pattern = GitignorePattern(line)
                    if pattern.is_negated:
                        self.negated_patterns.append(pattern)
                    else:
                        self.patterns.append(pattern)

    def is_ignored(self, path: str) -> bool:
        path = path.replace('\\', '/')
        if path.startswith('./'):
            path = path[2:]
            
        for pattern in self.negated_patterns:
            if pattern.matches(path):
                return False
                
        for pattern in self.patterns:
            if pattern.matches(path):
                return True
                
        return False