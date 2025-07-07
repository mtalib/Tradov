#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU19_InteractionMatrix.py
Group: U (Utilities)
Purpose: Generate module interaction matrices and heatmaps

Description:
    This module creates comprehensive interaction matrices showing dependencies
    between Spyder module groups. It generates visual heatmaps, statistical
    analyses, and identifies architectural patterns. The tool helps visualize
    the coupling between different parts of the system and identify potential
    refactoring opportunities.

Usage Instructions:
    1. Basic interaction matrix:
       generator = InteractionMatrixGenerator('/path/to/spyder')
       matrix = generator.generate_interaction_matrix()
    
    2. Create heatmap visualization:
       generator.create_heatmap('interaction_heatmap.png')
    
    3. Analyze coupling metrics:
       metrics = generator.analyze_coupling_metrics()
    
    4. Find highly coupled modules:
       coupled = generator.find_highly_coupled_groups(threshold=0.3)
    
    5. Generate full report:
       generator.generate_interaction_report('interaction_report.html')
    
    6. Command line usage:
       python SpyderU19_InteractionMatrix.py --path /path/to/spyder

Author: Mohamed Talib
Date: 2025-01-28
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform
import networkx as nx

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU18_DependencyAnalyzer import SpyderDependencyAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Module groups in order
MODULE_GROUPS_ORDERED = [
    'SpyderA_Core',
    'SpyderB_Broker', 
    'SpyderC_MarketData',
    'SpyderD_Strategies',
    'SpyderE_Risk',
    'SpyderF_Analysis',
    'SpyderG_GUI',
    'SpyderH_Storage',
    'SpyderI_Integration',
    'SpyderJ_Alerts',
    'SpyderK_Reports',
    'SpyderL_ML',
    'SpyderM_Monitoring',
    'SpyderN_OptionsAnalytics',
    'SpyderO_RiskControl',
    'SpyderP_PortfolioMgmt',
    'SpyderR_Runtime',
    'SpyderT_Testing',
    'SpyderU_Utilities',
    'SpyderX_Agents',
    'SpyderZ_Communication'
]

# Group labels for display
GROUP_LABELS = {
    'SpyderA_Core': 'Core',
    'SpyderB_Broker': 'Broker',
    'SpyderC_MarketData': 'Market Data',
    'SpyderD_Strategies': 'Strategies',
    'SpyderE_Risk': 'Risk',
    'SpyderF_Analysis': 'Analysis',
    'SpyderG_GUI': 'GUI',
    'SpyderH_Storage': 'Storage',
    'SpyderI_Integration': 'Integration',
    'SpyderJ_Alerts': 'Alerts',
    'SpyderK_Reports': 'Reports',
    'SpyderL_ML': 'ML',
    'SpyderM_Monitoring': 'Monitoring',
    'SpyderN_OptionsAnalytics': 'Options',
    'SpyderO_RiskControl': 'Risk Control',
    'SpyderP_PortfolioMgmt': 'Portfolio',
    'SpyderR_Runtime': 'Runtime',
    'SpyderT_Testing': 'Testing',
    'SpyderU_Utilities': 'Utilities',
    'SpyderX_Agents': 'AI Agents',
    'SpyderZ_Communication': 'Communication'
}

# Colormap for heatmap
COLORMAP = 'RdYlBu_r'  # Red for high coupling, Blue for low

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CouplingMetrics:
    """Metrics for module coupling analysis"""
    afferent_coupling: int = 0  # Modules that depend on this module
    efferent_coupling: int = 0  # Modules this module depends on
    instability: float = 0.0    # Efferent / (Efferent + Afferent)
    abstractness: float = 0.0   # Abstract classes / Total classes
    distance_from_main: float = 0.0  # Distance from ideal line

@dataclass
class InteractionAnalysis:
    """Results of interaction analysis"""
    matrix: pd.DataFrame
    normalized_matrix: pd.DataFrame
    coupling_metrics: Dict[str, CouplingMetrics]
    highly_coupled_pairs: List[Tuple[str, str, float]]
    architectural_issues: List[str]
    recommendations: List[str]

