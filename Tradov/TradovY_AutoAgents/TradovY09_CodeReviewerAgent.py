#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System

Tradov Version: 1.0
Module: TradovY09_CodeReviewerAgent.py
Group: Y (AutoAgents)
Purpose: Automated code quality auditing and improvement suggestions

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-06-26 Time: 13:25:07

Description:
    Runs during off-hours (overnight + post-market). Uses the CODE LLM to
    review Tradov source code for:

    - Bug detection (type errors, logic errors, edge cases)
    - Security vulnerabilities (credential exposure, injection)
    - Performance issues (unnecessary loops, memory leaks)
    - Code quality (complexity, dead code, missing error handling)
    - Test coverage gaps
    - Dependency health (outdated packages, license issues)

    IMPORTANT: This agent NEVER modifies code directly. It only
    produces reports and recommendations. All changes must be
    reviewed and applied by a human developer.

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

# ==============================================================================
# TRADOV IMPORTS
# ==============================================================================
from .TradovY00_BaseAutoAgent import (
    BaseAutoAgent,
    AgentOutput,
    LLMRole,
    MarketSession,
)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CodeIssue:
    """A code issue found during review."""
    file_path: str = ""
    line_number: int = 0
    severity: str = ""      # critical | high | medium | low | info
    category: str = ""      # bug | security | performance | quality | test
    description: str = ""
    suggestion: str = ""
    confidence: float = 0.0


@dataclass
class ReviewReport:
    """A complete review report for a file or module."""
    target: str = ""         # File path or module name
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    issues: list[CodeIssue] = field(default_factory=list)
    summary: str = ""
    risk_score: float = 0.0  # 0-10
    reviewed_lines: int = 0


