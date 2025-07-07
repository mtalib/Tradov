#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU18_DependencyAnalyzer.py
Group: U (Utilities)
Purpose: Automated dependency analysis and visualization for Spyder modules

Description:
    This module provides comprehensive dependency analysis for the entire Spyder
    codebase. It extracts import relationships, generates dependency graphs,
    creates visual maps, and produces detailed reports showing how modules
    interconnect. The analyzer helps identify circular dependencies, unused
    imports, and architectural patterns.

Usage Instructions:
    1. Basic dependency analysis:
       analyzer = SpyderDependencyAnalyzer('/path/to/spyder')
       deps = analyzer.generate_dependency_map()
    
    2. Create visual dependency graph:
       analyzer.create_visual_map(output_format='svg')
    
    3. Generate markdown report:
       report = analyzer.generate_markdown_report()
       with open('dependencies.md', 'w') as f:
           f.write(report)
    
    4. Find circular dependencies:
       circles = analyzer.find_circular_dependencies()
    
    5. Analyze specific module:
       module_deps = analyzer.get_module_dependencies('SpyderA01_Main')
    
    6. Command line usage:
       python SpyderU18_DependencyAnalyzer.py --path /path/to/spyder --output svg

Author: Mohamed Talib
Date: 2025-01-28
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import ast
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
import re

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import graphviz
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False
    print("Warning: graphviz not available. Visual maps will be disabled.")

import pandas as pd
import networkx as nx

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Spyder module groups
MODULE_GROUPS = {
    'SpyderA_Core': {'color': '#FF6B6B', 'label': 'Core Engine'},
    'SpyderB_Broker': {'color': '#4ECDC4', 'label': 'Broker Integration'},
    'SpyderC_MarketData': {'color': '#45B7D1', 'label': 'Market Data'},
    'SpyderD_Strategies': {'color': '#96CEB4', 'label': 'Trading Strategies'},
    'SpyderE_Risk': {'color': '#FECA57', 'label': 'Risk Management'},
    'SpyderF_Analysis': {'color': '#FF9FF3', 'label': 'Technical Analysis'},
    'SpyderG_GUI': {'color': '#48DBFB', 'label': 'User Interface'},
    'SpyderH_Storage': {'color': '#0ABDE3', 'label': 'Data Storage'},
    'SpyderI_Integration': {'color': '#EE5A24', 'label': 'Integration Hub'},
    'SpyderJ_Alerts': {'color': '#A29BFE', 'label': 'Notifications'},
    'SpyderK_Reports': {'color': '#6C5CE7', 'label': 'Reporting'},
    'SpyderL_ML': {'color': '#FDCB6E', 'label': 'Machine Learning'},
    'SpyderM_Monitoring': {'color': '#E17055', 'label': 'System Monitoring'},
    'SpyderN_OptionsAnalytics': {'color': '#00B894', 'label': 'Options Analytics'},
    'SpyderO_RiskControl': {'color': '#00CEC9', 'label': 'Risk Controls'},
    'SpyderP_PortfolioMgmt': {'color': '#FD79A8', 'label': 'Portfolio Management'},
    'SpyderR_Runtime': {'color': '#636E72', 'label': 'Runtime Engines'},
    'SpyderT_Testing': {'color': '#B2BEC3', 'label': 'Testing Framework'},
    'SpyderU_Utilities': {'color': '#DFE6E9', 'label': 'Utilities'},
    'SpyderX_Agents': {'color': '#74B9FF', 'label': 'AI Agents'},
    'SpyderZ_Communication': {'color': '#A0E7E5', 'label': 'Communication'}
}

# File patterns to analyze
PYTHON_FILE_PATTERN = "*.py"
EXCLUDE_PATTERNS = ["__pycache__", ".git", ".venv", "venv", "test_", "_test.py"]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ModuleInfo:
    """Information about a module"""
    name: str
    group: str
    filepath: Path
    imports: List[Dict[str, Any]] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    complexity: int = 0
    lines_of_code: int = 0