# ==============================================================================
# INTERACTION MATRIX GENERATOR CLASS
# ==============================================================================
class InteractionMatrixGenerator:
    """
    Generate and analyze module interaction matrices.
    
    This class creates visual and statistical analyses of dependencies
    between Spyder module groups to understand system architecture.
    """
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the interaction matrix generator.
        
        Args:
            project_root: Root directory of the Spyder project
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.project_root = Path(project_root)
        self.config = config or {}
        
        # Initialize dependency analyzer
        self.dep_analyzer = SpyderDependencyAnalyzer(project_root)
        
        # Data structures
        self.interaction_matrix = None
        self.normalized_matrix = None
        self.coupling_metrics = {}
        
        # Analysis results
        self.dependency_data = None
        self.module_graph = None
        
        self.logger.info(f"Interaction Matrix Generator initialized for: {project_root}")
    
    # ==========================================================================
    # MATRIX GENERATION
    # ==========================================================================
    
    def generate_interaction_matrix(self) -> pd.DataFrame:
        """
        Generate the module group interaction matrix.
        
        Returns:
            DataFrame with interaction counts between module groups
            
        Usage:
            matrix = generator.generate_interaction_matrix()
            print(matrix)
        """
        self.logger.info("Generating interaction matrix...")
        
        # First, generate dependency map
        self.dependency_data = self.dep_analyzer.generate_dependency_map()
        
        # Initialize matrix
        matrix = pd.DataFrame(
            0,
            index=MODULE_GROUPS_ORDERED,
            columns=MODULE_GROUPS_ORDERED
        )
        
        # Count dependencies between groups
        for module_name, module_info in self.dependency_data['modules'].items():
            source_group = module_info.group
            
            for dep in module_info.dependencies:
                # Resolve dependency to module
                target_module = self.dep_analyzer._resolve_dependency(dep)
                
                if target_module and target_module in self.dependency_data['modules']:
                    target_group = self.dependency_data['modules'][target_module].group
                    
                    # Increment matrix
                    if source_group in matrix.index and target_group in matrix.columns:
                        matrix.loc[source_group, target_group] += 1
        
        self.interaction_matrix = matrix
        
        # Calculate normalized matrix
        self._calculate_normalized_matrix()
        
        # Calculate coupling metrics
        self._calculate_coupling_metrics()
        
        self.logger.info(f"Interaction matrix generated: {matrix.shape}")
        
        return matrix
    
    def _calculate_normalized_matrix(self):
        """Calculate normalized interaction matrix"""
        if self.interaction_matrix is None:
            return
        
        # Normalize by total modules in each group
        module_counts = {}
        for group in MODULE_GROUPS_ORDERED:
            count = len(self.dep_analyzer.module_groups.get(group, []))
            module_counts[group] = max(count, 1)  # Avoid division by zero
        
        # Create normalized matrix
        self.normalized_matrix = pd.DataFrame(
            index=self.interaction_matrix.index,
            columns=self.interaction_matrix.columns
        )
        
        for source in self.interaction_matrix.index:
            for target in self.interaction_matrix.columns:
                value = self.interaction_matrix.loc[source, target]
                normalized = value / module_counts[source]
                self.normalized_matrix.loc[source, target] = normalized
    
    def _calculate_coupling_metrics(self):
        """Calculate coupling metrics for each module group"""
        for group in MODULE_GROUPS_ORDERED:
            metrics = CouplingMetrics()
            
            # Afferent coupling (incoming dependencies)
            metrics.afferent_coupling = self.interaction_matrix[group].sum()
            
            # Efferent coupling (outgoing dependencies)
            metrics.efferent_coupling = self.interaction_matrix.loc[group].sum()
            
            # Instability
            total = metrics.afferent_coupling + metrics.efferent_coupling
            if total > 0:
                metrics.instability = metrics.efferent_coupling / total
            
            # Store metrics
            self.coupling_metrics[group] = metrics
    
    # ==========================================================================
    # VISUALIZATION
    # ==========================================================================
    
    def create_heatmap(self, output_file: str = 'interaction_heatmap.png',
                      figsize: Tuple[int, int] = (12, 10),
                      annotate: bool = True) -> str:
        """
        Create heatmap visualization of the interaction matrix.
        
        Args:
            output_file: Output filename
            figsize: Figure size tuple
            annotate: Whether to annotate cells with values
            
        Returns:
            Path to saved figure
            
        Usage:
            path = generator.create_heatmap('my_heatmap.png', figsize=(15, 12))
        """
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        plt.figure(figsize=figsize)
        
        # Use normalized matrix for better visualization
        matrix_to_plot = self.normalized_matrix
        
        # Create custom labels
        labels = [GROUP_LABELS.get(g, g) for g in MODULE_GROUPS_ORDERED]
        
        # Create heatmap
        mask = matrix_to_plot == 0  # Mask zero values
        
        sns.heatmap(
            matrix_to_plot,
            annot=annotate,
            fmt='.2f',
            cmap=COLORMAP,
            center=0,
            square=True,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8, "label": "Normalized Dependencies"},
            mask=mask,
            xticklabels=labels,
            yticklabels=labels
        )
        
        plt.title('Spyder Module Group Interaction Matrix', fontsize=16, pad=20)
        plt.xlabel('Target Module Group', fontsize=12)
        plt.ylabel('Source Module Group', fontsize=12)
        
        # Rotate labels
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        # Add grid
        plt.grid(True, alpha=0.3)
        
        # Tight layout
        plt.tight_layout()
        
        # Save figure
        output_path = self.project_root / output_file
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"Heatmap saved to: {output_path}")
        return str(output_path)
    
    def create_clustered_heatmap(self, output_file: str = 'clustered_heatmap.png',
                               figsize: Tuple[int, int] = (14, 12)) -> str:
        """
        Create clustered heatmap using hierarchical clustering.
        
        Args:
            output_file: Output filename
            figsize: Figure size tuple
            
        Returns:
            Path to saved figure
            
        Usage:
            path = generator.create_clustered_heatmap()
        """
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        # Create figure
        fig = plt.figure(figsize=figsize)
        
        # Use normalized matrix
        matrix = self.normalized_matrix.values
        
        # Calculate distance matrix
        distance_matrix = squareform(1 - np.corrcoef(matrix))
        
        # Perform hierarchical clustering
        linkage = hierarchy.linkage(distance_matrix, method='average')
        
        # Create dendrogram
        dendro = hierarchy.dendrogram(
            linkage,
            no_plot=True,
            labels=[GROUP_LABELS.get(g, g) for g in MODULE_GROUPS_ORDERED]
        )
        
        # Reorder matrix based on clustering
        reordered_idx = dendro['leaves']
        reordered_matrix = matrix[reordered_idx][:, reordered_idx]
        reordered_labels = [GROUP_LABELS.get(MODULE_GROUPS_ORDERED[i], MODULE_GROUPS_ORDERED[i]) 
                           for i in reordered_idx]
        
        # Create clustered heatmap
        sns.heatmap(
            reordered_matrix,
            annot=True,
            fmt='.2f',
            cmap=COLORMAP,
            center=0,
            square=True,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8, "label": "Normalized Dependencies"},
            xticklabels=reordered_labels,
            yticklabels=reordered_labels
        )
        
        plt.title('Clustered Module Interaction Matrix', fontsize=16, pad=20)
        plt.xlabel('Target Module Group', fontsize=12)
        plt.ylabel('Source Module Group', fontsize=12)
        
        # Rotate labels
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        plt.tight_layout()
        
        # Save figure
        output_path = self.project_root / output_file
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"Clustered heatmap saved to: {output_path}")
        return str(output_path)
    
    def create_dependency_flow_diagram(self, output_file: str = 'dependency_flow.png',
                                     threshold: float = 0.1) -> str:
        """
        Create a flow diagram showing major dependencies.
        
        Args:
            output_file: Output filename
            threshold: Minimum normalized dependency value to show
            
        Returns:
            Path to saved figure
            
        Usage:
            path = generator.create_dependency_flow_diagram(threshold=0.2)
        """
        if self.normalized_matrix is None:
            self.generate_interaction_matrix()
        
        # Create directed graph
        G = nx.DiGraph()
        
        # Add nodes
        for group in MODULE_GROUPS_ORDERED:
            if group in self.coupling_metrics:
                metrics = self.coupling_metrics[group]
                G.add_node(
                    group,
                    label=GROUP_LABELS.get(group, group),
                    coupling=metrics.efferent_coupling + metrics.afferent_coupling
                )
        
        # Add edges above threshold
        for source in MODULE_GROUPS_ORDERED:
            for target in MODULE_GROUPS_ORDERED:
                if source != target:
                    weight = self.normalized_matrix.loc[source, target]
                    if weight >= threshold:
                        G.add_edge(source, target, weight=weight)
        
        # Create layout
        pos = nx.spring_layout(G, k=3, iterations=50)
        
        # Create figure
        plt.figure(figsize=(14, 10))
        
        # Draw nodes
        node_sizes = [G.nodes[node]['coupling'] * 50 for node in G.nodes()]
        node_colors = [self.coupling_metrics[node].instability for node in G.nodes()]
        
        nx.draw_networkx_nodes(
            G, pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap='coolwarm',
            alpha=0.8,
            linewidths=2,
            edgecolors='black'
        )
        
        # Draw edges
        edges = G.edges()
        weights = [G[u][v]['weight'] for u, v in edges]
        
        nx.draw_networkx_edges(
            G, pos,
            edge_color=weights,
            edge_cmap=plt.cm.Greys,
            width=[w * 5 for w in weights],
            alpha=0.6,
            arrows=True,
            arrowsize=20,
            arrowstyle='->'
        )
        
        # Draw labels
        labels = {node: G.nodes[node]['label'] for node in G.nodes()}
        nx.draw_networkx_labels(
            G, pos,
            labels,
            font_size=10,
            font_weight='bold'
        )
        
        # Add colorbar for instability
        sm = plt.cm.ScalarMappable(cmap='coolwarm', 
                                   norm=plt.Normalize(vmin=0, vmax=1))
        sm.set_array([])
        cbar = plt.colorbar(sm, fraction=0.02, pad=0.04)
        cbar.set_label('Instability', rotation=270, labelpad=20)
        
        plt.title('Module Group Dependency Flow\n(Node size = Total coupling, Color = Instability)',
                 fontsize=14)
        plt.axis('off')
        plt.tight_layout()
        
        # Save figure
        output_path = self.project_root / output_file
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"Dependency flow diagram saved to: {output_path}")
        return str(output_path)
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def analyze_coupling_metrics(self) -> Dict[str, Any]:
        """
        Analyze coupling metrics for all module groups.
        
        Returns:
            Dictionary with coupling analysis results
            
        Usage:
            metrics = generator.analyze_coupling_metrics()
            print(json.dumps(metrics, indent=2))
        """
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        analysis = {
            'summary': {},
            'groups': {},
            'warnings': [],
            'recommendations': []
        }
        
        # Calculate summary statistics
        all_instabilities = [m.instability for m in self.coupling_metrics.values()]
        all_couplings = [m.afferent_coupling + m.efferent_coupling 
                        for m in self.coupling_metrics.values()]
        
        analysis['summary'] = {
            'average_instability': np.mean(all_instabilities),
            'max_instability': max(all_instabilities),
            'average_coupling': np.mean(all_couplings),
            'max_coupling': max(all_couplings),
            'total_dependencies': self.interaction_matrix.sum().sum()
        }
        
        # Analyze each group
        for group, metrics in self.coupling_metrics.items():
            analysis['groups'][group] = {
                'afferent_coupling': metrics.afferent_coupling,
                'efferent_coupling': metrics.efferent_coupling,
                'instability': round(metrics.instability, 3),
                'total_coupling': metrics.afferent_coupling + metrics.efferent_coupling,
                'coupling_ratio': round(
                    metrics.efferent_coupling / max(1, metrics.afferent_coupling), 
                    3
                )
            }
            
            # Generate warnings
            if metrics.instability > 0.8:
                analysis['warnings'].append(
                    f"{GROUP_LABELS[group]} has high instability ({metrics.instability:.2f})"
                )
            
            if metrics.efferent_coupling > 50:
                analysis['warnings'].append(
                    f"{GROUP_LABELS[group]} has excessive outgoing dependencies ({metrics.efferent_coupling})"
                )
        
        # Generate recommendations
        self._generate_coupling_recommendations(analysis)
        
        return analysis
    
    def find_highly_coupled_groups(self, threshold: float = 0.2) -> List[Tuple[str, str, float]]:
        """
        Find module groups with high coupling.
        
        Args:
            threshold: Normalized coupling threshold
            
        Returns:
            List of (source, target, coupling) tuples
            
        Usage:
            coupled = generator.find_highly_coupled_groups(0.3)
            for source, target, value in coupled:
                print(f"{source} -> {target}: {value:.2f}")
        """
        if self.normalized_matrix is None:
            self.generate_interaction_matrix()
        
        highly_coupled = []
        
        for source in MODULE_GROUPS_ORDERED:
            for target in MODULE_GROUPS_ORDERED:
                if source != target:
                    coupling = self.normalized_matrix.loc[source, target]
                    if coupling >= threshold:
                        highly_coupled.append((
                            GROUP_LABELS.get(source, source),
                            GROUP_LABELS.get(target, target),
                            coupling
                        ))
        
        # Sort by coupling value
        highly_coupled.sort(key=lambda x: x[2], reverse=True)
        
        return highly_coupled
    
    def identify_architectural_patterns(self) -> Dict[str, Any]:
        """
        Identify architectural patterns and potential issues.
        
        Returns:
            Dictionary with identified patterns
            
        Usage:
            patterns = generator.identify_architectural_patterns()
        """
        patterns = {
            'layering_violations': [],
            'circular_dependencies': [],
            'god_modules': [],
            'isolated_modules': [],
            'architectural_style': 'unknown'
        }
        
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        # Check for layering violations
        # Expected flow: GUI -> Strategies -> Core -> Broker/Data
        layer_order = {
            'SpyderG_GUI': 0,
            'SpyderK_Reports': 1,
            'SpyderD_Strategies': 2,
            'SpyderE_Risk': 3,
            'SpyderA_Core': 4,
            'SpyderB_Broker': 5,
            'SpyderC_MarketData': 5,
            'SpyderH_Storage': 5
        }
        
        for source, source_layer in layer_order.items():
            for target, target_layer in layer_order.items():
                if source != target and target_layer < source_layer:
                    deps = self.interaction_matrix.loc[source, target]
                    if deps > 0:
                        patterns['layering_violations'].append({
                            'source': GROUP_LABELS[source],
                            'target': GROUP_LABELS[target],
                            'dependencies': int(deps)
                        })
        
        # Find god modules (high coupling)
        for group, metrics in self.coupling_metrics.items():
            total_coupling = metrics.afferent_coupling + metrics.efferent_coupling
            if total_coupling > 100:  # Threshold
                patterns['god_modules'].append({
                    'module': GROUP_LABELS[group],
                    'total_coupling': total_coupling,
                    'incoming': metrics.afferent_coupling,
                    'outgoing': metrics.efferent_coupling
                })
        
        # Find isolated modules
        for group in MODULE_GROUPS_ORDERED:
            row_sum = self.interaction_matrix.loc[group].sum()
            col_sum = self.interaction_matrix[group].sum()
            if row_sum == 0 and col_sum == 0:
                patterns['isolated_modules'].append(GROUP_LABELS[group])
        
        # Determine architectural style
        patterns['architectural_style'] = self._determine_architectural_style()
        
        return patterns
    
    def _determine_architectural_style(self) -> str:
        """Determine the overall architectural style"""
        # Analyze coupling patterns
        core_coupling = self.coupling_metrics.get('SpyderA_Core', CouplingMetrics())
        utils_coupling = self.coupling_metrics.get('SpyderU_Utilities', CouplingMetrics())
        
        # High afferent coupling on utilities suggests shared kernel
        if utils_coupling.afferent_coupling > 50:
            return "Modular with Shared Kernel (Utilities)"
        
        # High afferent coupling on core suggests hub-and-spoke
        elif core_coupling.afferent_coupling > 30:
            return "Hub-and-Spoke (Core-centric)"
        
        # Check for layered architecture
        elif self._check_layered_architecture():
            return "Layered Architecture"
        
        else:
            return "Hybrid/Mixed Architecture"
    
    def _check_layered_architecture(self) -> bool:
        """Check if the system follows layered architecture"""
        # Simplified check - would need more sophisticated analysis
        violations = 0
        
        # Expected layers (top to bottom)
        layers = [
            ['SpyderG_GUI', 'SpyderJ_Alerts', 'SpyderK_Reports'],
            ['SpyderD_Strategies', 'SpyderL_ML', 'SpyderX_Agents'],
            ['SpyderE_Risk', 'SpyderF_Analysis', 'SpyderN_OptionsAnalytics'],
            ['SpyderA_Core', 'SpyderI_Integration'],
            ['SpyderB_Broker', 'SpyderC_MarketData', 'SpyderH_Storage']
        ]
        
        # Check for upward dependencies
        for i, upper_layer in enumerate(layers[:-1]):
            for j, lower_layer in enumerate(layers[i+1:], i+1):
                for upper in upper_layer:
                    for lower in lower_layer:
                        if upper in self.interaction_matrix.index and \
                           lower in self.interaction_matrix.columns:
                            if self.interaction_matrix.loc[lower, upper] > 0:
                                violations += 1
        
        return violations < 5  # Allow some violations
    
    def _generate_coupling_recommendations(self, analysis: Dict[str, Any]):
        """Generate recommendations based on coupling analysis"""
        recommendations = []
        
        # Check for high instability
        high_instability = [
            group for group, metrics in self.coupling_metrics.items()
            if metrics.instability > 0.7
        ]
        
        if high_instability:
            recommendations.append(
                f"Consider stabilizing {', '.join(GROUP_LABELS[g] for g in high_instability)} "
                "by reducing outgoing dependencies"
            )
        
        # Check for god modules
        god_modules = [
            group for group, metrics in self.coupling_metrics.items()
            if metrics.afferent_coupling + metrics.efferent_coupling > 100
        ]
        
        if god_modules:
            recommendations.append(
                f"Consider refactoring {', '.join(GROUP_LABELS[g] for g in god_modules)} "
                "to reduce coupling"
            )
        
        # Check for utilities coupling
        if 'SpyderU_Utilities' in self.coupling_metrics:
            utils_metrics = self.coupling_metrics['SpyderU_Utilities']
            if utils_metrics.efferent_coupling > 10:
                recommendations.append(
                    "Utilities should have minimal outgoing dependencies"
                )
        
        analysis['recommendations'] = recommendations
    
    # ==========================================================================
    # REPORT GENERATION
    # ==========================================================================
    
    def generate_interaction_report(self, output_file: str = 'interaction_report.html') -> str:
        """
        Generate comprehensive HTML report of interactions.
        
        Args:
            output_file: Output filename
            
        Returns:
            Path to generated report
            
        Usage:
            report_path = generator.generate_interaction_report()
        """
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        # Gather all analysis results
        coupling_metrics = self.analyze_coupling_metrics()
        highly_coupled = self.find_highly_coupled_groups()
        patterns = self.identify_architectural_patterns()
        
        # Create visualizations
        heatmap_path = self.create_heatmap('temp_heatmap.png')
        flow_path = self.create_dependency_flow_diagram('temp_flow.png')
        
        # Generate HTML report
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Spyder Module Interaction Analysis</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .metric-card {{
            display: inline-block;
            margin: 10px;
            padding: 15px;
            background-color: #ecf0f1;
            border-radius: 5px;
            min-width: 200px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #3498db;
        }}
        .warning {{
            background-color: #e74c3c;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
        }}
        .recommendation {{
            background-color: #27ae60;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .visualization {{
            text-align: center;
            margin: 20px 0;
        }}
        .visualization img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Spyder Module Interaction Analysis</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Summary Metrics</h2>
        <div>
            <div class="metric-card">
                <div>Total Dependencies</div>
                <div class="metric-value">{int(coupling_metrics['summary']['total_dependencies'])}</div>
            </div>
            <div class="metric-card">
                <div>Average Coupling</div>
                <div class="metric-value">{coupling_metrics['summary']['average_coupling']:.1f}</div>
            </div>
            <div class="metric-card">
                <div>Average Instability</div>
                <div class="metric-value">{coupling_metrics['summary']['average_instability']:.2f}</div>
            </div>
            <div class="metric-card">
                <div>Architectural Style</div>
                <div class="metric-value" style="font-size: 16px;">{patterns['architectural_style']}</div>
            </div>
        </div>
        
        <h2>Visualizations</h2>
        <div class="visualization">
            <h3>Interaction Heatmap</h3>
            <img src="{Path(heatmap_path).name}" alt="Interaction Heatmap">
        </div>
        
        <div class="visualization">
            <h3>Dependency Flow</h3>
            <img src="{Path(flow_path).name}" alt="Dependency Flow">
        </div>
        
        <h2>Highly Coupled Module Groups</h2>
        <table>
            <tr>
                <th>Source</th>
                <th>Target</th>
                <th>Coupling</th>
            </tr>
