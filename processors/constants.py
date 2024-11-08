from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class AnalysisKeys:
    """Keys used in code analysis results"""
    # File information
    PATH: str = 'file_path'
    TYPE: str = 'file_type'
    SIZE: str = 'size'
    CONTENT: str = 'content'
    HASH: str = 'content_hash'
    
    # Analysis sections
    ANALYSIS: str = 'analysis'
    METRICS: str = 'metrics'
    IMPORTS: str = 'imports'
    EXPORTS: str = 'exports'
    FUNCTIONS: str = 'functions'
    CLASSES: str = 'classes'
    SUCCESS: str = 'success'
    ERROR: str = 'error'
    
    # Metrics
    LINES_OF_CODE: str = 'lines_of_code'
    COMMENT_LINES: str = 'comment_lines'
    BLANK_LINES: str = 'blank_lines'
    COMPLEXITY: str = 'complexity'
    MAINTAINABILITY: str = 'maintainability_index'
    MAX_DEPTH: str = 'max_depth'
    
    # Code elements
    NAME: str = 'name'
    ARGS: str = 'arguments'
    DECORATORS: str = 'decorators'
    IS_ASYNC: str = 'is_async'
    IS_PRIVATE: str = 'is_private'
    BASES: str = 'base_classes'
    METHODS: str = 'methods'

    @classmethod
    def file_result(cls, path: str, file_type: str, analysis: Dict[str, Any], 
                   size: int, content: str, file_hash: str) -> Dict[str, Any]:
        """Create a standardized file analysis result"""
        return {
            cls.PATH: path,
            cls.TYPE: file_type,
            cls.ANALYSIS: analysis,
            cls.SIZE: size,
            cls.CONTENT: content,
            cls.HASH: file_hash
        }

    @classmethod
    def metrics_result(cls, metrics: 'CodeMetrics') -> Dict[str, Any]:
        """Create a standardized metrics result"""
        return {
            cls.LINES_OF_CODE: metrics.lines_of_code,
            cls.COMMENT_LINES: metrics.comment_lines,
            cls.BLANK_LINES: metrics.blank_lines,
            cls.COMPLEXITY: metrics.complexity,
            cls.MAINTAINABILITY: metrics.maintainability_index,
            cls.MAX_DEPTH: metrics.max_depth
        }

    @classmethod
    def function_info(cls, name: str, args: list = None, 
                     decorators: list = None, is_async: bool = False) -> Dict[str, Any]:
        """Create a standardized function info dictionary"""
        return {
            cls.NAME: name,
            cls.ARGS: args or [],
            cls.DECORATORS: decorators or [],
            cls.IS_ASYNC: is_async
        }

    @classmethod
    def class_info(cls, name: str, methods: list = None, 
                  bases: list = None) -> Dict[str, Any]:
        """Create a standardized class info dictionary"""
        return {
            cls.NAME: name,
            cls.METHODS: methods or [],
            cls.BASES: bases or []
        }