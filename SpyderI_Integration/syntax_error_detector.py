#!/usr/bin/env python3
"""
Comprehensive Syntax Error Detector for Spyder Trading System

This script performs thorough syntax validation on all Python files using:
1. py_compile for compilation errors
2. AST parsing for advanced syntax issues
3. Pattern matching for common syntax errors
4. Parallel processing for performance
"""

import os
import ast
import sys
import json
import traceback
import multiprocessing
from pathlib import Path
from typing import List, Dict, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import py_compile
import tempfile
import re
from datetime import datetime

class SyntaxErrorDetector:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.errors_found = []
        self.files_checked = 0
        self.start_time = datetime.now()
        
        # Common syntax error patterns
        self.error_patterns = [
            (r'^\s*class\s+\w+\s*\(.*\)\s*$', 'Missing colon after class definition'),
            (r'^\s*def\s+\w+\s*\(.*\)\s*$', 'Missing colon after function definition'),
            (r'^\s*if\s+.*\s*$', 'Missing colon after if statement'),
            (r'^\s*elif\s+.*\s*$', 'Missing colon after elif statement'),
            (r'^\s*else\s*$', 'Missing colon after else statement'),
            (r'^\s*for\s+.*\s*$', 'Missing colon after for statement'),
            (r'^\s*while\s+.*\s*$', 'Missing colon after while statement'),
            (r'^\s*try\s*$', 'Missing colon after try statement'),
            (r'^\s*except\s+.*\s*$', 'Missing colon after except statement'),
            (r'^\s*finally\s*$', 'Missing colon after finally statement'),
            (r'^\s*with\s+.*\s*$', 'Missing colon after with statement'),
        ]
    
    def check_file_syntax(self, file_path: Path) -> Dict[str, Any]:
        """Check syntax of a single Python file using multiple methods"""
        result = {
            'file': str(file_path),
            'errors': [],
            'warnings': [],
            'status': 'ok'
        }
        
        try:
            # Method 1: py_compile check
            py_compile_errors = self._check_py_compile(file_path)
            if py_compile_errors:
                result['errors'].extend(py_compile_errors)
                result['status'] = 'error'
            
            # Method 2: AST parsing
            ast_errors = self._check_ast_parsing(file_path)
            if ast_errors:
                result['errors'].extend(ast_errors)
                result['status'] = 'error'
            
            # Method 3: Pattern matching for common issues
            pattern_warnings = self._check_common_patterns(file_path)
            if pattern_warnings:
                result['warnings'].extend(pattern_warnings)
                if result['status'] == 'ok':
                    result['status'] = 'warning'
                    
        except Exception as e:
            result['errors'].append({
                'type': 'check_error',
                'message': f"Error during syntax check: {str(e)}",
                'line': None
            })
            result['status'] = 'error'
        
        return result
    
    def _check_py_compile(self, file_path: Path) -> List[Dict[str, Any]]:
        """Check file using py_compile"""
        errors = []
        
        try:
            # Use temporary file for compilation check
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as src_file:
                    tmp_file.write(src_file.read())
                tmp_path = tmp_file.name
            
            try:
                py_compile.compile(tmp_path, doraise=True)
            except py_compile.PyCompileError as e:
                error_msg = str(e)
                line_num = None
                
                # Try to extract line number from error message
                line_match = re.search(r'line (\d+)', error_msg)
                if line_match:
                    line_num = int(line_match.group(1))
                
                errors.append({
                    'type': 'compilation_error',
                    'message': error_msg,
                    'line': line_num
                })
            
            # Clean up temp file
            os.unlink(tmp_path)
            
        except Exception as e:
            errors.append({
                'type': 'py_compile_error',
                'message': f"py_compile check failed: {str(e)}",
                'line': None
            })
        
        return errors
    
    def _check_ast_parsing(self, file_path: Path) -> List[Dict[str, Any]]:
        """Check file using AST parsing"""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Try to parse the AST
            ast.parse(content, filename=str(file_path))
            
        except SyntaxError as e:
            errors.append({
                'type': 'syntax_error',
                'message': f"SyntaxError: {e.msg}",
                'line': e.lineno,
                'column': e.offset,
                'text': e.text.strip() if e.text else None
            })
        except Exception as e:
            errors.append({
                'type': 'ast_parse_error',
                'message': f"AST parsing failed: {str(e)}",
                'line': None
            })
        
        return errors
    
    def _check_common_patterns(self, file_path: Path) -> List[Dict[str, Any]]:
        """Check for common syntax error patterns"""
        warnings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith('#'):
                    continue
                
                for pattern, message in self.error_patterns:
                    if re.match(pattern, line_stripped):
                        # Check if next non-empty line is properly indented
                        next_line_idx = line_num
                        next_line = ""
                        while next_line_idx < len(lines):
                            next_line = lines[next_line_idx].strip()
                            if next_line and not next_line.startswith('#'):
                                break
                            next_line_idx += 1
                        
                        # If next line exists but isn't indented, it's likely missing colon
                        if next_line and not lines[next_line_idx].startswith('    ') and not lines[next_line_idx].startswith('\t'):
                            warnings.append({
                                'type': 'pattern_warning',
                                'message': f"Possible issue: {message}",
                                'line': line_num,
                                'text': line_stripped
                            })
                
                # Check for unclosed brackets/parentheses
                open_chars = {'(': ')', '[': ']', '{': '}'}
                stack = []
                for char in line:
                    if char in open_chars:
                        stack.append((char, open_chars[char]))
                    elif char in open_chars.values():
                        if not stack:
                            warnings.append({
                                'type': 'bracket_warning',
                                'message': f"Unmatched closing bracket: {char}",
                                'line': line_num,
                                'text': line_stripped
                            })
                        else:
                            expected = stack.pop()[1]
                            if char != expected:
                                warnings.append({
                                    'type': 'bracket_warning', 
                                    'message': f"Mismatched bracket: expected {expected}, found {char}",
                                    'line': line_num,
                                    'text': line_stripped
                                })
                
                if stack:
                    for open_char, expected_close in stack:
                        warnings.append({
                            'type': 'bracket_warning',
                            'message': f"Unclosed bracket: {open_char} (expected {expected_close})",
                            'line': line_num,
                            'text': line_stripped
                        })
                        
        except Exception as e:
            warnings.append({
                'type': 'pattern_check_error',
                'message': f"Pattern check failed: {str(e)}",
                'line': None
            })
        
        return warnings
    
    def find_python_files(self) -> List[Path]:
        """Find all Python files in the project"""
        python_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip certain directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                      d not in ['__pycache__', 'node_modules', 'venv', 'env', '.git']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def check_all_files_parallel(self, max_workers: int = None) -> Dict[str, Any]:
        """Check all Python files in parallel"""
        python_files = self.find_python_files()
        
        if not python_files:
            return {
                'summary': 'No Python files found',
                'files_checked': 0,
                'errors_found': 0,
                'results': []
            }
        
        print(f"Found {len(python_files)} Python files to check...")
        
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 8)
        
        results = []
        files_with_errors = 0
        total_errors = 0
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all files for processing
            future_to_file = {
                executor.submit(self.check_file_syntax, file_path): file_path
                for file_path in python_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['status'] == 'error':
                        files_with_errors += 1
                        total_errors += len(result['errors'])
                        print(f"❌ {result['file']}: {len(result['errors'])} errors")
                    elif result['status'] == 'warning':
                        print(f"⚠️  {result['file']}: {len(result['warnings'])} warnings")
                    else:
                        print(f"✅ {result['file']}: OK")
                        
                    self.files_checked += 1
                    
                    # Progress indicator
                    if self.files_checked % 1000 == 0:
                        print(f"Progress: {self.files_checked}/{len(python_files)} files checked")
                        
                except Exception as e:
                    print(f"❌ Error checking {file_path}: {e}")
                    results.append({
                        'file': str(file_path),
                        'errors': [{'type': 'processing_error', 'message': str(e), 'line': None}],
                        'warnings': [],
                        'status': 'error'
                    })
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        return {
            'summary': {
                'files_checked': len(python_files),
                'files_with_errors': files_with_errors,
                'total_errors': total_errors,
                'duration_seconds': duration,
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat()
            },
            'results': results
        }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a detailed syntax error report"""
        report = []
        
        report.append("# Syntax Error Detection Report")
        report.append("=" * 50)
        report.append("")
        
        summary = results['summary']
        report.append(f"**Files Checked:** {summary['files_checked']}")
        report.append(f"**Files with Errors:** {summary['files_with_errors']}")
        report.append(f"**Total Errors:** {summary['total_errors']}")
        report.append(f"**Duration:** {summary['duration_seconds']:.2f} seconds")
        report.append("")
        
        # Group results by status
        error_files = [r for r in results['results'] if r['status'] == 'error']
        warning_files = [r for r in results['results'] if r['status'] == 'warning']
        clean_files = [r for r in results['results'] if r['status'] == 'ok']
        
        if error_files:
            report.append("## Critical Syntax Errors")
            report.append("-" * 30)
            report.append("")
            
            for result in error_files:
                report.append(f"### {result['file']}")
                for error in result['errors']:
                    line_info = f" (Line {error['line']})" if error['line'] else ""
                    report.append(f"- **{error['type']}**{line_info}: {error['message']}")
                    if error.get('text'):
                        report.append(f"  ```python")
                        report.append(f"  {error['text']}")
                        report.append(f"  ```")
                report.append("")
        
        if warning_files:
            report.append("## Warnings")
            report.append("-" * 15)
            report.append("")
            
            for result in warning_files[:10]:  # Limit to first 10 for brevity
                report.append(f"### {result['file']}")
                for warning in result['warnings'][:5]:  # Limit warnings per file
                    line_info = f" (Line {warning['line']})" if warning['line'] else ""
                    report.append(f"- **{warning['type']}**{line_info}: {warning['message']}")
                report.append("")
        
        report.append(f"## Summary Statistics")
        report.append(f"- Clean files: {len(clean_files)}")
        report.append(f"- Files with warnings: {len(warning_files)}")
        report.append(f"- Files with errors: {len(error_files)}")
        
        return "\n".join(report)


def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = "/home/adam/Projects/Spyder"
    
    print(f"Starting comprehensive syntax check of: {project_root}")
    print("=" * 60)
    
    detector = SyntaxErrorDetector(project_root)
    
    # Run the syntax check
    results = detector.check_all_files_parallel()
    
    # Generate and save report
    report_content = detector.generate_report(results)
    
    # Save detailed JSON results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = f"/home/adam/Projects/Spyder/reports/syntax_analysis_{timestamp}.json"
    report_file = f"/home/adam/Projects/Spyder/reports/syntax_report_{timestamp}.md"
    
    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    with open(report_file, 'w') as f:
        f.write(report_content)
    
    print("\n" + "=" * 60)
    print("SYNTAX ERROR DETECTION COMPLETE")
    print("=" * 60)
    print(report_content)
    print(f"\nDetailed results saved to: {json_file}")
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()