"""
        
        for source, target, coupling in highly_coupled[:10]:
            html += f"""
            <tr>
                <td>{source}</td>
                <td>{target}</td>
                <td>{coupling:.3f}</td>
            </tr>
"""
        
        html += """
        </table>
        
        <h2>Coupling Metrics by Group</h2>
        <table>
            <tr>
                <th>Module Group</th>
                <th>Incoming</th>
                <th>Outgoing</th>
                <th>Total</th>
                <th>Instability</th>
            </tr>
"""
        
        for group, metrics in sorted(coupling_metrics['groups'].items()):
            html += f"""
            <tr>
                <td>{GROUP_LABELS.get(group, group)}</td>
                <td>{metrics['afferent_coupling']}</td>
                <td>{metrics['efferent_coupling']}</td>
                <td>{metrics['total_coupling']}</td>
                <td>{metrics['instability']:.3f}</td>
            </tr>
"""
        
        html += """
        </table>
"""
        
        # Add warnings
        if coupling_metrics['warnings']:
            html += "<h2>Warnings</h2>"
            for warning in coupling_metrics['warnings']:
                html += f'<div class="warning">{warning}</div>'
        
        # Add recommendations
        if coupling_metrics['recommendations']:
            html += "<h2>Recommendations</h2>"
            for rec in coupling_metrics['recommendations']:
                html += f'<div class="recommendation">{rec}</div>'
        
        # Add architectural issues
        if patterns['layering_violations']:
            html += "<h2>Layering Violations</h2><ul>"
            for violation in patterns['layering_violations'][:10]:
                html += f"<li>{violation['source']} → {violation['target']} ({violation['dependencies']} dependencies)</li>"
            html += "</ul>"
        
        if patterns['god_modules']:
            html += "<h2>Highly Coupled Modules (God Modules)</h2><ul>"
            for god in patterns['god_modules']:
                html += f"<li>{god['module']}: {god['total_coupling']} total dependencies</li>"
            html += "</ul>"
        
        html += """
    </div>