@dataclass
class DependencyEdge:
    """Represents a dependency between modules"""
    source: str
    target: str
    import_type: str  # 'direct', 'from', 'conditional'
    imports: List[str] = field(default_factory=list)
    line_numbers: List[int] = field(default_factory=list)

@dataclass
class CircularDependency:
    """Represents a circular dependency"""
    modules: List[str]
    edges: List[DependencyEdge]
    severity: str  # 'low', 'medium', 'high'

# ==============================================================================
# MAIN DEPENDENCY ANALYZER CLASS
# ==============================================================================
class SpyderDependencyAnalyzer:
    """
    Comprehensive dependency analyzer for Spyder modules.
    
    This class analyzes Python code to extract import relationships,
    identify dependencies, and generate various reports and visualizations.
    """
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the dependency analyzer.
        
        Args:
            project_root: Root directory of the Spyder project
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.project_root = Path(project_root)
        self.config = config or {}
        
        # Data structures
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependencies: Dict[str, List[DependencyEdge]] = defaultdict(list)
        self.module_groups: Dict[str, List[str]] = defaultdict(list)
        self.import_graph = nx.DiGraph()
        
        # Analysis results
        self.circular_dependencies: List[CircularDependency] = []
        self.unused_imports: Dict[str, List[str]] = {}
        self.missing_modules: Set[str] = set()
        
        self.logger.info(f"Dependency Analyzer initialized for: {project_root}")
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def analyze_module(self, filepath: Path) -> Optional[ModuleInfo]:
        """
        Analyze a single Python module to extract dependencies.
        
        Args:
            filepath: Path to the Python file
            
        Returns:
            ModuleInfo object or None if analysis fails
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            # Extract module info
            module_name = filepath.stem
            group = self._get_module_group(filepath)
            
            module_info = ModuleInfo(
                name=module_name,
                group=group,
                filepath=filepath,
                lines_of_code=len(content.splitlines())
            )
            
            # Analyze AST
            self._analyze_ast(tree, module_info)
            
            # Calculate complexity
            module_info.complexity = self._calculate_complexity(tree)
            
            return module_info
            
        except Exception as e:
            self.logger.error(f"Failed to analyze {filepath}: {e}")
            return None
    
    def _analyze_ast(self, tree: ast.AST, module_info: ModuleInfo):
        """Analyze AST to extract imports, classes, and functions"""
        for node in ast.walk(tree):
            # Extract imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_info = {
                        'type': 'direct',
                        'module': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno
                    }
                    module_info.imports.append(import_info)
                    
                    # Check if it's a Spyder module
                    if alias.name.startswith('Spyder'):
                        module_info.dependencies.add(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_info = {
                        'type': 'from',
                        'module': node.module,
                        'names': [alias.name for alias in node.names],
                        'line': node.lineno
                    }
                    module_info.imports.append(import_info)
                    
                    # Check if it's a Spyder module
                    if node.module.startswith('Spyder'):
                        module_info.dependencies.add(node.module)
                        # Add specific imports as dependencies
                        for alias in node.names:
                            if alias.name != '*':
                                dep = f"{node.module}.{alias.name}"
                                module_info.dependencies.add(dep)
            
            # Extract class definitions
            elif isinstance(node, ast.ClassDef):
                module_info.classes.append(node.name)
                # Check for exports
                if node.name in self._get_exports(tree):
                    module_info.exports.append(node.name)
            
            # Extract function definitions
            elif isinstance(node, ast.FunctionDef):
                module_info.functions.append(node.name)
                # Check for exports
                if node.name in self._get_exports(tree):
                    module_info.exports.append(node.name)
    
    def _get_module_group(self, filepath: Path) -> str:
        """Get the module group from filepath"""
        parts = filepath.parts
        for part in parts:
            if part.startswith('Spyder') and '_' in part:
                return part
        return 'Unknown'
    
    def _get_exports(self, tree: ast.AST) -> Set[str]:
        """Extract __all__ exports from module"""
        exports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Str):
                                    exports.add(elt.s)
                                elif isinstance(elt, ast.Constant):
                                    exports.add(elt.value)
        
        return exports
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            # Count decision points
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        return complexity
    
    # ==========================================================================
    # DEPENDENCY MAP GENERATION
    # ==========================================================================
    
    def generate_dependency_map(self) -> Dict[str, Any]:
        """
        Generate complete dependency map for all Spyder modules.
        
        Returns:
            Dictionary containing dependency information
        """
        self.logger.info("Generating dependency map...")
        
        # Clear previous data
        self.modules.clear()
        self.dependencies.clear()
        self.module_groups.clear()
        self.import_graph.clear()
        
        # Find all Python files
        python_files = self._find_python_files()
        self.logger.info(f"Found {len(python_files)} Python files")
        
        # Analyze each file
        for filepath in python_files:
            module_info = self.analyze_module(filepath)
            if module_info:
                full_name = f"{module_info.group}.{module_info.name}"
                self.modules[full_name] = module_info
                self.module_groups[module_info.group].append(module_info.name)
                
                # Add to graph
                self.import_graph.add_node(full_name, **{
                    'group': module_info.group,
                    'complexity': module_info.complexity,
                    'loc': module_info.lines_of_code
                })
        
        # Build dependency edges
        self._build_dependency_edges()
        
        # Analyze graph properties
        self._analyze_graph_properties()
        
        # Create summary
        summary = {
            'total_modules': len(self.modules),
            'total_dependencies': self.import_graph.number_of_edges(),
            'module_groups': dict(self.module_groups),
            'circular_dependencies': len(self.circular_dependencies),
            'graph_density': nx.density(self.import_graph),
            'average_degree': sum(dict(self.import_graph.degree()).values()) / len(self.modules) if self.modules else 0
        }
        
        self.logger.info(f"Dependency map generated: {summary['total_modules']} modules, "
                        f"{summary['total_dependencies']} dependencies")
        
        return {
            'modules': self.modules,
            'dependencies': dict(self.dependencies),
            'summary': summary,
            'circular_dependencies': self.circular_dependencies
        }
    
    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the project"""
        python_files = []
        
        for group_dir in self.project_root.iterdir():
            if group_dir.is_dir() and group_dir.name.startswith('Spyder'):
                # Skip excluded patterns
                if any(pattern in str(group_dir) for pattern in EXCLUDE_PATTERNS):
                    continue
                
                # Find Python files
                for py_file in group_dir.glob(PYTHON_FILE_PATTERN):
                    if py_file.stem != '__init__' and not any(
                        pattern in py_file.name for pattern in EXCLUDE_PATTERNS
                    ):
                        python_files.append(py_file)
        
        return sorted(python_files)
    
    def _build_dependency_edges(self):
        """Build dependency edges between modules"""
        for module_name, module_info in self.modules.items():
            for dep in module_info.dependencies:
                # Resolve dependency to full module name
                target_module = self._resolve_dependency(dep)
                
                if target_module and target_module in self.modules:
                    # Create edge
                    edge = DependencyEdge(
                        source=module_name,
                        target=target_module,
                        import_type='direct'
                    )
                    
                    self.dependencies[module_name].append(edge)
                    self.import_graph.add_edge(module_name, target_module)
                    
                    # Update dependent information
                    self.modules[target_module].dependents.add(module_name)
                elif target_module:
                    # Module not found
                    self.missing_modules.add(target_module)
    
    def _resolve_dependency(self, dep: str) -> Optional[str]:
        """Resolve a dependency string to full module name"""
        # Handle different import formats
        if '.' in dep:
            parts = dep.split('.')
            if len(parts) >= 2:
                group = parts[0]
                module = parts[1]
                return f"{group}.{module}"
        
        # Search for module by name
        for full_name in self.modules:
            if full_name.endswith(f".{dep}"):
                return full_name
        
        return None
    
    def _analyze_graph_properties(self):
        """Analyze graph properties including circular dependencies"""
        # Find circular dependencies
        try:
            cycles = nx.simple_cycles(self.import_graph)
            for cycle in cycles:
                if len(cycle) > 1:  # Ignore self-loops
                    circular_dep = CircularDependency(
                        modules=cycle,
                        edges=[],
                        severity=self._assess_circular_severity(cycle)
                    )
                    self.circular_dependencies.append(circular_dep)
        except:
            pass  # No cycles
        
        # Find isolated modules
        self.isolated_modules = list(nx.isolates(self.import_graph))
        
        # Calculate centrality metrics
        if self.modules:
            self.centrality_metrics = {
                'degree': nx.degree_centrality(self.import_graph),
                'betweenness': nx.betweenness_centrality(self.import_graph),
                'closeness': nx.closeness_centrality(self.import_graph)
            }
    
    def _assess_circular_severity(self, cycle: List[str]) -> str:
        """Assess severity of circular dependency"""
        # Check if core modules are involved
        core_modules = ['SpyderA_Core', 'SpyderE_Risk', 'SpyderB_Broker']
        
        if any(module.startswith(core) for module in cycle for core in core_modules):
            return 'high'
        elif len(cycle) > 3:
            return 'medium'
        else:
            return 'low'
    
    # ==========================================================================
    # VISUALIZATION METHODS
    # ==========================================================================
    
    def create_visual_map(self, output_format: str = 'png', 
                         output_file: str = 'dependency_map') -> Optional[str]:
        """
        Create visual dependency graph.
        
        Args:
            output_format: Output format (png, svg, pdf)
            output_file: Output filename without extension
            
        Returns:
            Path to generated file or None if failed
        
        Usage:
            analyzer.create_visual_map('svg', 'my_dependencies')
        """
        if not GRAPHVIZ_AVAILABLE:
            self.logger.error("Graphviz not available. Cannot create visual map.")
            return None
        
        try:
            # Create Graphviz graph
            dot = graphviz.Digraph(
                comment='Spyder Module Dependencies',
                engine='dot',
                format=output_format
            )
            
            # Configure graph attributes
            dot.attr(rankdir='TB', size='20,20', dpi='150')
            dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
            dot.attr('edge', fontsize='8')
            
            # Create subgraphs for each module group
            for group, group_info in MODULE_GROUPS.items():
                if group not in self.module_groups:
                    continue
                
                with dot.subgraph(name=f'cluster_{group}') as cluster:
                    cluster.attr(
                        label=group_info['label'],
                        style='filled',
                        fillcolor=group_info['color'] + '40',  # Add transparency
                        fontsize='12',
                        fontweight='bold'
                    )
                    
                    # Add nodes for modules in this group
                    for module in self.module_groups[group]:
                        full_name = f"{group}.{module}"
                        if full_name in self.modules:
                            module_info = self.modules[full_name]
                            
                            # Node label
                            label = f"{module}\n({module_info.complexity})"
                            
                            # Node color based on centrality
                            if hasattr(self, 'centrality_metrics'):
                                centrality = self.centrality_metrics['degree'].get(full_name, 0)
                                if centrality > 0.1:
                                    fillcolor = group_info['color']
                                else:
                                    fillcolor = group_info['color'] + '80'
                            else:
                                fillcolor = group_info['color']
                            
                            cluster.node(
                                full_name,
                                label=label,
                                fillcolor=fillcolor,
                                fontcolor='white' if self._is_dark_color(fillcolor) else 'black'
                            )
            
            # Add edges
            edge_counts = defaultdict(int)
            for source, edges in self.dependencies.items():
                for edge in edges:
                    edge_key = (edge.source, edge.target)
                    edge_counts[edge_key] += 1
            
            for (source, target), count in edge_counts.items():
                # Edge style based on dependency count
                if count > 5:
                    style = 'bold'
                    color = 'red'
                elif count > 2:
                    style = 'solid'
                    color = 'orange'
                else:
                    style = 'solid'
                    color = 'gray'
                
                dot.edge(source, target, 
                        label=str(count) if count > 1 else '',
                        style=style,
                        color=color)
            
            # Render graph
            output_path = dot.render(output_file, cleanup=True)
            self.logger.info(f"Dependency map created: {output_path}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to create visual map: {e}")
            self.error_handler.handle_error(e, "create_visual_map")
            return None
    
    def _is_dark_color(self, hex_color: str) -> bool:
        """Check if a color is dark"""
        # Remove # if present
        hex_color = hex_color.lstrip('#')
        
        # Convert to RGB
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Calculate luminance
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            
            return luminance < 0.5
        except:
            return False
    
    # ==========================================================================
    # REPORT GENERATION
    # ==========================================================================
    
    def generate_markdown_report(self) -> str:
        """
        Generate comprehensive markdown report of dependencies.
        
        Returns:
            Markdown formatted report string
            
        Usage:
            report = analyzer.generate_markdown_report()
            with open('DEPENDENCIES.md', 'w') as f:
                f.write(report)
        """
        report = ["# Spyder Module Dependency Analysis"]
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\nTotal Modules: {len(self.modules)}")
        report.append(f"Total Dependencies: {self.import_graph.number_of_edges()}")
        
        # Executive Summary
        report.append("\n## Executive Summary\n")
        
        summary_data = []
        for group in sorted(self.module_groups.keys()):
            module_count = len(self.module_groups[group])
            group_deps = sum(
                1 for _, target in self.import_graph.edges()
                if any(target.startswith(f"{group}.") for _, target in self.import_graph.edges())
            )
            summary_data.append([MODULE_GROUPS[group]['label'], module_count, group_deps])
        
        # Create summary table
        report.append("| Module Group | Modules | Dependencies |")
        report.append("|--------------|---------|--------------|")
        for row in summary_data:
            report.append(f"| {row[0]} | {row[1]} | {row[2]} |")
        
        # Circular Dependencies
        report.append("\n## Circular Dependencies\n")
        if self.circular_dependencies:
            report.append(f"Found {len(self.circular_dependencies)} circular dependencies:\n")
            for i, circular in enumerate(self.circular_dependencies, 1):
                report.append(f"### {i}. Circular Dependency (Severity: {circular.severity})")
                report.append(f"Modules involved: {' → '.join(circular.modules + [circular.modules[0]])}")
                report.append("")
        else:
            report.append("✅ No circular dependencies found!\n")
        
        # Module Details
        report.append("\n## Module Details\n")
        
        for group in sorted(self.module_groups.keys()):
            report.append(f"### {MODULE_GROUPS[group]['label']} ({group})\n")
            
            for module_name in sorted(self.module_groups[group]):
                full_name = f"{group}.{module_name}"
                if full_name not in self.modules:
                    continue
                
                module_info = self.modules[full_name]
                
                report.append(f"#### {module_name}")
                report.append(f"- **File**: `{module_info.filepath.relative_to(self.project_root)}`")
                report.append(f"- **Lines of Code**: {module_info.lines_of_code}")
                report.append(f"- **Complexity**: {module_info.complexity}")
                report.append(f"- **Classes**: {len(module_info.classes)}")
                report.append(f"- **Functions**: {len(module_info.functions)}")
                
                # Dependencies
                deps = list(module_info.dependencies)
                if deps:
                    report.append(f"- **Dependencies** ({len(deps)}):")
                    for dep in sorted(deps)[:10]:  # Show first 10
                        report.append(f"  - {dep}")
                    if len(deps) > 10:
                        report.append(f"  - ... and {len(deps) - 10} more")
                else:
                    report.append("- **Dependencies**: None (standalone module)")
                
                # Dependents
                if module_info.dependents:
                    report.append(f"- **Used By** ({len(module_info.dependents)}):")
                    for dep in sorted(module_info.dependents)[:5]:  # Show first 5
                        report.append(f"  - {dep}")
                    if len(module_info.dependents) > 5:
                        report.append(f"  - ... and {len(module_info.dependents) - 5} more")
                
                report.append("")
        
        # Most Connected Modules
        report.append("\n## Most Connected Modules\n")
        
        if hasattr(self, 'centrality_metrics'):
            # Sort by degree centrality
            sorted_centrality = sorted(
                self.centrality_metrics['degree'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            report.append("| Module | Connections | Centrality |")
            report.append("|--------|-------------|------------|")
            for module, centrality in sorted_centrality:
                connections = self.import_graph.degree(module)
                report.append(f"| {module} | {connections} | {centrality:.3f} |")
        
        # Missing Modules
        if self.missing_modules:
            report.append("\n## Missing Modules\n")
            report.append("The following modules are referenced but not found:\n")
            for module in sorted(self.missing_modules):
                report.append(f"- {module}")
        
        # Isolated Modules
        if hasattr(self, 'isolated_modules') and self.isolated_modules:
            report.append("\n## Isolated Modules\n")
            report.append("The following modules have no dependencies or dependents:\n")
            for module in sorted(self.isolated_modules):
                report.append(f"- {module}")
        
        return "\n".join(report)
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def find_circular_dependencies(self) -> List[CircularDependency]:
        """
        Find all circular dependencies in the codebase.
        
        Returns:
            List of CircularDependency objects
            
        Usage:
            circles = analyzer.find_circular_dependencies()
            for circle in circles:
                print(f"Circular: {' -> '.join(circle.modules)}")
        """
        if not self.modules:
            self.generate_dependency_map()
        
        return self.circular_dependencies
    
    def get_module_dependencies(self, module_name: str) -> Dict[str, Any]:
        """
        Get all dependencies for a specific module.
        
        Args:
            module_name: Name of the module (can be partial)
            
        Returns:
            Dictionary with dependency information
            
        Usage:
            deps = analyzer.get_module_dependencies('SpyderA01_Main')
        """
        # Find full module name
        full_name = None
        for name in self.modules:
            if module_name in name:
                full_name = name
                break
        
        if not full_name or full_name not in self.modules:
            return {'error': f'Module {module_name} not found'}
        
        module_info = self.modules[full_name]
        
        # Get direct dependencies
        direct_deps = list(module_info.dependencies)
        
        # Get transitive dependencies
        transitive_deps = set()
        visited = set()
        queue = deque(direct_deps)
        
        while queue:
            dep = queue.popleft()
            if dep in visited:
                continue
            
            visited.add(dep)
            resolved_dep = self._resolve_dependency(dep)
            
            if resolved_dep and resolved_dep in self.modules:
                transitive_deps.add(resolved_dep)
                queue.extend(self.modules[resolved_dep].dependencies)
        
        return {
            'module': full_name,
            'direct_dependencies': direct_deps,
            'transitive_dependencies': list(transitive_deps),
            'dependents': list(module_info.dependents),
            'imports': module_info.imports,
            'exports': module_info.exports,
            'complexity': module_info.complexity,
            'lines_of_code': module_info.lines_of_code
        }
    
    def find_unused_imports(self) -> Dict[str, List[str]]:
        """
        Find potentially unused imports in modules.
        
        Returns:
            Dictionary mapping module names to unused imports
            
        Usage:
            unused = analyzer.find_unused_imports()
        """
        # This is a simplified version - full implementation would
        # need to analyze actual usage in the code
        unused = {}
        
        for module_name, module_info in self.modules.items():
            potentially_unused = []
            
            for imp in module_info.imports:
                # Check if imported names are in exports
                if imp['type'] == 'from' and 'names' in imp:
                    for name in imp['names']:
                        # Simple heuristic: if not in exports, might be unused
                        if name not in module_info.exports and name != '*':
                            potentially_unused.append(f"{imp['module']}.{name}")
            
            if potentially_unused:
                unused[module_name] = potentially_unused
        
        return unused
    
    def generate_critical_path_analysis(self) -> Dict[str, List[str]]:
        """
        Identify critical dependency paths in the system.
        
        Returns:
            Dictionary of critical paths
            
        Usage:
            paths = analyzer.generate_critical_path_analysis()
        """
        critical_paths = {}
        
        # Define critical starting points
        critical_modules = {
            'Main': 'SpyderA_Core.SpyderA01_Main',
            'TradingEngine': 'SpyderA_Core.SpyderA02_TradingEngine',
            'RiskManager': 'SpyderE_Risk.SpyderE01_RiskManager',
            'DataFeed': 'SpyderC_MarketData.SpyderC01_DataFeed'
        }
        
        for path_name, start_module in critical_modules.items():
            if start_module not in self.modules:
                continue
            
            # Find longest paths from this module
            try:
                paths = nx.single_source_shortest_path(
                    self.import_graph,
                    start_module,
                    cutoff=10
                )
                
                # Get longest path
                longest_path = max(paths.values(), key=len)
                critical_paths[path_name] = longest_path
                
            except:
                continue
        
        return critical_paths
    
    # ==========================================================================
    # EXPORT METHODS
    # ==========================================================================
    
    def export_to_json(self, output_file: str = 'dependencies.json') -> str:
        """
        Export dependency data to JSON format.
        
        Args:
            output_file: Output filename
            
        Returns:
            Path to created file
            
        Usage:
            analyzer.export_to_json('my_deps.json')
        """
        export_data = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'project_root': str(self.project_root),
                'total_modules': len(self.modules),
                'total_dependencies': self.import_graph.number_of_edges()
            },
            'modules': {},
            'dependencies': {},
            'circular_dependencies': [],
            'graph_metrics': {}
        }
        
        # Export module information
        for name, info in self.modules.items():
            export_data['modules'][name] = {
                'group': info.group,
                'filepath': str(info.filepath.relative_to(self.project_root)),
                'complexity': info.complexity,
                'lines_of_code': info.lines_of_code,
                'classes': info.classes,
                'functions': info.functions,
                'dependencies': list(info.dependencies),
                'dependents': list(info.dependents)
            }
        
        # Export dependencies
        for source, edges in self.dependencies.items():
            export_data['dependencies'][source] = [
                {
                    'target': edge.target,
                    'type': edge.import_type
                }
                for edge in edges
            ]
        
        # Export circular dependencies
        for circular in self.circular_dependencies:
            export_data['circular_dependencies'].append({
                'modules': circular.modules,
                'severity': circular.severity
            })
        
        # Export graph metrics
        if hasattr(self, 'centrality_metrics'):
            export_data['graph_metrics'] = {
                'degree_centrality': self.centrality_metrics['degree'],
                'betweenness_centrality': self.centrality_metrics['betweenness'],
                'density': nx.density(self.import_graph)
            }
        
        # Write to file
        output_path = self.project_root / output_file
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.logger.info(f"Dependencies exported to: {output_path}")
        return str(output_path)
    
    def export_to_csv(self, output_file: str = 'dependencies.csv') -> str:
        """
        Export dependency matrix to CSV format.
        
        Args:
            output_file: Output filename
            
        Returns:
            Path to created file
            
        Usage:
            analyzer.export_to_csv('dependency_matrix.csv')
        """
        # Create adjacency matrix
        modules = sorted(self.modules.keys())
        matrix = pd.DataFrame(
            0,
            index=modules,
            columns=modules
        )
        
        # Fill matrix
        for source, targets in nx.adjacency_iter(self.import_graph):
            for target in targets:
                matrix.loc[source, target] = 1
        
        # Save to CSV
        output_path = self.project_root / output_file
        matrix.to_csv(output_path)
        
        self.logger.info(f"Dependency matrix exported to: {output_path}")
        return str(output_path)


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def analyze_spyder_dependencies(project_path: str = '.', 
                               create_visual: bool = True,
                               output_format: str = 'svg') -> Dict[str, Any]:
    """
    Convenience function to analyze Spyder dependencies.
    
    Args:
        project_path: Path to Spyder project
        create_visual: Whether to create visual map
        output_format: Format for visual map
        
    Returns:
        Analysis results dictionary
        
    Usage:
        results = analyze_spyder_dependencies('/path/to/spyder')
    """
    analyzer = SpyderDependencyAnalyzer(project_path)
    
    # Generate dependency map
    results = analyzer.generate_dependency_map()
    
    # Create visual map
    if create_visual:
        visual_path = analyzer.create_visual_map(output_format)
        results['visual_map'] = visual_path
    
    # Generate reports
    results['markdown_report'] = analyzer.generate_markdown_report()
    results['json_export'] = analyzer.export_to_json()
    
    return results


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze Spyder module dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic analysis with visual map
    python SpyderU18_DependencyAnalyzer.py --path /path/to/spyder
    
    # Generate SVG visualization
    python SpyderU18_DependencyAnalyzer.py --path /path/to/spyder --output svg
    
    # Export to multiple formats
    python SpyderU18_DependencyAnalyzer.py --path /path/to/spyder --json --csv --markdown
    
    # Analyze specific module
    python SpyderU18_DependencyAnalyzer.py --path /path/to/spyder --module SpyderA01_Main
        """
    )
    
    parser.add_argument('--path', type=str, default='.',
                       help='Path to Spyder project root')
    parser.add_argument('--output', type=str, choices=['png', 'svg', 'pdf'], 
                       default='svg', help='Output format for visual map')
    parser.add_argument('--no-visual', action='store_true',
                       help='Skip visual map generation')
    parser.add_argument('--json', action='store_true',
                       help='Export to JSON')
    parser.add_argument('--csv', action='store_true',
                       help='Export dependency matrix to CSV')
    parser.add_argument('--markdown', action='store_true',
                       help='Generate markdown report')
    parser.add_argument('--module', type=str,
                       help='Analyze specific module')
    parser.add_argument('--find-circular', action='store_true',
                       help='Find circular dependencies')
    parser.add_argument('--find-unused', action='store_true',
                       help='Find unused imports')
    
    args = parser.parse_args()
    
    # Create analyzer
    print(f"Analyzing Spyder dependencies in: {args.path}")
    analyzer = SpyderDependencyAnalyzer(args.path)
    
    # Generate dependency map
    print("Generating dependency map...")
    results = analyzer.generate_dependency_map()
    
    print(f"\nAnalysis Summary:")
    print(f"  Total Modules: {results['summary']['total_modules']}")
    print(f"  Total Dependencies: {results['summary']['total_dependencies']}")
    print(f"  Circular Dependencies: {results['summary']['circular_dependencies']}")
    print(f"  Graph Density: {results['summary']['graph_density']:.3f}")
    
    # Create visual map
    if not args.no_visual:
        print(f"\nCreating visual map ({args.output} format)...")
        visual_path = analyzer.create_visual_map(args.output)
        if visual_path:
            print(f"Visual map saved to: {visual_path}")
    
    # Export options
    if args.json:
        json_path = analyzer.export_to_json()
        print(f"JSON export saved to: {json_path}")
    
    if args.csv:
        csv_path = analyzer.export_to_csv()
        print(f"CSV export saved to: {csv_path}")
    
    if args.markdown:
        report = analyzer.generate_markdown_report()
        report_path = Path(args.path) / "DEPENDENCIES.md"
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"Markdown report saved to: {report_path}")
    
    # Specific module analysis
    if args.module:
        print(f"\nAnalyzing module: {args.module}")
        module_deps = analyzer.get_module_dependencies(args.module)
        
        if 'error' not in module_deps:
            print(f"  Direct Dependencies: {len(module_deps['direct_dependencies'])}")
            print(f"  Transitive Dependencies: {len(module_deps['transitive_dependencies'])}")
            print(f"  Used By: {len(module_deps['dependents'])}")
            print(f"  Complexity: {module_deps['complexity']}")
    
    # Find circular dependencies
    if args.find_circular:
        print("\nSearching for circular dependencies...")
        circles = analyzer.find_circular_dependencies()
        
        if circles:
            print(f"Found {len(circles)} circular dependencies:")
            for i, circle in enumerate(circles, 1):
                print(f"  {i}. {' → '.join(circle.modules)} ({circle.severity} severity)")
        else:
            print("No circular dependencies found!")
    
    # Find unused imports
    if args.find_unused:
        print("\nSearching for unused imports...")
        unused = analyzer.find_unused_imports()
        
        if unused:
            print(f"Found potentially unused imports in {len(unused)} modules")
            for module, imports in list(unused.items())[:5]:  # Show first 5
                print(f"  {module}: {len(imports)} unused imports")
        else:
            print("No unused imports detected!")
    
    print("\nDependency analysis complete!")
