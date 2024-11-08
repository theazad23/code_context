import pickle
from pathlib import Path
from typing import Dict, Any, Optional
import logging

class FileAnalysisCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache: Dict[str, Any] = {}
        self.logger = logging.getLogger('code_context.cache')

    def get_cache_path(self, file_hash: str) -> Path:
        return self.cache_dir / f"{file_hash}.pickle"

    def get(self, file_hash: str) -> Optional[Dict[str, Any]]:
        # Check memory cache first
        if file_hash in self.memory_cache:
            self.logger.debug(f"Cache hit (memory) for {file_hash}")
            return self.memory_cache[file_hash]

        # Check disk cache
        cache_path = self.get_cache_path(file_hash)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    result = pickle.load(f)
                self.memory_cache[file_hash] = result
                self.logger.debug(f"Cache hit (disk) for {file_hash}")
                return result
            except Exception as e:
                self.logger.warning(f"Failed to load cache for {file_hash}: {e}")
        return None

    def set(self, file_hash: str, data: Dict[str, Any]):
        # Update memory cache
        self.memory_cache[file_hash] = data
        
        # Update disk cache
        cache_path = self.get_cache_path(file_hash)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache for {file_hash}: {e}")