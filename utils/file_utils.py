import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict
import chardet

def get_file_encoding(file_path: Path) -> str:
    """Detect file encoding using chardet."""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'] or 'utf-8'

def read_file_safely(file_path: Path, logger: logging.Logger) -> Optional[str]:
    """Safely read a file with multiple encoding fallbacks."""
    try:
        # Try to detect encoding first
        encoding = get_file_encoding(file_path)
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        logger.warning(f"Failed to read {file_path} with detected encoding {encoding}")
        # Try common encodings
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                logger.info(f"Successfully read {file_path} with {enc} encoding")
                return content
            except UnicodeDecodeError:
                continue
        # Last resort: read with replacement
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            logger.warning(f"Read {file_path} with replacement characters")
            return content
        except Exception as e:
            logger.error(f"Failed to read {file_path} with any encoding: {e}")
            return None

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()