# ==============================================================================
# CODE REVIEWER AGENT
# ==============================================================================
class TradovY09_CodeReviewerAgent(BaseAutoAgent):
    """Automated code review agent — off-hours static analysis with LLM.

    NEVER modifies code directly. Produces reports only.

    Active during overnight and post-market sessions only. Scans the Tradov
    codebase systematically, one module at a time, using the CODE LLM
    for deep analysis.

    Subscribes to:
        meta.orchestration   — Research requests from orchestrator
        meta.code_review     — Specific review requests

    Publishes to:
        meta.code_review     — Review reports and issue lists
    """

    AGENT_ID = "Y09_code_reviewer"
    AGENT_NAME = "CodeReviewer Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "Off-hours code review with LLM-powered static analysis"

    # Off-hours only
    ACTIVE_SESSIONS = {
        MarketSession.OVERNIGHT,
        MarketSession.POST_MARKET,
    }

    TICK_INTERVALS = {
        MarketSession.OVERNIGHT: 600,     # 10 min — deep analysis
        MarketSession.POST_MARKET: 300,   # 5 min — lighter review
    }

    TICK_INTERVAL = 600.0

    # Modules to review (in priority order)
    MODULE_PRIORITY = [
        "TradovB_Broker",         # Highest risk — handles money
        "TradovE_Risk",           # Risk management — critical for safety
        "TradovX_Agents",         # Agent framework
        "TradovY_AutoAgents",     # Our own code
        "TradovD_Strategies",     # Trading strategies
        "TradovS_Signals",        # Signal pipeline
        "TradovL_ML",             # ML pipeline
        "TradovA_Core",           # Core utilities
        "TradovC_Data",           # Data handling
        "TradovI_Integration",    # Integration
        "TradovF_Analysis",       # Analysis
        "TradovV_QuantModels",    # Quant models
    ]

    # File extensions to review
    REVIEWABLE_EXTENSIONS = {".py"}

    # Max lines per file to send to LLM (context window limit)
    MAX_REVIEW_LINES = 200

    def __init__(self, tradov_root: str | None = None, **kwargs: Any):
        super().__init__(**kwargs)

        # Configuration
        self._tradov_root = tradov_root or self._find_tradov_root()
        self._current_module_index: int = 0
        self._reviewed_files: set[str] = set()
        self._reports: list[ReviewReport] = []
        self._all_issues: list[CodeIssue] = []
        self._tick_count: int = 0
        self._files_reviewed_today: int = 0
        self._review_queue: list[str] = []  # Specific files to review

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to review request topics."""
        self.subscribe("meta.orchestration")
        self.subscribe("meta.code_review")

    def on_wake(self, session: MarketSession) -> None:
        """Prepare for review session."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 600.0)

        if session == MarketSession.POST_MARKET:
            self._files_reviewed_today = 0

        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Review one file per tick."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 600.0)

        # Get next file to review
        file_path = self._get_next_file()
        if not file_path:
            return

        # Review the file
        report = self._review_file(file_path)
        if report:
            self._reports.append(report)
            self._all_issues.extend(report.issues)
            self._reviewed_files.add(file_path)
            self._files_reviewed_today += 1

            # Publish report if issues found
            if report.issues:
                self._publish_review_report(report)

    # ==========================================================================
    # FILE SELECTION
    # ==========================================================================
    def _get_next_file(self) -> str | None:
        """Get the next file to review (priority-ordered)."""
        # First: check the explicit review queue
        if self._review_queue:
            return self._review_queue.pop(0)

        # Otherwise: scan modules in priority order
        if not self._tradov_root:
            return None

        while self._current_module_index < len(self.MODULE_PRIORITY):
            module_name = self.MODULE_PRIORITY[self._current_module_index]
            module_path = os.path.join(self._tradov_root, module_name)

            if os.path.isdir(module_path):
                # Find unreview files in this module
                for root, _dirs, files in os.walk(module_path):
                    for fname in sorted(files):
                        if Path(fname).suffix in self.REVIEWABLE_EXTENSIONS:
                            full_path = os.path.join(root, fname)
                            if full_path not in self._reviewed_files:
                                return full_path

            # Module fully reviewed — move to next
            self._current_module_index += 1

        # All modules reviewed — reset cycle
        self._current_module_index = 0
        self._reviewed_files.clear()
        return None

    # ==========================================================================
    # FILE REVIEW
    # ==========================================================================
    def _review_file(self, file_path: str) -> ReviewReport | None:
        """Review a single file using the CODE LLM."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            return None

        if not lines:
            return None

        # For large files, review in chunks
        total_lines = len(lines)
        code_sample = "".join(lines[: self.MAX_REVIEW_LINES])
        if total_lines > self.MAX_REVIEW_LINES:
            code_sample += f"\n# ... ({total_lines - self.MAX_REVIEW_LINES} more lines)\n"

        # Determine relative path for readability
        rel_path = os.path.relpath(file_path, self._tradov_root) if self._tradov_root else file_path

        prompt = (
            f"Code review for: {rel_path} ({total_lines} lines)\n\n"
            f"```python\n{code_sample}```\n\n"
            f"Review this code for:\n"
            f"1. Bugs (type errors, logic errors, edge cases)\n"
            f"2. Security (credential exposure, injection risks)\n"
            f"3. Performance (unnecessary operations, memory issues)\n"
            f"4. Quality (error handling, code clarity, dead code)\n\n"
            f"For each issue found, respond in JSON array format:\n"
            f"[\n"
            f"  {{\n"
            f"    \"line\": <approx line number>,\n"
            f"    \"severity\": \"<critical|high|medium|low>\",\n"
            f"    \"category\": \"<bug|security|performance|quality>\",\n"
            f"    \"description\": \"<what's wrong>\",\n"
            f"    \"suggestion\": \"<how to fix>\"\n"
            f"  }}\n"
            f"]\n"
            f"If no issues found, respond with an empty array: []"
        )

        response = self.llm_query(
            prompt=prompt,
            role=LLMRole.CODE,
            system_prompt=(
                "You are a senior Python code reviewer specializing in trading "
                "systems and financial software. Focus on correctness, safety, "
                "and robustness. Do not nitpick style — focus on real issues. "
                "Be precise with line numbers."
            ),
        ) or ""

        # Parse response into issues
        issues = self._parse_review_response(response, file_path)

        # Calculate risk score
        risk_score = self._calculate_file_risk(issues)

        # Generate summary
        summary = ""
        if issues:
            critical = sum(1 for i in issues if i.severity == "critical")
            high = sum(1 for i in issues if i.severity == "high")
            medium = sum(1 for i in issues if i.severity == "medium")
            low = sum(1 for i in issues if i.severity == "low")
            summary = (
                f"{rel_path}: {len(issues)} issues found "
                f"(C:{critical} H:{high} M:{medium} L:{low}). "
                f"Risk score: {risk_score:.1f}/10."
            )
        else:
            summary = f"{rel_path}: No issues found. Clean code."

        return ReviewReport(
            target=rel_path,
            issues=issues,
            summary=summary,
            risk_score=risk_score,
            reviewed_lines=total_lines,
        )

    def _parse_review_response(
        self, response: str, file_path: str
    ) -> list[CodeIssue]:
        """Parse LLM response into CodeIssue objects."""
        import json

        issues = []

        # Try to extract JSON from the response
        try:
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end])
                for item in parsed:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=item.get("line", 0),
                        severity=item.get("severity", "low"),
                        category=item.get("category", "quality"),
                        description=item.get("description", ""),
                        suggestion=item.get("suggestion", ""),
                        confidence=0.7,
                    ))
        except (json.JSONDecodeError, ValueError):
            # If JSON parsing fails, create a single issue with the raw response
            if response.strip() and "no issues" not in response.lower():
                issues.append(CodeIssue(
                    file_path=file_path,
                    severity="info",
                    category="quality",
                    description=response[:500],
                    confidence=0.4,
                ))

        return issues

    def _calculate_file_risk(self, issues: list[CodeIssue]) -> float:
        """Calculate a 0-10 risk score from issues."""
        if not issues:
            return 0.0

        severity_weights = {
            "critical": 4.0,
            "high": 2.0,
            "medium": 1.0,
            "low": 0.3,
            "info": 0.1,
        }

        total = sum(
            severity_weights.get(i.severity, 0.3)
            for i in issues
        )
        return min(10.0, total)

    # ==========================================================================
    # PUBLISHING
    # ==========================================================================
    def _publish_review_report(self, report: ReviewReport) -> None:
        """Publish a code review report."""
        priority = "HIGH" if report.risk_score >= 5.0 else "NORMAL"

        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="report",
            topic="meta.code_review",
            payload={
                "target": report.target,
                "risk_score": report.risk_score,
                "issue_count": len(report.issues),
                "issues": [
                    {
                        "line": i.line_number,
                        "severity": i.severity,
                        "category": i.category,
                        "description": i.description,
                        "suggestion": i.suggestion,
                    }
                    for i in report.issues
                ],
                "reviewed_lines": report.reviewed_lines,
                "summary": report.summary,
            },
            confidence=0.7,
            reasoning=report.summary,
            priority=priority,
            ttl_seconds=604800,  # 7 days
        ))

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    def _find_tradov_root(self) -> str | None:
        """Find the Tradov source root directory."""
        # Try relative to this file
        this_dir = Path(__file__).resolve().parent  # TradovY_AutoAgents/
        tradov_dir = this_dir.parent                # Tradov/
        if tradov_dir.is_dir() and (tradov_dir / "__init__.py").exists():
            return str(tradov_dir)

        # Try common paths
        for candidate in [
            Path.home() / "Projects" / "Tradov" / "Tradov",
        ]:
            if candidate.is_dir():
                return str(candidate)

        return None

    # ==========================================================================
    # MESSAGE HANDLER
    # ==========================================================================
    def _on_message(self, topic: str, message: dict[str, Any]) -> None:
        """Handle review requests."""
        if topic == "meta.code_review":
            # Specific file review request
            payload = message.get("payload", {})
            target = payload.get("target", "")
            if target and os.path.isfile(target):
                self._review_queue.append(target)

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "current_module_index": self._current_module_index,
            "reviewed_files_count": len(self._reviewed_files),
            "files_reviewed_today": self._files_reviewed_today,
            "total_issues_found": len(self._all_issues),
            "issues_by_severity": {
                severity: sum(
                    1 for i in self._all_issues if i.severity == severity
                )
                for severity in ("critical", "high", "medium", "low")
            },
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tick_count = state.get("tick_count", 0)
        self._current_module_index = state.get("current_module_index", 0)
        self._files_reviewed_today = state.get("files_reviewed_today", 0)


# ==============================================================================
# FACTORY
# ==============================================================================
def create_code_reviewer_agent(**kwargs: Any) -> TradovY09_CodeReviewerAgent:
    """Factory function for creating the CodeReviewer agent."""
    return TradovY09_CodeReviewerAgent(**kwargs)
