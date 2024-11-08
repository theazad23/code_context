import ast
import re
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
import radon.metrics
import radon.complexity
from typing import Set

@dataclass
class CodeMetrics:
    lines_of_code: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    complexity: int = 0
    functions_count: int = 0
    classes_count: int = 0
    max_depth: int = 0
    dependencies: Set[str] = None
    maintainability_index: float = 0.0
    cognitive_complexity: int = 0
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = set()

class LanguageAnalyzer(ABC):
    @abstractmethod
    def analyze(self, content: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def calculate_metrics(self, content: str) -> CodeMetrics:
        pass
    
    @abstractmethod
    def clean_content(self, content: str) -> str:
        pass

class PythonAnalyzer(LanguageAnalyzer):
    def clean_content(self, content: str) -> str:
        """Remove comments and normalize whitespace in Python code."""
        try:
            # Parse and unparse to remove comments and normalize whitespace
            tree = ast.parse(content)
            return ast.unparse(tree)
        except:
            # Fallback to regex-based cleaning if parsing fails
            content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            content = re.sub(r'"""[\s\S]*?"""', '', content)
            content = re.sub(r"'''[\s\S]*?'''", '', content)
            return '\n'.join(line for line in content.splitlines() if line.strip())

    def _analyze_imports(self, tree: ast.AST) -> Set[str]:
        """Analyze imports in Python code."""
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports

    def _analyze_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Analyze functions in Python code."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [ast.unparse(d) for d in node.decorator_list],
                    'is_async': isinstance(node, ast.AsyncFunctionDef),
                    'complexity': radon.complexity.cc_visit(node)
                }
                functions.append(func_info)
        return functions

    def _analyze_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Analyze classes in Python code."""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        methods.append({
                            'name': child.name,
                            'is_private': child.name.startswith('_'),
                            'is_async': isinstance(child, ast.AsyncFunctionDef)
                        })
                
                class_info = {
                    'name': node.name,
                    'bases': [ast.unparse(base) for base in node.bases],
                    'methods': methods,
                    'decorators': [ast.unparse(d) for d in node.decorator_list]
                }
                classes.append(class_info)
        return classes

    def calculate_metrics(self, content: str) -> CodeMetrics:
        """Calculate code metrics for Python code."""
        metrics = CodeMetrics()
        
        # Basic metrics
        lines = content.splitlines()
        metrics.lines_of_code = len(lines)
        metrics.blank_lines = sum(1 for line in lines if not line.strip())
        metrics.comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        
        try:
            tree = ast.parse(content)
            
            # Complexity metrics
            metrics.complexity = radon.complexity.cc_visit(tree)
            metrics.maintainability_index = radon.metrics.mi_visit(content, True)
            
            # Count functions and classes
            metrics.functions_count = len([node for node in ast.walk(tree) 
                                        if isinstance(node, ast.FunctionDef)])
            metrics.classes_count = len([node for node in ast.walk(tree) 
                                      if isinstance(node, ast.ClassDef)])
            
            # Calculate maximum nesting depth
            def get_depth(node: ast.AST, current_depth: int = 0) -> int:
                if isinstance(node, (ast.For, ast.While, ast.If, ast.With)):
                    current_depth += 1
                return max([current_depth] + 
                         [get_depth(child, current_depth) 
                          for child in ast.iter_child_nodes(node)])
            
            metrics.max_depth = get_depth(tree)
            
            # Get dependencies
            metrics.dependencies = self._analyze_imports(tree)
            
        except Exception as e:
            logging.error(f"Error calculating metrics: {e}")
        
        return metrics

    def analyze(self, content: str) -> Dict[str, Any]:
        """Perform comprehensive analysis of Python code."""
        try:
            tree = ast.parse(content)
            metrics = self.calculate_metrics(content)
            
            return {
                'metrics': {
                    'lines_of_code': metrics.lines_of_code,
                    'comment_lines': metrics.comment_lines,
                    'blank_lines': metrics.blank_lines,
                    'complexity': metrics.complexity,
                    'maintainability_index': metrics.maintainability_index,
                    'max_depth': metrics.max_depth
                },
                'imports': list(metrics.dependencies),
                'functions': self._analyze_functions(tree),
                'classes': self._analyze_classes(tree),
                'success': True
            }
        except Exception as e:
            logging.error(f"Error analyzing Python code: {e}")
            return {'success': False, 'error': str(e)}

class JavaScriptAnalyzer(LanguageAnalyzer):
    def clean_content(self, content: str) -> str:
        """Remove comments and normalize whitespace in JavaScript code."""
        # Remove single-line comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)
        return '\n'.join(line for line in content.splitlines() if line.strip())

    def calculate_metrics(self, content: str) -> CodeMetrics:
        metrics = CodeMetrics()
        lines = content.splitlines()
        metrics.lines_of_code = len(lines)
        metrics.blank_lines = sum(1 for line in lines if not line.strip())
        
        # Estimate complexity based on control structures
        control_structures = len(re.findall(r'\b(if|for|while|switch)\b', content))
        metrics.complexity = control_structures
        
        # Count functions and classes
        metrics.functions_count = len(re.findall(r'\bfunction\s+\w+\s*\(', content))
        metrics.classes_count = len(re.findall(r'\bclass\s+\w+\b', content))
        
        return metrics

    def analyze(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript code."""
        try:
            cleaned_content = self.clean_content(content)
            metrics = self.calculate_metrics(cleaned_content)
            
            # Extract imports/exports
            imports = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            exports = re.findall(r'export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)', content)
            
            return {
                'metrics': {
                    'lines_of_code': metrics.lines_of_code,
                    'blank_lines': metrics.blank_lines,
                    'complexity': metrics.complexity,
                    'functions_count': metrics.functions_count,
                    'classes_count': metrics.classes_count
                },
                'imports': imports,
                'exports': exports,
                'success': True
            }
        except Exception as e:
            logging.error(f"Error analyzing JavaScript code: {e}")
            return {'success': False, 'error': str(e)}

class CodeAnalyzer:
    """Main analyzer class that delegates to language-specific analyzers."""
    
    def __init__(self):
        self.analyzers = {
            'py': PythonAnalyzer(),
            'js': JavaScriptAnalyzer(),
            'jsx': JavaScriptAnalyzer(),
            'ts': JavaScriptAnalyzer(),
            'tsx': JavaScriptAnalyzer()
        }
        self.logger = logging.getLogger('code_context.analyzer')

    def get_analyzer(self, file_type: str) -> Optional[LanguageAnalyzer]:
        """Get the appropriate analyzer for a file type."""
        return self.analyzers.get(file_type.lower())

    def analyze_code(self, content: str, file_type: str) -> Dict[str, Any]:
        """Analyze code content with the appropriate analyzer."""
        analyzer = self.get_analyzer(file_type)
        if not analyzer:
            self.logger.warning(f"No analyzer available for file type: {file_type}")
            return {'success': False, 'error': f"Unsupported file type: {file_type}"}
        
        try:
            result = analyzer.analyze(content)
            result['file_type'] = file_type
            return result
        except Exception as e:
            self.logger.error(f"Error analyzing {file_type} code: {e}")
            return {'success': False, 'error': str(e)}

    def clean_content(self, content: str, file_type: str) -> str:
        """Clean code content with the appropriate analyzer."""
        analyzer = self.get_analyzer(file_type)
        if not analyzer:
            return content
        return analyzer.clean_content(content)