</body>
</html>
"""
        
        # Save report
        output_path = self.project_root / output_file
        with open(output_path, 'w') as f:
            f.write(html)
        
        # Copy images to same directory
        import shutil
        shutil.copy(heatmap_path, output_path.parent)
        shutil.copy(flow_path, output_path.parent)
        
        # Clean up temp files
        Path(heatmap_path).unlink()
        Path(flow_path).unlink()
        
        self.logger.info(f"Interaction report saved to: {output_path}")
        return str(output_path)
    
    # ==========================================================================
    # EXPORT METHODS
    # ==========================================================================
    
    def export_to_csv(self, output_file: str = 'interaction_matrix.csv') -> str:
        """
        Export interaction matrix to CSV.
        
        Args:
            output_file: Output filename
            
        Returns:
            Path to saved file
            
        Usage:
            path = generator.export_to_csv('matrix.csv')
        """
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        output_path = self.project_root / output_file
        self.interaction_matrix.to_csv(output_path)
        
        # Also save normalized matrix
        norm_path = output_path.with_stem(output_path.stem + '_normalized')
        self.normalized_matrix.to_csv(norm_path)
        
        self.logger.info(f"Matrices exported to: {output_path} and {norm_path}")
        return str(output_path)
    
    def export_to_json(self, output_file: str = 'interaction_analysis.json') -> str:
        """
        Export complete analysis to JSON.
        
        Args:
            output_file: Output filename
            
        Returns:
            Path to saved file
            
        Usage:
            path = generator.export_to_json()
        """
        if self.interaction_matrix is None:
            self.generate_interaction_matrix()
        
        export_data = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'project_root': str(self.project_root)
            },
            'interaction_matrix': self.interaction_matrix.to_dict(),
            'normalized_matrix': self.normalized_matrix.to_dict(),
            'coupling_metrics': self.analyze_coupling_metrics(),
            'highly_coupled_pairs': self.find_highly_coupled_groups(),
            'architectural_patterns': self.identify_architectural_patterns()
        }
        
        output_path = self.project_root / output_file
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.logger.info(f"Analysis exported to: {output_path}")
        return str(output_path)


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def analyze_module_interactions(project_path: str = '.', 
                              create_visualizations: bool = True) -> InteractionAnalysis:
    """
    Convenience function to analyze module interactions.
    
    Args:
        project_path: Path to Spyder project
        create_visualizations: Whether to create visualizations
        
    Returns:
        InteractionAnalysis object with results
        
    Usage:
        analysis = analyze_module_interactions('/path/to/spyder')
    """
    generator = InteractionMatrixGenerator(project_path)
    
    # Generate matrix
    matrix = generator.generate_interaction_matrix()
    
    # Perform analysis
    coupling_metrics = generator.analyze_coupling_metrics()
    highly_coupled = generator.find_highly_coupled_groups()
    patterns = generator.identify_architectural_patterns()
    
    # Create visualizations
    if create_visualizations:
        generator.create_heatmap()
        generator.create_clustered_heatmap()
        generator.create_dependency_flow_diagram()
        generator.generate_interaction_report()
    
    # Create analysis result
    analysis = InteractionAnalysis(
        matrix=matrix,
        normalized_matrix=generator.normalized_matrix,
        coupling_metrics=generator.coupling_metrics,
        highly_coupled_pairs=highly_coupled,
        architectural_issues=patterns.get('layering_violations', []),
        recommendations=coupling_metrics.get('recommendations', [])
    )
    
    return analysis


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate module interaction matrices for Spyder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic analysis with all visualizations
    python SpyderU19_InteractionMatrix.py --path /path/to/spyder
    
    # Create specific visualization
    python SpyderU19_InteractionMatrix.py --path /path/to/spyder --heatmap
    
    # Export data
    python SpyderU19_InteractionMatrix.py --path /path/to/spyder --export-csv --export-json
    
    # Full analysis with HTML report
    python SpyderU19_InteractionMatrix.py --path /path/to/spyder --full-report
        """
    )
    
    parser.add_argument('--path', type=str, default='.',
                       help='Path to Spyder project root')
    parser.add_argument('--heatmap', action='store_true',
                       help='Create interaction heatmap')
    parser.add_argument('--clustered', action='store_true',
                       help='Create clustered heatmap')
    parser.add_argument('--flow', action='store_true',
                       help='Create dependency flow diagram')
    parser.add_argument('--full-report', action='store_true',
                       help='Generate full HTML report')
    parser.add_argument('--export-csv', action='store_true',
                       help='Export matrix to CSV')
    parser.add_argument('--export-json', action='store_true',
                       help='Export analysis to JSON')
    parser.add_argument('--threshold', type=float, default=0.2,
                       help='Coupling threshold for analysis')
    
    args = parser.parse_args()
    
    # Create generator
    print(f"Analyzing module interactions in: {args.path}")
    generator = InteractionMatrixGenerator(args.path)
    
    # Generate matrix
    print("Generating interaction matrix...")
    matrix = generator.generate_interaction_matrix()
    
    print(f"\nMatrix Summary:")
    print(f"  Shape: {matrix.shape}")
    print(f"  Total Dependencies: {matrix.sum().sum()}")
    print(f"  Non-zero Cells: {(matrix > 0).sum().sum()}")
    
    # Perform analysis
    print("\nAnalyzing coupling metrics...")
    metrics = generator.analyze_coupling_metrics()
    
    print(f"\nCoupling Summary:")
    print(f"  Average Instability: {metrics['summary']['average_instability']:.3f}")
    print(f"  Max Coupling: {metrics['summary']['max_coupling']}")
    
    # Find highly coupled groups
    print(f"\nHighly Coupled Groups (threshold={args.threshold}):")
    coupled = generator.find_highly_coupled_groups(args.threshold)
    for source, target, value in coupled[:5]:
        print(f"  {source} → {target}: {value:.3f}")
    
    # Create visualizations
    if args.heatmap or args.full_report:
        print("\nCreating heatmap...")
        heatmap_path = generator.create_heatmap()
        print(f"  Saved to: {heatmap_path}")
    
    if args.clustered:
        print("\nCreating clustered heatmap...")
        clustered_path = generator.create_clustered_heatmap()
        print(f"  Saved to: {clustered_path}")
    
    if args.flow:
        print("\nCreating dependency flow diagram...")
        flow_path = generator.create_dependency_flow_diagram()
        print(f"  Saved to: {flow_path}")
    
    if args.full_report:
        print("\nGenerating full HTML report...")
        report_path = generator.generate_interaction_report()
        print(f"  Saved to: {report_path}")
    
    # Export data
    if args.export_csv:
        csv_path = generator.export_to_csv()
        print(f"\nCSV exported to: {csv_path}")
    
    if args.export_json:
        json_path = generator.export_to_json()
        print(f"JSON exported to: {json_path}")
    
    # Identify patterns
    print("\nArchitectural Analysis:")
    patterns = generator.identify_architectural_patterns()
    print(f"  Style: {patterns['architectural_style']}")
    print(f"  Layering Violations: {len(patterns['layering_violations'])}")
    print(f"  God Modules: {len(patterns['god_modules'])}")
    print(f"  Isolated Modules: {len(patterns['isolated_modules'])}")
    
    print("\nInteraction analysis complete!")
