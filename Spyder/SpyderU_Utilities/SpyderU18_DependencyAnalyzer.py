#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU18_DependencyAnalyzer.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
from datetime import datetime, timezone

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import ast
import networkx as nx

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

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
    'SpyderP_PortfolioMgmt': {'color': '#FD79A8', 'label': 'Portfolio Management'},
    'SpyderR_Runtime': {'color': '#636E72', 'label': 'Runtime Engines'},
    'SpyderT_Testing': {'color': '#B2BEC3', 'label': 'Testing Framework'},
    'Spyder.SpyderU_Utilities': {'color': '#DFE6E9', 'label': 'Utilities'},
    'SpyderX_Agents': {'color': '#74B9FF', 'label': 'AI Agents'},
    'SpyderZ_Communication': {'color': '#A0E7E5', 'label': 'Communication'}
}

# File patterns to analyze
PYTHON_FILE_PATTERN = "*.py"
EXCLUDE_PATTERNS = ["__pycache__", ".git", ".venv", "venv", "test_", "_test.py"]

# ==============================================================================
# ENUMS
# ==============================================================================
class DependencyType(Enum):
    """Types of dependencies"""
    DIRECT = "direct"
    INDIRECT = "indirect"
    CIRCULAR = "circular"
    EXTERNAL = "external"
    INTERNAL = "internal"

class AnalysisScope(Enum):
    """Analysis scope levels"""
    MODULE = "module"
    GROUP = "group"
    SYSTEM = "system"

