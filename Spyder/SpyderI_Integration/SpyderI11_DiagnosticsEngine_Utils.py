#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderI_Integration
Module: SpyderI11_DiagnosticsEngine_Utils.py
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
from typing import Any
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI10_DiagnosticsEngine_Types import (

    SystemMetrics, ModuleHealth, IntegrationHealth, DiagnosticIssue,
    HealthStatus, ProblemSeverity, health_status_to_score, HEALTH_SCORE_WEIGHTS
)

# ==============================================================================
# DIAGNOSTIC UTILITIES CLASS
# ==============================================================================

class DiagnosticUtils:
    """
    Utility functions for diagnostic operations.

    Provides methods for calculating health scores, generating recommendations,
    creating summaries, and other diagnostic utility functions.
    """

    def __init__(self):
        """Initialize diagnostic utilities."""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

    # ==========================================================================
    # HEALTH SCORE CALCULATIONS
    # ==========================================================================

    def calculate_overall_health_score(self,
                                     system_metrics: SystemMetrics,
                                     module_health: list[ModuleHealth],
                                     integration_health: list[IntegrationHealth],
                                     issues: list[DiagnosticIssue]) -> float:
        """
        Calculate overall system health score (0-1).

        Args:
            system_metrics: Current system metrics
            module_health: List of module health status
            integration_health: List of integration health status
            issues: List of current issues

        Returns:
            Overall health score (0.0 to 1.0)
        """
        try:
            scores = []

            # System health score (40% weight)
            system_score = self._calculate_system_score(system_metrics)
            scores.append(('system', system_score, HEALTH_SCORE_WEIGHTS['system']))

            # Module health score (30% weight)
            if module_health:
                module_score = self._calculate_module_score(module_health)
                scores.append(('modules', module_score, HEALTH_SCORE_WEIGHTS['modules']))

            # Integration health score (20% weight)
            if integration_health:
                integration_score = self._calculate_integration_score(integration_health)
                scores.append(('integrations', integration_score, HEALTH_SCORE_WEIGHTS['integration']))  # noqa: E501

            # Issue impact score (10% weight)
            issue_score = self._calculate_issue_score(issues)
            scores.append(('issues', issue_score, HEALTH_SCORE_WEIGHTS['issues']))

            # Calculate weighted average
            total_score = sum(score * weight for name, score, weight in scores)
            total_weight = sum(weight for name, score, weight in scores)

            return total_score / total_weight if total_weight > 0 else 0.0

        except Exception as e:
            self.error_handler.handle_error(e, "calculate_overall_health_score")
            return 0.5  # Default to medium health on error

    def _calculate_system_score(self, metrics: SystemMetrics) -> float:
        """Calculate system health score based on metrics."""
        try:
            score = 1.0

            # CPU impact (30% of system score)
            cpu_impact = max(0, (metrics.cpu_percent - 50) / 50) * 0.3
            score -= cpu_impact

            # Memory impact (30% of system score)
            memory_impact = max(0, (metrics.memory_percent - 50) / 50) * 0.3
            score -= memory_impact

            # Disk impact (40% of system score)
            disk_impact = max(0, (metrics.disk_usage_percent - 70) / 30) * 0.4
            score -= disk_impact

            return max(0.0, min(1.0, score))

        except Exception:
            return 0.5

    def _calculate_module_score(self, module_health: list[ModuleHealth]) -> float:
        """Calculate module health score."""
        try:
            if not module_health:
                return 1.0

            module_scores = [health_status_to_score(module.status) for module in module_health]
            return statistics.mean(module_scores)

        except Exception:
            return 0.5

    def _calculate_integration_score(self, integration_health: list[IntegrationHealth]) -> float:
        """Calculate integration health score."""
        try:
            if not integration_health:
                return 1.0

            integration_scores = [
                health_status_to_score(integration.connection_status)
                for integration in integration_health
            ]
            return statistics.mean(integration_scores)

        except Exception:
            return 0.5

    def _calculate_issue_score(self, issues: list[DiagnosticIssue]) -> float:
        """Calculate issue impact score."""
        try:
            if not issues:
                return 1.0

            # Calculate total issue impact
            total_impact = 0.0
            for issue in issues:
                if issue.severity == ProblemSeverity.CRITICAL:
                    total_impact += 0.5
                elif issue.severity == ProblemSeverity.HIGH:
                    total_impact += 0.3
                elif issue.severity == ProblemSeverity.MEDIUM:
                    total_impact += 0.1
                elif issue.severity == ProblemSeverity.LOW:
                    total_impact += 0.05

            # Convert to score (less impact = higher score)
            return max(0.0, 1.0 - min(1.0, total_impact))

        except Exception:
            return 0.5

    # ==========================================================================
    # RECOMMENDATION GENERATION
    # ==========================================================================

    def generate_recommendations(self,
                               issues: list[DiagnosticIssue],
                               performance_summary: dict[str, Any]) -> list[str]:
        """
        Generate actionable recommendations based on issues and performance.

        Args:
            issues: List of diagnostic issues
            performance_summary: Performance analysis summary

        Returns:
            List of recommendation strings
        """
        try:
            recommendations = []

            # Group issues by severity
            critical_issues = [i for i in issues if i.severity == ProblemSeverity.CRITICAL]
            high_issues = [i for i in issues if i.severity == ProblemSeverity.HIGH]
            medium_issues = [i for i in issues if i.severity == ProblemSeverity.MEDIUM]

            # Critical issue recommendations
            if critical_issues:
                recommendations.append("🚨 IMMEDIATE ACTION REQUIRED:")
                for issue in critical_issues[:3]:  # Top 3 critical
                    for rec in issue.recommendations[:2]:  # Top 2 per issue
                        recommendations.append(f"  • {rec}")

            # High priority recommendations
            if high_issues:
                recommendations.append("⚠️  HIGH PRIORITY:")
                for issue in high_issues[:3]:  # Top 3 high
                    if issue.recommendations:
                        recommendations.append(f"  • {issue.recommendations[0]}")

            # Medium priority recommendations
            if medium_issues and len(recommendations) < 10:
                recommendations.append("📋 MEDIUM PRIORITY:")
                for issue in medium_issues[:2]:  # Top 2 medium
                    if issue.recommendations:
                        recommendations.append(f"  • {issue.recommendations[0]}")

            # Performance recommendations
            if performance_summary.get('bottlenecks'):
                recommendations.append("📈 PERFORMANCE OPTIMIZATION:")
                for bottleneck in performance_summary['bottlenecks'][:2]:
                    recommendations.append(f"  • Optimize {bottleneck}")

            # General maintenance recommendations
            if not critical_issues and not high_issues:
                recommendations.extend([
                    "✅ System is operating normally",
                    "📊 Continue monitoring performance trends",
                    "🔄 Consider routine maintenance during low-activity periods"
                ])

            # Limit total recommendations
            return recommendations[:15]

        except Exception as e:
            self.error_handler.handle_error(e, "generate_recommendations")
            return ["❌ Error generating recommendations - review system manually"]

    # ==========================================================================
    # EXECUTIVE SUMMARY CREATION
    # ==========================================================================

    def create_executive_summary(self,
                               health_score: float,
                               issues: list[DiagnosticIssue],
                               performance_summary: dict[str, Any]) -> str:
        """
        Create executive summary of system health.

        Args:
            health_score: Overall health score (0-1)
            issues: List of diagnostic issues
            performance_summary: Performance analysis summary

        Returns:
            Executive summary string
        """
        try:
            # Determine overall status
            if health_score >= 0.9:
                status = "EXCELLENT"
                status_emoji = "🟢"
            elif health_score >= 0.7:
                status = "GOOD"
                status_emoji = "🟡"
            elif health_score >= 0.5:
                status = "WARNING"
                status_emoji = "🟠"
            elif health_score >= 0.3:
                status = "CRITICAL"
                status_emoji = "🔴"
            else:
                status = "FAILING"
                status_emoji = "💀"

            # Count issues by severity
            critical_count = len([i for i in issues if i.severity == ProblemSeverity.CRITICAL])
            high_count = len([i for i in issues if i.severity == ProblemSeverity.HIGH])
            medium_count = len([i for i in issues if i.severity == ProblemSeverity.MEDIUM])

            # Create summary sections
            summary_parts = [
                f"{status_emoji} **SYSTEM STATUS: {status}** (Health Score: {health_score:.1%})",
                ""
            ]

            # Issue summary
            if critical_count > 0:
                summary_parts.append(f"🚨 **{critical_count} CRITICAL ISSUES** require immediate attention")  # noqa: E501

            if high_count > 0:
                summary_parts.append(f"⚠️  {high_count} high-priority issues detected")

            if medium_count > 0:
                summary_parts.append(f"📋 {medium_count} medium-priority issues for review")

            if critical_count == 0 and high_count == 0:
                summary_parts.append("✅ No critical or high-priority issues detected")

            # Performance insights
            if performance_summary.get('trends'):
                summary_parts.append("")
                summary_parts.append("📈 **Performance Trends:**")
                for trend in performance_summary['trends'][:3]:
                    summary_parts.append(f"  • {trend}")

            # Key recommendations for critical issues
            if critical_count > 0:
                summary_parts.append("")
                summary_parts.append("🎯 **Immediate Actions:**")
                critical_issues = [i for i in issues if i.severity == ProblemSeverity.CRITICAL]
                for issue in critical_issues[:2]:
                    if issue.recommendations:
                        summary_parts.append(f"  • {issue.recommendations[0]}")

            return "\n".join(summary_parts)

        except Exception as e:
            self.error_handler.handle_error(e, "create_executive_summary")
            return f"Executive summary generation failed: {str(e)}"

    # ==========================================================================
    # DATA ANALYSIS HELPERS
    # ==========================================================================

    def analyze_issue_patterns(self, issues: list[DiagnosticIssue]) -> dict[str, Any]:
        """
        Analyze patterns in diagnostic issues.

        Args:
            issues: List of diagnostic issues

        Returns:
            Pattern analysis results
        """
        try:
            patterns = {
                'by_category': defaultdict(int),
                'by_severity': defaultdict(int),
                'by_component': defaultdict(int),
                'recurring_issues': [],
                'most_impacted_components': []
            }

            # Count by category and severity
            for issue in issues:
                patterns['by_category'][issue.category.value] += 1
                patterns['by_severity'][issue.severity.value] += 1

                # Count affected components
                for component in issue.affected_components:
                    patterns['by_component'][component] += 1

            # Find most impacted components
            if patterns['by_component']:
                sorted_components = sorted(
                    patterns['by_component'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                patterns['most_impacted_components'] = sorted_components[:5]

            return dict(patterns)

        except Exception as e:
            self.error_handler.handle_error(e, "analyze_issue_patterns")
            return {}

    def calculate_system_availability(self,
                                    module_health: list[ModuleHealth]) -> float:
        """
        Calculate system availability based on module health.

        Args:
            module_health: List of module health status

        Returns:
            Availability percentage (0-100)
        """
        try:
            if not module_health:
                return 100.0

            # Count healthy modules
            healthy_count = len([
                m for m in module_health
                if m.status in [HealthStatus.EXCELLENT, HealthStatus.GOOD]
            ])

            return (healthy_count / len(module_health)) * 100.0

        except Exception as e:
            self.error_handler.handle_error(e, "calculate_system_availability")
            return 0.0

    def get_performance_insights(self, performance_summary: dict[str, Any]) -> list[str]:
        """
        Extract key performance insights.

        Args:
            performance_summary: Performance analysis summary

        Returns:
            List of insight strings
        """
        try:
            insights = []

            # Trend insights
            if performance_summary.get('trends'):
                trend_count = len(performance_summary['trends'])
                if trend_count > 3:
                    insights.append(f"Multiple performance trends detected ({trend_count} metrics)")
                elif trend_count > 0:
                    insights.append("Performance trends identified in key metrics")

            # Bottleneck insights
            if performance_summary.get('bottlenecks'):
                bottleneck_count = len(performance_summary['bottlenecks'])
                if bottleneck_count > 2:
                    insights.append(f"Multiple bottlenecks detected ({bottleneck_count} components)")  # noqa: E501
                elif bottleneck_count > 0:
                    insights.append("Performance bottlenecks identified")

            # Anomaly insights
            if performance_summary.get('anomalies'):
                anomaly_count = len(performance_summary['anomalies'])
                if anomaly_count > 1:
                    insights.append(f"Performance anomalies detected ({anomaly_count} metrics)")

            # Baseline insights
            if performance_summary.get('baselines'):
                baseline_count = len(performance_summary['baselines'])
                insights.append(f"Performance baselines established for {baseline_count} metrics")

            return insights

        except Exception as e:
            self.error_handler.handle_error(e, "get_performance_insights")
            return []

    # ==========================================================================
    # FORMATTING UTILITIES
    # ==========================================================================

    def format_health_status(self, status: HealthStatus) -> str:
        """
        Format health status with emoji.

        Args:
            status: HealthStatus enum

        Returns:
            Formatted status string
        """
        status_emojis = {
            HealthStatus.EXCELLENT: "🟢 Excellent",
            HealthStatus.GOOD: "🟡 Good",
            HealthStatus.WARNING: "🟠 Warning",
            HealthStatus.CRITICAL: "🔴 Critical",
            HealthStatus.FAILING: "💀 Failing"
        }
        return status_emojis.get(status, f"❓ {status.value}")

    def format_severity(self, severity: ProblemSeverity) -> str:
        """
        Format problem severity with emoji.

        Args:
            severity: ProblemSeverity enum

        Returns:
            Formatted severity string
        """
        severity_emojis = {
            ProblemSeverity.CRITICAL: "🚨 Critical",
            ProblemSeverity.HIGH: "⚠️ High",
            ProblemSeverity.MEDIUM: "📋 Medium",
            ProblemSeverity.LOW: "ℹ️ Low",
            ProblemSeverity.INFO: "💬 Info"
        }
        return severity_emojis.get(severity, f"❓ {severity.value}")

    def format_duration(self, duration_seconds: float) -> str:
        """
        Format duration in human-readable format.

        Args:
            duration_seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        try:
            if duration_seconds < 60:
                return f"{duration_seconds:.1f}s"
            elif duration_seconds < 3600:
                return f"{duration_seconds/60:.1f}m"
            elif duration_seconds < 86400:
                return f"{duration_seconds/3600:.1f}h"
            else:
                return f"{duration_seconds/86400:.1f}d"

        except Exception:
            return "unknown"

    def format_bytes(self, bytes_value: int) -> str:
        """
        Format bytes in human-readable format.

        Args:
            bytes_value: Size in bytes

        Returns:
            Formatted size string
        """
        try:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.1f}{unit}"
                bytes_value /= 1024.0
            return f"{bytes_value:.1f}PB"

        except Exception:
            return "unknown"

    def format_percentage(self, value: float, decimal_places: int = 1) -> str:
        """
        Format value as percentage.

        Args:
            value: Value to format (0-1 or 0-100)
            decimal_places: Number of decimal places

        Returns:
            Formatted percentage string
        """
        try:
            # Assume 0-1 scale if value is <= 1, otherwise 0-100 scale
            if value <= 1.0:
                percentage = value * 100
            else:
                percentage = value

            return f"{percentage:.{decimal_places}f}%"

        except Exception:
            return "unknown"

    # ==========================================================================
    # UTILITY HELPERS
    # ==========================================================================

    def prioritize_issues(self, issues: list[DiagnosticIssue]) -> list[DiagnosticIssue]:
        """
        Prioritize issues by severity and impact.

        Args:
            issues: List of diagnostic issues

        Returns:
            Sorted list of issues by priority
        """
        try:
            # Define severity order
            severity_order = {
                ProblemSeverity.CRITICAL: 0,
                ProblemSeverity.HIGH: 1,
                ProblemSeverity.MEDIUM: 2,
                ProblemSeverity.LOW: 3,
                ProblemSeverity.INFO: 4
            }

            # Sort by severity first, then by impact score
            return sorted(
                issues,
                key=lambda x: (severity_order.get(x.severity, 999), -x.impact_score)
            )

        except Exception as e:
            self.error_handler.handle_error(e, "prioritize_issues")
            return issues

    def filter_issues_by_category(self,
                                 issues: list[DiagnosticIssue],
                                 categories: list[str]) -> list[DiagnosticIssue]:
        """
        Filter issues by categories.

        Args:
            issues: List of diagnostic issues
            categories: List of category names to include

        Returns:
            Filtered list of issues
        """
        try:
            return [
                issue for issue in issues
                if issue.category.value in categories
            ]

        except Exception as e:
            self.error_handler.handle_error(e, "filter_issues_by_category")
            return []

    def get_health_trend_indicator(self, current_score: float, previous_score: float) -> str:
        """
        Get health trend indicator.

        Args:
            current_score: Current health score
            previous_score: Previous health score

        Returns:
            Trend indicator string
        """
        try:
            if abs(current_score - previous_score) < 0.05:
                return "→ Stable"
            elif current_score > previous_score:
                return "↗ Improving"
            else:
                return "↘ Declining"

        except Exception:
            return "? Unknown"

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_diagnostic_utils() -> DiagnosticUtils:
    """
    Factory function to create diagnostic utilities.

    Returns:
        DiagnosticUtils instance
    """
    return DiagnosticUtils()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create utils
    utils = DiagnosticUtils()

    # Test formatting functions

    # Test trend indicator

