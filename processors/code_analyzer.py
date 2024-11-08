import ast
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set
import logging
from .constants import AnalysisKeys as Keys

@dataclass
class CodeMetrics:
    lines_of_code: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    complexity: int = 0
    maintainability_index: float = 100.0
    max_depth: int = 0

class CodeAnalyzer:
    """Analyzes source code files with language-specific handling."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 0
        for child in ast.walk(node):
            # Count control flow statements
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                                ast.ExceptHandler, ast.With, ast.AsyncWith,
                                ast.Assert, ast.Raise)):
                complexity += 1
            # Count boolean operators
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            # Count conditional expressions
            elif isinstance(child, ast.IfExp):
                complexity += 1
        return max(1, complexity)

    def _calculate_depth(self, node: ast.AST, current: int = 0) -> int:
        """Calculate maximum nesting depth."""
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With,
                           ast.AsyncFor, ast.AsyncWith)):
            current += 1
        
        max_depth = current
        for child in ast.iter_child_nodes(node):
            child_depth = self._calculate_depth(child, current)
            max_depth = max(max_depth, child_depth)
        
        return max_depth

    def _collect_imports(self, tree: ast.AST) -> Set[str]:
        """Collect all unique imports."""
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split('.')[0])
        return imports

    def analyze_python(self, content: str) -> Dict[str, Any]:
        """Analyze Python source code."""
        try:
            tree = ast.parse(content)
            
            # Basic metrics
            lines = content.splitlines()
            metrics = CodeMetrics(
                lines_of_code=len(lines),
                blank_lines=sum(1 for line in lines if not line.strip()),
                comment_lines=sum(1 for line in lines if line.strip().startswith('#'))
            )
            
            # Calculate complexity and depth
            metrics.complexity = self._calculate_complexity(tree)
            metrics.max_depth = self._calculate_depth(tree)
            
            # Analyze code elements
            imports = self._collect_imports(tree)
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(Keys.function_info(
                        name=node.name,
                        args=[arg.arg for arg in node.args.args],
                        decorators=[ast.unparse(d) for d in node.decorator_list],
                        is_async=isinstance(node, ast.AsyncFunctionDef)
                    ))
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for child in node.body:
                        if isinstance(child, ast.FunctionDef):
                            methods.append(Keys.function_info(
                                name=child.name,
                                is_async=isinstance(child, ast.AsyncFunctionDef),
                                decorators=[ast.unparse(d) for d in child.decorator_list]
                            ))
                    classes.append(Keys.class_info(
                        name=node.name,
                        methods=methods,
                        bases=[ast.unparse(base) for base in node.bases]
                    ))
            
            return {
                Keys.SUCCESS: True,
                Keys.METRICS: Keys.metrics_result(metrics),
                Keys.IMPORTS: list(imports),
                Keys.FUNCTIONS: functions,
                Keys.CLASSES: classes
            }
            
        except Exception as e:
            self.logger.error(f'Error analyzing Python code: {e}')
            return {
                Keys.SUCCESS: False,
                Keys.ERROR: str(e)
            }

    def analyze_javascript(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript source code."""
        try:
            # Clean comments first
            content = re.sub('//.*$', '', content, flags=re.MULTILINE)
            content = re.sub('/\\*[\\s\\S]*?\\*/', '', content)
            
            lines = content.splitlines()
            metrics = CodeMetrics(
                lines_of_code=len(lines),
                blank_lines=sum(1 for line in lines if not line.strip())
            )
            
            # Simple complexity estimation
            control_structures = len(re.findall(r'\b(if|for|while|switch)\b', content))
            boolean_ops = len(re.findall(r'\b(&&|\|\|)\b', content))
            ternary_ops = len(re.findall(r'\?.*:(?![^{]*})', content))
            metrics.complexity = control_structures + boolean_ops + ternary_ops
            
            # Estimate max depth by counting nested blocks
            block_matches = re.findall(r'{(?:[^{}]*|{(?:[^{}]*|{[^{}]*})*})*}', content)
            metrics.max_depth = max((1 + s.count('{') for s in block_matches), default=0)
            
            # Find imports and exports
            imports = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            exports = re.findall(r'export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)', content)
            
            # Find functions and classes
            functions = []
            for match in re.finditer(r'(?:async\s+)?function\s+(\w+)\s*\((.*?)\)', content):
                functions.append(Keys.function_info(
                    name=match.group(1),
                    is_async=bool(re.match(r'\s*async\s+', match.group(0)))
                ))
            
            classes = []
            for match in re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{', content):
                classes.append(Keys.class_info(
                    name=match.group(1),
                    bases=[match.group(2)] if match.group(2) else []
                ))
            
            return {
                Keys.SUCCESS: True,
                Keys.METRICS: Keys.metrics_result(metrics),
                Keys.IMPORTS: imports,
                Keys.EXPORTS: exports,
                Keys.FUNCTIONS: functions,
                Keys.CLASSES: classes
            }
            
        except Exception as e:
            self.logger.error(f'Error analyzing JavaScript code: {e}')
            return {
                Keys.SUCCESS: False,
                Keys.ERROR: str(e)
            }
    
    def analyze_code(self, content: str, file_type: str) -> Dict[str, Any]:
        """Analyze code content based on file type."""
        if file_type.lower() in {'py'}:
            return self.analyze_python(content)
        elif file_type.lower() in {'js', 'jsx', 'ts', 'tsx'}:
            return self.analyze_javascript(content)
        else:
            return {
                Keys.SUCCESS: False,
                Keys.ERROR: f'Unsupported file type: {file_type}'
            }
    
    def clean_content(self, content: str, file_type: str) -> str:
        """Remove comments and normalize whitespace."""
        if file_type.lower() == 'py':
            try:
                tree = ast.parse(content)
                return ast.unparse(tree)
            except:
                content = re.sub('#.*$', '', content, flags=re.MULTILINE)
                content = re.sub('"""[\\s\\S]*?"""', '', content)
                content = re.sub("'''[\\s\\S]*?'''", '', content)
        else:  # js, jsx, ts, tsx
            content = re.sub('//.*$', '', content, flags=re.MULTILINE)
            content = re.sub('/\\*[\\s\\S]*?\\*/', '', content)
        
        return '\n'.join(line for line in content.splitlines() if line.strip())