class SeverityLevel(Enum):
    """Issue severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ModuleInfo:
    """Information about a single module"""
    name: str
    path: str
    group: str
    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    external_imports: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    lines_of_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "group": self.group,
            "imports": self.imports,
            "imported_by": self.imported_by,
            "external_imports": self.external_imports,
            "functions": self.functions,
            "classes": self.classes,
            "lines_of_code": self.lines_of_code
        }

@dataclass
class CircularDependency:
    """Information about circular dependency"""
    modules: list[str]
    severity: SeverityLevel
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "modules": self.modules,
            "severity": self.severity.value,
            "description": self.description
        }

@dataclass
class DependencyGraph:
    """Dependency graph representation"""
    nodes: list[str]
    edges: list[tuple[str, str]]
    circular_dependencies: list[CircularDependency]
    isolated_modules: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "circular_dependencies": [cd.to_dict() for cd in self.circular_dependencies],
            "isolated_modules": self.isolated_modules
        }

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DependencyAnalyzer:
    """
    Comprehensive dependency analysis for Spyder modules.

    This class provides detailed analysis of module dependencies including
    circular dependency detection, dependency graph generation, and
    architectural pattern analysis. It helps maintain clean module
    architecture and identifies potential issues in the codebase.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        project_root: Root directory of the project
        modules: Dictionary of analyzed modules
        import_graph: NetworkX graph of dependencies

    Example:
        >>> analyzer = DependencyAnalyzer("/path/to/spyder")
        >>> analyzer.analyze_dependencies()
        >>> circular_deps = analyzer.find_circular_dependencies()
        >>> report = analyzer.generate_dependency_report()
    """

    def __init__(self, project_root: str = "."):
        """Initialize the dependency analyzer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.project_root = Path(project_root)
        self.modules: dict[str, ModuleInfo] = {}
        self.import_graph = nx.DiGraph()
        self.module_groups: dict[str, list[str]] = {}
        self.circular_dependencies: list[CircularDependency] = []
        self.missing_modules: set[str] = set()

        self.logger.info("%s initialized for %s", self.__class__.__name__, project_root)

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def analyze_dependencies(self, force_refresh: bool = False) -> None:
        """
        Analyze all module dependencies in the project.

        Args:
            force_refresh: Whether to force re-analysis
        """
        try:
            if self.modules and not force_refresh:
                self.logger.info("Dependencies already analyzed, use force_refresh=True to re-analyze")  # noqa: E501
                return

            self.logger.info("Starting dependency analysis...")

            # Clear existing data
            self.modules.clear()
            self.import_graph.clear()
            self.module_groups.clear()
            self.circular_dependencies.clear()
            self.missing_modules.clear()

            # Find all Python files
            python_files = self._find_python_files()
            self.logger.info("Found %s Python files to analyze", len(python_files))

            # Analyze each file
            for file_path in python_files:
                try:
                    self._analyze_file(file_path)
                except Exception as e:
                    self.logger.warning("Failed to analyze %s: %s", file_path, e)

            # Build dependency graph
            self._build_dependency_graph()

            # Find circular dependencies
            self._find_circular_dependencies()

            # Group modules by category
            self._group_modules()

            self.logger.info("Analysis complete: %s modules analyzed", len(self.modules))

        except Exception as e:
            self.logger.error("Dependency analysis failed: %s", e)
            raise

    def find_circular_dependencies(self) -> list[CircularDependency]:
        """
        Find all circular dependencies in the codebase.

        Returns:
            List of CircularDependency objects
        """
        if not self.modules:
            self.analyze_dependencies()

        return self.circular_dependencies

    def get_module_dependencies(self, module_name: str) -> dict[str, Any]:
        """
        Get all dependencies for a specific module.

        Args:
            module_name: Name of the module

        Returns:
            Dictionary with dependency information
        """
        try:
            if module_name not in self.modules:
                return {"error": f"Module {module_name} not found"}

            module = self.modules[module_name]

            # Get direct dependencies
            direct_deps = module.imports

            # Get modules that depend on this one
            dependents = module.imported_by

            # Calculate dependency depth
            depth = self._calculate_dependency_depth(module_name)

            return {
                "module": module_name,
                "direct_dependencies": direct_deps,
                "dependent_modules": dependents,
                "external_dependencies": module.external_imports,
                "dependency_depth": depth,
                "group": module.group,
                "lines_of_code": module.lines_of_code
            }

        except Exception as e:
            self.logger.error("Failed to get dependencies for %s: %s", module_name, e)
            return {"error": str(e)}

    def generate_dependency_graph(self) -> DependencyGraph:
        """
        Generate dependency graph representation.

        Returns:
            DependencyGraph object
        """
        try:
            if not self.modules:
                self.analyze_dependencies()

            nodes = list(self.modules.keys())
            edges = list(self.import_graph.edges())

            # Find isolated modules
            isolated = [node for node in nodes if self.import_graph.degree(node) == 0]

            return DependencyGraph(
                nodes=nodes,
                edges=edges,
                circular_dependencies=self.circular_dependencies,
                isolated_modules=isolated
            )

        except Exception as e:
            self.logger.error("Failed to generate dependency graph: %s", e)
            return DependencyGraph([], [], [], [])

    # ==========================================================================
    # PUBLIC METHODS - REPORTING
    # ==========================================================================
    def generate_dependency_report(self) -> str:
        """
        Generate comprehensive dependency analysis report.

        Returns:
            Markdown formatted report string
        """
        try:
            if not self.modules:
                self.analyze_dependencies()

            report = ["# Spyder Module Dependency Analysis"]
            report.append(f"\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"\nTotal Modules: {len(self.modules)}")
            report.append(f"Total Dependencies: {self.import_graph.number_of_edges()}")

            # Executive Summary
            report.append("\n## Executive Summary\n")

            summary_data = []
            for group in sorted(self.module_groups.keys()):
                module_count = len(self.module_groups[group])
                group_deps = sum(
                    1 for _, target in self.import_graph.edges()
                    if any(target.startswith(f"{group}.") for _, target in self.import_graph.edges())  # noqa: E501
                )
                summary_data.append([MODULE_GROUPS.get(group, {}).get('label', group), module_count, group_deps])  # noqa: E501

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
                    report.append(f"### {i}. Circular Dependency (Severity: {circular.severity.value})")  # noqa: E501
                    report.append(f"Modules involved: {' → '.join(circular.modules + [circular.modules[0]])}")  # noqa: E501
                    report.append(f"Description: {circular.description}")
                    report.append("")
            else:
                report.append("✅ No circular dependencies found!\n")

            # Module Details
            report.append("\n## Module Details\n")

            for group in sorted(self.module_groups.keys()):
                if group in MODULE_GROUPS:
                    report.append(f"### {MODULE_GROUPS[group]['label']} ({group})\n")

                    for module_name in sorted(self.module_groups[group]):
                        module = self.modules[module_name]
                        report.append(f"**{module_name}**")
                        report.append(f"- Dependencies: {len(module.imports)}")
                        report.append(f"- Imported by: {len(module.imported_by)}")
                        report.append(f"- Lines of code: {module.lines_of_code}")
                        report.append("")

            # Missing Modules
            if self.missing_modules:
                report.append("\n## Missing Modules\n")
                report.append("The following modules are referenced but not found:\n")
                for module in sorted(self.missing_modules):
                    report.append(f"- {module}")

            return "\n".join(report)

        except Exception as e:
            self.logger.error("Failed to generate dependency report: %s", e)
            return f"Error generating report: {e}"

    def export_graph_data(self, format: str = "json") -> str:
        """
        Export dependency graph data in specified format.

        Args:
            format: Export format (json, csv, graphml)

        Returns:
            Formatted graph data
        """
        try:
            if not self.modules:
                self.analyze_dependencies()

            if format.lower() == "json":
                graph_data = {
                    "nodes": [
                        {
                            "id": name,
                            "group": info.group,
                            "lines_of_code": info.lines_of_code,
                            "functions": len(info.functions),
                            "classes": len(info.classes)
                        }
                        for name, info in self.modules.items()
                    ],
                    "edges": [
                        {"source": source, "target": target}
                        for source, target in self.import_graph.edges()
                    ]
                }
                return json.dumps(graph_data, indent=2)

            elif format.lower() == "csv":
                # Export as CSV with adjacency list
                lines = ["Source,Target,Type"]
                for source, target in self.import_graph.edges():
                    lines.append(f"{source},{target},import")
                return "\n".join(lines)

            else:
                return "Unsupported format. Use 'json' or 'csv'."

        except Exception as e:
            self.logger.error("Failed to export graph data: %s", e)
            return f"Error exporting data: {e}"

    # ==========================================================================
    # PRIVATE METHODS - FILE ANALYSIS
    # ==========================================================================
    def _find_python_files(self) -> list[Path]:
        """Find all Python files in the project."""
        python_files = []

        for pattern in [f"**/{PYTHON_FILE_PATTERN}"]:
            for file_path in self.project_root.glob(pattern):
                # Skip excluded patterns
                if any(exclude in str(file_path) for exclude in EXCLUDE_PATTERNS):
                    continue

                if file_path.is_file():
                    python_files.append(file_path)

        return python_files

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single Python file."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content, filename=str(file_path))

            # Extract module information
            module_name = self._get_module_name(file_path)
            group = self._get_module_group(module_name)

            # Extract imports, functions, and classes
            imports = self._extract_imports(tree)
            functions = self._extract_functions(tree)
            classes = self._extract_classes(tree)

            # Count lines of code (excluding empty lines and comments)
            lines_of_code = self._count_lines_of_code(content)

            # Separate internal and external imports
            internal_imports = []
            external_imports = []

            for imp in imports:
                if self._is_spyder_module(imp):
                    internal_imports.append(imp)
                else:
                    external_imports.append(imp)

            # Create module info
            module_info = ModuleInfo(
                name=module_name,
                path=str(file_path),
                group=group,
                imports=internal_imports,
                external_imports=external_imports,
                functions=functions,
                classes=classes,
                lines_of_code=lines_of_code
            )

            self.modules[module_name] = module_info

        except Exception as e:
            self.logger.warning("Failed to analyze %s: %s", file_path, e)

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from AST."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        return imports

    def _extract_functions(self, tree: ast.AST) -> list[str]:
        """Extract function definitions from AST."""
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)

        return functions

    def _extract_classes(self, tree: ast.AST) -> list[str]:
        """Extract class definitions from AST."""
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)

        return classes

    def _count_lines_of_code(self, content: str) -> int:
        """Count non-empty, non-comment lines."""
        lines = content.split('\n')
        loc = 0

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                loc += 1

        return loc

    # ==========================================================================
    # PRIVATE METHODS - GRAPH ANALYSIS
    # ==========================================================================
    def _build_dependency_graph(self) -> None:
        """Build NetworkX dependency graph."""
        # Add nodes
        for module_name in self.modules:
            self.import_graph.add_node(module_name)

        # Add edges
        for module_name, module_info in self.modules.items():
            for imported_module in module_info.imports:
                if imported_module in self.modules:
                    self.import_graph.add_edge(module_name, imported_module)
                    # Update imported_by relationships
                    self.modules[imported_module].imported_by.append(module_name)
                else:
                    # Track missing modules
                    if self._is_spyder_module(imported_module):
                        self.missing_modules.add(imported_module)

    def _find_circular_dependencies(self) -> None:
        """Find circular dependencies using NetworkX."""
        try:
            # Find strongly connected components
            strongly_connected = list(nx.strongly_connected_components(self.import_graph))

            for component in strongly_connected:
                if len(component) > 1:
                    # This is a circular dependency
                    modules = list(component)
                    severity = self._assess_circular_severity(modules)
                    description = f"Circular dependency involving {len(modules)} modules"

                    circular_dep = CircularDependency(
                        modules=modules,
                        severity=severity,
                        description=description
                    )

                    self.circular_dependencies.append(circular_dep)

        except Exception as e:
            self.logger.error("Failed to find circular dependencies: %s", e)

    def _assess_circular_severity(self, modules: list[str]) -> SeverityLevel:
        """Assess the severity of a circular dependency."""
        if len(modules) > 5:
            return SeverityLevel.CRITICAL
        elif len(modules) > 3:
            return SeverityLevel.HIGH
        elif len(modules) > 2:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _calculate_dependency_depth(self, module_name: str) -> int:
        """Calculate dependency depth for a module."""
        try:
            if module_name not in self.import_graph:
                return 0

            # Use shortest path to calculate depth
            max_depth = 0
            for target in self.import_graph.successors(module_name):
                try:
                    depth = nx.shortest_path_length(self.import_graph, module_name, target)
                    max_depth = max(max_depth, depth)
                except nx.NetworkXNoPath:
                    continue

            return max_depth

        except Exception:
            return 0

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_module_name(self, file_path: Path) -> str:
        """Extract module name from file path."""
        # Convert path to module name
        relative_path = file_path.relative_to(self.project_root)
        module_name = str(relative_path.with_suffix(''))
        module_name = module_name.replace(os.path.sep, '.')

        # Remove __init__ from module names
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]

        return module_name

    def _get_module_group(self, module_name: str) -> str:
        """Determine module group from module name."""
        for group in MODULE_GROUPS:
            if module_name.startswith(group):
                return group

        return "Unknown"

    def _is_spyder_module(self, module_name: str) -> bool:
        """Check if a module is part of the Spyder project."""
        return module_name.startswith('Spyder') or any(
            module_name.startswith(group) for group in MODULE_GROUPS
        )

    def _group_modules(self) -> None:
        """Group modules by their category."""
        for module_name, module_info in self.modules.items():
            group = module_info.group
            if group not in self.module_groups:
                self.module_groups[group] = []
            self.module_groups[group].append(module_name)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def analyze_project_dependencies(project_root: str = ".") -> DependencyAnalyzer:
    """
    Quick function to analyze project dependencies.

    Args:
        project_root: Root directory of the project

    Returns:
        DependencyAnalyzer instance with analysis complete
    """
    analyzer = DependencyAnalyzer(project_root)
    analyzer.analyze_dependencies()
    return analyzer

def find_circular_dependencies(project_root: str = ".") -> list[CircularDependency]:
    """
    Quick function to find circular dependencies.

    Args:
        project_root: Root directory of the project

    Returns:
        List of circular dependencies found
    """
    analyzer = analyze_project_dependencies(project_root)
    return analyzer.find_circular_dependencies()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_dependency_analyzer_instance: DependencyAnalyzer | None = None

def get_dependency_analyzer(project_root: str = ".") -> DependencyAnalyzer:
    """
    Get singleton instance of dependency analyzer.

    Args:
        project_root: Root directory of the project

    Returns:
        DependencyAnalyzer instance
    """
    global _dependency_analyzer_instance
    if _dependency_analyzer_instance is None:
        _dependency_analyzer_instance = DependencyAnalyzer(project_root)
    return _dependency_analyzer_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    analyzer = DependencyAnalyzer(".")

    analyzer.analyze_dependencies()

    circular_deps = analyzer.find_circular_dependencies()
    if circular_deps:
        for _cd in circular_deps:
            pass
    else:
        pass

    graph = analyzer.generate_dependency_graph()

    if analyzer.modules:
        sample_module = list(analyzer.modules.keys())[0]
        deps = analyzer.get_module_dependencies(sample_module)

