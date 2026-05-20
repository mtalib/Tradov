#!/usr/bin/env python3
"""SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG05_TradingDashboard.py
Purpose: Complete Trading Dashboard with Real Data Integration & Enhanced Features
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-18 Time: 02:00:00

Data Sources:
    - Tradier API for account data and order execution (SpyderB40_TradierClient)
    - Tradier API for real-time & historical market data (SpyderB40_TradierClient)
    - SpyderC01_DataFeed for provider-agnostic data abstraction

Module Description:
    Enhanced trading dashboard with TWO TRADING MODES:
    - PAPER:    Live data with simulated fills via SpyderBox + SpyderR02_PaperEngine
    - LIVE:     Real order execution via Tradier production API + SpyderR04_LiveEngine

    Includes real-time market data integration, comprehensive signal monitoring,
    and professional dark theme interface. Supports automatic detection and
    switching between real and simulation data.

FEATURES:
    • Two trading modes (PAPER / LIVE) with toolbar selector
    • LIVE mode requires explicit user confirmation before execution
    • Automatic real data detection and seamless switching
    • Simulation fallback with monitoring for real data availability
    • Professional signal monitor with 12 indicators including HMM/SKEW
    • Market hours awareness and connection health monitoring
    • Custom metrics integration (GEX/DEX/OGL/DIX/SWAN)
    • Enhanced P&L tracking and risk monitoring
    • Professional dark theme with traffic light indicators
    • 30-second heartbeat connection monitoring with visual indicator

DATA SOURCES:
    • Tradier API for account data, quotes, and order execution
    • Tradier for real-time streaming and historical market data
    • Auto-detection with fallback to simulation mode
    • Status indicators show real vs simulation data source

CONNECTION MONITORING:
    • 30-second heartbeat timer for connection health checks
    • Visual heartbeat indicator with 3-state system
    • Fixed-width status containers prevent UI jumping
    • Real-time connection status updates
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import math
import os
import sys
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time
from datetime import tzinfo
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytz
from PySide6.QtCore import (
    QModelIndex,
    QMetaObject,
    QMutex,  # noqa: F401
    QMutexLocker,  # noqa: F401
    QObject,
    QRect,  # noqa: F401
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,  # noqa: F401
    QColor,
    QFont,  # noqa: F401
    QPainter,  # noqa: F401
    QPen,  # noqa: F401
    QTextCursor,
)

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,  # noqa: F401
    QGridLayout,  # noqa: F401
    QGroupBox,
    QHBoxLayout,
    QHeaderView,  # noqa: F401
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,  # noqa: F401
    QSizePolicy,  # noqa: F401
    QSplitter,
    QTableWidget,
    QTableWidgetItem,  # noqa: F401
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ==============================================================================
# BROKER/DATA IMPORTS (Tradier)
# ==============================================================================
# Tradier API for execution and market data

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging  # noqa: E402

logger = logging.getLogger(__name__)
from Spyder.SpyderG_GUI.SpyderG17_PaperPositionResolver import (  # noqa: E402
    load_paper_open_positions,
    parse_occ_option_contract,
    restore_paper_spreads_from_positions,
)
from Spyder.SpyderG_GUI.SpyderG24_PnlMetricsResolver import (  # noqa: E402
    build_today_trade_analytics,
    normalize_today_worker_metrics,
    overlay_period_pnl_summary,
)
from Spyder.SpyderG_GUI.SpyderG25_DashboardSessionAdapter import (  # noqa: E402
    DashboardSessionAdapter,
)
from Spyder.SpyderG_GUI.SpyderG26_RecentTradeFormatter import (  # noqa: E402
    build_recent_trade_banner_text,
    build_recent_trade_display,
)
from Spyder.SpyderG_GUI.SpyderG27_RecentTradesDialog import (  # noqa: E402
    RecentTradesDialog,
)
from Spyder.SpyderG_GUI.SpyderG28_AccountPanelPresenter import (  # noqa: E402
    build_account_pnl_presentation,
    build_account_snapshot_presentation,
    capture_account_snapshot_from_texts,
    format_account_money_text,
    parse_money_text,
)
from Spyder.SpyderG_GUI.SpyderG33_AccountSnapshotSelector import (  # noqa: E402
    get_restorable_account_snapshot,
)
from Spyder.SpyderG_GUI.SpyderG34_AccountCapitalMath import (  # noqa: E402
    calculate_buying_power_usage,
    derive_realized_pnl_delta_from_equity,
    resolve_capital_baseline,
)
from Spyder.SpyderG_GUI.SpyderG35_PaperSummaryPresenter import (  # noqa: E402
    build_buying_power_badge_presentation,
    build_portfolio_summary_rows,
    build_realized_today_badge_presentation,
    build_spreads_summary_badge_presentation,
)
from Spyder.SpyderG_GUI.SpyderG36_StripMetricsPresenter import (  # noqa: E402
    build_atm_iv_label_presentation,
    build_iv_rank_label_presentation,
    build_portfolio_greek_strip_presentations,
)
from Spyder.SpyderG_GUI.SpyderG37_GreekBarPresenter import (  # noqa: E402
    build_greek_bar_updates,
)
from Spyder.SpyderG_GUI.SpyderG38_LegacySpreadsTablePresenter import (  # noqa: E402
    build_legacy_spreads_table_rows,
)
from Spyder.SpyderG_GUI.SpyderG39_PaperPositionsTreePresenter import (  # noqa: E402
    build_paper_spread_tree_presentation,
    build_restored_position_group_presentations,
    coerce_float,
    coerce_timestamp,
    format_days_to_expiration,
    format_expiration_short,
    format_signed_dollars,
)
from Spyder.SpyderG_GUI.SpyderG40_ToolbarIndexPresenter import (  # noqa: E402
    build_toolbar_index_presentations,
)
from Spyder.SpyderG_GUI.SpyderG41_RegimeLiquidityPresenter import (  # noqa: E402
    build_liquidity_diagnostics_panel_presentation,
    summarize_liquidity_diagnostics,
)
from Spyder.SpyderG_GUI.SpyderG52_RegimePillBarPresenter import (  # noqa: E402
    build_regime_pill_bar_presentation,
)
from Spyder.SpyderG_GUI.SpyderG53_GoNoGoPresenter import (  # noqa: E402
    build_go_no_go_presentation,
)
from Spyder.SpyderG_GUI.SpyderG54_ReadinessResultPresenter import (  # noqa: E402
    build_readiness_result_log_presentation,
)
from Spyder.SpyderG_GUI.SpyderG55_ReadinessReportPresenter import (  # noqa: E402
    build_readiness_bypass_audit_entry,
    build_readiness_bypass_audit_filename,
    build_readiness_report_filename,
)
from Spyder.SpyderG_GUI.SpyderG112_CloseStrategyConfirmHelper import (  # noqa: E402
    build_close_strategy_confirm_plan,
)
from Spyder.SpyderG_GUI.SpyderG113_CloseStrategySuccessHelper import (  # noqa: E402
    build_close_strategy_success_plan,
)
from Spyder.SpyderG_GUI.SpyderG114_CloseStrategyFailureHelper import (  # noqa: E402
    build_close_strategy_failure_plan,
)
from Spyder.SpyderG_GUI.SpyderG115_EventSubscriptionPlanHelper import (  # noqa: E402
    build_event_subscription_plan,
)
from Spyder.SpyderG_GUI.SpyderG116_EventClockRiskEventHelper import (  # noqa: E402
    build_event_clock_risk_event_plan,
)
from Spyder.SpyderG_GUI.SpyderG117_EventClockOverrideHelper import (  # noqa: E402
    build_event_clock_override_plan,
)
from Spyder.SpyderG_GUI.SpyderG118_PaperRiskLimitMappingHelper import (  # noqa: E402
    build_paper_risk_limit_mapping_plan,
)
from Spyder.SpyderG_GUI.SpyderG119_RingLogBufferHelper import (  # noqa: E402
    build_log_widget_refresh_plan,
    build_ring_log_append_plan,
)
from Spyder.SpyderG_GUI.SpyderG120_SystemLogSuppressionHelper import (  # noqa: E402
    should_suppress_after_hours_system_log_text,
    should_suppress_opening_warmup_system_log_text,
)
from Spyder.SpyderG_GUI.SpyderG121_AutomationLogRoutingHelper import (  # noqa: E402
    build_automation_log_routing_plan,
)
from Spyder.SpyderG_GUI.SpyderG122_SystemLogVerbosityHelper import (  # noqa: E402
    build_system_log_verbosity_plan,
)
from Spyder.SpyderG_GUI.SpyderG123_VetoToggleButtonHelper import (  # noqa: E402
    build_veto_toggle_button_presentation,
)
from Spyder.SpyderG_GUI.SpyderG124_VetoToggleResultHelper import (  # noqa: E402
    build_veto_toggle_result_plan,
)
from Spyder.SpyderG_GUI.SpyderG125_VetoControlsStateHelper import (  # noqa: E402
    resolve_veto_controls_enabled_state,
)
from Spyder.SpyderG_GUI.SpyderG126_VetoControlsPersistPlanHelper import (  # noqa: E402
    build_veto_controls_persist_plan,
)
from Spyder.SpyderG_GUI.SpyderG127_StartupReadinessStateEnvelopeHelper import (  # noqa: E402
    build_startup_readiness_base_state,
    build_startup_readiness_success_state_payload,
)
from Spyder.SpyderG_GUI.SpyderG128_DashboardSnapshotPayloadHelper import (  # noqa: E402
    build_dashboard_snapshot_payload,
)
from Spyder.SpyderG_GUI.SpyderG129_MetricsPayloadMergeHelper import (  # noqa: E402
    merge_metrics_payload,
)
from Spyder.SpyderG_GUI.SpyderG130_CachedMetricsFallbackHelper import (  # noqa: E402
    build_cached_metrics_fallback_payload_from_sources,
)
from Spyder.SpyderG_GUI.SpyderG131_CachedMarketSnapshotMergeHelper import (  # noqa: E402
    build_cached_market_display_snapshot_result,
)
from Spyder.SpyderG_GUI.SpyderG132_CachedChartCandlesHelper import (  # noqa: E402
    build_cached_chart_candles_result,
)
from Spyder.SpyderG_GUI.SpyderG133_CachedChartBarSeriesHelper import (  # noqa: E402
    CachedChartBarSeries,
    build_cached_chart_bar_series,
)
from Spyder.SpyderG_GUI.SpyderG56_ReadinessStartGatePresenter import (  # noqa: E402
    build_conditional_readiness_reason_dialog_presentation,
    build_start_trading_readiness_gate_presentation,
)
from Spyder.SpyderG_GUI.SpyderG57_StartTradingPrecheckPresenter import (  # noqa: E402
    build_start_trading_precheck_presentation,
)
from Spyder.SpyderG_GUI.SpyderG58_StartTradingLiveGuardPresenter import (  # noqa: E402
    build_start_trading_live_guard_presentation,
)
from Spyder.SpyderG_GUI.SpyderG59_StartTradingFailurePresenter import (  # noqa: E402
    build_start_trading_failure_presentation,
)
from Spyder.SpyderG_GUI.SpyderG60_ReadinessStartBlockPresenter import (  # noqa: E402
    build_readiness_start_block_presentation,
)
from Spyder.SpyderG_GUI.SpyderG61_ReadinessAsyncPresenter import (  # noqa: E402
    build_readiness_async_already_running_log_message,
    build_readiness_async_failure_presentation,
    build_readiness_async_start_log_message,
)
from Spyder.SpyderG_GUI.SpyderG62_ReadinessWorkerCleanupHelper import (  # noqa: E402
    build_readiness_worker_cleanup_plan,
)
from Spyder.SpyderG_GUI.SpyderG63_ReadinessSnapshotHelper import (  # noqa: E402
    build_preopen_check_snapshot_payload,
    normalize_readiness_data_status_label,
)
from Spyder.SpyderG_GUI.SpyderG64_ReadinessConnectionRefreshHelper import (  # noqa: E402
    build_readiness_connection_refresh_plan,
)
from Spyder.SpyderG_GUI.SpyderG65_ReadinessEventClockSnapshotHelper import (  # noqa: E402
    build_readiness_event_clock_snapshot,
)
from Spyder.SpyderG_GUI.SpyderG66_ReadinessStartupStateHelper import (  # noqa: E402
    build_readiness_startup_state_plan,
)
from Spyder.SpyderG_GUI.SpyderG67_ReadinessDecisionHelper import (  # noqa: E402
    build_trading_readiness_evaluation,
)
from Spyder.SpyderG_GUI.SpyderG68_ReadinessBypassAuditHelper import (  # noqa: E402
    build_readiness_bypass_audit_plan,
)
from Spyder.SpyderG_GUI.SpyderG69_LiveDataStatusHelper import (  # noqa: E402
    is_live_equivalent_data_status,
)
from Spyder.SpyderG_GUI.SpyderG70_ReadinessCacheDecisionHelper import (  # noqa: E402
    build_readiness_cache_decision_plan,
)
from Spyder.SpyderG_GUI.SpyderG71_ReadinessGateDecisionHelper import (  # noqa: E402
    build_start_trading_readiness_gate_decision_plan,
)
from Spyder.SpyderG_GUI.SpyderG72_PaperSessionQueueHelper import (  # noqa: E402
    build_paper_session_queue_plan,
)
from Spyder.SpyderG_GUI.SpyderG73_PaperSessionFinalizeHelper import (  # noqa: E402
    build_paper_session_finalize_outcome_plan,
)
from Spyder.SpyderG_GUI.SpyderG74_SessionSupervisorStartHelper import (  # noqa: E402
    build_session_supervisor_start_plan,
)
from Spyder.SpyderG_GUI.SpyderG75_SessionSupervisorStartAttemptHelper import (  # noqa: E402
    build_session_supervisor_start_attempt_plan,
)
from Spyder.SpyderG_GUI.SpyderG76_SessionSupervisorAdoptionHelper import (  # noqa: E402
    build_session_supervisor_adoption_plan,
)
from Spyder.SpyderG_GUI.SpyderG77_LoadingTransitionCompletionHelper import (  # noqa: E402
    build_loading_transition_completion_plan,
)
from Spyder.SpyderG_GUI.SpyderG78_LoadingTransitionBeginHelper import (  # noqa: E402
    build_loading_transition_begin_plan,
)
from Spyder.SpyderG_GUI.SpyderG79_StartButtonReadyStateHelper import (  # noqa: E402
    build_start_button_ready_state_plan,
)
from Spyder.SpyderG_GUI.SpyderG80_StartButtonActiveStateHelper import (  # noqa: E402
    build_start_button_active_state_plan,
)
from Spyder.SpyderG_GUI.SpyderG81_MarketWorkerSlotInvokeHelper import (  # noqa: E402
    build_market_worker_slot_invoke_plan,
)
from Spyder.SpyderG_GUI.SpyderG82_QThreadShutdownHelper import (  # noqa: E402
    build_qthread_shutdown_plan,
)
from Spyder.SpyderG_GUI.SpyderG83_MetricsOrchestratorShutdownHelper import (  # noqa: E402
    build_metrics_orchestrator_shutdown_plan,
)
from Spyder.SpyderG_GUI.SpyderG84_MarketWorkerSignalEmitHelper import (  # noqa: E402
    build_market_worker_signal_emit_plan,
)
from Spyder.SpyderG_GUI.SpyderG85_MarketWorkerSignalDisconnectHelper import (  # noqa: E402
    build_market_worker_signal_disconnect_plan,
)
from Spyder.SpyderG_GUI.SpyderG86_ShutdownTimerStopHelper import (  # noqa: E402
    build_shutdown_timer_stop_plan,
)
from Spyder.SpyderG_GUI.SpyderG87_PostWorkerShutdownTimerHelper import (  # noqa: E402
    build_post_worker_shutdown_timer_plan,
)
from Spyder.SpyderG_GUI.SpyderG88_MarketWorkerShutdownHelper import (  # noqa: E402
    build_market_worker_shutdown_plan,
)
from Spyder.SpyderG_GUI.SpyderG89_ShutdownMessageHelper import (  # noqa: E402
    build_dashboard_shutdown_message_plan,
)
from Spyder.SpyderG_GUI.SpyderG90_CloseEventShutdownSequenceHelper import (  # noqa: E402
    build_close_event_shutdown_sequence_plan,
)
from Spyder.SpyderG_GUI.SpyderG91_StartupReadinessLogHelper import (  # noqa: E402
    build_startup_readiness_log_plan,
)
from Spyder.SpyderG_GUI.SpyderG92_StartupReadinessBannerHelper import (  # noqa: E402
    build_startup_readiness_banner_plan,
)
from Spyder.SpyderG_GUI.SpyderG93_StartupReadinessStateHelper import (  # noqa: E402
    build_startup_readiness_state_plan,
)
from Spyder.SpyderG_GUI.SpyderG94_StartupReadinessRefreshHelper import (  # noqa: E402
    build_startup_readiness_refresh_plan,
)
from Spyder.SpyderG_GUI.SpyderG95_DJIProxyMultiplierHelper import (  # noqa: E402
    normalize_dji_proxy_multiplier,
)
from Spyder.SpyderG_GUI.SpyderG96_RiskAlertDispatchHelper import (  # noqa: E402
    build_risk_alert_dispatch_plan,
)
from Spyder.SpyderG_GUI.SpyderG97_PendingOrdersGateHelper import (  # noqa: E402
    build_pending_orders_gate_outcome,
    build_pending_orders_gate_prompt,
)
from Spyder.SpyderG_GUI.SpyderG98_ExecutionTelemetryEventHelper import (  # noqa: E402
    extract_execution_telemetry_sample,
)
from Spyder.SpyderG_GUI.SpyderG100_PositionUpdatedEventHelper import (  # noqa: E402
    extract_position_update_symbol,
)
from Spyder.SpyderG_GUI.SpyderG101_RecentDecisionFlowFetchHelper import (  # noqa: E402
    build_recent_decision_flow_fetch_plan,
)
from Spyder.SpyderG_GUI.SpyderG102_MetricsOrchestratorStartHelper import (  # noqa: E402
    build_metrics_orchestrator_start_plan,
)
from Spyder.SpyderG_GUI.SpyderG103_LiveToPaperSwitchHelper import (  # noqa: E402
    build_live_to_paper_switch_plan,
)
from Spyder.SpyderG_GUI.SpyderG104_MetricsSnapshotProbeHelper import (  # noqa: E402
    inspect_metrics_orchestrator_snapshot,
)
from Spyder.SpyderG_GUI.SpyderG105_PaperToLiveSwitchHelper import (  # noqa: E402
    build_paper_to_live_switch_plan,
)
from Spyder.SpyderG_GUI.SpyderG106_CustomMetricWidgetUpdateHelper import (  # noqa: E402
    build_custom_metric_widget_update_plan,
)
from Spyder.SpyderG_GUI.SpyderG107_CustomMetricSignalPanelSyncHelper import (  # noqa: E402
    build_custom_metric_signal_panel_sync_plan,
)
from Spyder.SpyderG_GUI.SpyderG108_CustomMetricBreadthDialogSyncHelper import (  # noqa: E402
    build_custom_metric_breadth_dialog_payload,
)
from Spyder.SpyderG_GUI.SpyderG109_RegimePillStateHelper import (  # noqa: E402
    build_regime_pill_state_plan,
)
from Spyder.SpyderG_GUI.SpyderG110_RegimePillStatusHelper import (  # noqa: E402
    build_regime_pill_status_plan,
)
from Spyder.SpyderG_GUI.SpyderG111_RegimeDispatchAnnouncementHelper import (  # noqa: E402
    build_regime_dispatch_announcement_plan,
)
from Spyder.SpyderG_GUI.SpyderG42_PCADetailPresenter import (  # noqa: E402
    build_metric_sparkline,
    build_pca_iv_details_html,
    build_pca_iv_operator_takeaway,
    build_pca_proxy_details_html,
    build_pca_proxy_operator_takeaway,
    coerce_metric_float,
    format_metric_dialog_value,
)
from Spyder.SpyderG_GUI.SpyderG43_CustomMetricDialogPresenter import (  # noqa: E402
    build_pmr_details_html,
    build_psr_details_html,
    build_wrs_details_html,
)
from Spyder.SpyderG_GUI.SpyderG44_RecentDecisionFlowPresenter import (  # noqa: E402
    build_recent_decision_flow_panel_presentation,
    format_recent_decision_events,
)
from Spyder.SpyderG_GUI.SpyderG45_ExecutionHealthPresenter import (  # noqa: E402
    build_execution_health_presentation,
)
from Spyder.SpyderG_GUI.SpyderG46_ReadinessStatusPresenter import (  # noqa: E402
    build_readiness_status_presentation,
)
from Spyder.SpyderG_GUI.SpyderG47_EventClockDisplayPresenter import (  # noqa: E402
    build_event_clock_display_presentation,
)
from Spyder.SpyderG_GUI.SpyderG48_TradingArmingPresenter import (  # noqa: E402
    build_trading_arming_presentation,
)
from Spyder.SpyderG_GUI.SpyderG49_TradingWindowBadgePresenter import (  # noqa: E402
    build_trading_window_badge_presentation,
)
from Spyder.SpyderG_GUI.SpyderG50_EntryBlockCompactPresenter import (  # noqa: E402
    build_entry_block_alert_presentation,
    build_entry_block_compact_presentation,
)
from Spyder.SpyderG_GUI.SpyderG51_ModeTitlePresenter import (  # noqa: E402
    build_orders_title_presentation,
    build_pnl_title_presentation,
)

_AUTONOMOUS_EVENT_TYPE_ALLOWLIST: set[str] = {
    "AGENT_DECISION",
    "AGENT_ACTION_EXECUTED",
    "AGENT_VETO",
    "AGENT_ESCALATION",
    "AGENT_HEALTH_DEGRADED",
    "AGENT_OBSERVATION",
}


def _parse_chart_bar_timestamp(raw_timestamp: str) -> datetime:
    """Parse cached chart timestamps without importing pandas at module load."""
    normalized = str(raw_timestamp).strip()

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue

        return datetime.fromisoformat(normalized)


class _ReadinessCheckWorker(QObject):
    """Background worker for trading readiness evaluation."""

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, snapshot: dict[str, object], evaluator) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._evaluator = evaluator

    @Slot()
    def run(self) -> None:
        try:
            result = self._evaluator(self._snapshot)
            if not isinstance(result, dict):
                raise ValueError("Trading readiness evaluator returned non-dict result")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import (  # noqa: E402
    COLORS,
    ConnectionInfo,
    GreekBar,  # noqa: F401
    GreekRisk,
    MarketData,  # noqa: F401
    MarketSymbolWidget,  # noqa: F401
    SignalMonitorPanel,  # noqa: F401
    TradingMode,
    TrafficLightButton,  # noqa: F401
    apply_tooltip_theme,
)
from Spyder.SpyderG_GUI.SpyderG20_DashboardBuilder import (  # noqa: E402
    build_center_panel,
    build_left_panel,
    build_right_panel,
    build_toolbar,
    create_chart_widget,
    create_pnl_table as build_pnl_table,
    create_positions_table as build_positions_table,
    create_unified_prometheus_metrics as build_unified_prometheus_metrics,
)
from Spyder.SpyderG_GUI.SpyderG21_DashboardSignalHandlers import (  # noqa: E402
    handle_connection_status_changed,
    handle_heartbeat_received,
    handle_heartbeat_status_changed,
    handle_market_data_status_changed,
    handle_market_data_updated,
    handle_market_error,
)

# Tradier client for API connectivity checks
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        OptionLeg,
        OrderDuration,
        OrderSide,
        TradierAPIError,
        TradierClient,
        TradingEnvironment,
        build_option_symbol,
        create_tradier_client_from_env,
    )
    TRADIER_AVAILABLE = True
except ImportError:
    TradierClient = None  # type: ignore
    TradierAPIError = Exception  # type: ignore
    OptionLeg = None  # type: ignore
    OrderSide = None  # type: ignore
    OrderDuration = None  # type: ignore
    build_option_symbol = None  # type: ignore
    TradingEnvironment = None  # type: ignore
    create_tradier_client_from_env = None  # type: ignore
    TRADIER_AVAILABLE = False

# Import Risk Parameters Dialog
try:
    from Spyder.SpyderG_GUI.SpyderG09_RiskParametersDialog import (
        RiskParametersDialog,
        show_risk_parameters_dialog,
    )

    risk_dialog_available = True
    logger.info("✅ Risk Parameters Dialog module available")
except ImportError:
    RiskParametersDialog = None  # type: ignore
    show_risk_parameters_dialog = None  # type: ignore
    risk_dialog_available = False
    logger.info("⚠️ Risk Parameters Dialog not available")

# Try to import Prometheus metrics display module if available
try:
    from Spyder.SpyderG_GUI.SpyderG07_PrometheusMetricsDisplay import (
        get_client_status,
        get_system_metrics,
    )

    prometheus_available = True
    logger.info("✅ Prometheus metrics collector available")
except ImportError:
    get_client_status = None  # type: ignore
    get_system_metrics = None  # type: ignore
    prometheus_available = False
    logger.info("⚠️ Prometheus metrics collector not available - using simulation")

# ==============================================================================
# CIRCUIT BREAKER MONITOR
# ==============================================================================
try:
    from Spyder.SpyderG_GUI.SpyderG16_CircuitBreakerMonitor import create_circuit_breaker_monitor

    circuit_breaker_monitor_available = True
    logger.info("✅ Circuit Breaker Monitor available")
except ImportError:
    create_circuit_breaker_monitor = None  # type: ignore
    circuit_breaker_monitor_available = False
    logger.info("⚠️ Circuit Breaker Monitor not available")

# Circuit breaker singletons — reset from heartbeat when API confirmed healthy
try:
    from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import (
        tradier_breaker as _tradier_breaker,
    )
    _circuit_breakers_available = True
except ImportError:
    _tradier_breaker = None  # type: ignore
    _circuit_breakers_available = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


LIVE_DATA_LOADING_START_TIME = dt_time(9, 25)
MARKET_OPEN_TIME = dt_time(9, 30)
OPENING_DATA_WARMUP_END_TIME = dt_time(9, 33)
MARKET_CLOSE_TIME = dt_time(16, 0)
TRADIER_CONNECT_TIME = dt_time(9, 20)
TRADIER_DISCONNECT_TIME = dt_time(16, 30)


@lru_cache(maxsize=1)
def _get_eastern_timezone() -> tzinfo:
    """Resolve the ET timezone once and reuse it across startup paths."""
    return pytz.timezone("US/Eastern")


def is_tradier_window(now_et: datetime | None = None) -> bool:
    """Return True during the dashboard's Tradier live-data window."""
    current_et = now_et or datetime.now(_get_eastern_timezone())
    return TRADIER_CONNECT_TIME <= current_et.time() <= TRADIER_DISCONNECT_TIME


def is_market_hours(now_et: datetime | None = None) -> bool:
    """Return True only during regular trading hours (9:30 AM – 4:00 PM ET), Mon–Fri."""
    current_et = now_et or datetime.now(_get_eastern_timezone())
    if current_et.weekday() >= 5:
        return False
    t = current_et.time()
    return MARKET_OPEN_TIME <= t <= MARKET_CLOSE_TIME


def _is_preconnect_idle_window(now_et: datetime | None = None) -> bool:
    """Return True before the 09:25 ET live-data loading window opens."""
    current_et = now_et or datetime.now(_get_eastern_timezone())
    if current_et.weekday() >= 5:
        return False
    return current_et.time() < LIVE_DATA_LOADING_START_TIME


def _next_weekday_time(target_time: dt_time, now_et: datetime | None = None) -> datetime:
    """Return the next weekday occurrence of *target_time* in Eastern Time."""
    current_et = now_et or datetime.now(_get_eastern_timezone())
    candidate = current_et.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0,
    )
    if current_et.weekday() < 5 and current_et.time() <= target_time:
        return candidate

    next_day = current_et + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0,
    )


# Market data worker, heartbeat constants, quote-freshness helpers, and
# check_api_connection now live in SpyderG18_MarketDataWorker (audit §1/§14/§23).
# G05 re-imports them here so existing references continue to resolve.
from Spyder.SpyderG_GUI.SpyderG18_MarketDataWorker import (  # noqa: E402
    HEARTBEAT_INTERVAL,  # noqa: F401
    HEARTBEAT_LOG_INTERVAL,  # noqa: F401
    HEARTBEAT_WARNING_TIME,  # noqa: F401
    REALTIME_QUOTE_MAX_AGE_SECONDS,
    REALTIME_SENTINEL_SYMBOLS,  # noqa: F401
    ThreadSafeMarketDataWorker,
    _coerce_epoch_ms,  # noqa: F401
    _datetime_from_epoch_ms,  # noqa: F401
    _freshest_live_data_timestamp,  # noqa: F401
    _freshest_quote_timestamp_ms,  # noqa: F401
    check_api_connection,
)
# Chart indicator computation extracted per audit §3.
from Spyder.SpyderG_GUI.SpyderG19_ChartIndicators import (  # noqa: E402
    ChartIndicators,  # noqa: F401
    PivotLevels,  # noqa: F401
    compute_chart_indicators,
)
from Spyder.SpyderU_Utilities.SpyderU49_SymbolCatalog import (  # noqa: E402
    get_symbol_catalog,
    get_market_overview_symbols,
)


def _market_data_datetime_from_epoch_ms(value) -> datetime | None:
    """Convert market-data epoch milliseconds to an ET-aware datetime."""
    epoch_ms = _coerce_epoch_ms(value)
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, UTC).astimezone(_get_eastern_timezone())


def _freshest_market_data_timestamp(live_data: dict) -> datetime | None:
    """Return the freshest ET-aware timestamp present in a live-data payload."""
    fetch_time = _market_data_datetime_from_epoch_ms(live_data.get("_fetch_time_ms"))
    if fetch_time is not None:
        return fetch_time

    for symbol in REALTIME_SENTINEL_SYMBOLS:
        quote = live_data.get(symbol)
        if isinstance(quote, dict):
            quote_time = _market_data_datetime_from_epoch_ms(quote.get("timestamp_ms"))
            if quote_time is not None:
                return quote_time

    freshest: datetime | None = None
    for quote in live_data.values():
        if not isinstance(quote, dict):
            continue
        quote_time = _market_data_datetime_from_epoch_ms(quote.get("timestamp_ms"))
        if quote_time is not None and (freshest is None or quote_time > freshest):
            freshest = quote_time
    return freshest

# Canonical market-overview symbol source (Phase 2 symbol-governance cleanup).
MARKET_SYMBOLS: dict[str, list[str]] = get_market_overview_symbols()
STARTUP_READY_REQUIRED_SYMBOLS: frozenset[str] = frozenset(
    set(REALTIME_SENTINEL_SYMBOLS)
    | {
        definition.symbol
        for definition in get_symbol_catalog()
        if definition.visible
        and not definition.optional
        and definition.fetch_requirement in {"quote", "proxy"}
    }
)
START_BUTTON_LOADING_DELAY_MS = 0

# ==============================================================================
# PAPER TRADING WORKER (runs off the GUI thread)
# ==============================================================================
from Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import (  # noqa: E402
    PaperTradingQtWorker as _PaperTradingWorker,
)
from Spyder.SpyderD_Strategies.SpyderD00_StrategyConstants import StrategyLifecycleState  # noqa: E402


# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with fixed API connection detection and heartbeat monitoring"""

    manual_close_spread_requested = Signal(str)
    optional_metrics_refreshed = Signal(dict)

    # ------------------------------------------------------------------
    # S07 metric routing (audit §21 — display-unit adaptation layer)
    # Maps S07 metric keys → (dashboard widget key, raw→widget scale).
    # Scales live here because S07 emits in domain units (raw dollars for
    # GEX/DEX) and the dashboard widgets expect pre-scaled values that they
    # then format to "B"/"M" labels. When S07's contract is normalised so it
    # emits in widget-ready units, this table collapses to pure key mapping.
    # ------------------------------------------------------------------
    _S07_METRIC_ROUTING: dict[str, tuple[str, float]] = {
        "GEX":      ("GEX",   1e9),
        "DEX":      ("DEX",   1e6),
        "OGL":      ("OGL",   1.0),
        "DIX":      ("DIX",   1.0),
        "PCA-PROXY": ("PCA-PROXY", 1.0),
        "PCA-IV":   ("PCA-IV", 1.0),
        "WRS":      ("WRS",   1.0),
        "PSR":      ("PSR",   1.0),
        "SWAN":     ("SWAN",  1.0),
        "TICK":      ("$TICK", 1.0),
        "ADD":       ("$ADD",  1.0),
        "TRIN":      ("$TRIN", 1.0),
        "NYMO":      ("NYMO",  1.0),
        "YIELD_10Y": ("TNX",   1.0),
        "IVR":       ("IVR",   1.0),
        "ATM_IV":    ("ATM_IV",1.0),
        "VRP":       ("VRP",   1.0),
        # 0-DTE abort-gate additions (2026-04)
        "VOLD":      ("$VOLD", 1.0),
        "XLK":       ("XLK",   1.0),
        "XLF":       ("XLF",   1.0),
        "RVOL":      ("RVOL",  1.0),
    }

    # ------------------------------------------------------------------
    # Connection-state accessors (audit §16 — single source of truth)
    # Both flags are backed by self.connection_info to eliminate the
    # parallel scalar attributes that previously drifted out of sync.
    # ------------------------------------------------------------------
    @property
    def api_connected(self) -> bool:
        return self.connection_info.api_connected

    @api_connected.setter
    def api_connected(self, value: bool) -> None:
        self.connection_info.api_connected = bool(value)

    @property
    def mkt_data_connected(self) -> bool:
        return self.connection_info.mkt_data_connected

    @mkt_data_connected.setter
    def mkt_data_connected(self, value: bool) -> None:
        self.connection_info.mkt_data_connected = bool(value)

    def __init__(self):
        super().__init__()

        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)

        # Suppress verbose INFO-level messages from WRS and PSR signal modules.
        # These emit multiple per-bar diagnostic lines (basket fetches, bar
        # counts, etc.) that add noise without actionable information in the
        # dashboard log.  WARNING and above (actual errors) still pass through.
        logging.getLogger("SpyderS_Signals.SpyderS12_WRSSignal").setLevel(logging.WARNING)
        logging.getLogger("SpyderS_Signals.SpyderS13_PSRSignal").setLevel(logging.WARNING)

        # Connection info - FIXED: Start disconnected
        self.connection_info = ConnectionInfo(
            api_connected=False,
            connection_mode="DISCONNECTED",
            market_data_status="NONE",
            trading_active=False,
            simulation_mode=False,
        )
        self.market_worker = None
        self.market_thread = None
        self._market_data_initialized = False  # True after first data_updated signal
        self._queued_trading_start = False
        self._start_button_loading_generation = 0
        self._start_button_loading_timer_active = False
        self._paper_session_start_pending = False
        self._paper_session_start_show_failure_dialog = False
        self._paper_launch_loading_deadline_monotonic = None

        # Paper trading worker (created lazily by _start_paper_trading)
        self._paper_worker = None
        self._paper_thread = None
        # Unified backend session (single code path for paper/live).
        self._session_supervisor = None
        # Live P&L poll timer — active only during a live trading session.
        self._live_pnl_timer = None

        # Dashboard data
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.system_logs = []
        self._last_custom_metrics_payload: dict[str, dict] = {}

        # CRITICAL: Add startup banner FIRST to show actual launch time (ET)
        et_tz = _get_eastern_timezone()
        startup_time = datetime.now(et_tz).strftime("%Y-%m-%d %H:%M:%S ET")
        startup_hms  = datetime.now(et_tz).strftime("%H:%M:%S")
        self.system_logs.extend([
            f"[{startup_hms}] {'=' * 56}",
            f"[{startup_hms}] 🚀 SPYDER DASHBOARD STARTED: {startup_time}",
            f"[{startup_hms}] {'=' * 56}",
        ])
        # Emit startup marker through module logger as well so it appears in
        # the unified log stream (not only the in-widget system log buffer).
        self.logger.info("🚀 SPYDER DASHBOARD STARTED: %s", startup_time)
        # Startup readiness/config warmup is deferred until after first paint so
        # the initial dashboard render is not blocked by A03 validation work.
        self._startup_readiness_state = {
            "checked": False,
            "pending": True,
            "mode": "paper",
            "automation_enabled": True,
            "warnings": [],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
            "source": "post-paint warmup",
        }
        self._last_readiness_result = None
        self._last_readiness_ts = None
        self._readiness_ttl_seconds = 120
        self._readiness_worker_thread = None
        self._readiness_worker = None
        self._readiness_reports_dir = project_root / "market_data" / "trading_readiness_reports"
        self._append_startup_readiness_banner(startup_hms)

        # Toolbar proxy multipliers start with safe defaults and are refreshed
        # from A03 once the first frame has rendered.
        self._dji_from_dia_multiplier = 101.2
        # Per-symbol stale-data log throttling for Market Overview rows.
        self._stale_symbol_log_ts: dict[str, float] = {}

        # Optional after-hours quiet mode for non-critical startup/EOD chatter.
        # Enabled by default; disable with SPYDER_QUIET_AFTER_HOURS_LOGS=0.
        self._quiet_after_hours_logs = str(
            os.getenv("SPYDER_QUIET_AFTER_HOURS_LOGS", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}

        # System log verbosity mode (NORMAL suppresses routine signal chatter,
        # DEBUG restores full stream for diagnostics).
        self.system_log_mode = "NORMAL"
        self._signal_noise_loggers = (
            "SpyderS_Signals.SpyderS01_DIXCalculator",
            "Spyder.SpyderS_Signals.SpyderS01_DIXCalculator",
            "SpyderS_Signals.SpyderS02_DIXScheduler",
            "Spyder.SpyderS_Signals.SpyderS02_DIXScheduler",
            "SpyderS_Signals.SpyderS03_BlackSwanIndicator",
            "Spyder.SpyderS_Signals.SpyderS03_BlackSwanIndicator",
            "SpyderS_Signals.SpyderS06_SKEWCalculator",
            "Spyder.SpyderS_Signals.SpyderS06_SKEWCalculator",
            "SpyderS_Signals.SpyderS09_FREDClient",
            "Spyder.SpyderS_Signals.SpyderS09_FREDClient",
            "SpyderS_Signals.SpyderS10_SentimentScraper",
            "Spyder.SpyderS_Signals.SpyderS10_SentimentScraper",
        )
        self._set_system_log_verbosity("NORMAL", announce=False)

        self.automation_logs = []
        self.trading_mode = TradingMode.PAPER
        self._real_trading_armed = False
        self._paper_trading_armed = True
        self._paper_trading_enabled_this_session = True
        self._paper_start_authorized = False
        if is_market_hours(datetime.now(_get_eastern_timezone())):
            self._paper_launch_loading_deadline_monotonic = (
                time.monotonic() + (START_BUTTON_LOADING_DELAY_MS / 1000.0)
            )
        self.trading_active = False  # must be set before _sync_runtime_trading_mode_override
        self._sync_runtime_trading_mode_override()

        # Per-mode snapshots — preserved across PAPER ↔ LIVE switches so each
        # mode's table contents survive while the other mode is active.
        self._pnl_stats_by_mode: dict = {}          # TradingMode → stats dict
        self._positions_snapshot_by_mode: dict = {}  # TradingMode → serialized list
        self._account_snapshot_by_mode: dict = {}    # TradingMode → account panel values

        # api_connected and mkt_data_connected are @property accessors backed
        # by self.connection_info (see ConnectionInfo docstring, audit §16).
        self.tradier_client = (
            None  # FIXED: Initialize API client attribute before timer starts
        )
        self.auto_connect_attempts = 0

        # Order manager — broker-layer facade (audit §5)
        from Spyder.SpyderB_Broker.SpyderB06_DashboardOrderManager import (
            DashboardOrderManager,
        )
        self._order_manager = DashboardOrderManager(client=None, use_live=True)

        # Per-mode H05 session DB handles for recent-trade rendering.
        self._live_session_db = None
        self._paper_session_db = None
        self._session_db_init_failed_by_mode = {
            TradingMode.PAPER: False,
            TradingMode.LIVE: False,
        }
        self._session_db_adapter = DashboardSessionAdapter()

        # H07 PerformanceAnalytics is optional and expensive to build, so defer
        # it until the event loop is running instead of blocking first paint.
        self._h07_performance_analytics = None
        self._event_subscriptions_started = False
        self._decision_flow_timer_started = False
        self._market_worker_started = False
        self._opening_data_warmup_started = False
        self._opening_runtime_warmup_completed = False
        self._suppress_market_data_ready_log = False
        self._defer_opening_runtime_startup = self._should_defer_opening_runtime_startup()
        self._market_hours_launch_loading_hold_active = False
        self._startup_runtime_followups_scheduled = False

        # Risk parameters
        self.current_risk_params = None
        self.risk_monitoring_active = False

        # Event-clock state (Phase 5-A dashboard observability)
        from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState
        self.event_clock_state = EventClockState()
        self._event_clock_lock = threading.Lock()
        self._event_clock_handler_id = None
        self._execution_telemetry_lock = threading.Lock()
        self._execution_telemetry_events: deque[dict] = deque(maxlen=200)
        self._execution_telemetry_handler_id = None
        self._decision_flow_diagnostics = None
        self._decision_flow_recent_limit = 2
        self._risk_alert_handler_id = None
        self._last_entry_block_message = ""
        self._last_entry_block_ts = 0.0

        # Widget storage
        self.symbol_widgets = {}
        self._pmr_row_state: dict[str, object] | None = None

        # Prometheus metrics attributes
        self.system_components = {}
        self.client_indicators = {}
        self.system_stats = {}

        # Real data integration attributes
        self.real_data_active = False
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self._real_data_timer = None
        self._check_timer = None
        self._decision_flow_timer = None
        self._optional_signal_timer = None
        self._optional_signal_refresh_inflight = False
        self._error_count = 0
        self._system_log_flush_pending = False
        self._automation_log_flush_pending = False
        self._last_dispatch_state_key = ""
        self._veto_controls_enabled = self._load_veto_controls_state()

        # Initialize UI elements that will be created in setup methods
        self.connection_status_label = None
        self.api_status_container = None
        self.api_connection_label = None
        self.data_status_container = None
        self.data_status_label = None
        self.api_connect_icon = None
        self.mkt_connect_icon = None
        self.circuit_breaker_dot = None
        self.datetime_label = None
        self.dji_value = None
        self.dji_change = None
        self.spx_value = None
        self.spx_change = None
        self.ndx_value = None
        self.ndx_change = None
        self.positions_table = None
        self.system_log = None
        self.signal_panel = None
        self.liquidity_candidates_value = None
        self.liquidity_pass_ratio_value = None
        self.liquidity_freshness_value = None
        self.liquidity_top_failure_value = None
        self.execution_slippage_bps_value = None
        self.execution_fill_latency_value = None
        self.execution_reject_rate_value = None
        self.execution_partial_fill_value = None
        self.execution_recent_dispatch_value = None
        self.execution_recent_drop_value = None
        self.start_btn = None
        self.stop_btn = None
        self.emergency_btn = None
        self.mode_lbl = None
        self.mode_selector = None
        self.live_btn = None
        self.paper_btn = None
        self.acct_number_lbl = None
        self.spyderbox_acct_number_lbl = None
        self.spyderbox_account_type_lbl = None
        self.spyderbox_paper_status_btn = None
        self.spyderbox_paper_toggle_btn = None
        self.backtest_controls = None
        self.backtest_pnl_widget = None
        self.paper_pnl_widget = None
        self.risk_params_btn = None
        self.settled_value = None
        self.realized_value = None
        self.buying_value = None
        self.unrealized_value = None
        self.spyderbox_settled_value = None
        self.spyderbox_realized_value = None
        self.spyderbox_buying_value = None
        self.spyderbox_unrealized_value = None
        self.pnl_table = None
        self.refresh_orders_btn = None
        self.recent_trades_history_btn = None
        self.trade_audit_btn = None
        self.decision_log_btn = None
        self.veto_toggle_btn = None
        self.readiness_btn = None
        self.readiness_status_label = None
        self.greek_bars = None
        self.auto_log = None
        self.chart_widget = None
        self.chart_hidden_controls_panel = None
        self.figure = None
        self.canvas = None
        # Event-clock display UI elements (Phase 5-A)
        self.event_clock_panel = None
        self.signal_flow_heartbeat_label = None
        self.event_clock_compact_label = None
        self.entry_block_compact_label = None
        self.trading_window_compact_label = None
        self.event_clock_state_label = None
        self.event_clock_policy_label = None
        self.event_clock_windows_label = None
        self.event_clock_strategies_label = None
        # Phase 2: spreads & volatility panel widgets.
        self.spreads_table = None
        self.spreads_group = None
        self.atm_iv_label = None
        self.iv_rank_label = None
        self.spreads_summary_label = None
        # Unified status strip (added when SPREADS & VOLATILITY was folded in).
        self.realized_today_label = None
        self.bp_used_label = None
        # Phase 5: closed-trade audit log cached from worker emits.
        self._closed_trades_cache: list = []
        # Decision Log dialog singleton (None when closed).
        self._decision_log_dialog = None
        self._recent_trades_dialog = None
        # Phase 3: portfolio-aggregate Greeks labels (all None — data lives in
        # _portfolio_summary_cache and is surfaced via the popup dialog).
        self.port_delta_label = None
        self.port_gamma_label = None
        self.port_theta_label = None
        self.port_vega_label = None
        # Phase 7: higher-order Greeks labels (charm/vanna) from N04.
        self.port_charm_label = None
        self.port_vanna_label = None
        # Portfolio Strip popup: cache of last-received data and dialog singleton.
        self._portfolio_summary_cache: dict = {}
        self._portfolio_summary_dialog = None
        # Portfolio Strip toggle button reference (set by builder).
        self.portfolio_strip_btn = None
        self.internal_module_indicators = {}
        self.datetime_timer = None
        self.chart_timer = None
        self._shutdown_snapshot_saved = False
        self._shutdown_in_progress = False

        # Try to connect to real Prometheus collector if available
        if prometheus_available:
            self.get_client_status = get_client_status
            self.get_system_metrics = get_system_metrics
        else:
            # Use simulation functions
            self.get_client_status = None
            self.get_system_metrics = None

        # Initialize UI
        self.setup_ui()
        self.setup_timers()
        self.load_default_risk_parameters()
        self.optional_metrics_refreshed.connect(self._on_optional_metrics_refreshed)
        launch_loading_hold_active = (
            not self._defer_opening_runtime_startup
            and self._is_market_hours_launch_loading_hold_active()
        )
        self._market_hours_launch_loading_hold_active = launch_loading_hold_active
        if self._defer_opening_runtime_startup:
            self._schedule_opening_runtime_startup()
        elif launch_loading_hold_active:
            self._begin_market_hours_launch_loading_window()
            self._schedule_after_launch_loading_hold(
                self._complete_market_hours_launch_loading_window,
            )
        else:
            # Subscribe after first paint so event-bus initialization does not
            # block the initial dashboard render.
            QTimer.singleShot(150, self._subscribe_to_events)

        # Restore previous session's symbol values (if any) — runs after the
        # event loop starts so all widgets are fully initialised.
        if launch_loading_hold_active:
            self._schedule_after_launch_loading_hold(self._restore_snapshot, 10)
        else:
            QTimer.singleShot(0, self._restore_snapshot)

        if not self._defer_opening_runtime_startup:
            if not launch_loading_hold_active:
                # Start market worker with fixed connection detection
                QTimer.singleShot(100, self.start_market_worker)
                QTimer.singleShot(250, self._init_h07_performance_analytics)
                self._start_decision_flow_timer()

        # Pre-populate account P&L fields and performance table so the dashboard
        # shows sensible values immediately — before any trading session starts.
        if launch_loading_hold_active:
            self._schedule_after_launch_loading_hold(self._init_account_display, 25)
        else:
            QTimer.singleShot(0, self._init_account_display)

        # Start custom metrics orchestrator (DIX + Black Swan schedulers)
        # Deferred 1 s so the Qt event loop is fully running before QTimer creation in S07
        self._metrics_orchestrator = None
        if not self._defer_opening_runtime_startup and not launch_loading_hold_active:
            self._schedule_runtime_followup_startup_tasks()
        # Refresh optional WRS/PSR rows from signal-module caches on a background
        # thread so Market Overview rows populate without blocking the UI.
        if launch_loading_hold_active:
            self._schedule_after_launch_loading_hold(
                self._start_optional_signal_refresh_timer,
                2000,
            )
        else:
            QTimer.singleShot(2000, self._start_optional_signal_refresh_timer)

        # Log the actual dashboard initialization time (ET)
        _et_tz = _get_eastern_timezone()
        init_time = datetime.now(_et_tz).strftime("%H:%M:%S ET")
        self.add_system_log(f"🚀 Dashboard initialized at {init_time}")
        self.logger.info("🚀 Dashboard initialized at %s", init_time)
        if launch_loading_hold_active:
            self._schedule_after_launch_loading_hold(
                self._refresh_startup_readiness_state,
                75,
            )
        else:
            QTimer.singleShot(75, self._refresh_startup_readiness_state)
        QTimer.singleShot(200, self.setup_white_tooltips)
        # Re-emit once after startup burst so users can still see startup state
        # when the system log is rapidly populated by module initialization.
        QTimer.singleShot(12000, lambda: self._emit_sticky_startup_marker(init_time))

        # Ensure snapshot save also runs on full app shutdown paths.
        app = QApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.connect(self._on_app_about_to_quit)
            except Exception as _quit_hook_err:  # noqa: BLE001
                logger.debug("Could not connect aboutToQuit snapshot hook: %s", _quit_hook_err)

        self.logger.info(
            "Enhanced Dashboard initialized with Tradier API connection detection and heartbeat monitoring",  # noqa: E501
        )

    def _emit_sticky_startup_marker(self, init_time: str) -> None:
        """Emit a one-time delayed startup marker for dashboard visibility."""
        try:
            # Keep this marker out of the visible system log to avoid
            # duplicate startup lines during normal operations.
            self.logger.debug("Startup confirmed marker at %s", init_time)
        except RuntimeError:
            # QWidget may be closing during shutdown; ignore late timer emit.
            return

    def _init_h07_performance_analytics(self) -> None:
        """Initialise H07 analytics after first paint so startup stays responsive."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if self._h07_performance_analytics is not None:
            return

        try:
            from Spyder.SpyderH_Storage.SpyderH07_PerformanceAnalytics import (
                PerformanceAnalytics as _PerformanceAnalytics,
            )

            self._h07_performance_analytics = _PerformanceAnalytics()
        except Exception as h07_import_err:
            logger.warning("H07 PerformanceAnalytics unavailable: %s", h07_import_err)
            return

        current_mode = getattr(self, "trading_mode", None)
        stats = self._pnl_stats_by_mode.get(current_mode)
        if stats:
            try:
                self._refresh_pnl_table(dict(stats))
            except Exception as h07_refresh_err:
                logger.debug("Could not refresh P&L table after H07 init: %s", h07_refresh_err)

    def _should_defer_opening_runtime_startup(self, now_et: datetime | None = None) -> bool:
        """Return True when pre-open/after-hours startup should stay quiet."""
        current_et = now_et or datetime.now(_get_eastern_timezone())
        if current_et.weekday() >= 5:
            return True

        current_time = current_et.time()
        return current_time < OPENING_DATA_WARMUP_END_TIME or current_time >= MARKET_CLOSE_TIME

    def _schedule_opening_runtime_startup(self) -> None:
        """Attempt launch-time data hydration immediately, then honor warmup timers."""
        now_et = datetime.now(_get_eastern_timezone())
        current_time = now_et.time()
        if now_et.weekday() < 5 and LIVE_DATA_LOADING_START_TIME <= current_time < OPENING_DATA_WARMUP_END_TIME:
            loading_start_at = now_et
            runtime_start_at = now_et.replace(
                hour=OPENING_DATA_WARMUP_END_TIME.hour,
                minute=OPENING_DATA_WARMUP_END_TIME.minute,
                second=0,
                microsecond=0,
            )
        elif now_et.weekday() < 5 and current_time < LIVE_DATA_LOADING_START_TIME:
            loading_start_at = now_et.replace(
                hour=LIVE_DATA_LOADING_START_TIME.hour,
                minute=LIVE_DATA_LOADING_START_TIME.minute,
                second=0,
                microsecond=0,
            )
            runtime_start_at = now_et.replace(
                hour=OPENING_DATA_WARMUP_END_TIME.hour,
                minute=OPENING_DATA_WARMUP_END_TIME.minute,
                second=0,
                microsecond=0,
            )
        else:
            loading_start_at = _next_weekday_time(LIVE_DATA_LOADING_START_TIME, now_et)
            runtime_start_at = _next_weekday_time(OPENING_DATA_WARMUP_END_TIME, now_et)
        self._suppress_market_data_ready_log = True

        market_open_delay_ms = max(0, int((loading_start_at - now_et).total_seconds() * 1000))
        runtime_start_delay_ms = max(0, int((runtime_start_at - now_et).total_seconds() * 1000))

        if QTimer is not None:
            QTimer.singleShot(0, self._begin_launch_live_data_prewarm)
            QTimer.singleShot(market_open_delay_ms, self._begin_opening_data_warmup_window)
            QTimer.singleShot(runtime_start_delay_ms, self._complete_opening_runtime_warmup)
        else:
            self._begin_launch_live_data_prewarm()
            self._begin_opening_data_warmup_window()
            self._complete_opening_runtime_warmup()

    def _begin_launch_live_data_prewarm(self) -> None:
        """Attempt any available live-data hydration immediately after launch.

        This is display-only prewarm: it starts the quiet market worker and the
        existing startup follow-up fetches, but does not subscribe runtime event
        loops or relax the downstream entry gate.
        """
        if getattr(self, "_shutdown_in_progress", False):
            return
        if getattr(self, "_launch_live_data_prewarm_started", False):
            return

        self._launch_live_data_prewarm_started = True
        if not self._market_worker_started:
            self.start_market_worker(quiet_startup=True, announce=False)
        self._schedule_runtime_followup_startup_tasks()

    def _is_market_hours_launch_loading_hold_active(self) -> bool:
        """Return True while the launch-anchored 30-second paper hold is active."""
        if getattr(self, "_shutdown_in_progress", False):
            return False
        if getattr(self, "trading_mode", TradingMode.PAPER) != TradingMode.PAPER:
            return False
        if getattr(self, "_defer_opening_runtime_startup", False):
            return False
        if not is_market_hours():
            return False

        return self._remaining_paper_start_loading_delay_ms() > 0

    def _schedule_after_launch_loading_hold(self, callback, delay_ms: int = 0) -> None:
        """Delay a startup callback until the launch loading window has elapsed."""
        hold_delay_ms = 0
        if self._is_market_hours_launch_loading_hold_active():
            hold_delay_ms = self._remaining_paper_start_loading_delay_ms()

        total_delay_ms = max(0, int(hold_delay_ms) + int(delay_ms))
        if QTimer is not None:
            QTimer.singleShot(total_delay_ms, callback)
        else:
            callback()

    def _begin_market_hours_launch_loading_window(self) -> None:
        """Keep market-hours launch quiet while the initial loading window is active."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if self._opening_data_warmup_started:
            return

        self._opening_data_warmup_started = True
        self._suppress_market_data_ready_log = True
        if getattr(self, "_session_supervisor", None) is not None and not getattr(self, "trading_active", False):
            self._set_start_button_loading_live_data_state()
        if not self._market_worker_started:
            self.start_market_worker(quiet_startup=True, announce=False)
        # Hydrate live quotes plus S07 options metrics during the loading hold
        # so the first post-hold strategy decision can use fresh live_data.json.
        self._schedule_runtime_followup_startup_tasks()

    def _complete_market_hours_launch_loading_window(self) -> None:
        """Release the quiet launch hold and enable the normal runtime startup path."""
        if getattr(self, "_shutdown_in_progress", False):
            return

        self._market_hours_launch_loading_hold_active = False
        market_data_ready_during_hold = bool(getattr(self, "_market_data_initialized", False))
        self._complete_opening_runtime_warmup()
        if market_data_ready_during_hold:
            self.add_system_log("✅ Market data loaded — system ready")

    def _begin_opening_data_warmup_window(self) -> None:
        """Start live-data connections and quiet market-data hydration."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if self._opening_data_warmup_started:
            return

        self._opening_data_warmup_started = True
        if getattr(self, "_session_supervisor", None) is not None and not getattr(self, "trading_active", False):
            self._set_start_button_loading_live_data_state()
        self.add_system_log("🟡 Establishing live connections and loading live data")
        self.add_system_log(
            "⏳ ENTRY gate remains blocked until 10:15 ET"
        )
        self.start_market_worker(quiet_startup=True, announce=False)
        # Run the same prewarm tasks during the opening window so live_data.json
        # and S07 options analytics are already hydrated before the entry gate opens.
        self._schedule_runtime_followup_startup_tasks()

    def _complete_opening_runtime_warmup(self) -> None:
        """Enable runtime components once the opening data warmup window ends."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if self._opening_runtime_warmup_completed:
            return

        self._opening_runtime_warmup_completed = True
        self._suppress_market_data_ready_log = False
        self._release_market_worker_quiet_startup()

        if not self._market_worker_started:
            self.start_market_worker()
        self._subscribe_to_events()
        self._init_h07_performance_analytics()
        self._start_decision_flow_timer()
        self._schedule_runtime_followup_startup_tasks()

    def _release_market_worker_quiet_startup(self) -> None:
        """Re-enable normal worker side effects after the quiet startup hold."""
        worker = getattr(self, "market_worker", None)
        if worker is None:
            return

        try:
            worker._quiet_startup = False
        except RuntimeError:
            return

    def _schedule_runtime_followup_startup_tasks(self) -> None:
        """Schedule startup follow-up tasks once the opening warmup allows them."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if getattr(self, "_startup_runtime_followups_scheduled", False):
            return

        self._startup_runtime_followups_scheduled = True
        if QTimer is None:
            self._start_metrics_orchestrator()
            self.apply_proven_real_data_pattern()
            self._trigger_initial_live_fetch()
            return

        QTimer.singleShot(1000, self._start_metrics_orchestrator)
        QTimer.singleShot(1000, self.apply_proven_real_data_pattern)
        QTimer.singleShot(4000, self._trigger_initial_live_fetch)

    def create_api_connection(self) -> bool:
        """Check Tradier API connectivity.

        Legacy method name preserved for backward compatibility.
        Now checks Tradier API connectivity.
        """
        try:
            self.logger.info("🔄 Checking Tradier API connectivity...")
            connected, mode = check_api_connection()

            if connected:
                self.logger.info("✅ Tradier API connected: %s", mode)
                self.on_connection_status_changed(True)
                return True
            self.logger.warning("⚠️ Tradier API not available: %s", mode)
            self.on_connection_status_changed(False)
            return False

        except Exception as e:
            self.logger.exception("❌ API connection check failed: %s", e)
            self.on_connection_status_changed(False)
            return False

    def _trigger_initial_live_fetch(self, _retry: int = 0):
        """Ask the market worker to attempt immediate launch-time hydration.

        This intentionally does not depend on the worker's startup API probe. When
        Spyder launches outside the Tradier session window, the worker still needs
        to attempt the read-only quote/chain/chart fetch path so startup hydration
        is tried at any launch time while the runtime decision flow remains gated
        elsewhere.
        """
        if self.market_worker and self._emit_market_worker_signal("fetch_requested"):
            return
        if self.market_worker and _retry < 6:
            # The worker thread or its signals may not be ready yet. Retry a few
            # times so launch hydration still gets an initial fetch attempt.
            QTimer.singleShot(5000, lambda: self._trigger_initial_live_fetch(_retry + 1))

    # ==========================================================================
    # REAL DATA INTEGRATION PATTERN (UNCHANGED)
    # ==========================================================================
    def apply_proven_real_data_pattern(self):
        """Apply the proven real data integration pattern from temp_WorkingRealDashboard"""
        # Outside the trading window: load the EOD snapshot immediately so the
        # dashboard shows genuine closing prices.  The market worker will fetch
        # a fresh Tradier snapshot in the background (via eod_snapshot_fetched
        # signal → _on_eod_snapshot_fetched) and update the display once it
        # arrives.  We only start the file-read timer here — no Tradier polling.
        if not is_tradier_window():
            snapshot_file = self.data_file.parent / "eod_snapshot.json"
            source_file = (
                snapshot_file if snapshot_file.exists()
                else (self.data_file if self.data_file.exists() else None)
            )
            if source_file:
                try:
                    with open(source_file) as _f:
                        _snap = json.load(_f)
                    spy_price = _snap.get("SPY", {}).get("last", "N/A")
                    spx_price = _snap.get("SPX", {}).get("last", "N/A")
                    dji_price = _snap.get("$DJI", {}).get("last", "N/A")
                    dia_price = _snap.get("DIA", {}).get("last", "N/A")
                    vxv_price = _snap.get("VXV", {}).get("last", "N/A")
                    eod_date = _snap.get("_eod_date", "unknown date")
                    self.add_system_log(
                        f"📊 EOD snapshot loaded ({eod_date}) — SPY: ${spy_price} | SPX: ${spx_price} | DJI: ${dji_price}"  # noqa: E501
                    )
                    self.logger.debug(
                        "📈 EOD snapshot details — DIA: $%s | VXV: %s",
                        dia_price,
                        vxv_price,
                    )
                    # Start file-read timer so widgets populate immediately;
                    # skip fast-fetch (no Tradier polling outside trading hours).
                    self.real_data_active = True
                    if not getattr(self, "_real_data_timer", None) or not self._real_data_timer.isActive():  # noqa: E501
                        self._real_data_timer = QTimer()
                        self._real_data_timer.timeout.connect(self.update_with_real_data)
                        self._real_data_timer.start(1000)
                    QTimer.singleShot(250, self.update_with_real_data)
                    self.update_data_status("EOD")
                except Exception as e:
                    self.add_system_log(f"⚠️ Could not load EOD snapshot: {e}")
            else:
                self.add_system_log("🕐 Outside trading window — awaiting EOD data from Tradier")
            return

        try:
            # Check if real data is available
            real_data_available = False

            if self.data_file.exists():
                try:
                    with open(self.data_file) as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    self.add_system_log(f"🔥 Real data detected - SPY: ${spy_price}")
                    real_data_available = True
                except (OSError, json.JSONDecodeError, KeyError) as e:
                    self.add_system_log(f"⚠️ Real data file exists but couldn't read it: {e}")
            else:
                self.add_system_log(
                    "📊 No real data detected - will monitor for availability",
                )

            # Apply the appropriate pattern
            if real_data_available:
                self.add_system_log("🔥 Applying proven real data patch...")
                self.apply_real_data_patch()
            else:
                self.add_system_log(
                    "📊 No Tradier snapshot yet - monitoring for real market data",
                )
                self.setup_real_data_monitoring()

        except Exception as e:
            self.add_system_log(f"❌ Error applying real data pattern: {e}")

    def apply_real_data_patch(self):
        """Apply real data patch using the proven working pattern"""
        try:
            # Stop the worker-owned standby emitter once file-backed data takes over.
            if hasattr(self, "market_worker") and self.market_worker:
                if self._invoke_market_worker_slot("pause_periodic_updates"):
                    self.logger.debug("Stopped worker standby timer")

            # Start real data updates
            self._real_data_timer = QTimer()
            self._real_data_timer.timeout.connect(self.update_with_real_data)
            self._real_data_timer.start(1000)  # Update every second

            # Fast quote refresh — polls Tradier for fresh prices every 10 s.
            # Runs in the market worker thread via fast_fetch_requested so it
            # doesn't block the UI.  The full fetch (balance + options + chart)
            # still happens every 30 s via the heartbeat.
            self._fast_quote_timer = QTimer()
            self._fast_quote_timer.timeout.connect(
                lambda: self._emit_market_worker_signal("fast_fetch_requested")
            )
            self._fast_quote_timer.start(10_000)  # every 10 seconds

            self.real_data_active = True

            # Initial update after the event loop clears the startup burst.
            QTimer.singleShot(250, self.update_with_real_data)

            # Update status
            self.update_status_for_real_data()

            # Log success with market-hours-aware wording.
            if is_market_hours():
                self.add_system_log("🔥 REAL MARKET DATA ACTIVE - Tradier API prices")
                self.add_system_log("Real-time market data from Tradier")
            else:
                off_hours_status = self.determine_data_status()
                if off_hours_status == "PRE-OPEN":
                    self.add_system_log("📡 PRE-OPEN LIVE SNAPSHOT ACTIVE - Tradier launch hydration only")
                    self.add_system_log("Pre-open live snapshot hydrated from Tradier")
                elif off_hours_status == "AFTER-HOURS":
                    self.logger.debug("🌙 AFTER-HOURS LIVE SNAPSHOT ACTIVE - Tradier launch hydration only")
                    self.logger.debug("After-hours live snapshot hydrated from Tradier")
                else:
                    self.add_system_log("📊 EOD MARKET DATA ACTIVE - Tradier API prices")
                    self.add_system_log("EOD market data from Tradier")

            self.add_system_log("✅ Real data patch applied successfully!")

        except Exception as e:
            self.add_system_log(f"❌ Error applying real data patch: {e}")

    def _mark_market_data_ready(self) -> None:
        """Mark the dashboard as ready exactly once after real market hydration."""
        if self._market_data_initialized:
            return

        self._market_data_initialized = True
        if not getattr(self, "_suppress_market_data_ready_log", False):
            self.add_system_log("✅ Market data loaded — system ready")

        if getattr(self, "_queued_trading_start", False):
            if QTimer is not None:
                QTimer.singleShot(0, self._process_queued_trading_start)
            else:
                self._process_queued_trading_start()

    def _process_queued_trading_start(self) -> None:
        """Resume a queued start request once fresh market data is ready."""
        if not getattr(self, "_queued_trading_start", False):
            return

        self._queued_trading_start = False
        self.add_system_log(
            "✅ Fresh market data fetched — processing queued Start Trading request"
        )
        self.start_trading(from_queued=True)

    def _set_start_button_loading_live_data_state(self) -> None:
        """Show that Start Trading is queued behind fresh market data hydration."""
        start_btn = getattr(self, "start_btn", None)
        if start_btn is None:
            return

        start_btn.setStyleSheet("background-color: #d3d3d3; color: black;")
        start_btn.setText("LOADING LIVE DATA")
        set_enabled = getattr(start_btn, "setEnabled", None)
        if callable(set_enabled):
            set_enabled(True)
        set_tooltip = getattr(start_btn, "setToolTip", None)
        if callable(set_tooltip):
            set_tooltip("Waiting for the live-data loading window to complete")

    def _set_start_button_active_state(self) -> None:
        """Render the steady-state active trading button."""
        start_btn = getattr(self, "start_btn", None)
        active_state_plan = build_start_button_active_state_plan(
            has_start_button=start_btn is not None,
            is_paper_mode=self.trading_mode == TradingMode.PAPER,
            automation_active_color=str(COLORS["automation_active"]),
        )

        if active_state_plan.action == "noop":
            return

        start_btn.setStyleSheet(str(active_state_plan.style_sheet or ""))
        start_btn.setText(str(active_state_plan.text or ""))
        set_enabled = getattr(start_btn, "setEnabled", None)
        if callable(set_enabled) and active_state_plan.enabled is not None:
            set_enabled(bool(active_state_plan.enabled))
        set_tooltip = getattr(start_btn, "setToolTip", None)
        if callable(set_tooltip) and active_state_plan.tooltip is not None:
            set_tooltip(str(active_state_plan.tooltip))

    def _cancel_start_button_loading_transition(self) -> None:
        """Invalidate any pending delayed transition from loading to active."""
        self._start_button_loading_generation = (
            getattr(self, "_start_button_loading_generation", 0) + 1
        )
        self._start_button_loading_timer_active = False
        self._paper_session_start_pending = False
        self._paper_session_start_show_failure_dialog = False
        self._paper_start_authorized = False

    def _remaining_paper_start_loading_delay_ms(self) -> int:
        """Return the remaining launch-time paper loading window in milliseconds."""
        deadline = getattr(self, "_paper_launch_loading_deadline_monotonic", None)
        if not isinstance(deadline, (int, float)):
            return 0

        remaining_ms = int(((float(deadline) - time.monotonic()) * 1000.0) + 0.999)
        return max(0, remaining_ms)

    def _queue_paper_session_start(self, *, show_failure_dialog: bool = True) -> None:
        """Delay paper session startup until the launch-time loading window completes."""
        supervisor = getattr(self, "_session_supervisor", None)
        queue_plan = build_paper_session_queue_plan(
            shutdown_in_progress=bool(getattr(self, "_shutdown_in_progress", False)),
            is_paper_mode=self.trading_mode == TradingMode.PAPER,
            trading_active=bool(getattr(self, "trading_active", False)),
            supervisor_running=bool(getattr(supervisor, "is_running", False)),
            session_start_pending=bool(getattr(self, "_paper_session_start_pending", False)),
            show_failure_dialog=bool(show_failure_dialog),
            delay_ms=self._remaining_paper_start_loading_delay_ms(),
        )

        if queue_plan.action == "cancel_loading":
            self._cancel_start_button_loading_transition()
            return

        if queue_plan.action == "noop":
            return

        if queue_plan.action == "adopt_running":
            self._adopt_running_session_supervisor_ui_state()
            return

        if queue_plan.set_pending:
            self._paper_session_start_pending = bool(queue_plan.pending_value)
        if queue_plan.set_show_failure_dialog:
            self._paper_session_start_show_failure_dialog = bool(
                queue_plan.show_failure_dialog
            )

        if queue_plan.action == "finalize_now":
            self._finalize_queued_paper_session_start()
            return

        if queue_plan.action == "begin_loading":
            self._begin_start_button_loading_transition(int(queue_plan.delay_ms or 0))

    def _finalize_queued_paper_session_start(self) -> None:
        """Start the paper session once the loading-live-data window completes."""
        if not getattr(self, "_paper_session_start_pending", False):
            return

        if getattr(self, "_shutdown_in_progress", False):
            self._cancel_start_button_loading_transition()
            return

        supervisor = getattr(self, "_session_supervisor", None)
        paper_start_allowed = (
            (
                self.trading_mode == TradingMode.PAPER
                and self._is_paper_trading_enabled_for_session()
                and bool(getattr(self, "_paper_start_authorized", False))
            )
            or (
                self.trading_mode == TradingMode.PAPER
                and bool(getattr(supervisor, "_spyder_paper_start_authorized", False))
            )
        )
        if not paper_start_allowed:
            self._cancel_start_button_loading_transition()
            self._restore_start_button_ready_state()
            self.add_system_log(
                "Delayed PAPER start cancelled — authorization no longer active"
            )
            return

        self._paper_session_start_pending = False
        show_failure_dialog = bool(
            getattr(self, "_paper_session_start_show_failure_dialog", False)
        )
        self._paper_session_start_show_failure_dialog = False

        market_open = bool(is_market_hours())
        start_succeeded = bool(self._start_unified_session_supervisor())

        finalize_plan = build_paper_session_finalize_outcome_plan(
            market_open=market_open,
            start_succeeded=start_succeeded,
            show_failure_dialog=show_failure_dialog,
        )

        if finalize_plan.action == "start_failed":
            if finalize_plan.show_dialog:
                QMessageBox.critical(
                    self,
                    "Start Failed",
                    "Unified backend session failed to start.\n"
                    "Trading remains stopped (fail-closed).",
                )
            self._restore_start_button_ready_state()
            return

        self._adopt_running_session_supervisor_ui_state()

    def _complete_start_button_loading_transition(self, generation: int) -> None:
        """Switch the loading button into the steady active state after the delay."""
        supervisor = getattr(self, "_session_supervisor", None)
        completion_plan = build_loading_transition_completion_plan(
            expected_generation=int(generation),
            current_generation=int(getattr(self, "_start_button_loading_generation", 0)),
            shutdown_in_progress=bool(getattr(self, "_shutdown_in_progress", False)),
            session_start_pending=bool(getattr(self, "_paper_session_start_pending", False)),
            trading_active=bool(getattr(self, "trading_active", False)),
            supervisor_running=bool(getattr(supervisor, "is_running", False)),
        )

        if completion_plan.action == "noop":
            return

        if completion_plan.action == "cancel_loading":
            self._cancel_start_button_loading_transition()
            return

        if completion_plan.set_timer_inactive:
            self._start_button_loading_timer_active = False
        if completion_plan.finalize_pending_start:
            self._finalize_queued_paper_session_start()
            supervisor = getattr(self, "_session_supervisor", None)
            completion_plan = type(completion_plan)(
                action=completion_plan.action,
                finalize_pending_start=completion_plan.finalize_pending_start,
                set_timer_inactive=completion_plan.set_timer_inactive,
                activate_button=bool(
                    getattr(self, "trading_active", False)
                    or getattr(supervisor, "is_running", False)
                ),
            )
        if completion_plan.activate_button:
            self._set_start_button_active_state()

    def _begin_start_button_loading_transition(self, delay_ms: int | None = None) -> None:
        """Hold the paper start button in a loading state before paper becomes active."""
        if delay_ms is None:
            delay_ms = self._remaining_paper_start_loading_delay_ms()

        begin_plan = build_loading_transition_begin_plan(
            is_paper_mode=self.trading_mode == TradingMode.PAPER,
            current_generation=int(getattr(self, "_start_button_loading_generation", 0)),
            delay_ms=int(delay_ms),
            qtimer_available=QTimer is not None,
        )

        if begin_plan.action == "noop":
            return

        generation = int(begin_plan.next_generation or 0)
        self._start_button_loading_generation = generation
        if begin_plan.set_timer_active:
            self._start_button_loading_timer_active = True
        self._set_start_button_loading_live_data_state()

        if begin_plan.schedule_with_qtimer:
            QTimer.singleShot(
                int(begin_plan.delay_ms or 0),
                lambda: self._complete_start_button_loading_transition(generation),
            )
        else:
            self._complete_start_button_loading_transition(generation)

    def _restore_start_button_ready_state(self) -> None:
        """Restore the idle Start Trading button after a queued start is blocked."""
        self._cancel_start_button_loading_transition()
        start_btn = getattr(self, "start_btn", None)
        ready_state_plan = build_start_button_ready_state_plan(
            has_start_button=start_btn is not None,
            trading_active=bool(getattr(self, "trading_active", False)),
            is_paper_mode=self.trading_mode == TradingMode.PAPER,
            positive_color=str(COLORS["positive"]),
        )

        if ready_state_plan.action == "noop":
            return

        start_btn.setStyleSheet(str(ready_state_plan.style_sheet or ""))
        start_btn.setText(str(ready_state_plan.text or ""))
        set_enabled = getattr(start_btn, "setEnabled", None)
        if callable(set_enabled) and ready_state_plan.enabled is not None:
            set_enabled(bool(ready_state_plan.enabled))
        set_tooltip = getattr(start_btn, "setToolTip", None)
        if callable(set_tooltip) and ready_state_plan.tooltip is not None:
            set_tooltip(str(ready_state_plan.tooltip))

    def _has_hydrated_live_market_data(self, live_data: dict | None) -> bool:
        """Return True only after the required startup quote basket is hydrated."""
        if not isinstance(live_data, dict):
            return False

        if _market_data_datetime_from_epoch_ms(live_data.get("_fetch_time_ms")) is None:
            return False

        for symbol in STARTUP_READY_REQUIRED_SYMBOLS:
            entry = live_data.get(symbol)
            if not isinstance(entry, dict):
                return False

            last = entry.get("last")
            if not isinstance(last, (int, float)) or float(last) <= 0.0:
                return False

        return _freshest_market_data_timestamp(live_data) is not None

    def _invoke_market_worker_slot(self, slot_name: str) -> bool:
        """Invoke a market-worker slot on the worker thread when available."""
        worker = getattr(self, "market_worker", None)
        slot = getattr(worker, slot_name, None)
        market_thread = getattr(self, "market_thread", None)
        invoke_plan = build_market_worker_slot_invoke_plan(
            has_worker=worker is not None,
            has_callable_slot=callable(slot),
            thread_running=bool(market_thread is not None and market_thread.isRunning()),
            slot_name=str(slot_name),
        )

        if invoke_plan.action == "return_false":
            return False

        if invoke_plan.action == "warn_and_return_false":
            self.logger.warning(str(invoke_plan.warning_message or ""))
            return False

        if invoke_plan.action == "call_direct":
            slot()
            return True

        try:
            return bool(QMetaObject.invokeMethod(worker, slot_name, Qt.QueuedConnection))
        except Exception as exc:
            self.logger.warning("Failed to invoke market worker slot '%s': %s", slot_name, exc)
            return False

    def _emit_market_worker_signal(self, signal_name: str) -> bool:
        """Safely emit a market-worker signal, tolerating shutdown-time deletion."""
        worker = getattr(self, "market_worker", None)
        signal_obj = getattr(worker, signal_name, None) if worker is not None else None
        emit_plan = build_market_worker_signal_emit_plan(
            has_worker=worker is not None,
            has_signal=signal_obj is not None,
            has_emit_method=bool(signal_obj is not None and hasattr(signal_obj, "emit")),
        )
        if emit_plan.action == "noop":
            return False

        try:
            signal_obj.emit()
            return True
        except RuntimeError:
            return False

    def _disconnect_market_worker_fetch_signals(self) -> None:
        """Disconnect queued fetch triggers before stopping the worker thread."""
        worker = getattr(self, "market_worker", None)
        disconnect_plan = build_market_worker_signal_disconnect_plan(
            has_worker=worker is not None,
            disconnectable_signals={
                signal_name: bool(
                    worker is not None
                    and (signal_obj := getattr(worker, signal_name, None)) is not None
                    and hasattr(signal_obj, "disconnect")
                )
                for signal_name in ("fetch_requested", "fast_fetch_requested")
            },
        )

        for signal_name in disconnect_plan.signal_names:
            signal_obj = getattr(worker, signal_name, None)

            try:
                signal_obj.disconnect()
            except (RuntimeError, TypeError):
                continue

    def _stop_metrics_orchestrator_for_shutdown(self) -> None:
        """Stop the dashboard-owned custom metrics orchestrator."""
        orchestrator = getattr(self, "_metrics_orchestrator", None)
        shutdown_plan = build_metrics_orchestrator_shutdown_plan(
            has_orchestrator=orchestrator is not None,
            has_stop_method=bool(orchestrator is not None and hasattr(orchestrator, "stop")),
            stop_failed=False,
        )
        if shutdown_plan.action == "noop":
            return

        try:
            orchestrator.stop()
        except Exception as exc:
            shutdown_plan = build_metrics_orchestrator_shutdown_plan(
                has_orchestrator=True,
                has_stop_method=True,
                stop_failed=True,
            )
            self.logger.warning(str(shutdown_plan.warning_template or ""), exc, exc_info=True)
        finally:
            if shutdown_plan.clear_owner:
                self._metrics_orchestrator = None

    def _stop_pre_worker_shutdown_timers(self) -> None:
        """Stop early shutdown timers before worker/thread teardown begins."""
        shutdown_plan = build_shutdown_timer_stop_plan(
            timer_presence={
                timer_attr: bool(getattr(self, timer_attr, None))
                for timer_attr in (
                    "_real_data_timer",
                    "_fast_quote_timer",
                    "_check_timer",
                    "_decision_flow_timer",
                )
            }
        )

        for timer_attr in shutdown_plan.timer_attrs:
            timer_obj = getattr(self, timer_attr, None)
            if timer_obj is not None:
                timer_obj.stop()

    def _stop_post_worker_shutdown_timers(self) -> None:
        """Stop late shutdown timers after worker/thread teardown settles."""
        shutdown_plan = build_post_worker_shutdown_timer_plan(
            timer_presence={
                timer_attr: bool(getattr(self, timer_attr, None))
                for timer_attr in ("datetime_timer", "chart_timer")
            }
        )

        for timer_attr in shutdown_plan.timer_attrs:
            timer_obj = getattr(self, timer_attr, None)
            if timer_obj is not None:
                timer_obj.stop()

    def _stop_market_worker_for_shutdown(self) -> None:
        """Stop the market worker after disconnecting queued fetch signals."""
        worker = getattr(self, "market_worker", None)
        shutdown_plan = build_market_worker_shutdown_plan(
            has_worker=worker is not None,
            has_stop_method=bool(worker is not None and hasattr(worker, "stop")),
        )
        if shutdown_plan.action == "noop":
            return

        self._disconnect_market_worker_fetch_signals()
        self._invoke_market_worker_slot("stop")

    def _log_close_event_shutdown_messages(self) -> None:
        """Emit the fixed close-event shutdown copy to the system log."""
        shutdown_message_plan = build_dashboard_shutdown_message_plan()
        for message in shutdown_message_plan.close_event_system_messages:
            self.add_system_log(str(message))

    def _run_close_event_shutdown_sequence(self, event: object) -> None:
        """Run the helper-backed shutdown sequence for closeEvent."""
        shutdown_sequence_plan = build_close_event_shutdown_sequence_plan()

        for method_name in shutdown_sequence_plan.pre_qthread_methods:
            getattr(self, method_name)()

        for shutdown_spec in shutdown_sequence_plan.qthread_shutdown_specs:
            self._stop_qthread_for_shutdown(
                shutdown_spec.thread_attr,
                shutdown_spec.label,
                wait_ms=shutdown_spec.wait_ms,
                terminate_wait_ms=shutdown_spec.terminate_wait_ms,
            )

        for method_name in shutdown_sequence_plan.post_qthread_methods:
            getattr(self, method_name)()

        event.accept()

    def _stop_qthread_for_shutdown(
        self,
        thread_attr: str,
        label: str,
        wait_ms: int = 3000,
        terminate_wait_ms: int = 5000,
    ) -> None:
        """Stop a Qt worker thread and block until a forced termination settles."""
        thread = getattr(self, thread_attr, None)
        if thread is None or not thread.isRunning():
            return

        thread.quit()
        shutdown_plan = build_qthread_shutdown_plan(
            stop_succeeded_after_quit=bool(thread.wait(wait_ms)),
            stop_succeeded_after_terminate=None,
            label=str(label),
            wait_ms=int(wait_ms),
            terminate_wait_ms=int(terminate_wait_ms),
        )
        if shutdown_plan.action == "done":
            return

        logger.warning(str(shutdown_plan.warning_message or ""))
        thread.terminate()
        shutdown_plan = build_qthread_shutdown_plan(
            stop_succeeded_after_quit=False,
            stop_succeeded_after_terminate=bool(thread.wait(terminate_wait_ms)),
            label=str(label),
            wait_ms=int(wait_ms),
            terminate_wait_ms=int(terminate_wait_ms),
        )
        if shutdown_plan.action == "done":
            return

        logger.error(str(shutdown_plan.error_message or ""))

    def setup_real_data_monitoring(self):
        """Setup monitoring for real data to become available"""

        def check_for_real_data():
            """Check if real data becomes available"""
            if self.real_data_active:
                return  # Already using real data

            if self.data_file.exists():
                try:
                    with open(self.data_file) as f:
                        data = json.load(f)

                    if data:
                        self.add_system_log(
                            "🔥 Fresh Tradier snapshot detected - activating live market data!",
                        )
                        self._check_timer.stop()
                        self.apply_real_data_patch()
                except Exception as e:
                    self.logger.debug("Error checking for real data: %s", e)

        # Check every 5 seconds for real data
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(check_for_real_data)
        self._check_timer.start(5000)

    def update_with_real_data(self):
        """Update dashboard with real market data"""
        try:
            if not self.data_file.exists():
                return

            # Read as text first so we can gracefully handle transient
            # partial-writes from the producer without surfacing noisy errors.
            with open(self.data_file, encoding="utf-8") as f:
                raw_live_data = f.read()

            if not raw_live_data.strip():
                return

            try:
                live_data = json.loads(raw_live_data)
            except json.JSONDecodeError:
                # Retry once immediately in case we raced a writer flush.
                with open(self.data_file, encoding="utf-8") as f:
                    retry_raw_live_data = f.read()
                if not retry_raw_live_data.strip():
                    return
                try:
                    live_data = json.loads(retry_raw_live_data)
                except json.JSONDecodeError as parse_exc:
                    self.logger.debug(
                        "Real data snapshot parse skipped (partial write): %s",
                        parse_exc,
                    )
                    return

            if not live_data:
                return

            if self._has_hydrated_live_market_data(live_data):
                self._mark_market_data_ready()

            # Keep self.market_data in sync with live prices so other code
            # reading self.market_data (e.g. update_chart) gets real values.
            # Skip metadata keys (e.g. _fetch_time_ms) whose values are not dicts.
            for symbol, data in live_data.items():
                if not isinstance(data, dict):
                    continue
                if symbol not in self.market_data:
                    self.market_data[symbol] = {}
                self.market_data[symbol]["last"] = data["last"]
                self.market_data[symbol]["change"] = data["change"]
                self.market_data[symbol]["change_pct"] = data["change_pct"]
                quote_time = _market_data_datetime_from_epoch_ms(data.get("timestamp_ms"))
                if quote_time is not None:
                    self.market_data[symbol]["timestamp"] = quote_time

            freshest_quote_time = _freshest_market_data_timestamp(live_data)
            if freshest_quote_time is not None:
                self.connection_info.last_successful_data = freshest_quote_time
                self.connection_info.data_was_live = True

            # Detect per-symbol stale quotes relative to this fetch. Tradier can
            # occasionally return a lagging quote for one symbol in an otherwise
            # fresh basket; avoid showing that value as if it were current.
            stale_symbols: set[str] = set()
            fetch_time = _market_data_datetime_from_epoch_ms(live_data.get("_fetch_time_ms"))
            if fetch_time is not None:
                self.connection_info.last_market_data_fetch_time = fetch_time
            if fetch_time is not None:
                for symbol in ("DIA",):
                    entry = live_data.get(symbol)
                    if not isinstance(entry, dict):
                        continue
                    quote_time = _market_data_datetime_from_epoch_ms(entry.get("timestamp_ms"))
                    if quote_time is None:
                        continue
                    quote_age_seconds = (fetch_time - quote_time).total_seconds()
                    # DIA has a dedicated per-symbol refetch in G18, but
                    # Tradier quote trade-timestamps for DIA can lag 15+ minutes
                    # even during regular market hours.  Use the same 1800 s
                    # (30-min) tolerance applied to index-like symbols in the
                    # toolbar so genuine trading activity never shows STALE.
                    _dia_stale_threshold = 1800.0
                    if quote_age_seconds > _dia_stale_threshold:
                        stale_symbols.add(symbol)
                        widget = self.symbol_widgets.get(symbol)
                        if widget is not None:
                            widget.set_unavailable("STALE")

            # Update symbol widgets — delegate to update_data() so each widget's
            # symbol-specific formatting and colour logic is applied correctly
            # (e.g. $TICK/$ADD as signed integers, $TRIN colour-coded by value).
            for symbol, data in live_data.items():
                if not isinstance(data, dict):
                    continue
                if symbol in stale_symbols:
                    continue
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(data)

            # Push standard-quote values (VIX, SKEW, …) to the signal panel
            # so popup dialogs show the same figures as the Market Overview.
            if self.signal_panel is not None:
                _sp = {}
                for _sym in ("VIX", "SKEW", "CPC"):
                    _e = live_data.get(_sym)
                    if isinstance(_e, dict) and _e.get("last") is not None:
                        _sp[_sym] = _e["last"]
                if _sp:
                    self.signal_panel.update_live_data(_sp)

            # Update toolbar indices
            self.update_toolbar_with_real_data(live_data)

            # Re-evaluate the status badge on every real-data refresh so stale
            # quotes flip the UI promptly instead of waiting for the next heartbeat.
            _correct_status = self.determine_data_status()
            _label_map = {
                "REAL-TIME": "REAL-TIME",
                "PRE-OPEN": "PRE-OPEN",
                "AFTER-HOURS": "AFTER-HRS",
                "EOD": "EOD",
                "FROZEN": "FROZEN",
                "NONE": "NO DATA",
            }
            _current_label = self.data_status_label.text() if hasattr(self, "data_status_label") else ""  # noqa: E501
            _target_label = _label_map.get(_correct_status, "NO DATA")
            if _current_label != _target_label:
                self.update_data_status(_correct_status)
                self.connection_info.market_data_status = _correct_status

        except Exception as e:
            # Suppress frequent errors in logs
            if not hasattr(self, "_error_count"):
                self._error_count = 0

            self._error_count += 1
            if self._error_count <= 5:  # Only show first 5 errors
                self.add_system_log(f"⚠️ Real data update error: {e}")

    def update_toolbar_with_real_data(self, live_data):
        """Update toolbar indices with real data"""
        try:
            now_et = datetime.now(_get_eastern_timezone())
            presentations = build_toolbar_index_presentations(
                live_data,
                now_et=now_et,
                market_hours_open=is_market_hours(now_et),
                realtime_quote_max_age_seconds=REALTIME_QUOTE_MAX_AGE_SECONDS,
                dji_from_dia_multiplier=self._dji_from_dia_multiplier,
                positive_color=COLORS["positive"],
                negative_color=COLORS["negative"],
            )

            for prefix, presentation in presentations.items():
                value_widget = getattr(self, f"{prefix}_value", None)
                if value_widget is not None:
                    value_widget.setText(presentation.value_text)

                change_widget = getattr(self, f"{prefix}_change", None)
                if change_widget is not None:
                    change_widget.setText(presentation.change_text)
                    change_widget.setStyleSheet(f"color: {presentation.change_color};")

        except Exception as e:
            self.logger.debug("Toolbar update error: %s", e)

    def update_status_for_real_data(self):
        """Update status indicators when real file data has been loaded."""
        if self.data_file.exists():
            try:
                with open(self.data_file, encoding="utf-8") as _f:
                    live_data = json.load(_f)
                fetch_time = _market_data_datetime_from_epoch_ms(live_data.get("_fetch_time_ms"))
                if fetch_time is not None:
                    self.connection_info.last_market_data_fetch_time = fetch_time
            except Exception:
                pass

        resolved_status = self.determine_data_status()
        self.update_data_status(resolved_status)
        self.connection_info.market_data_status = resolved_status

    def refresh_market_data(self):
        """Enhanced refresh market data - callback for refresh icon click"""
        try:
            if self.real_data_active:
                self.add_system_log("🔥 Refreshing real market data...")

                # Force immediate update
                self.update_with_real_data()

                self.add_system_log("✅ Real market data refreshed")

            elif self.market_worker:
                self.add_system_log("🔥 Requesting Tradier market data...")

                if not self.api_connected:
                    self.add_system_log(
                        "⚠️ Tradier API is not connected - waiting for the next available EOD or live snapshot",
                    )

                self.add_system_log("✅ Market data refresh requested")
            else:
                self.add_system_log("❌ Market worker not available")

        except Exception as e:
            self.logger.exception("Error refreshing market data: %s", e)
            self.add_system_log(f"❌ Refresh error: {e}")

    # ==========================================================================
    # UI CREATION METHODS - FIXED TOOLBAR WITH HEARTBEAT
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete UI"""
        self.setWindowTitle("SPYDER - Autonomous Options Trading System v1.0")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.showMaximized()

        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {COLORS["background"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
                    market_open_delay_ms = max(0, int((loading_start_at - now_et).total_seconds() * 1000))
            }}
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS["background"]};
            }}
            QGroupBox::title {{
                    if getattr(self, "_session_supervisor", None) is not None and not getattr(self, "trading_active", False):
                        self._set_start_button_loading_live_data_state()
                left: 10px;
                padding: 0 5px 0 5px;
                    "⏳ ENTRY gate remains blocked until 10:15 ET"
            QPushButton {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 8px;
                border-radius: 3px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS["panel"]};
                alternate-background-color: {COLORS["background"]};
                color: {COLORS["text"]};
                gridline-color: {COLORS["grid"]};
                border: 1px solid {COLORS["border"]};
                font-size: 11px;
            }}
            QTableWidgetItem {{
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {COLORS["background"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 5px;
                font-size: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
            }}
        """,
        )

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(3)

        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)

        # Seed the PMR row with its disabled/armed default before any worker
        # connects, so it never sits blank at startup.
        try:
            import os as _os_pmr
            self._pmr_row_state = {
                "enabled": _os_pmr.environ.get("SPYDER_PIVOT_MR_ENABLED", "0") == "1",
                "available": True,
                "fired": False,
                "direction": None,
                "score": None,
                "level_name": None,
                "level_price": None,
                "atr_distance": None,
                "reasons": [],
                "penalties": [],
            }
            pmr_widget = self.symbol_widgets.get("PMR") if hasattr(self, "symbol_widgets") else None
            if pmr_widget is not None:
                pmr_widget.update_pmr_state(self._pmr_row_state)
        except (AttributeError, RuntimeError):
            pass

            # Optional symbols may not have an active producer at startup. Render
            # a clear unavailable state instead of leaving placeholder dashes.
            self._seed_optional_symbol_placeholders()

        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)

        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)

        content_splitter.setSizes([340, 970, 610])

        main_layout.addWidget(content_splitter)
        central_widget.setLayout(main_layout)

    def _seed_optional_symbol_placeholders(self) -> None:
        """Set explicit placeholders for optional Market Overview symbols."""
        optional_symbols = ("WRS", "PSR", "PCA-PROXY", "PCA-IV", "NYMO", "$VOLD")
        for sym in optional_symbols:
            widget = self.symbol_widgets.get(sym) if hasattr(self, "symbol_widgets") else None
            if widget is None or not hasattr(widget, "price_label"):
                continue
            text = (widget.price_label.text() or "").strip()
            if text.startswith("---"):
                try:
                    widget.set_unavailable("N/A")
                except (AttributeError, RuntimeError):
                    # Fallback for legacy widgets lacking set_unavailable().
                    widget.update_data({"last": 0.0, "change": 0.0, "change_pct": 0.0})

    def _start_optional_signal_refresh_timer(self) -> None:
        """Start periodic, non-blocking refresh for optional Market Overview rows."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if self._optional_signal_timer is not None:
            return
        self._optional_signal_timer = QTimer(self)
        self._optional_signal_timer.setInterval(120000)  # 2 minutes
        self._optional_signal_timer.timeout.connect(self._dispatch_optional_signal_refresh)
        self._optional_signal_timer.start()
        # Kick once immediately after startup to populate rows quickly.
        self._dispatch_optional_signal_refresh()

    def _dispatch_optional_signal_refresh(self) -> None:
        """Spawn a background worker that reads WRS/PSR cache-backed signals."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if self._optional_signal_refresh_inflight:
            return
        self._optional_signal_refresh_inflight = True

        def _worker() -> None:
            updates: dict[str, dict[str, float]] = {}
            try:
                try:
                    from SpyderS_Signals.SpyderS12_WRSSignal import get_wrs_signal
                    wrs_payload = get_wrs_signal().get_signal_dict()
                    wrs_value = wrs_payload.get("wrs")
                    if isinstance(wrs_value, (int, float)):
                        updates["WRS"] = {"value": float(wrs_value)}
                except Exception:
                    pass

                try:
                    from SpyderS_Signals.SpyderS13_PSRSignal import get_psr_signal
                    psr_payload = get_psr_signal().get_signal_dict()
                    psr_value = psr_payload.get("psr")
                    if isinstance(psr_value, (int, float)):
                        updates["PSR"] = {"value": float(psr_value)}
                except Exception:
                    pass

                if updates:
                    self.optional_metrics_refreshed.emit(updates)
            finally:
                self._optional_signal_refresh_inflight = False

        threading.Thread(target=_worker, daemon=True).start()

    def _on_optional_metrics_refreshed(self, metrics: dict) -> None:
        """Apply asynchronously fetched optional metrics onto Market Overview rows."""
        if not isinstance(metrics, dict) or not metrics:
            return
        self._on_custom_metrics_updated(metrics)

    def _create_event_clock_panel(self) -> QGroupBox:
        """Create event-clock status display panel (Phase 5-A).
        
        Returns a compact panel showing:
        - Current event-clock state (pre/live/post/clear)
        - Policy configuration (enabled/sources)
        - Blackout window settings
        - Allowed strategies
        """  # noqa: W293
        panel = QGroupBox("EVENT-CLOCK STATUS")
        panel.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                margin-top: 5px;
                padding-top: 5px;
                background-color: {COLORS["panel"]};
                font-weight: bold;
                font-size: 11px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """)
  # noqa: W293
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
  # noqa: W293
        # State label (main indicator)
        self.event_clock_state_label = QLabel("✓ CLEAR")
        self.event_clock_state_label.setStyleSheet(f"color: {COLORS['positive']}; font-weight: bold; font-size: 12px;")  # noqa: E501
        layout.addWidget(self.event_clock_state_label)
  # noqa: W293
        # Policy label
        self.event_clock_policy_label = QLabel("Policy: ✓ Enabled | Sources: calendar+manual")
        self.event_clock_policy_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")  # noqa: E501
        layout.addWidget(self.event_clock_policy_label)
  # noqa: W293
        # Blackout windows label
        self.event_clock_windows_label = QLabel("Blackout: -30m / +30m | Size: 25%")
        self.event_clock_windows_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")  # noqa: E501
        layout.addWidget(self.event_clock_windows_label)
  # noqa: W293
        # Allowed strategies label
        self.event_clock_strategies_label = QLabel("Allowlist: None")
        self.event_clock_strategies_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")  # noqa: E501
        layout.addWidget(self.event_clock_strategies_label)

        # Manual override toggle
        self.event_clock_override_active = False
        self.event_clock_override_button = QPushButton("Manual Blackout: OFF")
        self.event_clock_override_button.setCheckable(True)
        self.event_clock_override_button.clicked.connect(self._toggle_event_clock_override)
        self.event_clock_override_button.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 10px;"
        )
        layout.addWidget(self.event_clock_override_button)
  # noqa: W293
        panel.setLayout(layout)
        self.event_clock_panel = panel
  # noqa: W293
        return panel

    def create_toolbar(self) -> QWidget:
        """Create top toolbar with FIXED WIDTH status containers and heartbeat monitor."""
        return build_toolbar(self)

    def create_left_panel(self) -> QWidget:
        """Create left panel with market overview"""
        return build_left_panel(self, MARKET_SYMBOLS)

    def create_center_panel(self) -> QWidget:
        """Create center panel (UNCHANGED)"""
        return build_center_panel(self)

    def toggle_chart(self):
        """Toggle the SPY chart visibility to provide more space for positions table"""
        if self.chart_visible:
            # Hide chart
            self.chart_widget.hide()
            if self.chart_hidden_controls_panel is not None:
                self.chart_hidden_controls_panel.show()
            self.chart_visible = False
            self.chart_toggle_btn.setToolTip("Show SPY Chart (5-min)")
            self.log_system_message("Chart hidden - Advanced controls shown")
        else:
            # Show chart
            self.chart_widget.show()
            if self.chart_hidden_controls_panel is not None:
                self.chart_hidden_controls_panel.hide()
            self.chart_visible = True
            self.chart_toggle_btn.setToolTip("Hide SPY Chart (5-min)")
            self.log_system_message("Chart visible")

    def create_right_panel(self) -> QWidget:
        """Create right panel with controls and metrics (UNCHANGED EXCEPT BUTTON MESSAGES)"""
        return build_right_panel(self)

    def _acct_lbl(self, text: str, style: str, right: bool = False) -> QLabel:
        """Helper: create a styled account-grid cell label."""
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        if right:
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def create_chart(self):
        """Create the SPY chart widget (UNCHANGED)"""
        create_chart_widget(self)

    def _load_chart_candles_from_cache(self) -> tuple[list[dict], bool]:
        """Return cached chart bars and whether they should be filtered to today."""
        current_chart_file = self.data_file.parent / "spy_5min_chart.json"
        prev_day_chart_file = self.data_file.parent / "spy_5min_prev_day.json"

        if is_market_hours():
            candidate_files = ((current_chart_file, True),)
        else:
            candidate_files = (
                (prev_day_chart_file, False),
                (current_chart_file, False),
            )

        loaded_caches: list[tuple[object, bool]] = []
        for chart_file, filter_to_today in candidate_files:
            if not chart_file.exists():
                continue
            try:
                with open(chart_file) as _f:
                    candles = json.load(_f)
            except (OSError, json.JSONDecodeError) as chart_err:
                logger.debug("Could not read chart cache %s: %s", chart_file, chart_err)
                continue
            loaded_caches.append((candles, filter_to_today))

        return build_cached_chart_candles_result(loaded_caches)

    def update_chart(self):
        """Update the SPY intraday chart — fixed 9:30–4:00 ET session, line chart."""
        if self.figure is None or self.canvas is None:
            return

        self.figure.clear()

        # --- Load real 5-min bars from cache file written by the market data worker ---
        opens_raw: list[float] = []
        highs_raw: list[float] = []
        lows_raw: list[float] = []
        closes_raw: list[float] = []
        volumes_raw: list[int] = []
        dates_raw: list = []

        candles, filter_to_today = self._load_chart_candles_from_cache()
        preferred_target_date = (
            datetime.now(_get_eastern_timezone()).date() if filter_to_today else None
        )
        bar_series: CachedChartBarSeries = build_cached_chart_bar_series(
            candles,
            preferred_target_date,
            _parse_chart_bar_timestamp,
        )
        opens_raw = bar_series.opens
        highs_raw = bar_series.highs
        lows_raw = bar_series.lows
        closes_raw = bar_series.closes
        volumes_raw = bar_series.volumes
        dates_raw = bar_series.dates

        # If no real data yet, show a "waiting for data" placeholder
        if not closes_raw:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(COLORS["panel"])
            ax.text(
                0.5, 0.5, "Waiting for 5-min bar data…",
                ha="center", va="center", color="#888888",
                fontsize=12, transform=ax.transAxes,
            )
            for spine in ax.spines.values():
                spine.set_color(COLORS["border"])
            self.canvas.draw_idle()
            return

        # --- Fixed 78-slot session skeleton: slots 0–77 map to 9:30–15:55 (5-min bars) ---
        # Slot index = (bar_minutes_since_midnight - 570) // 5  where 570 = 9h30m
        TOTAL_SLOTS = 78  # 6.5 hours × 12 bars/hour
        OPEN_MINUTES = 9 * 60 + 30  # 570

        slot_closes = np.full(TOTAL_SLOTS, np.nan)
        slot_opens  = np.full(TOTAL_SLOTS, np.nan)
        slot_highs  = np.full(TOTAL_SLOTS, np.nan)
        slot_lows   = np.full(TOTAL_SLOTS, np.nan)

        for i, dt in enumerate(dates_raw):
            slot = (dt.hour * 60 + dt.minute - OPEN_MINUTES) // 5
            if 0 <= slot < TOTAL_SLOTS:
                slot_closes[slot] = closes_raw[i]
                slot_opens[slot]  = opens_raw[i]
                slot_highs[slot]  = highs_raw[i]
                slot_lows[slot]   = lows_raw[i]

        # Previous close reference — use first bar's open so the dashed line is
        # the "where we started" anchor (analogous to prior-close in Google Finance)
        prev_close = opens_raw[0]
        last_close = closes_raw[-1]
        line_color = COLORS["positive"] if last_close >= prev_close else COLORS["negative"]  # noqa: F841

        # --- Compute chart indicators on raw bars (audit §3) ---
        # Load previous session's daily H/L/C so pivot levels stay fixed all
        # day (floor-trader convention: pivots derive from yesterday, not today).
        _prev_day_tuple: tuple[float, float, float] | None = None
        _prev_day_file = self.data_file.parent / "spy_prev_day.json"
        if _prev_day_file.exists():
            try:
                with open(_prev_day_file) as _pdf:
                    _pd = json.load(_pdf)
                _prev_day_tuple = (float(_pd["high"]), float(_pd["low"]), float(_pd["close"]))
            except Exception:
                pass

        try:
            indicators = compute_chart_indicators(highs_raw, lows_raw, closes_raw, volumes_raw, prev_day=_prev_day_tuple)  # noqa: E501
        except ValueError:
            indicators = None

        if indicators is not None:
            pivot = indicators.pivots.pivot
            r1 = indicators.pivots.r1
            r2 = indicators.pivots.r2
            r3 = indicators.pivots.r3
            s1 = indicators.pivots.s1
            s2 = indicators.pivots.s2
            s3 = indicators.pivots.s3
            ma_20_raw = indicators.ma20
            vwap_raw = indicators.vwap
        else:
            pivot = r1 = r2 = r3 = s1 = s2 = s3 = last_close
            ma_20_raw = [None] * len(closes_raw)
            vwap_raw = closes_raw[:]

        # Map MA(20) and VWAP from bar-index space to slot-index space
        ma_slot_x: list[int] = []
        ma_slot_y: list[float] = []
        vwap_slot_x: list[int] = []
        vwap_slot_y: list[float] = []
        for i, dt in enumerate(dates_raw):
            slot = (dt.hour * 60 + dt.minute - OPEN_MINUTES) // 5
            if 0 <= slot < TOTAL_SLOTS:
                if i < len(ma_20_raw) and ma_20_raw[i] is not None:
                    ma_slot_x.append(slot)
                    ma_slot_y.append(ma_20_raw[i])
                if i < len(vwap_raw):
                    vwap_slot_x.append(slot)
                    vwap_slot_y.append(vwap_raw[i])

        # --- Create plot ---
        ax = self.figure.add_subplot(111)
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")
        ax.set_facecolor(COLORS["panel"])

        # x-axis always spans the full session: slot -0.5 → 78.5
        # Slot 78 is used as the "4:00 PM" tick label (session end boundary)
        ax.set_xlim(-0.5, 78.5)

        # Fibonacci Daily Pivot Points
        ax.axhline(y=pivot, color="#FFFF00", linewidth=1.5, linestyle="-", alpha=0.7, label="Pivot", zorder=1)  # noqa: E501
        ax.axhline(y=r1, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R1", zorder=1)  # noqa: E501
        ax.axhline(y=r2, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R2", zorder=1)  # noqa: E501
        ax.axhline(y=r3, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R3", zorder=1)  # noqa: E501
        ax.axhline(y=s1, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S1", zorder=1)  # noqa: E501
        ax.axhline(y=s2, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S2", zorder=1)  # noqa: E501
        ax.axhline(y=s3, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S3", zorder=1)  # noqa: E501

        # Prior-close reference line (dashed grey — anchors the day's move)
        ax.axhline(y=prev_close, color="#888888", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)  # noqa: E501

        # MA(20) overlay
        if ma_slot_x:
            ax.plot(ma_slot_x, ma_slot_y, color="#00FFFF", linewidth=1.1, alpha=0.90, label="MA(20)", zorder=2)  # noqa: E501

        # VWAP overlay — smooth solid white line
        if vwap_slot_x:
            _vwap_color = COLORS.get("text", "#FFFFFF")
            ax.plot(
                vwap_slot_x,
                vwap_slot_y,
                color=_vwap_color,
                linewidth=0.8,
                linestyle="-",
                alpha=1.0,
                solid_capstyle="butt",
                label="VWAP",
                zorder=3,
            )

        # Candlestick bars — bodies via bar(), wicks via vlines()
        slot_indices = np.arange(TOTAL_SLOTS)
        valid = ~np.isnan(slot_closes)
        xs      = slot_indices[valid]
        op      = slot_opens[valid]
        hi      = slot_highs[valid]
        lo      = slot_lows[valid]
        cl      = slot_closes[valid]
        body_lo = np.minimum(op, cl)
        body_hi = np.maximum(op, cl)
        is_up   = cl >= op
        bar_colors = np.where(is_up, COLORS["positive"], COLORS["negative"])
        # Draw wicks first (behind bodies)
        # Vectorised wick drawing — one LineCollection per colour group instead of
        # 78 individual vlines() calls (each creates a separate LineCollection).
        wick_colors = np.where(is_up, COLORS["positive"], COLORS["negative"])
        ax.vlines(xs, lo, hi, colors=wick_colors, linewidth=0.5, zorder=2)
        # Draw bodies
        ax.bar(xs, height=body_hi - body_lo, bottom=body_lo, width=0.45,
               color=bar_colors, align="center", edgecolor="none", linewidth=0, zorder=3)

        # Pivot level labels on the right (just beyond slot 78)
        label_x = 79
        ax.text(label_x, pivot, f" P: {pivot:.2f}", color="#FFFF00", fontsize=9, va="center")
        ax.text(label_x, r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(label_x, r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(label_x, r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(label_x, s1, f" S1: {s1:.2f}", color="#FF073A", fontsize=8, va="center")
        ax.text(label_x, s2, f" S2: {s2:.2f}", color="#FF073A", fontsize=8, va="center")
        ax.text(label_x, s3, f" S3: {s3:.2f}", color="#FF073A", fontsize=8, va="center")

        # Fixed hourly x-axis ticks — always present regardless of bars received
        # slot 0=9:30, 6=10:00, 18=11:00, 30=12:00, 42=1:00, 54=2:00, 66=3:00, 78=4:00
        ax.set_xticks([0, 6, 18, 30, 42, 54, 66, 78])
        ax.set_xticklabels(["9:30", "10:00", "11:00", "12:00", "1:00", "2:00", "3:00", "4:00"], fontsize=9)  # noqa: E501

        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)
        ax.tick_params(colors="#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        # Use fixed margins instead of tight_layout() — tight_layout() synchronously
        # measures font extents for every artist, which can take 1–5 s on a complex
        # chart and stalls the Qt event loop long enough to trigger the OS
        # "Not Responding" dialog.  The pivot labels at label_x=79 sit outside the
        # axes clip region, so right=0.86 gives them enough room at any window size.
        self.figure.subplots_adjust(left=0.07, right=0.86, top=0.97, bottom=0.10)
        self.canvas.draw_idle()

    def create_positions_table(self) -> QTreeWidget:
        """Create positions tree with strategy headers and expandable trade legs."""
        return build_positions_table(self)

    def _positions_context_menu(self, pos):
        """Show right-click context menu for positions tree."""
        item = self.positions_table.itemAt(pos)
        if not item:
            return

        # Determine if this is a strategy header or a leg
        is_strategy = item.parent() is None
        strategy_item = item if is_strategy else item.parent()
        strategy_item.data(0, Qt.ItemDataRole.UserRole) or ""
        status = strategy_item.data(1, Qt.ItemDataRole.UserRole) or ""  # noqa: F841

        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 4px;
            }}
            QMenu::item:selected {{
                background-color: #2a3a4a;
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS["border"]};
                margin: 4px 8px;
            }}
        """,
        )

        # Close / Roll / Adjust actions intentionally absent until an
        # OrderManager service is wired. A do-nothing context-menu item
        # misleads traders (see 2026-04-15 audit §24).

        if is_strategy:
            expand_action = menu.addAction(
                "\u25b8  Collapse" if item.isExpanded() else "\u25be  Expand",
            )
            expand_action.triggered.connect(
                lambda: item.setExpanded(not item.isExpanded()),
            )

        copy_action = menu.addAction("\U0001f4cb  Copy Details")
        copy_action.triggered.connect(
            lambda: self._on_copy_strategy(strategy_item),
        )

        menu.exec(self.positions_table.viewport().mapToGlobal(pos))

    def _on_copy_strategy(self, strategy_item: QTreeWidgetItem):
        """Copy strategy and leg details to clipboard."""
        lines = [strategy_item.text(0)]
        for i in range(strategy_item.childCount()):
            child = strategy_item.child(i)
            parts = [child.text(c) for c in range(self.positions_table.columnCount())]
            lines.append("    " + "\t".join(parts))
        text = "\n".join(lines)
        from PySide6.QtWidgets import QApplication as _QApp
        clipboard = _QApp.clipboard()
        if clipboard:
            clipboard.setText(text)
            name = strategy_item.data(0, Qt.ItemDataRole.UserRole) or "strategy"
            self.add_system_log(f"Copied {name} to clipboard")

    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table (UNCHANGED)"""
        return build_pnl_table()

    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (8 clients in 4x2 grid + 2 empty rows)"""
        return build_unified_prometheus_metrics(self)

    # ==========================================================================
    # SIGNAL HANDLERS - ENHANCED WITH HEARTBEAT
    # ==========================================================================
    @Slot(bool, str)
    def on_connection_status_changed(self, connected: bool, status: str):
        """Handle connection status change and synchronize UI state."""
        handle_connection_status_changed(self, connected, status)

    @Slot(str)
    def on_heartbeat_status_changed(self, status: str):
        """Handle heartbeat status transitions for toolbar indicators."""
        handle_heartbeat_status_changed(self, status)

    @Slot(str)
    def on_market_data_status_changed(self, status: str):
        """Handle market-data status transitions from the worker."""
        handle_market_data_status_changed(self, status)

    @Slot(dict)
    def on_market_data_updated(self, data: dict):
        """Handle market data updates from the market worker."""
        handle_market_data_updated(self, data)

    @Slot(str)
    def on_market_error(self, error: str):
        """Handle market error"""
        handle_market_error(self, error)

    @Slot(str)
    def on_heartbeat_received(self, message: str):
        """Handle heartbeat message - FIXED to route to system log"""
        handle_heartbeat_received(self, message)

    def toggle_api_connection(self, event):
        """Toggle API connection when clicking on status - UNCHANGED"""
        if self.api_connected:
            if self.trading_active:
                reply = QMessageBox.warning(
                    self,
                    "Trading Active",
                    "Trading is currently active.\n\n"
                    "Disconnecting will stop all trading activities.\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply != QMessageBox.StandardButton.Yes:
                    return

                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;",
                )
                self.start_btn.setText("START TRADING")

                self.add_system_log("Trading stopped due to API disconnection")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.api_connected = False
            self.add_system_log("Manually disconnected from API")
        else:
            if not is_market_hours():
                QMessageBox.information(
                    self,
                    "Market Closed",
                    "Market is closed. Connection available during trading hours:\n"
                    "4:00 AM - 4:30 PM ET",
                )
                return

            # Try to create a new API connection if we don't have a client
            if not hasattr(self, "tradier_client") or self.tradier_client is None:
                self.add_system_log("🔄 Creating new Tradier API connection...")
                if self.create_api_connection():
                    self.add_system_log("✅ Successfully connected to Tradier API!")
                    return
                self.add_system_log(
                    "❌ Failed to connect to Tradier API",
                )
                QMessageBox.warning(
                    self,
                    "Connection Failed",
                    "Could not connect to Tradier API.\n\n"
                    "Check your API credentials and try again.",
                )
                return

            # Otherwise use the market worker's force_connect (socket check)
            if self.market_worker and self.market_worker.force_connect():
                self.api_connected = True
                self.add_system_log("Manually connected to API")
            else:
                self.add_system_log("Failed to connect to API")

    # ==========================================================================
    # ORDERS & POSITIONS — LIVE DATA
    # ==========================================================================

    def _get_tradier_client_for_mode(self, mode: "TradingMode | None" = None) -> "TradierClient | None":  # noqa: E501
        """Return a usable TradierClient for the given mode.

        Policy: dashboard broker calls always use LIVE Tradier credentials.
        PAPER mode is simulated in SpyderBox/local state and never targets
        Tradier sandbox.
        """
        if not TRADIER_AVAILABLE or create_tradier_client_from_env is None:
            return None
        if self.tradier_client is not None:
            existing_env = getattr(self.tradier_client, "environment", None)
            if existing_env == TradingEnvironment.LIVE:
                return self.tradier_client
            self.add_system_log("⚠️ Discarding non-live Tradier client (live-only policy)")
            self.tradier_client = None

        env = TradingEnvironment.LIVE
        try:
            client = create_tradier_client_from_env(environment=env)
            self.tradier_client = client
            return client
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not create Tradier client: {exc}")
            return None

    def _fetch_pending_orders(self, mode: "TradingMode | None" = None) -> list[dict]:
        """Thin wrapper — delegates to DashboardOrderManager (audit §5)."""
        mode = mode or self.trading_mode
        if mode == TradingMode.PAPER:
            return []
        self._order_manager.set_client(self._get_tradier_client_for_mode(mode))
        return self._order_manager.fetch_pending_orders()

    def _cancel_orders(
        self, orders: list[dict], mode: "TradingMode | None" = None
    ) -> tuple[int, int]:
        """Thin wrapper — delegates to DashboardOrderManager (audit §5)."""
        mode = mode or self.trading_mode
        if mode == TradingMode.PAPER:
            return 0, 0
        self._order_manager.set_client(self._get_tradier_client_for_mode(mode))
        ok, fail = self._order_manager.cancel_orders(orders)
        for order in orders[:ok]:
            self.add_system_log(f"✅ Cancelled order #{order.get('id')}")
        return ok, fail

    def _open_trade_audit_dialog(self) -> None:
        """Open (or raise) the Trade Audit dialog with the cached closed-spread log.

        The dialog is held as a non-modal singleton so the user can keep it
        open alongside the dashboard. Subsequent worker emits push fresh
        rows in via update_trades(), so the dialog reflects new closes
        without requiring a manual refresh.
        """
        from Spyder.SpyderG_GUI.SpyderG22_TradeAuditDialog import TradeAuditDialog
        existing = getattr(self, "_trade_audit_dialog", None)
        if existing is not None and existing.isVisible():
            existing.update_trades(self._closed_trades_cache)
            existing.raise_()
            existing.activateWindow()
            return
        dlg = TradeAuditDialog(self._closed_trades_cache, parent=self)
        dlg.finished.connect(lambda *_: setattr(self, "_trade_audit_dialog", None))
        self._trade_audit_dialog = dlg
        dlg.show()

    def _open_decision_log_dialog(self) -> None:
        """Open (or raise) the Decision Log dialog.

        Shows the gate-by-gate JSON-lines audit records written by R08 for
        every 30-second poll.  The dialog auto-refreshes while open; it is
        a non-modal singleton so it can stay open beside the dashboard.
        """
        from Spyder.SpyderG_GUI.SpyderG23_DecisionLogDialog import DecisionLogDialog
        existing = getattr(self, "_decision_log_dialog", None)
        if existing is not None and existing.isVisible():
            existing.force_refresh()
            existing.raise_()
            existing.activateWindow()
            return
        dlg = DecisionLogDialog(parent=self)
        dlg.finished.connect(lambda *_: setattr(self, "_decision_log_dialog", None))
        self._decision_log_dialog = dlg
        dlg.show()

    # ------------------------------------------------------------------
    # TODAY'S PORTFOLIO SUMMARY popup
    # ------------------------------------------------------------------

    def _open_portfolio_summary_dialog(self) -> None:
        """Open (or raise + refresh) the Today's Portfolio Summary dialog.

        The dialog shows a three-column table:
            Metric  |  Explanation  |  Colour Logic
        Values are read from ``_portfolio_summary_cache`` (the last
        ``position_update`` payload received from the paper/live worker).
        While the dialog is open it is refreshed automatically each time
        new data arrives.
        """
        existing = self._portfolio_summary_dialog
        if existing is not None and existing.isVisible():
            self._populate_portfolio_summary_table(existing)
            existing.raise_()
            existing.activateWindow()
            return

        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtWidgets import (
            QDialog as _QDialog,
            QHBoxLayout as _QHBox,
            QHeaderView as _QHV,
            QLabel as _QLabel,
            QPushButton as _QPB,
            QTableWidget as _QTW,
            QTableWidgetItem as _QTWI,  # noqa: F401
            QVBoxLayout as _QVBox,
        )

        dlg = _QDialog(self)
        dlg.setWindowTitle("TODAY'S PORTFOLIO SUMMARY")
        dlg.setMinimumSize(1060, 620)
        dlg.resize(1060, 620)
        dlg.setStyleSheet(
            f"background-color: {COLORS['background']}; color: {COLORS['text']};"
        )
        layout = _QVBox(dlg)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Sub-title / last-updated line
        dlg._updated_label = _QLabel("Last updated: —")
        dlg._updated_label.setStyleSheet(
            "color: #b8b8b8; font-size: 12px;"
        )
        layout.addWidget(dlg._updated_label)

        # Three-column table
        tbl = _QTW(0, 3)
        tbl.setHorizontalHeaderLabels(["Metric", "Explanation", "Colour Logic"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(_QTW.NoEditTriggers)
        tbl.setSelectionMode(_QTW.NoSelection)
        tbl.setFocusPolicy(_Qt.NoFocus)
        tbl.setStyleSheet(
            f"QTableWidget {{ background-color: {COLORS['panel']};"
            f" gridline-color: {COLORS['border']}; border: none; }}"
            f"QTableWidget::item {{ padding: 6px 10px; font-size: 13px; }}"
            f"QHeaderView::section {{ background-color: {COLORS['panel']};"
            f" color: #c8c8c8; font-size: 12px; font-weight: bold;"
            f" padding: 5px 10px; border: none;"
            f" border-bottom: 1px solid {COLORS['border']}; }}"
        )
        tbl.setVerticalScrollBarPolicy(_Qt.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(_Qt.ScrollBarAlwaysOff)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, _QHV.ResizeToContents)
        hdr.setSectionResizeMode(1, _QHV.Stretch)
        hdr.setSectionResizeMode(2, _QHV.ResizeToContents)
        tbl.setWordWrap(True)
        tbl.setShowGrid(True)
        dlg._table = tbl
        layout.addWidget(tbl)

        # Button row
        btn_row = _QHBox()
        btn_row.addStretch()
        refresh_btn = _QPB("⟳ Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setStyleSheet(
            f"font-size: 13px; padding: 0 12px; background-color: {COLORS['panel']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border']};"
            f" border-radius: 3px;"
        )
        refresh_btn.clicked.connect(lambda: self._populate_portfolio_summary_table(dlg))
        close_btn = _QPB("Close")
        close_btn.setFixedHeight(28)
        close_btn.setStyleSheet(refresh_btn.styleSheet())
        close_btn.clicked.connect(dlg.close)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.finished.connect(lambda *_: setattr(self, "_portfolio_summary_dialog", None))
        self._portfolio_summary_dialog = dlg
        self._populate_portfolio_summary_table(dlg)
        dlg.show()

    def _populate_portfolio_summary_table(self, dlg: "QDialog") -> None:  # noqa: F821
        """Fill (or refresh) the portfolio summary table inside *dlg*.

        Reads ``_portfolio_summary_cache`` (the raw last ``position_update``
        payload) and populates each row with a colour-coded value, a plain-
        English explanation, and the threshold legend for that metric.
        """
        from datetime import datetime as _dt
        from PySide6.QtGui import QColor as _QColor
        from PySide6.QtWidgets import QTableWidgetItem as _QTWI

        data = self._portfolio_summary_cache
        now_str = _dt.now().strftime("%H:%M:%S ET")
        lbl = getattr(dlg, "_updated_label", None)
        if lbl is not None:
            lbl.setText(f"Last updated: {now_str}")

        tbl = dlg._table

        # --- derive values from cache ---
        spreads_detail = data.get("open_spreads_detail") or []
        spreads_mtm = float(data.get("spreads_unrealized_pnl", 0.0) or 0.0)
        atm_iv_raw = data.get("atm_iv")
        iv_rank = data.get("iv_rank")
        greeks = data.get("portfolio_greeks") or {}

        # Realized P&L
        realized_raw = data.get("realized_pnl_today") or data.get("realized_pnl", 0.0)
        try:
            realized = float(realized_raw)
        except (TypeError, ValueError):
            realized = 0.0

        # Buying power
        bp_usage = calculate_buying_power_usage(
            spreads_detail,
            capital_raw=getattr(self, "_paper_initial_capital", 100_000.0),
            default_capital=100_000.0,
        )
        rows = build_portfolio_summary_rows(
            open_count=len(spreads_detail),
            spreads_mtm=spreads_mtm,
            realized=realized,
            atm_iv_raw=atm_iv_raw,
            iv_rank=iv_rank,
            greeks=greeks,
            bp_usage=bp_usage,
            colors=COLORS,
        )

        tbl.setRowCount(len(rows))
        _cell_style = (
            f"background-color: {COLORS['panel']}; padding: 4px 8px;"
        )
        for row_idx, summary_row in enumerate(rows):
            for col_idx, text in enumerate((
                summary_row.text,
                summary_row.explanation,
                summary_row.legend,
            )):
                item = _QTWI(text)
                item.setTextAlignment(0x0081)  # AlignLeft | AlignVCenter
                if col_idx == 0:
                    item.setForeground(_QColor(summary_row.color))
                    from PySide6.QtGui import QFont as _QFont
                    f = _QFont("monospace", 12)
                    f.setBold(True)
                    item.setFont(f)
                elif col_idx == 1:
                    item.setForeground(_QColor("#e8e8e8"))
                    from PySide6.QtGui import QFont as _QFont
                    item.setFont(_QFont("sans-serif", 12))
                else:
                    item.setForeground(_QColor("#ffffff"))
                    from PySide6.QtGui import QFont as _QFont
                    item.setFont(_QFont("sans-serif", 11))
                tbl.setItem(row_idx, col_idx, item)

        tbl.resizeRowsToContents()

    @Slot()
    def _refresh_positions_table(self) -> None:
        """Fetch live orders & positions from Tradier and repopulate the table.

        Falls back silently (keeping existing rows) when no API client is
        available or on network error.  Called by the Refresh button and
        automatically after a successful API connection.
        """
        if not self.positions_table:
            return

        # In paper trading mode the live account endpoints are not used;
        # paper positions are tracked internally by _PaperTradingWorker.
        if getattr(self, "trading_mode", None) == TradingMode.PAPER:
            cached = getattr(self, "_portfolio_summary_cache", None)
            cached_has_activity = False
            if isinstance(cached, dict) and cached:
                cached_has_activity = bool(cached.get("open_spreads_detail") or cached.get("closed_trades"))
                if not cached_has_activity:
                    cached_has_activity = any(
                        abs(coerce_float(cached.get(key), 0.0) or 0.0) > 0.0
                        for key in ("unrealized_pnl", "realized_pnl", "spreads_unrealized_pnl")
                    )
            if cached_has_activity:
                self._refresh_spreads_panel(cached)
            else:
                hydrated = self._load_cached_paper_state_payload()
                if hydrated:
                    self._refresh_spreads_panel(hydrated)
                    self._set_spyderbox_account_panel_values(
                        settled=float(hydrated.get("equity", 0.0) or 0.0),
                        buying=float(hydrated.get("cash", 0.0) or 0.0),
                        unrealized=float(hydrated.get("unrealized_pnl", 0.0) or 0.0),
                        realized=float(hydrated.get("realized_pnl", 0.0) or 0.0),
                    )
                    self.add_system_log("♻️ Loaded paper positions from saved session state")
                elif isinstance(cached, dict) and cached:
                    self._refresh_spreads_panel(cached)
                else:
                    # Unified SessionSupervisor paper mode does not depend on
                    # the legacy Qt paper worker to produce the first table
                    # snapshot, so render the steady-state empty view instead
                    # of a stale waiting placeholder.
                    self._refresh_spreads_panel({
                        "open_spreads_detail": [],
                        "spreads_unrealized_pnl": 0.0,
                        "closed_trades": [],
                        "equity": 0.0,
                        "cash": 0.0,
                        "unrealized_pnl": 0.0,
                        "realized_pnl": 0.0,
                    })
            return

        if not getattr(self, "api_connected", False):
            self.add_system_log("ℹ️ Not connected — showing demo data")
            return

        client = self._get_tradier_client_for_mode()
        self._order_manager.set_client(client)

        try:
            self.positions_table.clear()
            has_rows = False

            data = self._order_manager.fetch_orders_and_positions()

            # ── Pending / open orders ─────────────────────────────────────────
            for o in data["pending_orders"]:
                self._add_order_row(o)
                has_rows = True

            # ── Open positions ────────────────────────────────────────────────
            for p in data["open_positions"]:
                self._add_position_row(p)
                has_rows = True

            if not has_rows:
                _empty = QTreeWidgetItem(self.positions_table)
                _empty.setText(0, "No open orders or positions")
                _empty.setForeground(0, Qt.GlobalColor.gray)
                self.positions_table.setFirstColumnSpanned(0, QModelIndex(), True)

            self.add_system_log("✅ Orders & positions refreshed from Tradier")

        except Exception as exc:
            self.add_system_log(f"❌ Refresh failed: {exc}")

    def _get_recent_trades(self, limit: int = 30) -> list[dict]:
        """Return most-recent trade records for the current mode (paper/live)."""
        return self._get_session_db_adapter().fetch_recent_trades(
            self._get_mode_session_db(),
            limit=limit,
            log_error=getattr(self, "add_system_log", None),
        )

    def _get_recent_trade_history_records(self, limit: int = 30) -> list[dict]:
        """Return the records shown in the Trade History dialog."""
        safe_limit = max(1, int(limit))

        if getattr(self, "trading_mode", None) == TradingMode.PAPER:
            closed_trades = getattr(self, "_closed_trades_cache", None)
            if isinstance(closed_trades, list) and closed_trades:
                return sorted(
                    closed_trades,
                    key=lambda trade: coerce_timestamp(
                        trade.get("closed_at") or trade.get("opened_at")
                    )
                    or 0.0,
                    reverse=True,
                )[:safe_limit]

            return []

        return self._get_recent_trades(limit=safe_limit)

    def _open_recent_trades_history_dialog(self) -> None:
        """Open (or raise) a dialog showing the last 30 trade records."""
        trades = self._get_recent_trade_history_records(limit=30)

        existing = getattr(self, "_recent_trades_dialog", None)
        if existing is not None and existing.isVisible():
            self._populate_recent_trades_table(existing, trades)
            existing.raise_()
            existing.activateWindow()
            return

        mode_name = "PAPER" if self.trading_mode == TradingMode.PAPER else "LIVE"
        dlg = RecentTradesDialog(mode_name=mode_name, trades=trades, parent=self)
        dlg.finished.connect(lambda *_: setattr(self, "_recent_trades_dialog", None))
        self._recent_trades_dialog = dlg
        dlg.show()

    def _populate_recent_trades_table(self, dialog: QDialog, trades: list[dict]) -> None:
        """Compatibility wrapper for dialog-managed recent trades table refresh."""
        update_trades = getattr(dialog, "update_trades", None)
        if not callable(update_trades):
            return
        update_trades(trades)

    def _add_order_row(self, order: dict) -> None:
        """Add a single Tradier order dict as a top-level row in positions_table."""
        order_id = order.get("id", "—")
        symbol = order.get("symbol") or order.get("option_symbol", "—")
        o_type = order.get("type", "—").upper()
        side = order.get("side", "—").replace("_", " ").upper()
        qty = int(order.get("quantity", 0))
        remaining = int(order.get("remaining_quantity", qty))
        status = order.get("status", "—").upper()
        o_class = order.get("class", "").lower()

        header = (
            f"ORDER #{order_id} | {symbol} | {o_type} | {side} | "
            f"QTY: {qty} | REMAINING: {remaining} | STATUS: {status}"
        )

        parent = QTreeWidgetItem(self.positions_table)
        parent.setText(0, header)
        parent.setForeground(0, Qt.GlobalColor.yellow)
        self.positions_table.setFirstColumnSpanned(
            self.positions_table.indexOfTopLevelItem(parent),
            QModelIndex(),
            True,
        )
        parent.setExpanded(True)

        # Add close button widget in last column
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            f"background-color: {COLORS['negative']}; color: white; border: none;"
            " font-size: 10px; border-radius: 2px;"
        )
        close_btn.setToolTip(f"Cancel order #{order_id}")
        close_btn.clicked.connect(lambda _=False, oid=order_id: self._cancel_order_by_id(oid))
        self.positions_table.setItemWidget(parent, self.positions_table.columnCount() - 1, close_btn)

        # For multileg orders, show each leg as a child row
        if o_class == "multileg":
            legs_node = order.get("legs", {}) or {}
            leg_list = legs_node.get("leg", [])
            if isinstance(leg_list, dict):
                leg_list = [leg_list]
            for leg in leg_list:
                leg_symbol = str(leg.get("option_symbol", "—") or "—")
                parsed_leg = parse_occ_option_contract(leg_symbol)
                strike_text = leg_symbol
                expiry_text = str(leg.get("expiration_date", "—") or "—")
                if parsed_leg:
                    parsed_strike = coerce_float(parsed_leg.get("strike"), None)
                    parsed_type = str(parsed_leg.get("option_type", "") or "").upper()[:1]
                    if parsed_strike is not None:
                        strike_text = (
                            f"${parsed_strike:.0f}{parsed_type}"
                            if parsed_type
                            else f"${parsed_strike:.0f}"
                        )
                    expiry_text = str(parsed_leg.get("expiration") or expiry_text)

                price_value = coerce_float(
                    leg.get("price", leg.get("limit_price", leg.get("avg_fill_price"))),
                    None,
                )
                price_text = f"${price_value:,.2f}" if price_value is not None else ""
                cost_text = ""
                cost_color = None
                if price_value is not None:
                    leg_side = str(leg.get("side", "") or "").lower()
                    leg_qty = abs(int(leg.get("quantity", 0) or 0))
                    signed_cost = price_value * 100.0 * leg_qty
                    if "sell" in leg_side:
                        signed_cost *= -1.0
                    cost_text = format_signed_dollars(signed_cost)
                    cost_color = COLORS["positive"] if signed_cost >= 0 else COLORS["negative"]

                child = QTreeWidgetItem(parent)
                child.setText(0, f"  {leg.get('side','—').replace('_',' ').upper()}")
                child.setText(1, strike_text)
                child.setText(2, str(int(leg.get("quantity", 0))))
                child.setText(3, price_text)
                child.setText(4, cost_text)
                child.setText(5, format_expiration_short(expiry_text) if expiry_text not in ("", "—") else "—")
                self._align_positions_data_row(child)
                if cost_color is not None:
                    child.setForeground(4, QColor(cost_color))

    def _add_position_row(self, pos: dict) -> None:
        """Add a single Tradier position dict as a top-level row in positions_table."""
        symbol = pos.get("symbol", "—")
        qty = int(pos.get("quantity", 0))
        cost_basis = float(pos.get("cost_basis", 0.0))
        date_acquired = pos.get("date_acquired", "—")[:10]  # YYYY-MM-DD

        header = (
            f"POSITION | {symbol} | QTY: {qty} | "
            f"COST BASIS: ${cost_basis:,.2f} | ACQUIRED: {date_acquired} | STATUS: OPEN"
        )
        parent = QTreeWidgetItem(self.positions_table)
        parent.setText(0, header)
        parent.setForeground(0, Qt.GlobalColor.green)
        self.positions_table.setFirstColumnSpanned(
            self.positions_table.indexOfTopLevelItem(parent),
            QModelIndex(),
            True,
        )

    def _align_positions_data_row(self, item: QTreeWidgetItem) -> None:
        """Apply ORDERS & POSITIONS data-column alignment policy.

        LEG is left aligned for easier scanning. STRIKE/QTY/EXPIRY are centered.
        PRICE/COST/P&L are right aligned.
        """
        item.setTextAlignment(0, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(1, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(2, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(3, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(4, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(5, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(6, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))

    def _get_mode_session_db(self):
        """Return cached H05 session DB for the current trading mode."""
        mode = getattr(self, "trading_mode", None)
        is_paper = mode == TradingMode.PAPER
        if self._session_db_init_failed_by_mode.get(mode, False):
            return None

        cached = self._paper_session_db if is_paper else self._live_session_db
        if cached is not None:
            return cached

        adapter = self._get_session_db_adapter()
        db = adapter.get_mode_session_db(
            mode,
            log_error=getattr(self, "add_system_log", None),
        )
        self._session_db_init_failed_by_mode[mode] = adapter.has_init_failed(mode)
        if db is None:
            return None

        if is_paper:
            self._paper_session_db = db
        else:
            self._live_session_db = db
        return db

    def _get_session_db_adapter(self) -> DashboardSessionAdapter:
        """Return the dashboard's H05 read adapter, creating it lazily for tests."""
        adapter = getattr(self, "_session_db_adapter", None)
        if adapter is None:
            adapter = DashboardSessionAdapter()
            self._session_db_adapter = adapter
        return adapter

    def _add_recent_trade_rows(self, limit: int = 3) -> int:
        """Render most-recent trades for the current mode (paper/live)."""
        if self.positions_table is None:
            return 0

        trades = self._get_recent_trades(limit=limit)
        if not trades:
            return 0

        count = 0
        for trade in trades:
            try:
                display = build_recent_trade_display(trade, symbol_placeholder="—")

                row = QTreeWidgetItem(self.positions_table)
                row.setText(0, build_recent_trade_banner_text(display))

                if display.realized_pnl_value > 0:
                    color = QColor(COLORS["positive"])
                elif display.realized_pnl_value < 0:
                    color = QColor(COLORS["negative"])
                else:
                    color = QColor(COLORS["text"])

                row.setForeground(0, color)
                self.positions_table.setFirstColumnSpanned(
                    self.positions_table.indexOfTopLevelItem(row),
                    QModelIndex(),
                    True,
                )
                count += 1
            except Exception:
                continue

        return count

    def _load_cached_paper_state_payload(self) -> dict | None:
        """Build a worker-like position payload from persisted paper state."""
        try:
            state_file = _PaperTradingWorker.STATE_FILE
            if not state_file.exists():
                return None
            with open(state_file, encoding="utf-8") as fh:
                state = json.load(fh)
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not hydrate paper state cache: {exc}")
            return None

        open_spreads = state.get("_open_spreads") or []
        if not isinstance(open_spreads, list) or not open_spreads:
            return None

        spreads_detail = []
        spreads_unrealized = 0.0
        for p in open_spreads:
            if not isinstance(p, dict):
                continue
            qty = int(p.get("qty", 0) or 0)
            credit_per = float(p.get("credit", 0.0) or 0.0)
            debit_per = float(p.get("last_debit", credit_per) or credit_per)
            mtm_pnl = (credit_per - debit_per) * 100.0 * qty
            spreads_unrealized += mtm_pnl
            raw_legs = p.get("legs") or []
            legs = raw_legs if isinstance(raw_legs, list) else []
            spreads_detail.append(
                {
                    "id": p.get("id"),
                    "expiration": p.get("expiration"),
                    "short_strike": float(p.get("short_strike", 0.0) or 0.0),
                    "long_strike": float(p.get("long_strike", 0.0) or 0.0),
                    "qty": qty,
                    "credit": credit_per,
                    "debit": debit_per,
                    "mtm_pnl": mtm_pnl,
                    "max_loss_per_contract": float(p.get("max_loss_per_contract", 0.0) or 0.0),
                    "structure": p.get(
                        "structure",
                        "BULL_PUT" if p.get("option_type") == "P" else "BEAR_CALL",
                    ),
                    "origin": p.get("origin", "AI"),
                    "lifecycle_state": p.get(
                        "lifecycle_state",
                        StrategyLifecycleState.MANAGED_BY_AI.value,
                    ),
                    "opened_at": float(p.get("opened_at") or 0.0),
                    "option_type": p.get("option_type", "P"),
                    "direction": p.get("direction", "bullish"),
                    "short_entry_mid": p.get("short_entry_mid"),
                    "long_entry_mid": p.get("long_entry_mid"),
                    "last_short_mid": p.get("last_short_mid"),
                    "last_long_mid": p.get("last_long_mid"),
                    "legs": legs,
                }
            )

        cash = float(state.get("_cash", 100_000.0) or 100_000.0)
        closed_trades = list(state.get("_closed_trades") or [])
        return {
            "spy_last": 0.0,
            "spy_bid": 0.0,
            "spy_ask": 0.0,
            "position_qty": 0,
            "position_avg_price": 0.0,
            "unrealized_pnl": spreads_unrealized,
            "realized_pnl": float(state.get("_total_realized_pnl", 0.0) or 0.0),
            "cash": cash,
            "equity": cash + spreads_unrealized,
            "initial_capital": float(state.get("_initial_capital", 100_000.0) or 100_000.0),
            "open_spreads": len(spreads_detail),
            "open_spreads_detail": spreads_detail,
            "spreads_unrealized_pnl": spreads_unrealized,
            "atm_iv": None,
            "iv_rank": None,
            "portfolio_greeks": {},
            "closed_trades": closed_trades,
            "closed_trades_count": len(closed_trades),
            "armed_candidate": None,
        }

    def _get_paper_open_positions_from_session_db(self) -> list[dict]:
        """Return persisted paper positions when no spread snapshot is available."""
        if getattr(self, "trading_mode", None) != TradingMode.PAPER:
            return []
        if self._is_opening_runtime_warmup_active():
            return []

        db = self._get_mode_session_db()
        if db is None:
            return []

        try:
            rows = load_paper_open_positions(
                db,
                trading_active=bool(getattr(self, "trading_active", False)),
            )
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not load paper open positions: {exc}")
            return []

        return rows if isinstance(rows, list) else []

    @staticmethod
    def _parse_occ_option_contract(symbol: str) -> dict:
        """Parse an OCC option symbol into underlying, expiration, strike, and type."""
        return parse_occ_option_contract(symbol)

    def _restore_paper_spreads_from_positions(
        self,
        positions: list[dict],
        *,
        default_lifecycle_state: str,
    ) -> tuple[list[dict], list[dict]]:
        """Rebuild spread-like paper positions from persisted single-leg option rows."""
        return restore_paper_spreads_from_positions(
            positions,
            default_lifecycle_state=default_lifecycle_state,
        )

    def _render_paper_spreads_in_tree(
        self,
        spreads_detail: list,
        armed_candidate: dict | None = None,
    ) -> None:
        """Render paper spreads as deterministic top-level rows.

        Layout: one cyan strategy header row per spread, followed by explicit
        leg rows (also top-level items). Avoiding child rows prevents Qt tree
        decoration edge-cases in the unified table configuration.
        """
        from datetime import date as _date

        self.positions_table.clear()
        today = _date.today()
        eastern_timezone = _get_eastern_timezone()
        fallback_positions_to_render: list[dict] = []
        data_column_count = max(self.positions_table.columnCount() - 1, 0)

        if armed_candidate:
            ac_structure = str(armed_candidate.get("structure", "SPREAD")).replace("_", " ").upper()
            ac_reason = str(armed_candidate.get("blocked_reason", "gate check"))
            ac_lifecycle = str(
                armed_candidate.get("lifecycle_state")
                or StrategyLifecycleState.ARMED_BY_AI.value
            )
            ac_armed_at = float(armed_candidate.get("armed_at") or 0.0)
            ac_elapsed = int(time.time() - ac_armed_at) if ac_armed_at > 0 else 0
            ac_exp = str((armed_candidate.get("spread") or {}).get("expiration", "") or "")
            ac_dte = format_days_to_expiration(ac_exp, today)

            ac_row = QTreeWidgetItem(self.positions_table)
            ac_row.setText(
                0,
                (
                    f"WAITING  STRATEGY {ac_lifecycle} : {ac_structure}  |  "
                    f"DTE: {ac_dte}  |  REASON: {ac_reason}  |  {ac_elapsed}s"
                ),
            )
            for col in range(6):
                ac_row.setForeground(col, QColor("#FFA500"))
            self.positions_table.setFirstColumnSpanned(
                self.positions_table.indexOfTopLevelItem(ac_row),
                QModelIndex(),
                True,
            )

        if not spreads_detail:
            fallback_positions = self._get_paper_open_positions_from_session_db()
            if fallback_positions:
                fallback_lifecycle_state = (
                    StrategyLifecycleState.MANAGED_BY_AI.value
                    if bool(getattr(self, "trading_active", False))
                    else "CARRIED OVER"
                )
                spreads_detail, fallback_positions_to_render = self._restore_paper_spreads_from_positions(
                    fallback_positions,
                    default_lifecycle_state=fallback_lifecycle_state,
                )
            if not spreads_detail and not fallback_positions_to_render:
                empty = QTreeWidgetItem(self.positions_table)
                empty.setText(0, "Paper trading - no open spreads")
                empty.setForeground(0, Qt.GlobalColor.gray)
                self.positions_table.setFirstColumnSpanned(
                    self.positions_table.indexOfTopLevelItem(empty),
                    QModelIndex(),
                    True,
                )
                return

        for sp in spreads_detail:
            spread_id = str(sp.get("id", ""))
            spread_header, spread_legs = build_paper_spread_tree_presentation(
                sp,
                today,
                eastern_timezone,
                COLORS,
                StrategyLifecycleState.MANAGED_BY_AI.value,
            )
            header_row = QTreeWidgetItem(self.positions_table)
            self.positions_table.setFirstColumnSpanned(
                self.positions_table.indexOfTopLevelItem(header_row),
                QModelIndex(),
                True,
            )

            close_btn = QPushButton("X")
            close_btn.setFixedSize(20, 20)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet(
                "QPushButton {"
                "color: #ff3b30; background: transparent;"
                "border: 1px solid #ff3b30; border-radius: 3px;"
                "font-size: 11px; font-weight: bold;"
                "}"
                "QPushButton:hover { background: #2a0f0f; }"
            )
            if spread_id:
                close_btn.clicked.connect(
                    lambda _checked=False, _id=spread_id: self._request_manual_close_spread(_id)
                )
            else:
                close_btn.setEnabled(False)
            # Compose one full-width strategy row with right-aligned action button.
            row_widget = QWidget(self.positions_table)
            row_widget.setMinimumHeight(22)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 0, 6, 0)
            row_layout.setSpacing(6)
            row_font = self.orders_title_label.font()
            title_font = self.orders_title_label.font()
            if title_font.pointSizeF() > 0:
                row_font.setPointSizeF(max(title_font.pointSizeF() - 1.0, 9.0))
            elif title_font.pointSize() > 0:
                row_font.setPointSize(max(title_font.pointSize() - 1, 9))
            row_font.setBold(False)

            if spread_header.timestamp_text:
                timestamp_label = QLabel(spread_header.timestamp_text, row_widget)
                timestamp_label.setFont(row_font)
                timestamp_label.setMinimumWidth(
                    timestamp_label.fontMetrics().horizontalAdvance("2026-05-12 00:00")
                )
                timestamp_label.setStyleSheet(
                    "color: #a8a8a8; font-weight: normal;"
                )
                row_layout.addWidget(timestamp_label, 0)

            summary_label = QLabel(spread_header.summary_text, row_widget)
            summary_label.setFont(row_font)
            summary_label.setStyleSheet(
                f"color: {COLORS.get('cyan', '#00ffff')}; font-weight: normal;"
            )
            row_layout.addWidget(summary_label, 1)

            pnl_label = QLabel(spread_header.pnl_text, row_widget)
            pnl_label.setFont(row_font)
            pnl_label.setStyleSheet(f"color: {spread_header.pnl_color}; font-weight: normal;")
            row_layout.addWidget(pnl_label, 0, Qt.AlignmentFlag.AlignRight)
            row_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
            self.positions_table.setItemWidget(header_row, 0, row_widget)
            for spread_leg in spread_legs:
                leg_row = QTreeWidgetItem(self.positions_table)
                leg_row.setText(0, spread_leg.side_text)
                leg_row.setText(1, spread_leg.strike_text)
                leg_row.setText(2, spread_leg.quantity_text)
                leg_row.setText(3, spread_leg.price_text)
                leg_row.setText(5, spread_leg.expiry_text)
                self._align_positions_data_row(leg_row)
                for col in range(data_column_count):
                    leg_row.setForeground(col, QColor("#ffffff"))

                if spread_leg.cost_text:
                    leg_row.setText(4, spread_leg.cost_text)
                    if spread_leg.cost_color:
                        leg_row.setForeground(4, QColor(spread_leg.cost_color))
                if spread_leg.pnl_text:
                    leg_row.setText(6, spread_leg.pnl_text)
                    if spread_leg.pnl_color:
                        leg_row.setForeground(6, QColor(spread_leg.pnl_color))

        if fallback_positions_to_render:
            for restored_group in build_restored_position_group_presentations(
                fallback_positions_to_render,
                COLORS,
            ):
                summary_row = QTreeWidgetItem(self.positions_table)
                summary_row.setText(0, restored_group.summary_text)
                for col in range(data_column_count):
                    summary_row.setForeground(col, QColor(COLORS.get("cyan", "#00ffff")))
                self.positions_table.setFirstColumnSpanned(
                    self.positions_table.indexOfTopLevelItem(summary_row),
                    QModelIndex(),
                    True,
                )

                for restored_row in restored_group.detail_rows:
                    row = QTreeWidgetItem(self.positions_table)
                    row.setText(0, restored_row.symbol_text)
                    row.setText(1, restored_row.strike_text)
                    row.setText(2, restored_row.quantity_text)
                    row.setText(3, restored_row.entry_price_text)
                    row.setText(4, restored_row.cost_text)
                    row.setText(5, restored_row.expiry_text)
                    row.setText(6, restored_row.pnl_text)
                    self._align_positions_data_row(row)

                    for col in range(data_column_count):
                        row.setForeground(col, QColor("#ffffff"))
                        row.setToolTip(col, restored_row.tooltip_text)

                    row.setForeground(0, QColor(restored_row.quantity_color))
                    row.setForeground(4, QColor(restored_row.cost_color))
                    row.setForeground(6, QColor(restored_row.pnl_color))

    def _request_manual_close_spread(self, spread_id: str) -> None:
        """Queue a manual close request to the paper worker thread.

        If the worker is running the close is forwarded via the Qt signal.
        If the worker is stopped (or not yet started) the spread is closed
        directly in the persisted state file so the position is not orphaned.
        """
        if not spread_id:
            return
        if self._paper_worker is not None:
            self.add_system_log(f"🖱️ Manual close requested for spread {spread_id}")
            self.manual_close_spread_requested.emit(str(spread_id))
            return
        # ── Fallback: worker not running — close directly in state file ──────
        self.add_system_log(f"⚠️ Worker not running — closing spread {spread_id} via state file")
        try:
            from SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingQtWorker  # noqa: PLC0415
            state_path = PaperTradingQtWorker.STATE_FILE
        except Exception:
            state_path = Path("market_data/paper_trading_state.json")
        if not state_path.exists():
            self.add_system_log("❌ State file not found — cannot force-close")
            return
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            open_spreads = state.get("_open_spreads", [])
            target = next((s for s in open_spreads if str(s.get("id", "")) == str(spread_id)), None)
            if target is None:
                self.add_system_log(f"❌ Spread {spread_id} not found in state file")
                return
            credit = float(target.get("credit", 0.0))
            qty    = int(target.get("qty", 1))
            debit  = credit * 0.50
            credit_received = credit * 100.0 * qty
            debit_paid      = debit  * 100.0 * qty
            realized_pnl    = credit_received - debit_paid
            now = time.time()
            closed_trade = dict(target)
            closed_trade.update({
                "debit_to_close":       debit,
                "debit_paid":           debit_paid,
                "credit_received":      credit_received,
                "realized_pnl":         realized_pnl,
                "max_loss_dollars":     float(target.get("max_loss_per_contract", 0)) * qty * 100,
                "open_commission":      0.0,
                "close_commission":     0.0,
                "return_on_credit_pct": (realized_pnl / credit_received * 100) if credit_received else 0.0,  # noqa: E501
                "return_on_risk_pct":   0.0,
                "closed_at":            now,
                "hold_seconds":         now - float(target.get("opened_at", now)),
                "close_reason":         "MANUAL_CLOSE (worker offline)",
                "lifecycle_state":      "CLOSED BY USER",
            })
            state["_open_spreads"] = [s for s in open_spreads if str(s.get("id", "")) != str(spread_id)]  # noqa: E501
            state.setdefault("_closed_trades", []).append(closed_trade)
            state["_cash"]               = float(state.get("_cash", 0)) + debit_paid
            state["_trades_executed"]    = int(state.get("_trades_executed", 0)) + 1
            state["_total_realized_pnl"] = float(state.get("_total_realized_pnl", 0)) + realized_pnl
            if realized_pnl >= 0:
                state["_winning_trades"] = int(state.get("_winning_trades", 0)) + 1
            else:
                state["_losing_trades"] = int(state.get("_losing_trades", 0)) + 1
            state.setdefault("_spread_pnl_history", []).append(realized_pnl)
            state["_saved_at"] = now
            tmp = state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(state_path)
            self.add_system_log(
                f"✅ Spread {spread_id} force-closed via state file — P&L ${realized_pnl:+.2f}"
            )
            # Refresh display so the row disappears
            self._refresh_positions_table()
        except Exception as exc:  # pragma: no cover
            self.add_system_log(f"❌ Force-close failed: {exc}")

    def _cancel_order_by_id(self, order_id: int) -> None:
        """Cancel a single order by Tradier order ID (called from row close button)."""
        answer = QMessageBox.question(
            self,
            "Cancel Order",
            f"Cancel order #{order_id} at Tradier?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._order_manager.set_client(self._get_tradier_client_for_mode())
        try:
            self._order_manager.cancel_order_by_id(int(order_id))
            self.add_system_log(f"✅ Order #{order_id} cancelled")
            self._refresh_positions_table()
        except Exception as exc:
            self.add_system_log(f"❌ Failed to cancel order #{order_id}: {exc}")
            QMessageBox.critical(self, "Cancel Failed", str(exc))

    # ==========================================================================
    # TRADING MODE MANAGEMENT
    # ==========================================================================

    def _count_open_live_positions(self) -> int:
        """Return the number of live positions visible in the positions table.

        Separated from _on_mode_btn_clicked per audit §18 so the policy check
        (does the user have open live positions?) can be tested without a dialog.
        The table row count is used as a proxy because positions are fetched from
        Tradier and rendered row-by-row into that widget.
        """
        if self.positions_table is None:
            return 0
        return self.positions_table.topLevelItemCount()

    def _handle_pending_orders_gate(
        self, pending_mode: TradingMode, target_label: str, support_suffix: str
    ) -> bool:
        """Run the shared 'pending orders must be cancelled' gate.

        Detects pending orders in *pending_mode*, prompts the user to cancel
        them, executes the cancellation, and reports failures. Returns True
        when the gate passes (no pending, or everything cancelled cleanly)
        and False when the caller must abort the mode switch. Both PAPER→LIVE
        and LIVE→PAPER branches route through here so the cancel-recheck
        policy lives in one place."""
        pending = self._fetch_pending_orders(pending_mode)
        if not pending:
            return True

        mode_name = "paper" if pending_mode == TradingMode.PAPER else "live"
        prompt = build_pending_orders_gate_prompt(
            pending_orders=pending,
            pending_mode_name=mode_name,
            target_label=target_label,
        )
        result = QMessageBox.warning(
            self,
            prompt.prompt_title,
            prompt.prompt_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            self.add_system_log(prompt.declined_log_message)
            return False

        ok, fail = self._cancel_orders(pending, pending_mode)
        outcome = build_pending_orders_gate_outcome(
            pending_mode_name=mode_name,
            support_suffix=support_suffix,
            cancelled_count=ok,
            failed_count=fail,
        )
        if fail:
            QMessageBox.critical(
                self,
                outcome.failure_dialog_title,
                outcome.failure_dialog_text,
            )
            return False
        self.add_system_log(outcome.success_log_message)
        return True

    def _on_mode_btn_clicked(self, new_mode: TradingMode):
        """Handle LIVE TRADING / PAPER TRADING toggle button click.

        Gate logic
        ----------
        PAPER → LIVE  (hard blocks, then typed confirmation)
          1. trading_active must be False         — stop paper engine first
                    2. No pending paper-local actions       — handled inside SpyderBox
          3. api_connected must be True           — Tradier EXEC must be connected
          4. mkt_data_connected must be True      — a data feed must be connected
          5. Typed confirmation gate              — type "I CONFIRM LIVE TRADING"

        LIVE → PAPER  (hard blocks, then Yes/No)
          1. trading_active must be False         — stop live engine first
          2. No pending live orders               — must be cancelled first
          3. Open positions warning               — user can override
          4. Yes/No confirmation
        """
        if new_mode == self.trading_mode:
            self._update_mode_buttons()
            return

        # ── PAPER → LIVE ──────────────────────────────────────────────────────
        if new_mode == TradingMode.LIVE:
            paper_to_live_plan = build_paper_to_live_switch_plan()

            # Gate 1: no active trading session
            if self.trading_active:
                QMessageBox.warning(
                    self,
                    "Trading Active",
                    "Cannot switch to LIVE while paper trading is running.\n"
                    "Stop paper trading first, then switch.",
                )
                self._update_mode_buttons()
                return

            # Gate 2: local paper mode has no Tradier pending-order dependency
            if not self._handle_pending_orders_gate(
                TradingMode.PAPER,
                target_label="LIVE",
                support_suffix="Resolve them manually before switching to LIVE trading.",
            ):
                self._update_mode_buttons()
                return

            # Gate 3: Tradier EXEC must be connected
            if not getattr(self, "api_connected", False):
                api_plan = paper_to_live_plan.api_disconnected
                QMessageBox.critical(
                    self,
                    api_plan.dialog_title,
                    api_plan.dialog_text,
                )
                self._update_mode_buttons()
                return

            # Gate 4: a market data feed must be connected
            if not getattr(self, "mkt_data_connected", False):
                market_data_plan = paper_to_live_plan.market_data_disconnected
                QMessageBox.critical(
                    self,
                    market_data_plan.dialog_title,
                    market_data_plan.dialog_text,
                )
                self._update_mode_buttons()
                return

            # Gate 5: typed confirmation
            confirmation_plan = paper_to_live_plan.confirmation
            if not self._confirm_live_trading(
                required_phrase=confirmation_plan.required_phrase,
                dialog_title=confirmation_plan.dialog_title,
                header_text=confirmation_plan.header_text,
                confirm_button_text=confirmation_plan.confirm_button_text,
            ):
                self.add_system_log(confirmation_plan.declined_log_message)
                self._update_mode_buttons()
                return

        # ── LIVE → PAPER ──────────────────────────────────────────────────────
        else:
            # Gate 1: no active trading session
            if self.trading_active:
                QMessageBox.warning(
                    self,
                    "Trading Active",
                    "Cannot switch to PAPER while live trading is running.\n"
                    "Stop live trading first, then switch.",
                )
                self._update_mode_buttons()
                return

            # Gate 2: check for pending live orders — must be cancelled first
            if not self._handle_pending_orders_gate(
                TradingMode.LIVE,
                target_label="PAPER",
                support_suffix="Resolve them manually or call Tradier: +1 (312) 542-6901.",
            ):
                self._update_mode_buttons()
                return

            # Gate 3: warn if live positions still open (positions, not orders)
            open_count = self._count_open_live_positions()
            live_to_paper_plan = build_live_to_paper_switch_plan(
                open_positions_count=open_count,
            )
            if live_to_paper_plan.open_positions_warning is not None:
                warning_plan = live_to_paper_plan.open_positions_warning
                answer = QMessageBox.warning(
                    self,
                    warning_plan.dialog_title,
                    warning_plan.dialog_text,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self.add_system_log(warning_plan.declined_log_message)
                    self._update_mode_buttons()
                    return

            # Gate 4: final confirmation
            final_confirmation_plan = live_to_paper_plan.final_confirmation
            answer = QMessageBox.question(
                self,
                final_confirmation_plan.dialog_title,
                final_confirmation_plan.dialog_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.add_system_log(final_confirmation_plan.declined_log_message)
                self._update_mode_buttons()
                return

        self._apply_mode_change(new_mode, arm_selected_mode=False)

    def _on_real_arm_toggle_clicked(self) -> None:
        """Enable/disable REAL trading arming via the upper-right mode control."""
        if self.trading_active:
            QMessageBox.warning(
                self,
                "Trading Active",
                "Stop the active trading session before changing REAL/PAPER arming.",
            )
            return

        if self._real_trading_armed:
            self._real_trading_armed = False
            self._paper_trading_armed = True
            self._paper_trading_enabled_this_session = True
            self._paper_start_authorized = False
            self._cancel_start_button_loading_transition()
            self._sync_runtime_trading_mode_override()
            self._update_mode_buttons()
            self.add_system_log("REAL trading disabled — PAPER trading re-armed")
            return

        if self.trading_mode == TradingMode.LIVE:
            confirmation_plan = build_paper_to_live_switch_plan().confirmation
            if not self._confirm_live_trading(
                required_phrase=confirmation_plan.required_phrase,
                dialog_title=confirmation_plan.dialog_title,
                header_text=confirmation_plan.header_text,
                confirm_button_text=confirmation_plan.confirm_button_text,
            ):
                self.add_system_log("Enable REAL cancelled by user")
                return
        else:
            self._on_mode_btn_clicked(TradingMode.LIVE)
            if self.trading_mode != TradingMode.LIVE:
                return

        self._real_trading_armed = True
        self._paper_trading_armed = False
        self._paper_trading_enabled_this_session = False
        self._sync_runtime_trading_mode_override()
        self._update_mode_buttons()
        self.add_system_log("REAL trading enabled — PAPER trading will be disabled")

    def _on_paper_arm_toggle_clicked(self) -> None:
        """Enable/disable SpyderBox PAPER arming via the lower-right mode control."""
        if self.trading_active:
            QMessageBox.warning(
                self,
                "Trading Active",
                "Stop the active trading session before changing REAL/PAPER arming.",
            )
            return

        if self._paper_trading_armed:
            self._paper_trading_armed = False
            self._real_trading_armed = False
            self._paper_trading_enabled_this_session = False
            self._paper_start_authorized = False
            self._cancel_start_button_loading_transition()
            self._sync_runtime_trading_mode_override()
            self._update_mode_buttons()
            self.add_system_log("PAPER trading disabled")
            return

        if self.trading_mode != TradingMode.PAPER:
            self._on_mode_btn_clicked(TradingMode.PAPER)
            if self.trading_mode != TradingMode.PAPER:
                return

        self._paper_trading_armed = True
        self._real_trading_armed = False
        self._paper_trading_enabled_this_session = True
        self._paper_start_authorized = False
        self._sync_runtime_trading_mode_override()
        self._update_mode_buttons()
        self.add_system_log("PAPER trading enabled")

    def _sync_runtime_trading_mode_override(self) -> None:
        """Keep runtime guard mode aligned with GUI mode + arming state.

        ``SPYDER_TRADING_MODE`` is consumed by broker/runtime safety guards.
        It is intentionally "paper" unless real trading is explicitly armed
        (or currently active) in LIVE mode.
        """
        runtime_mode = "paper"
        if self.trading_active:
            runtime_mode = "live" if self.trading_mode == TradingMode.LIVE else "paper"
        elif self.trading_mode == TradingMode.LIVE and self._real_trading_armed:
            runtime_mode = "live"

        os.environ["SPYDER_TRADING_MODE"] = runtime_mode

    def _apply_mode_change(self, new_mode: TradingMode, arm_selected_mode: bool = False):
        """Internal: commit trading mode switch and refresh all dependent UI."""
        # ── Snapshot outgoing mode before committing the switch ───────────────
        old_mode = self.trading_mode
        self._positions_snapshot_by_mode[old_mode] = self._snapshot_positions_table()
        self._remember_current_account_snapshot(old_mode)

        self.trading_mode = new_mode
        is_paper = new_mode == TradingMode.PAPER

        if arm_selected_mode:
            self._real_trading_armed = new_mode == TradingMode.LIVE
            self._paper_trading_armed = new_mode == TradingMode.PAPER
        else:
            self._real_trading_armed = False
            self._paper_trading_armed = new_mode == TradingMode.PAPER
        self._paper_trading_enabled_this_session = new_mode == TradingMode.PAPER
        self._paper_start_authorized = False

        self._sync_runtime_trading_mode_override()
        self._update_mode_buttons()

        # Keep the live account panel stable across mode switches; paper-mode
        # account hydration now targets the dedicated SpyderBox panel.
        if self.acct_number_lbl:
            import os as _os_mode
            _live_acct_id = _os_mode.environ.get("TRADIER_ACCOUNT_ID", "LIVE ACCOUNT UNSET")
            self.acct_number_lbl.setText(_live_acct_id)
        self._sync_spyderbox_account_labels()

        # Update START/STOP tooltips
        if is_paper:
            self.start_btn.setToolTip("Start paper trading with simulated fills")
            self.stop_btn.setToolTip("Stop paper trading but keep simulated positions")
        else:
            self.start_btn.setToolTip("Start LIVE trading with real order execution")
            self.stop_btn.setToolTip("Stop live trading — open orders remain at Tradier")

        self._update_orders_title()
        self._update_pnl_title()
        self.add_system_log(f"Trading mode changed to {new_mode.value}")

        import os
        current_provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        self._apply_mkt_provider_display(current_provider)

        # ── Restore incoming mode's previously saved table contents ───────────
        saved_positions = self._positions_snapshot_by_mode.get(new_mode)
        if saved_positions and new_mode != TradingMode.PAPER:
            self._restore_positions_snapshot(saved_positions)
        elif new_mode == TradingMode.PAPER:
            cached = getattr(self, "_portfolio_summary_cache", None)
            if isinstance(cached, dict) and cached:
                self._refresh_spreads_panel(cached)
            else:
                hydrated = self._load_cached_paper_state_payload()
                if hydrated:
                    self._refresh_spreads_panel(hydrated)
                    self._set_spyderbox_account_panel_values(
                        settled=float(hydrated.get("equity", 0.0) or 0.0),
                        buying=float(hydrated.get("cash", 0.0) or 0.0),
                        unrealized=float(hydrated.get("unrealized_pnl", 0.0) or 0.0),
                        realized=float(hydrated.get("realized_pnl", 0.0) or 0.0),
                    )
        saved_account = get_restorable_account_snapshot(
            self._account_snapshot_by_mode,
            new_mode,
            paper_mode=TradingMode.PAPER,
        )
        if saved_account:
            self._apply_account_snapshot(saved_account)

        self._sync_spyderbox_account_labels()
        self._refresh_pnl_table(self._pnl_stats_by_mode.get(new_mode, {}))
        self._update_recent_decision_flow_diagnostics()

    def _update_pnl_title(self):
        """Update the P&L PERFORMANCE title label text and color based on trading mode."""
        if not hasattr(self, "pnl_title_lbl") or self.pnl_title_lbl is None:
            return
        presentation = build_pnl_title_presentation(
            is_paper=self.trading_mode == TradingMode.PAPER,
        )
        self.pnl_title_lbl.setText(presentation.text)

        system_title_group = getattr(self, "system_log_group", None)
        if system_title_group is not None:
            title_font = system_title_group.font()
            title_font.setBold(False)
            self.pnl_title_lbl.setFont(title_font)

        self.pnl_title_lbl.setStyleSheet(presentation.style)

    def _update_orders_title(self):
        """Update the ORDERS & POSITIONS title label text and color based on trading mode."""
        if not hasattr(self, "orders_title_label") or self.orders_title_label is None:
            return
        presentation = build_orders_title_presentation(
            is_paper=self.trading_mode == TradingMode.PAPER,
        )
        title_text = presentation.text

        self.orders_title_label.setText(title_text)
        system_title_group = getattr(self, "system_log_group", None)
        if system_title_group is not None:
            title_font = system_title_group.font()
            title_font.setBold(False)
            self.orders_title_label.setFont(title_font)

        self.orders_title_label.setStyleSheet(presentation.style)
        title_width = self.orders_title_label.fontMetrics().horizontalAdvance(title_text) + 18
        self.orders_title_label.setMinimumWidth(title_width)

    def _update_mode_buttons(self):
        """Apply arming styles for REAL and PAPER controls in both account blocks."""
        if not self.live_btn or not self.paper_btn:
            return
        paper_armed = bool(
            getattr(self, "_paper_trading_armed", False)
            and getattr(self, "_paper_trading_enabled_this_session", False)
        )
        presentation = build_trading_arming_presentation(
            real_armed=bool(self._real_trading_armed),
            paper_armed=paper_armed,
            colors=COLORS,
        )

        self.live_btn.setText(presentation.real_status.text)
        self.live_btn.setStyleSheet(presentation.real_status.style)

        self.paper_btn.setText(presentation.real_toggle.text)
        self.paper_btn.setStyleSheet(presentation.real_toggle.style)

        if self.spyderbox_paper_status_btn:
            self.spyderbox_paper_status_btn.setText(presentation.paper_status.text)
            self.spyderbox_paper_status_btn.setStyleSheet(presentation.paper_status.style)

        if self.spyderbox_paper_toggle_btn:
            self.spyderbox_paper_toggle_btn.setText(presentation.paper_toggle.text)
            self.spyderbox_paper_toggle_btn.setStyleSheet(presentation.paper_toggle.style)

    # ── Per-mode snapshot helpers ─────────────────────────────────────────────

    def _snapshot_positions_table(self) -> list:
        """Serialize the current positions QTreeWidget into a plain list of dicts.

        Each entry represents one top-level row and its children so that the
        snapshot can be fully restored via ``_restore_positions_snapshot()``.
        """
        if not self.positions_table:
            return []
        ncols = self.positions_table.columnCount()
        snapshot = []
        for i in range(self.positions_table.topLevelItemCount()):
            item = self.positions_table.topLevelItem(i)
            entry = {
                "texts": [item.text(c) for c in range(ncols)],
                "foreground": item.foreground(0).color().name(),
                "span": True,
                "children": [
                    [item.child(j).text(c) for c in range(ncols)]
                    for j in range(item.childCount())
                ],
            }
            snapshot.append(entry)
        return snapshot

    def _restore_positions_snapshot(self, snapshot: list) -> None:
        """Repopulate the positions table from a previously captured snapshot.

        Restores text, foreground colour, column spanning, and child rows.
        The per-order cancel buttons are intentionally omitted because the
        orders they referenced belong to a different mode session.
        """
        if not self.positions_table or not snapshot:
            return
        from PySide6.QtGui import QColor
        self.positions_table.clear()
        ncols = self.positions_table.columnCount()
        for entry in snapshot:
            parent = QTreeWidgetItem(self.positions_table)
            texts = entry.get("texts", [])
            for c in range(min(len(texts), ncols)):
                parent.setText(c, texts[c])
            color_name = entry.get("foreground", "")
            if color_name:
                parent.setForeground(0, QColor(color_name))
            if entry.get("span"):
                self.positions_table.setFirstColumnSpanned(
                    self.positions_table.indexOfTopLevelItem(parent),
                    QModelIndex(),
                    True,
                )
            parent.setExpanded(True)
            for child_texts in entry.get("children", []):
                child = QTreeWidgetItem(parent)
                for c in range(min(len(child_texts), ncols)):
                    child.setText(c, child_texts[c])

    # kept for any external callers that may reference this name
    def _on_mode_changed(self, mode_text: str):
        """Deprecated shim — forwards to _apply_mode_change."""
        try:
            self._apply_mode_change(TradingMode(mode_text))
        except ValueError:
            pass

    def _confirm_live_trading(
        self,
        required_phrase: str = "I CONFIRM LIVE TRADING",
        dialog_title: str = "⚠️  LIVE TRADING — CONFIRMATION REQUIRED",
        header_text: str = "⚠️  YOU ARE ABOUT TO START LIVE TRADING",
        confirm_button_text: str = "CONFIRM LIVE TRADING",
    ) -> bool:
        """Show a typed-confirmation dialog for live arming/start actions.

        Args:
            required_phrase: Exact phrase required to enable confirmation.
            dialog_title: Dialog window title text.
            header_text: Header warning text.
            confirm_button_text: Text displayed on the confirm button.

        Returns:
            True only if the required phrase is typed exactly and confirmed.
        """
        REQUIRED_PHRASE = str(required_phrase)
        dlg = QDialog(self)
        dlg.setModal(True)
        dlg.setWindowTitle(str(dialog_title))

        layout = QVBoxLayout(dlg)
        header = QLabel(str(header_text))
        header.setStyleSheet(
            f"color: {COLORS['negative']}; font-size: 15px; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Body text
        body = QLabel(
            "This will execute <b>REAL orders</b> with <b>REAL money</b> "
            "through the Tradier <b>production</b> API.\n\n"
            "All trades are immediately binding and cannot be undone by this application.\n\n"
            "<b>PAPER TRADING will be disabled</b> while REAL trading is enabled."
        )
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 13px;")
        layout.addWidget(body)

        # Instruction label
        instruction = QLabel(f'To confirm, type exactly:  <b>{REQUIRED_PHRASE}</b>')
        instruction.setStyleSheet("font-size: 12px;")
        layout.addWidget(instruction)

        # Input field
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(REQUIRED_PHRASE)
        line_edit.setStyleSheet(
            f"font-size: 13px; padding: 6px; border: 2px solid {COLORS['negative']};"
        )
        layout.addWidget(line_edit)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        confirm_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        confirm_btn.setText(str(confirm_button_text))
        confirm_btn.setEnabled(False)
        confirm_btn.setStyleSheet(
            f"background-color: {COLORS['negative']}; color: white; font-weight: bold; padding: 6px 14px;"  # noqa: E501
        )
        btn_box.rejected.connect(dlg.reject)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        def _on_text_changed(text: str) -> None:
            confirm_btn.setEnabled(text == REQUIRED_PHRASE)

        line_edit.textChanged.connect(_on_text_changed)

        return dlg.exec() == QDialog.DialogCode.Accepted

    def _confirm_paper_trading(self) -> bool:
        """Require an explicit confirmation before starting paper automation."""
        reply = QMessageBox.question(
            self,
            "Start PAPER Trading",
            "Start autonomous PAPER trading now?\n\n"
            "Spyder will begin simulated paper execution and may place new paper orders automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _is_paper_trading_enabled_for_session(self) -> bool:
        """Return True only when paper automation was explicitly enabled this launch."""
        return bool(
            getattr(self, "_paper_trading_armed", False)
            and getattr(self, "_paper_trading_enabled_this_session", False)
        )

    def start_trading(self, from_queued: bool = False):
        """Handle start trading button click via unified SessionSupervisor path."""
        if self.trading_active:
            if from_queued:
                self._adopt_running_session_supervisor_ui_state()
            self.add_system_log("Trading already active")
            return

        if self.trading_mode == TradingMode.LIVE and not self._real_trading_armed:
            presentation = build_start_trading_precheck_presentation(
                guard="mode_not_armed",
                mode_label="REAL",
            )
            QMessageBox.warning(
                self,
                presentation.dialog_title,
                presentation.dialog_text,
            )
            self.add_system_log(presentation.log_message)
            if from_queued:
                self._restore_start_button_ready_state()
            return

        if (
            self.trading_mode == TradingMode.PAPER
            and not self._is_paper_trading_enabled_for_session()
        ):
            presentation = build_start_trading_precheck_presentation(
                guard="mode_not_armed",
                mode_label="PAPER",
            )
            QMessageBox.warning(
                self,
                presentation.dialog_title,
                presentation.dialog_text,
            )
            self.add_system_log(presentation.log_message)
            if from_queued:
                self._restore_start_button_ready_state()
            return

        if self.trading_mode == TradingMode.PAPER:
            if from_queued and not bool(getattr(self, "_paper_start_authorized", False)):
                self._restore_start_button_ready_state()
                self.add_system_log("PAPER trading queued start blocked — confirmation missing")
                return
            if not from_queued and not self._confirm_paper_trading():
                self._paper_start_authorized = False
                self.add_system_log("PAPER trading start cancelled by user")
                return
            if not from_queued:
                self._paper_start_authorized = True

        if not self._market_data_initialized:
            presentation = build_start_trading_precheck_presentation(
                guard="market_data_loading",
                queued_start_requested=bool(getattr(self, "_queued_trading_start", False)),
            )
            if getattr(self, "_queued_trading_start", False):
                self.add_system_log(presentation.log_message)
            else:
                self._queued_trading_start = True
                self._set_start_button_loading_live_data_state()
                self.add_system_log(presentation.log_message)
            QMessageBox.information(
                self,
                presentation.dialog_title,
                presentation.dialog_text,
            )
            return

        if not is_market_hours():
            presentation = build_start_trading_precheck_presentation(
                guard="market_closed",
            )
            self.add_system_log(presentation.log_message)
            QMessageBox.warning(
                self,
                presentation.dialog_title,
                presentation.dialog_text,
            )
            if from_queued:
                self._restore_start_button_ready_state()
            return

        readiness_gate_presentation = build_start_trading_readiness_gate_presentation(
            mode_label=self.trading_mode.value,
        )

        if self._startup_readiness_state.get("safe_fallback_applied", False):
            self.add_system_log(readiness_gate_presentation.safe_mode_log)

        # Apply the same readiness evaluation gate to both PAPER and LIVE starts.
        decision = self._require_fresh_readiness_or_block(self.trading_mode)
        gate_plan = build_start_trading_readiness_gate_decision_plan(
            decision=decision,
            last_readiness_result=self._last_readiness_result,
            from_queued=from_queued,
        )
        latest_result = gate_plan.latest_result
        if gate_plan.blocked:
            self.add_system_log(readiness_gate_presentation.blocked_log)
            if gate_plan.restore_start_button_on_block:
                self._restore_start_button_ready_state()
            if gate_plan.sync_go_no_go_on_block:
                self._update_go_no_go_status_from_result(latest_result)
            if gate_plan.block_audit_action is not None:
                self._append_readiness_bypass_audit(
                    gate_plan.block_audit_action,
                    str(gate_plan.block_audit_decision),
                    gate_plan.block_audit_reason,
                )
            return

        if gate_plan.requires_reason_prompt:
            reason = self._prompt_conditional_readiness_reason()
            if reason is None:
                self.add_system_log(readiness_gate_presentation.cancelled_log)
                if from_queued:
                    self._restore_start_button_ready_state()
                return
            self.add_system_log(
                build_start_trading_readiness_gate_presentation(
                    mode_label=self.trading_mode.value,
                    reason=reason,
                ).override_log
            )
            self._append_readiness_bypass_audit("override", "OK - CONDITIONAL", reason)

        # Keep existing live-mode safety gates before backend start.
        if self.trading_mode == TradingMode.LIVE:

            if not self.api_connected:
                presentation = build_start_trading_live_guard_presentation(
                    guard="api_disconnected",
                )
                QMessageBox.warning(
                    self,
                    presentation.dialog_title,
                    presentation.dialog_text,
                )
                self.add_system_log(presentation.log_message)
                if from_queued:
                    self._restore_start_button_ready_state()
                return

            if not self._confirm_live_trading():
                self.add_system_log(
                    build_start_trading_live_guard_presentation(
                        guard="live_cancelled",
                    ).log_message
                )
                if from_queued:
                    self._restore_start_button_ready_state()
                return

            data_status = self.data_status_label.text()
            if not is_live_equivalent_data_status(data_status):
                presentation = build_start_trading_live_guard_presentation(
                    guard="no_live_data",
                )
                QMessageBox.warning(
                    self,
                    presentation.dialog_title,
                    presentation.dialog_text,
                )
                self.add_system_log(presentation.log_message)
                if from_queued:
                    self._restore_start_button_ready_state()
                return

        if self.trading_mode == TradingMode.PAPER:
            self._queue_paper_session_start(show_failure_dialog=True)
            return

        if not self._start_unified_session_supervisor():
            presentation = build_start_trading_failure_presentation()
            QMessageBox.critical(
                self,
                presentation.dialog_title,
                presentation.dialog_text,
            )
            if from_queued:
                self._restore_start_button_ready_state()
            return

        self._adopt_running_session_supervisor_ui_state()

    def _require_fresh_readiness_or_block(self, mode: TradingMode | None = None) -> str:
        """Ensure a fresh readiness decision exists before trading start.

        Returns one of: OK, NO.
        """
        mode_label = (mode or self.trading_mode).value.upper()
        cache_plan = build_readiness_cache_decision_plan(
            last_readiness_ts=self._last_readiness_ts,
            last_readiness_result=self._last_readiness_result,
            now=time.time(),
            ttl_seconds=self._readiness_ttl_seconds,
        )
        if cache_plan.cached_decision is not None:
            return cache_plan.cached_decision

        result = self.run_trading_readiness_check(show_dialog=False)
        decision = str(result.get("decision", "NO"))
        if decision == "NO":
            presentation = build_readiness_start_block_presentation(
                mode_label=mode_label,
                reasons=result.get("reasons", []),
            )
            QMessageBox.critical(
                self,
                presentation.dialog_title,
                presentation.dialog_text,
            )
            self.add_system_log(presentation.log_message)
        return decision

    def run_trading_readiness_check_async(self) -> None:
        """Run trading readiness check on a worker thread."""
        if self._readiness_worker_thread is not None:
            self.add_system_log(build_readiness_async_already_running_log_message())
            return

        snapshot = self._build_preopen_check_snapshot()
        self.add_system_log(build_readiness_async_start_log_message())

        button = getattr(self, "readiness_btn", None)
        if button is not None:
            button.setEnabled(False)

        self._readiness_worker_thread = QThread(self)
        self._readiness_worker = _ReadinessCheckWorker(snapshot, self._evaluate_trading_readiness_snapshot)  # noqa: E501
        self._readiness_worker.moveToThread(self._readiness_worker_thread)

        self._readiness_worker_thread.started.connect(self._readiness_worker.run)
        self._readiness_worker.finished.connect(self._on_readiness_worker_finished)
        self._readiness_worker.failed.connect(self._on_readiness_worker_failed)
        self._readiness_worker.finished.connect(self._readiness_worker_thread.quit)
        self._readiness_worker.failed.connect(self._readiness_worker_thread.quit)
        self._readiness_worker_thread.finished.connect(self._cleanup_readiness_worker)

        self._readiness_worker_thread.start()

    def _on_readiness_worker_finished(self, result: dict) -> None:
        """Handle async trading-readiness worker success on UI thread."""
        self._apply_readiness_result(result, show_dialog=True)

    def _on_readiness_worker_failed(self, error_message: str) -> None:
        """Handle async trading-readiness worker failure on UI thread."""
        presentation = build_readiness_async_failure_presentation(error_message)
        self.add_system_log(presentation.log_message)
        QMessageBox.critical(
            self,
            presentation.dialog_title,
            presentation.dialog_text,
        )

    def _cleanup_readiness_worker(self) -> None:
        """Release async trading-readiness worker resources."""
        button = getattr(self, "readiness_btn", None)
        cleanup_plan = build_readiness_worker_cleanup_plan(
            readiness_button=button,
            readiness_worker=self._readiness_worker,
            readiness_worker_thread=self._readiness_worker_thread,
        )

        if cleanup_plan.enable_button and button is not None:
            button.setEnabled(True)

        for target in cleanup_plan.delete_targets:
            try:
                target.deleteLater()
            except Exception:
                pass

        self._readiness_worker = None
        self._readiness_worker_thread = None

    def _build_preopen_check_snapshot(self) -> dict[str, object]:
        """Capture UI-safe snapshot used by sync/async readiness evaluation."""
        startup_plan = build_readiness_startup_state_plan(self._startup_readiness_state)
        startup_state = startup_plan.startup_state
        if startup_plan.refresh_cache:
            startup_state = self._collect_startup_readiness_state()
            self._startup_readiness_state = startup_state

        raw_data_label = ""
        if getattr(self, "data_status_label", None) is not None:
            try:
                raw_data_label = self.data_status_label.text()
            except Exception:
                raw_data_label = ""
        data_label = normalize_readiness_data_status_label(raw_data_label)

        with self._event_clock_lock:
            event_clock_snapshot = build_readiness_event_clock_snapshot(
                getattr(self, "event_clock_state", None)
            )
        event_enabled = event_clock_snapshot.enabled
        event_name = event_clock_snapshot.state

        et_now = datetime.now(_get_eastern_timezone())

        # If the cached worker state shows disconnected, do a fresh inline check so a
        # slow/async startup connection probe doesn't give a false NO.  The result is
        # also pushed through the normal signal handlers so the toolbar labels update.
        cached_api = bool(getattr(self, "api_connected", False))
        cached_mkt = bool(getattr(self, "mkt_data_connected", False))
        fresh_connected: bool | None = None
        fresh_mode: str | None = None
        if not cached_api:
            try:
                fresh_connected, fresh_mode = check_api_connection()
            except Exception:
                pass

        connection_refresh = build_readiness_connection_refresh_plan(
            cached_api=cached_api,
            cached_mkt=cached_mkt,
            fresh_connected=fresh_connected,
            fresh_mode=fresh_mode,
        )
        if connection_refresh.connection_status is not None:
            # Drive through the normal handlers so toolbar labels go green.
            self.on_connection_status_changed(True, connection_refresh.connection_status)
        if connection_refresh.market_data_status is not None:
            self.on_market_data_status_changed(connection_refresh.market_data_status)
        cached_api = connection_refresh.api_connected
        cached_mkt = connection_refresh.mkt_data_connected

        return build_preopen_check_snapshot_payload(
            startup_state=startup_state,
            api_connected=cached_api,
            mkt_data_connected=cached_mkt,
            data_status_label=data_label,
            event_clock_enabled=event_enabled,
            event_clock_state=event_name,
            checked_at_et=et_now,
        )

    @staticmethod
    def _evaluate_trading_readiness_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
        """Evaluate trading readiness decision from an immutable snapshot."""
        return build_trading_readiness_evaluation(snapshot)

    def run_trading_readiness_check(self, show_dialog: bool = True) -> dict[str, object]:
        """Run dashboard-visible trading-readiness checks and store decision."""
        snapshot = self._build_preopen_check_snapshot()
        result = self._evaluate_trading_readiness_snapshot(snapshot)
        return self._apply_readiness_result(result, show_dialog=show_dialog)

    def run_preopen_go_no_go_check(self, show_dialog: bool = True) -> dict[str, object]:
        """Pre-open Go/No-Go checklist returning GO / NO-GO / CONDITIONAL GO.

        Wraps ``run_trading_readiness_check`` with operator-friendly decision
        labels and updates the ``go_no_go_status_label`` / ``start_btn`` UI
        elements present in the pre-open panel.

        Args:
            show_dialog: When True, show a blocking QMessageBox on NO-GO.

        Returns:
            Dict with keys ``decision`` (str), ``reasons`` (list[str]),
            ``warnings`` (list[str]), and ``checked_at_et`` (str).
        """
        snapshot = self._build_preopen_check_snapshot()
        inner = self._evaluate_trading_readiness_snapshot(snapshot)
        presentation = build_go_no_go_presentation(inner)

        result: dict[str, object] = {
            "decision": presentation.decision,
            "reasons": list(presentation.reasons),
            "warnings": list(presentation.warnings),
            "checked_at_et": presentation.checked_at_et,
        }

        # ── Update UI elements ───────────────────────────────────────────────
        label = getattr(self, "go_no_go_status_label", None)
        if label is not None:
            try:
                label.setText(presentation.status_text)
            except Exception:
                pass

        start = getattr(self, "start_btn", None)
        if start is not None:
            try:
                start.setEnabled(presentation.start_enabled)
            except Exception:
                pass

        btn = getattr(self, "go_no_go_btn", None)
        if btn is not None:
            try:
                btn.setStyleSheet(presentation.button_style)
            except Exception:
                pass

        self.add_system_log(presentation.log_message)

        return result

    def _apply_readiness_result(self, result: dict[str, object], show_dialog: bool = True) -> dict[str, object]:  # noqa: E501
        """Persist, display, and log readiness result."""
        self._last_readiness_result = result
        self._last_readiness_ts = time.time()
        self._update_readiness_status_display(result)

        presentation = build_readiness_result_log_presentation(result)
        for line in presentation.detail_lines:
            self.add_system_log(line)
        self.add_system_log(presentation.summary_line)

        report_path = self._export_readiness_report(result)
        if report_path:
            self.add_system_log(f"Trading readiness report saved: {report_path}")

        return result

    def _export_readiness_report(self, result: dict[str, object]) -> str:
        """Persist trading-readiness decision report to disk as JSON."""
        try:
            reports_dir = Path(self._readiness_reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(_get_eastern_timezone()).strftime("%Y%m%d_%H%M%S")
            out_path = reports_dir / build_readiness_report_filename(result, stamp=stamp)
            with out_path.open("w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2, default=str)
            return str(out_path)
        except Exception as exc:
            self.add_system_log(f"⚠️ Failed to save trading readiness report: {exc}")
            return ""

    def _prompt_conditional_readiness_reason(self) -> str | None:
        """Show a modal dialog requiring a typed bypass reason for OK-CONDITIONAL.

        Returns the trimmed reason string if the operator confirms, or None if
        they cancel.  An empty reason is not accepted — the dialog stays open
        until a non-blank reason is supplied or the user cancels.
        """
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout

        presentation = build_conditional_readiness_reason_dialog_presentation()

        while True:
            dlg = QDialog(self)
            dlg.setWindowTitle(presentation.window_title)
            dlg.setMinimumWidth(520)
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(presentation.instruction_html))
            reason_edit = QLineEdit()
            reason_edit.setPlaceholderText(presentation.placeholder_text)
            layout.addWidget(reason_edit)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            layout.addWidget(btns)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            reason = reason_edit.text().strip()
            if reason:
                return reason
            QMessageBox.warning(
                self,
                presentation.warning_title,
                presentation.warning_text,
            )

    def _append_readiness_bypass_audit(
        self, action: str, decision: str, reason: str
    ) -> None:
        """Append a bypass / block audit record to the most recent readiness report.

        If no report exists for this session, writes a new audit-only file so
        that every session start attempt is traceable.
        """
        try:
            reports_dir = Path(self._readiness_reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(_get_eastern_timezone()).strftime("%Y%m%d_%H%M%S")
            audit_entry = build_readiness_bypass_audit_entry(
                action=action,
                decision=decision,
                reason=reason,
                stamp=stamp,
            )
            audit_plan = build_readiness_bypass_audit_plan(
                self._last_readiness_result,
                audit_entry,
            )
            if audit_plan.export_result is not None:
                self._last_readiness_result = audit_plan.export_result
                self._export_readiness_report(audit_plan.export_result)
            else:
                # No checklist result cached — write a standalone audit file.
                out_path = reports_dir / build_readiness_bypass_audit_filename(
                    action=action,
                    stamp=stamp,
                )
                with out_path.open("w", encoding="utf-8") as handle:
                    json.dump(audit_plan.standalone_payload, handle, indent=2, default=str)
        except Exception as exc:
            self.add_system_log(f"⚠️ Failed to write readiness bypass audit: {exc}")

    def _update_readiness_status_display(self, result: dict[str, object] | None) -> None:
        """Update status label and button style for latest readiness decision."""
        label = getattr(self, "readiness_status_label", None)
        button = getattr(self, "readiness_btn", None)
        start_btn = getattr(self, "start_btn", None)
        if label is None or button is None:
            return

        presentation = build_readiness_status_presentation(
            result,
            trading_mode=self.trading_mode,
            trading_active=bool(getattr(self, "trading_active", False)),
            colors=COLORS,
        )
        label.setText(presentation.status_text)
        label.setStyleSheet(presentation.status_style)
        button.setText(presentation.button_text)
        button.setStyleSheet(presentation.button_style)

        if start_btn is not None and presentation.start_enabled is not None:
            start_btn.setEnabled(presentation.start_enabled)
        if start_btn is not None and presentation.start_tooltip is not None:
            start_btn.setToolTip(presentation.start_tooltip)

    def _start_unified_session_supervisor(self) -> bool:
        """Start SessionSupervisor using the currently selected trading mode."""
        supervisor = self._session_supervisor
        local_paper_start_authorized = bool(
            self.trading_mode == TradingMode.PAPER
            and self._is_paper_trading_enabled_for_session()
            and bool(getattr(self, "_paper_start_authorized", False))
        )
        injected_paper_start_authorized = bool(
            self.trading_mode == TradingMode.PAPER
            and bool(getattr(supervisor, "_spyder_paper_start_authorized", False))
        )
        start_plan = build_session_supervisor_start_plan(
            has_supervisor=supervisor is not None,
            autostart_in_progress=bool(
                getattr(supervisor, "_spyder_autostart_in_progress", False)
            ),
            supervisor_running=bool(getattr(supervisor, "is_running", False)),
        )

        if start_plan.action == "block_autostart":
            self.add_system_log("⏳ Unified session autostart still in progress")
            return False

        if start_plan.action == "already_running":
            self.logger.debug("Unified session already running")
            return True

        if start_plan.action == "reuse_existing":
            try:
                if local_paper_start_authorized or injected_paper_start_authorized:
                    from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
                        authorize_paper_session_start,
                    )

                    authorize_paper_session_start(supervisor)
                attempt_plan = build_session_supervisor_start_attempt_plan(
                    started=bool(supervisor.start()),
                    error_text=None,
                )
            except Exception as exc:
                attempt_plan = build_session_supervisor_start_attempt_plan(
                    started=None,
                    error_text=str(exc),
                )

            if attempt_plan.log_message:
                self.add_system_log(attempt_plan.log_message)
            if attempt_plan.clear_supervisor:
                self._session_supervisor = None
            return bool(attempt_plan.return_value)

        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
                authorize_paper_session_start,
                create_session_supervisor,
            )

            mode = "live" if self.trading_mode == TradingMode.LIVE else "paper"
            self._session_supervisor = create_session_supervisor(mode=mode)
            if local_paper_start_authorized:
                authorize_paper_session_start(self._session_supervisor)
            attempt_plan = build_session_supervisor_start_attempt_plan(
                started=bool(self._session_supervisor.start()),
                error_text=None,
            )
        except Exception as exc:
            attempt_plan = build_session_supervisor_start_attempt_plan(
                started=None,
                error_text=str(exc),
            )

        if attempt_plan.log_message:
            self.add_system_log(attempt_plan.log_message)
        if attempt_plan.clear_supervisor:
            self._session_supervisor = None
        return bool(attempt_plan.return_value)

    def _adopt_running_session_supervisor_ui_state(self) -> None:
        """Mirror an already-running SessionSupervisor into the dashboard UI."""
        supervisor = self._session_supervisor
        if supervisor is None or not getattr(supervisor, "is_running", False):
            return

        was_active = bool(getattr(self, "trading_active", False))
        self.trading_active = True
        if getattr(self, "connection_info", None) is not None:
            self.connection_info.trading_active = True
        self._sync_runtime_trading_mode_override()

        adoption_plan = build_session_supervisor_adoption_plan(
            trading_mode_value=self.trading_mode.value,
            loading_timer_active=bool(
                getattr(self, "_start_button_loading_timer_active", False)
            ),
            was_active=was_active,
            market_open=(
                bool(is_market_hours())
                if self.trading_mode == TradingMode.PAPER and not was_active
                else True
            ),
        )

        if getattr(self, "start_btn", None) is not None and adoption_plan.set_start_button_active:
            self._set_start_button_active_state()

        for message in adoption_plan.log_messages:
            self.add_system_log(message)

        # Unified paper mode does not emit the legacy Qt worker's first UI
        # snapshot, so refresh the positions strip immediately on successful
        # startup to replace any stale placeholder/restore state.
        if adoption_plan.follow_up_action == "refresh_paper_positions":
            self._refresh_positions_table()
        elif adoption_plan.follow_up_action == "start_live_pnl_poll":
            self._start_live_pnl_poll()

    def _stop_unified_session_supervisor(self, flatten: bool = False) -> None:
        """Stop SessionSupervisor when it is active."""
        supervisor = self._session_supervisor
        self._session_supervisor = None
        if supervisor is None:
            return
        try:
            supervisor.stop(flatten=flatten)
        except Exception as exc:
            self.add_system_log(f"⚠️ Unified session stop error: {exc}")

    def _start_paper_trading(self):
        """Launch the paper trading worker in a background QThread."""
        if not TRADIER_AVAILABLE:
            QMessageBox.warning(
                self,
                "Tradier Unavailable",
                "TradierClient module could not be imported.\n"
                "Paper trading requires SpyderB40_TradierClient.",
            )
            return

        self.add_system_log("Launching paper trading engine…")

        self.trading_active = True
        self.connection_info.trading_active = True
        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['automation_active']}; color: white;",
        )
        self.start_btn.setText("PAPER ACTIVE")
        self.start_btn.setEnabled(False)

        # Pre-populate account panel with initial paper capital immediately,
        # so the user sees $100k right away without waiting for the first Tradier poll.
        # (On market-closed days SPY last=0 so the poll returns early and labels would
        # stay stuck on "Connecting…" indefinitely.)
        if self.acct_number_lbl:
            import os as _os_pt
            self.acct_number_lbl.setText(_os_pt.environ.get("TRADIER_ACCOUNT_ID", "LIVE ACCOUNT UNSET"))
        # Single source of truth for paper-trading starting capital. Used to
        # initialise the worker AND to scale the E01 risk-manager limits so
        # percentage-based dialog inputs map to the correct dollar amounts.
        paper_initial_capital = 100_000.0
        _ic = paper_initial_capital
        self._set_spyderbox_account_panel_values(
            settled=_ic,
            buying=_ic,
            realized=0.0,
            unrealized=0.0,
        )
        self._sync_spyderbox_account_labels()

        # Create worker and thread
        self._paper_thread = QThread(self)
        self._paper_worker = _PaperTradingWorker(initial_capital=paper_initial_capital)
        # Pass current risk parameters before moving to thread (thread-safe at this point)
        if self.current_risk_params:
            self._paper_worker.set_risk_params(self.current_risk_params)
        # Phase 1: build a real SpyderE01_RiskManager from the dialog params
        # and inject it into the worker so validate_signal() gates every trade.
        risk_manager = self._build_paper_risk_manager(initial_capital=paper_initial_capital)
        if risk_manager is not None:
            self._paper_worker.set_risk_manager(risk_manager)
            self.add_system_log("✅ E-series RiskManager attached to paper worker")
        # Phase 1: forward S07 regime metrics to the worker so it can gate
        # entries on SWAN tail-risk, etc. The orchestrator is started by
        # _start_metrics_orchestrator() early in __init__.
        if self._metrics_orchestrator is not None:
            try:
                self._metrics_orchestrator.metrics_updated.connect(
                    self._paper_worker.set_regime_metrics
                )
                self.add_system_log("✅ S07 regime metrics piped to paper worker")
            except Exception as exc:
                self.add_system_log(f"⚠️ Could not wire S07 → paper worker: {exc}")
        self._paper_worker.moveToThread(self._paper_thread)

        # Wire signals (all bound methods for proper QueuedConnection)
        self._paper_thread.started.connect(self._paper_worker.run)
        self._paper_worker.status_update.connect(self._on_paper_status)
        self._paper_worker.position_update.connect(self._on_paper_position)
        self._paper_worker.metrics_update.connect(self._on_paper_metrics)
        self._paper_worker.error.connect(self._on_paper_error)
        self._paper_worker.stopped.connect(self._on_paper_stopped)
        self._paper_worker.connection_ready.connect(self._on_paper_connection)
        self._paper_worker.pivot_signal_updated.connect(self._on_pivot_signal_state)
        self.manual_close_spread_requested.connect(
            self._paper_worker.request_close_spread,
            Qt.ConnectionType.QueuedConnection,
        )

        self._paper_thread.start()
        self.add_system_log("PAPER TRADING — Connecting to local SpyderBox account…")

    def _stop_paper_trading(self):
        """Stop the paper trading worker gracefully."""
        if self._paper_worker:
            self._paper_worker.stop()
            self.add_system_log("Stopping paper trading…")

    @Slot(str)
    def _on_paper_status(self, msg: str):
        """Handle paper trading status update in the GUI thread."""
        self.add_system_log(f"Paper: {msg}")

    @Slot(dict)
    def _on_pivot_signal_state(self, state: dict) -> None:
        """Forward S08 PMR signal state to the left-panel ``PMR`` row."""
        if isinstance(state, dict):
            self._pmr_row_state = dict(state)
            self._publish_pivot_signal_to_runtime(self._pmr_row_state)
        widget = self.symbol_widgets.get("PMR") if hasattr(self, "symbol_widgets") else None
        if widget is None:
            return
        try:
            widget.update_pmr_state(self._pmr_row_state or state)
        except (AttributeError, RuntimeError):
            # Widget gone or wrong type — safe to ignore.
            pass

    @staticmethod
    def _normalize_pivot_signal_for_runtime(state: dict) -> dict[str, object]:
        """Convert the dashboard PMR widget payload into D31 selector shape."""
        if not isinstance(state, dict):
            return {}

        return {
            "fired": bool(state.get("fired", False)),
            "direction": state.get("direction"),
            "score": state.get("score"),
            "nearest_level_name": state.get("nearest_level_name") or state.get("level_name"),
            "atr_distance": state.get("atr_distance"),
        }

    def _publish_pivot_signal_to_runtime(self, state: dict) -> None:
        """Mirror PMR state into D31 cache so selector logic sees live S08 output."""
        runtime_payload = self._normalize_pivot_signal_for_runtime(state)
        if not runtime_payload:
            return

        supervisor = getattr(self, "_session_supervisor", None)
        orchestrator = getattr(supervisor, "orchestrator", None)
        if orchestrator is None:
            return

        cache = getattr(orchestrator, "market_data_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            try:
                orchestrator.market_data_cache = cache
            except AttributeError:
                return

        cache["pivot_signal"] = dict(runtime_payload)
        cache["pivot_mr_signal"] = dict(runtime_payload)

        market_conditions = cache.get("market_conditions")
        if not isinstance(market_conditions, dict):
            market_conditions = {}
            cache["market_conditions"] = market_conditions

        market_conditions["pivot_signal"] = dict(runtime_payload)
        market_conditions["pivot_mr_signal"] = dict(runtime_payload)

    @Slot(str)
    def _on_symbol_widget_clicked(self, symbol: str) -> None:
        """Handle a left-click on any market-overview row."""
        if symbol == "PMR":
            self._show_pmr_details_dialog()
        elif symbol == "PCA-PROXY":
            self._show_pca_proxy_details_dialog()
        elif symbol == "PCA-IV":
            self._show_pca_iv_details_dialog()
        elif symbol == "WRS":
            self._show_wrs_details_dialog()
        elif symbol == "PSR":
            self._show_psr_details_dialog()

    def _get_custom_metric_entry(self, symbol: str) -> dict:
        """Return the latest nested S07 payload for a custom metric row."""
        cached_payload = getattr(self, "_last_custom_metrics_payload", {})
        if isinstance(cached_payload, dict):
            cached_entry = cached_payload.get(symbol)
            if isinstance(cached_entry, dict):
                return dict(cached_entry)

        orchestrator = getattr(self, "_metrics_orchestrator", None)
        if orchestrator is None:
            return {}

        try:
            all_metrics = orchestrator.get_all_metrics()
        except Exception:
            return {}

        details = all_metrics.get(f"{symbol}_DETAILS", {})
        if not isinstance(details, dict):
            details = {}

        value = all_metrics.get(symbol, float("nan"))
        change = all_metrics.get(f"{symbol}_CHANGE", float("nan"))
        quality = float("nan")
        try:
            quality_bucket = getattr(orchestrator, "metric_quality", {}).get(symbol)
            if quality_bucket is not None:
                quality = float(quality_bucket.quality_score)
        except (AttributeError, TypeError, ValueError):
            quality = float("nan")

        return {
            "value": value,
            "change": change,
            "quality": quality,
            "details": details,
        }

    @staticmethod
    def _format_metric_dialog_value(value, fmt: str, fallback: str = "—") -> str:
        """Format numeric values for details dialogs."""
        return format_metric_dialog_value(value, fmt, fallback)

    @staticmethod
    def _build_metric_sparkline(values: list[float]) -> str:
        """Convert a recent numeric series into a compact sparkline string."""
        return build_metric_sparkline(values)

    @staticmethod
    def _coerce_metric_float(value) -> float | None:
        """Return a finite float when a metric value can be parsed."""
        return coerce_metric_float(value)

    @classmethod
    def _build_pca_proxy_operator_takeaway(
        cls,
        entry: dict,
        details: dict,
        decomposition: dict,
    ) -> str:
        """Build a one-line operator takeaway for the PCA-Proxy dialog."""
        return build_pca_proxy_operator_takeaway(entry, details, decomposition)

    @classmethod
    def _build_pca_iv_operator_takeaway(
        cls,
        entry: dict,
        details: dict,
        nested_details: dict,
    ) -> str:
        """Build a one-line operator takeaway for the PCA-IV dialog."""
        return build_pca_iv_operator_takeaway(entry, details, nested_details)

    @classmethod
    def _build_pca_proxy_details_html(cls, entry: dict) -> str:
        """Build the PCA-Proxy details dialog HTML from the latest metric payload."""
        return build_pca_proxy_details_html(entry)

    def _show_custom_metric_html_dialog(
        self,
        title: str,
        html_body: str,
        min_width: int = 680,
        min_height: int = 560,
    ) -> None:
        """Render a reusable read-only HTML dialog for Custom Metrics rows."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumSize(min_width, min_height)
        layout = QVBoxLayout(dlg)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setHtml(html_body)
        layout.addWidget(body)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)

        dlg.exec()

    def _show_pca_proxy_details_dialog(self) -> None:
        """Open a modal dialog showing the live PCA-Proxy state."""
        self._show_custom_metric_html_dialog(
            "PCA-Proxy — Sector Eigenfactor Signal (S14)",
            self._build_pca_proxy_details_html(self._get_custom_metric_entry("PCA-PROXY")),
            min_width=700,
            min_height=600,
        )

    def _show_pca_iv_details_dialog(self) -> None:
        """Open a modal dialog showing the PCA-IV live or seeded state."""
        entry = self._get_custom_metric_entry("PCA-IV")
        details = entry.get("details", {}) if isinstance(entry, dict) else {}
        status = str(details.get("status") or "").lower() if isinstance(details, dict) else ""
        self._show_custom_metric_html_dialog(
            (
                "PCA-IV — Surface Factor Signal (S14)"
                if status == "live"
                else "PCA-IV — Placeholder Signal (S14)"
            ),
            self._build_pca_iv_details_html(entry),
            min_width=680,
            min_height=540,
        )

    def _show_wrs_details_dialog(self) -> None:
        """Open a modal dialog showing the live Walmart Recession Signal state."""
        # Pull latest data from S12 singleton (uses disk cache — no extra API call)
        d: dict = {}
        try:
            from SpyderS_Signals.SpyderS12_WRSSignal import get_wrs_signal
            d = get_wrs_signal().get_signal_dict()
        except Exception:
            pass
        self._show_custom_metric_html_dialog(
            "WRS — Walmart Recession Signal (S12)",
            build_wrs_details_html(d),
            min_width=680,
            min_height=560,
        )

    def _show_psr_details_dialog(self) -> None:
        """Open a modal dialog showing the live Pawn Shop Ratio state."""
        d: dict = {}
        try:
            from SpyderS_Signals.SpyderS13_PSRSignal import get_psr_signal

            d = get_psr_signal().get_signal_dict()
        except Exception:
            pass

        wrs_level = "NORMAL"
        try:
            from SpyderS_Signals.SpyderS12_WRSSignal import get_wrs_signal

            wrs_d = get_wrs_signal().get_signal_dict()
            wrs_level = wrs_d.get("wrs_signal_level", "NORMAL")
        except Exception:
            pass

        try:
            from SpyderS_Signals.SpyderS13_PSRSignal import interpret_dual_signal

            dual = interpret_dual_signal(d.get("psr_signal_level", "NORMAL"), wrs_level)
        except Exception:
            dual = {
                "regime": "UNKNOWN",
                "description": "Dual-signal data unavailable.",
                "trading_bias": "—",
                "size_multiplier": "1.00",
            }

        self._show_custom_metric_html_dialog(
            "PSR — Pawn Shop Ratio (S13)",
            build_psr_details_html(d, wrs_level, dual),
            min_width=700,
            min_height=620,
        )

    def _show_pmr_details_dialog(self) -> None:
        """Open a modal dialog showing the current PMR signal state."""
        widget = self.symbol_widgets.get("PMR") if hasattr(self, "symbol_widgets") else None
        state: dict = getattr(widget, "_last_pmr_state", None) or {}

        self._show_custom_metric_html_dialog(
            "PMR — Pivot Mean-Reversion Signal (S08)",
            build_pmr_details_html(state),
            min_width=620,
            min_height=520,
        )

    @Slot(dict)
    def _on_paper_position(self, data: dict):
        """Handle paper position update — push figures into the account container."""
        equity = data.get("equity", 0.0)
        cash = data.get("cash", 0.0)
        unrealized = data.get("unrealized_pnl", 0.0)
        realized = data.get("realized_pnl", 0.0)

        self._set_spyderbox_account_panel_values(
            settled=float(equity or 0.0),
            buying=float(cash or 0.0),
            unrealized=float(unrealized or 0.0),
            realized=float(realized or 0.0),
        )

        qty = data.get("position_qty", 0)
        n_spreads = data.get("open_spreads", 0)
        spy_last = data.get("spy_last", 0.0)
        if qty > 0:
            self.add_system_log(
                f"Paper: SPY ${spy_last:.2f} | {qty} shares | "
                f"Unrealized: ${unrealized:+,.2f} | Equity: ${equity:,.2f}"
            )
        elif n_spreads > 0:
            self.add_system_log(
                f"Paper: SPY ${spy_last:.2f} | {n_spreads} spread(s) open | "
                f"MTM: ${data.get('spreads_unrealized_pnl', 0.0):+,.2f} | Equity: ${equity:,.2f}"
            )
        else:
            self.add_system_log(
                f"Paper: SPY ${spy_last:.2f} | No position | Equity: ${equity:,.2f}"
            )

        self._refresh_spreads_panel(data)

    def _refresh_spreads_panel(self, data: dict) -> None:
        """Populate the 'SPREADS & VOLATILITY' panel from a worker emit."""
        payload = data if isinstance(data, dict) else {}
        self._portfolio_summary_cache = dict(payload)

        atm_iv = payload.get("atm_iv")
        iv_rank = payload.get("iv_rank")
        if self.atm_iv_label is not None:
            atm_iv_badge = build_atm_iv_label_presentation(atm_iv, COLORS)
            self.atm_iv_label.setText(atm_iv_badge.text)
            self.atm_iv_label.setStyleSheet(atm_iv_badge.style)
        if self.iv_rank_label is not None:
            iv_rank_badge = build_iv_rank_label_presentation(iv_rank, COLORS)
            self.iv_rank_label.setText(iv_rank_badge.text)
            self.iv_rank_label.setStyleSheet(iv_rank_badge.style)

        spreads_detail = payload.get("open_spreads_detail") or []
        spreads_mtm = coerce_float(payload.get("spreads_unrealized_pnl"), 0.0) or 0.0

        closed = payload.get("closed_trades")
        if closed is not None:
            self._closed_trades_cache = list(closed)
            dlg = getattr(self, "_trade_audit_dialog", None)
            if dlg is not None and dlg.isVisible():
                try:
                    dlg.update_trades(self._closed_trades_cache)
                except Exception:
                    pass

        if self.spreads_summary_label is not None:
            summary_badge = build_spreads_summary_badge_presentation(
                len(spreads_detail),
                spreads_mtm,
                COLORS,
            )
            self.spreads_summary_label.setText(summary_badge.text)
            self.spreads_summary_label.setStyleSheet(summary_badge.style)

        if self.bp_used_label is not None:
            bp_usage = calculate_buying_power_usage(
                spreads_detail,
                capital_raw=getattr(self, "_paper_initial_capital", 100_000.0),
                default_capital=100_000.0,
            )
            bp_badge = build_buying_power_badge_presentation(bp_usage, COLORS)
            self.bp_used_label.setText(bp_badge.text)
            self.bp_used_label.setStyleSheet(bp_badge.style)

        if self.realized_today_label is not None:
            realized_raw = payload.get("realized_pnl_today")
            if realized_raw is None:
                realized_raw = payload.get("realized_pnl", 0.0)
            try:
                realized_value = (
                    parse_money_text(str(realized_raw))
                    if isinstance(realized_raw, str)
                    else float(realized_raw or 0.0)
                )
            except (TypeError, ValueError):
                realized_value = 0.0
            realized_badge = build_realized_today_badge_presentation(realized_value, COLORS)
            self.realized_today_label.setText(realized_badge.text)
            self.realized_today_label.setStyleSheet(realized_badge.style)

        if (
            getattr(self, "trading_mode", None) == TradingMode.PAPER
            and self.positions_table is not None
        ):
            self._render_paper_spreads_in_tree(
                spreads_detail,
                armed_candidate=payload.get("armed_candidate"),
            )

        if self.spreads_table is not None:
            from PySide6.QtGui import QColor
            from PySide6.QtWidgets import QTableWidgetItem

            legacy_rows = build_legacy_spreads_table_rows(spreads_detail, COLORS)
            self.spreads_table.setRowCount(len(legacy_rows))
            for row_index, row in enumerate(legacy_rows):
                for column_index, text in enumerate(row.cells):
                    item = QTableWidgetItem(text)
                    if column_index == 6:
                        item.setForeground(QColor(row.mtm_color))
                    self.spreads_table.setItem(row_index, column_index, item)

        greeks = payload.get("portfolio_greeks") or {}
        greek_strip = build_portfolio_greek_strip_presentations(greeks, COLORS)
        if self.port_delta_label is not None:
            self.port_delta_label.setText(greek_strip.delta.text)
            self.port_delta_label.setStyleSheet(greek_strip.delta.style)
        if self.port_gamma_label is not None:
            self.port_gamma_label.setText(greek_strip.gamma.text)
            self.port_gamma_label.setStyleSheet(greek_strip.gamma.style)
        if self.port_theta_label is not None:
            self.port_theta_label.setText(greek_strip.theta.text)
            self.port_theta_label.setStyleSheet(greek_strip.theta.style)
        if self.port_vega_label is not None:
            self.port_vega_label.setText(greek_strip.vega.text)
            self.port_vega_label.setStyleSheet(greek_strip.vega.style)
        if self.port_charm_label is not None:
            self.port_charm_label.setText(greek_strip.charm_text)
        if self.port_vanna_label is not None:
            self.port_vanna_label.setText(greek_strip.vanna_text)

        if self.greek_bars:
            for update in build_greek_bar_updates(greeks):
                bar = self.greek_bars.get(update.key)
                if bar is not None:
                    bar.set_value(update.value, update.status)

        dlg = self._portfolio_summary_dialog
        if dlg is not None and dlg.isVisible():
            self._populate_portfolio_summary_table(dlg)

    @Slot(dict)
    def _on_paper_metrics(self, metrics: dict):
        """Handle paper P&L metrics update — push summary figures into account container."""
        equity_raw = metrics.get("equity", "")
        realized_raw = metrics.get("realized_pnl", "")

        if equity_raw:
            try:
                self._set_spyderbox_account_panel_values(settled=parse_money_text(str(equity_raw)))
            except (TypeError, ValueError):
                pass
        if realized_raw:
            try:
                self._set_spyderbox_account_panel_values(realized=parse_money_text(str(realized_raw)))
            except (TypeError, ValueError):
                pass

        enriched = normalize_today_worker_metrics(metrics)

        try:
            et_tz = _get_eastern_timezone()
            settled_label = getattr(self, "settled_value", None)
            initial_capital = resolve_capital_baseline(
                getattr(self, "_paper_initial_capital", 0.0),
                fallback_text=(
                    settled_label.text()
                    if settled_label is not None and hasattr(settled_label, "text")
                    else None
                ),
            )
            enriched = {
                **build_today_trade_analytics(
                    getattr(self, "_closed_trades_cache", []),
                    target_date=datetime.now(et_tz).date(),
                    display_tz=et_tz,
                    calmar_mode="drawdown_value",
                    initial_capital=initial_capital,
                    realized_pnl_raw=enriched.get("realized_pnl", ""),
                    max_drawdown_raw=enriched.get("max_drawdown", "0"),
                ),
                **enriched,
            }
        except Exception:
            pass

        self._refresh_pnl_table(enriched)

    def _refresh_pnl_table(self, stats: dict) -> None:
        """Refresh the P&L performance table from trading stats.

        Called from _on_paper_metrics with the latest metrics dict, and can be
        called with any dict that contains per-period keys. Recognised keys
        (all optional — missing values stay as —):

            today_pnl, week_pnl, month_pnl, year_pnl          — formatted P&L strings
            today_win_rate, week_win_rate, ...                — e.g. "75%"
            today_win_loss, week_win_loss, ...                — e.g. "$300/$120"
            today_profit_factor, ...                          — e.g. "1.65"
            today_sharpe, week_sharpe, ...                    — e.g. "1.85"
            today_sortino, ...                                — e.g. "2.12"
            today_calmar, ...                                 — e.g. "1.95"
        """
        if self.pnl_table is None:
            return

        if self._h07_performance_analytics is not None:
            try:
                h07_stats = self._h07_performance_analytics.get_summary_stats()
                if h07_stats:
                    stats = {**stats, **h07_stats}
            except Exception as _h07_err:
                logger.warning("H07 PerformanceAnalytics.get_summary_stats failed: %s", _h07_err)

        try:
            _db = self._get_mode_session_db()
            if _db is not None:
                stats = overlay_period_pnl_summary(
                    stats,
                    self._get_session_db_adapter().fetch_pnl_summary(
                        _db,
                        log_error=lambda msg: self.logger.debug(msg),
                    ),
                    preserve_existing_today=True,
                )
        except Exception as _h05_err:
            logger.debug("H05 get_pnl_summary skipped: %s", _h05_err)

        periods = ["today", "week", "month", "year"]
        col_map = {1: "pnl", 2: "win_rate", 3: "win_loss", 4: "profit_factor", 5: "sharpe", 6: "sortino", 7: "calmar"}

        for row, period in enumerate(periods):
            for col, metric in col_map.items():
                key = f"{period}_{metric}"
                value = str(stats.get(key, "—"))
                item = self.pnl_table.item(row, col)
                if item is None:
                    from PySide6.QtWidgets import QTableWidgetItem

                    item = QTableWidgetItem(value)
                    self.pnl_table.setItem(row, col, item)
                else:
                    item.setText(value)
                if col == 1 and value not in ("—", "", "-"):
                    try:
                        num = parse_money_text(value)
                        from PySide6.QtGui import QColor

                        item.setForeground(
                            QColor(COLORS["positive"] if num >= 0 else COLORS["negative"])
                        )
                    except (ValueError, TypeError):
                        pass

        self._pnl_stats_by_mode[self.trading_mode] = dict(stats)

    @Slot(str)
    def _on_paper_error(self, error_msg: str):
        """Handle paper trading error."""
        self.add_system_log(f"❌ Paper trading error: {error_msg}")
        QMessageBox.warning(self, "Paper Trading Error", error_msg)

    @Slot()
    def _on_paper_stopped(self):
        """Handle paper trading worker exit."""
        # Clean up thread
        if self._paper_thread and self._paper_thread.isRunning():
            self._paper_thread.quit()
            self._paper_thread.wait(10_000)

        self.trading_active = False
        self.connection_info.trading_active = False
        self._paper_start_authorized = False
        self._sync_runtime_trading_mode_override()
        self._paper_trading_armed = True
        self._paper_trading_enabled_this_session = True

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;",
        )
        self.start_btn.setText("START TRADING")
        self.start_btn.setEnabled(True)
        self._update_mode_buttons()

        # Leave the live account panel untouched; balances refresh independently.
        if self.acct_number_lbl:
            import os as _os_stop
            self.acct_number_lbl.setText(_os_stop.environ.get("TRADIER_ACCOUNT_ID", "LIVE ACCOUNT UNSET"))
        self._sync_spyderbox_account_labels()

        self.add_system_log("PAPER TRADING STOPPED — Session ended")

    # ------------------------------------------------------------------
    # Live P&L polling (fills the same table as paper's _on_paper_metrics)
    # ------------------------------------------------------------------

    def _start_live_pnl_poll(self, interval_ms: int = 15_000) -> None:
        """Start a recurring timer that refreshes the P&L table during live sessions.

        Runs every *interval_ms* milliseconds (default 15 s).  Stopped
        automatically when ``stop_trading()`` is called.
        """
        if self._live_pnl_timer is not None:
            return  # already running
        from PySide6.QtCore import QTimer
        timer = QTimer(self)
        timer.setInterval(interval_ms)
        timer.timeout.connect(self._poll_live_pnl_metrics)
        timer.start()
        self._live_pnl_timer = timer
        # Fire immediately so the table isn't blank for the first 15 s.
        self._poll_live_pnl_metrics()

    def _stop_live_pnl_poll(self) -> None:
        """Stop and discard the live P&L poll timer."""
        timer = self._live_pnl_timer
        self._live_pnl_timer = None
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass  # already destroyed

    def _poll_live_pnl_metrics(self) -> None:
        """Collect live-session metrics and push them into the P&L table.

        Data sources (in priority order):
        1. H05 TradingSessionDB.for_live() — period P&L buckets and trade list.
        2. Account panel labels — current equity / realized P&L from Tradier.
        3. H07 PerformanceAnalytics — historical aggregates (Sharpe/Sortino/Calmar).
        """

        enriched: dict = {}

        # ── 1. H05: period P&L buckets (TODAY / WEEK / MONTH / YEAR) ──────────
        try:
            db = self._get_mode_session_db()  # returns for_live() when LIVE
            if db is not None:
                pnl_summary = db.get_pnl_summary()
                for period in ("today", "week", "month", "year"):
                    val = pnl_summary.get(period, 0.0)
                    if val != 0.0:
                        enriched[f"{period}_pnl"] = f"${val:+,.2f}"

                # ── H05 trade list → win/loss, win rate, profit factor, Sharpe, Sortino, Calmar ──
                try:
                    import pytz

                    et_tz = _get_eastern_timezone()
                    today_et = datetime.now(et_tz).date()

                    trades = db.get_recent_trades(limit=500)
                    today_trades = []
                    for t in trades:
                        if not isinstance(t, dict):
                            continue
                        closed_at = t.get("closed_at") or t.get("timestamp")
                        if closed_at is None:
                            continue
                        try:
                            closed_dt = datetime.fromisoformat(str(closed_at)).astimezone(et_tz)
                        except (ValueError, TypeError):
                            try:
                                closed_dt = datetime.fromtimestamp(float(closed_at), tz=pytz.UTC).astimezone(et_tz)  # noqa: E501
                            except Exception:
                                continue
                        if closed_dt.date() == today_et:
                            today_trades.append(t)

                    wins = sum(1 for t in today_trades if float(t.get("realized_pnl", 0) or 0) > 0)
                    losses = sum(1 for t in today_trades if float(t.get("realized_pnl", 0) or 0) < 0)
                    total = wins + losses
                    if total > 0:
                        enriched["today_win_loss"] = f"{wins}/{losses}"
                        enriched["today_win_rate"] = f"{wins / total * 100:.1f}%"

                    gross_profit = sum(float(t.get("realized_pnl", 0) or 0) for t in today_trades if float(t.get("realized_pnl", 0) or 0) > 0)  # noqa: E501
                    gross_loss = abs(sum(float(t.get("realized_pnl", 0) or 0) for t in today_trades if float(t.get("realized_pnl", 0) or 0) < 0))  # noqa: E501
                    if gross_loss > 0:
                        enriched["today_profit_factor"] = f"{gross_profit / gross_loss:.2f}"
                    elif gross_profit > 0:
                        enriched["today_profit_factor"] = "∞"

                    # Sharpe / Sortino from per-trade return-on-risk
                    returns: list[float] = []
                    downside: list[float] = []
                    for t in today_trades:
                        ret = t.get("return_on_risk_pct")
                        if ret is None:
                            try:
                                pnl = float(t.get("realized_pnl", 0) or 0)
                                max_loss = float(t.get("max_loss_dollars", 0) or 0)
                                if max_loss <= 0:
                                    continue
                                ret = (pnl / max_loss) * 100.0
                            except (TypeError, ValueError):
                                continue
                        try:
                            r = float(ret) / 100.0
                        except (TypeError, ValueError):
                            continue
                        returns.append(r)
                        if r < 0:
                            downside.append(r)

                    if len(returns) >= 2:
                        mean_r = sum(returns) / len(returns)
                        var = sum((x - mean_r) ** 2 for x in returns) / (len(returns) - 1)
                        std = math.sqrt(max(var, 0.0))
                        if std > 0:
                            enriched["today_sharpe"] = f"{(mean_r / std) * math.sqrt(len(returns)):.2f}"
                        if downside:
                            dvar = sum(x ** 2 for x in downside) / len(downside)
                            dstd = math.sqrt(max(dvar, 0.0))
                            if dstd > 0:
                                enriched["today_sortino"] = f"{(mean_r / dstd) * math.sqrt(len(returns)):.2f}"  # noqa: E501
                            elif mean_r > 0:
                                enriched["today_sortino"] = "∞"
                        elif mean_r > 0:
                            enriched["today_sortino"] = "∞"

                    # Calmar: session return / max drawdown
                    try:
                        realized_pnl_total = sum(float(t.get("realized_pnl", 0) or 0) for t in today_trades)  # noqa: E501
                        initial_cap = float(getattr(self, "_paper_initial_capital", 0.0) or 0.0)
                        # For live, try to read starting equity from account label
                        if initial_cap <= 0 and self.settled_value:
                            try:
                                initial_cap = float(str(self.settled_value.text())).replace("$", "").replace(",", "") or 0.0  # noqa: E501
                            except (ValueError, TypeError):
                                pass
                        if initial_cap > 0:
                            running_equity = initial_cap
                            peak = initial_cap
                            max_dd_pct = 0.0
                            for t in sorted(today_trades, key=lambda x: x.get("closed_at") or x.get("timestamp") or ""):  # noqa: E501
                                running_equity += float(t.get("realized_pnl", 0) or 0)
                                if running_equity > peak:
                                    peak = running_equity
                                dd = (peak - running_equity) / peak * 100.0 if peak > 0 else 0.0
                                if dd > max_dd_pct:
                                    max_dd_pct = dd
                            if max_dd_pct > 0:
                                total_return_pct = (realized_pnl_total / initial_cap) * 100.0
                                enriched["today_calmar"] = f"{total_return_pct / max_dd_pct:.2f}"
                            elif realized_pnl_total > 0:
                                enriched["today_calmar"] = "∞"
                    except Exception:
                        pass

                except Exception as trade_err:
                    self.logger.debug("Live P&L poll — trade analytics skipped: %s", trade_err)
        except Exception as h05_err:
            self.logger.debug("Live P&L poll — H05 skipped: %s", h05_err)

        # ── 2. Account panel labels for today_pnl fallback ────────────────────
        if not enriched.get("today_pnl") and self.realized_value:
            realized_text = self.realized_value.text()
            if realized_text and realized_text not in ("—", "$0.00", ""):
                enriched["today_pnl"] = realized_text

        # ── 3. H07 overlay (historical multi-period Sharpe etc.) ──────────────
        if self._h07_performance_analytics is not None:
            try:
                h07_stats = self._h07_performance_analytics.get_summary_stats()
                if h07_stats:
                    for k, v in h07_stats.items():
                        enriched.setdefault(k, v)
            except Exception as h07_err:
                self.logger.debug("Live P&L poll — H07 skipped: %s", h07_err)

        # Only refresh when we actually have something to show.
        if enriched:
            self._pnl_stats_by_mode[TradingMode.LIVE] = dict(enriched)
            self._refresh_pnl_table(enriched)

    @Slot(str, float, float)
    def _on_balance_updated(self, source: str, equity: float, buying_power: float):
        """Update the live or SpyderBox account panel from the market worker."""
        source_key = str(source or "").strip().lower()

        if source_key == "paper":
            self._set_spyderbox_account_panel_values(
                settled=float(equity or 0.0),
                buying=float(buying_power or 0.0),
            )

            # Reconcile idle PAPER account balances into visible SpyderBox P&L
            # so orphan account-level adjustments are not silently omitted.
            if self.trading_mode == TradingMode.PAPER and not self.trading_active:
                try:
                    realized_delta = derive_realized_pnl_delta_from_equity(
                        equity,
                        capital_raw=getattr(self, "_paper_initial_capital", 100_000.0),
                        default_capital=100_000.0,
                    )
                    self._set_spyderbox_account_panel_values(realized=realized_delta)

                    mode_stats = dict(self._pnl_stats_by_mode.get(self.trading_mode, {}))
                    self._refresh_pnl_table(mode_stats)
                except Exception as exc:
                    self.logger.debug("paper balance reconciliation skipped: %s", exc)
            return

        self._set_account_money_label(self.settled_value, equity)
        self._set_account_money_label(self.buying_value, buying_power)

        # Persist most recent live-account panel values for startup restore.
        self._remember_current_account_snapshot()

    def _apply_paper_clean_slate_startup_guard(self) -> None:
        """Force PAPER account labels to baseline when no persisted state exists."""
        if self.trading_mode != TradingMode.PAPER:
            return

        state_file_raw = str(os.environ.get("SPYDER_PAPER_ACCOUNT_STATE_FILE", "")).strip()
        state_path = (
            Path(state_file_raw)
            if state_file_raw
            else (Path.home() / "Projects/Spyder/market_data/paper_trading_state.json")
        )

        # If persisted state exists, keep normal startup restore behavior.
        if state_path.exists():
            return

        try:
            from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

            paper_db = TradingSessionDB.for_paper()
            latest_snapshot = paper_db.get_latest_snapshot()
            has_recent_trade = bool(paper_db.get_recent_trades(limit=1))
            has_open_position = bool(paper_db.get_open_positions())
            db_is_empty = (
                latest_snapshot is None
                and not has_recent_trade
                and not has_open_position
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("paper clean-slate startup guard skipped: %s", exc)
            return

        if not db_is_empty:
            return

        baseline_capital = resolve_capital_baseline(
            getattr(self, "_paper_initial_capital", 100_000.0),
            default=100_000.0,
        )
        clean_account_snapshot = {
            "settled_cash": baseline_capital,
            "buying_power": baseline_capital,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }
        self._account_snapshot_by_mode[TradingMode.PAPER] = dict(clean_account_snapshot)
        self._pnl_stats_by_mode[TradingMode.PAPER] = {}
        self._apply_account_snapshot(clean_account_snapshot)
        self._set_spyderbox_account_panel_values(
            settled=baseline_capital,
            buying=baseline_capital,
            realized=0.0,
            unrealized=0.0,
        )

    def _init_account_display(self):
        """Set account P&L fields to $0.00 and load any persisted performance stats.

        Called once on startup (via QTimer.singleShot) after setup_ui() so every
        label is a real widget rather than None.  Ensures the account section never
        stays on the placeholder "—" values while waiting for the first trading
        session to start.
        """
        # Show $0.00 for session P&L — no trades have occurred yet.
        if self.realized_value:
            self.realized_value.setText("$0.00")
        if self.unrealized_value:
            self.unrealized_value.setText("$0.00")

        self._apply_paper_clean_slate_startup_guard()

        # Restore persisted account values for the current mode when available.
        saved_account = get_restorable_account_snapshot(
            self._account_snapshot_by_mode,
            self.trading_mode,
            paper_mode=TradingMode.PAPER,
        )
        if saved_account:
            self._apply_account_snapshot(saved_account)

        # Load any historical performance stats persisted by H07 so the P&L
        # Performance table shows real data immediately, not all "—".
        self._refresh_pnl_table(self._pnl_stats_by_mode.get(self.trading_mode, {}))

    @Slot(bool)
    def _on_paper_connection(self, connected: bool):
        """Handle paper trading connection result."""
        if connected:
            self.on_connection_status_changed(True, "Tradier (PAPER)")
            self.update_data_status("PAPER")
            if self.acct_number_lbl:
                import os as _os_conn
                self.acct_number_lbl.setText(_os_conn.environ.get("TRADIER_ACCOUNT_ID", "LIVE ACCOUNT UNSET"))
            self.add_system_log("PAPER TRADING ACTIVE — Connected to local SpyderBox account")
        else:
            self.add_system_log("❌ Paper trading could not connect to Tradier")

    def stop_trading(self):
        """Handle stop trading button click — mode-aware."""
        if not self.trading_active:
            if not self.api_connected:
                QMessageBox.information(
                    self,
                    "API Disconnected",
                    "API is disconnected - further trading has already stopped, but open orders at Tradier still remain in effect. If you wish to close or cancel these orders, call Tradier at +1 (312) 542-6901",  # noqa: E501
                )
            self.add_system_log("No active trading to stop")
            return

        self._stop_unified_session_supervisor(flatten=False)
        self._stop_live_pnl_poll()

        self.trading_active = False
        self.connection_info.trading_active = False
        self._paper_start_authorized = False
        self._cancel_start_button_loading_transition()
        self._paper_trading_armed = True
        self._paper_trading_enabled_this_session = True

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;",
        )
        self.start_btn.setText("START TRADING")
        self._update_mode_buttons()

        self.add_system_log("Trading stopped - Orders and positions remain active")
        self.add_system_log("TRADING STOPPED - Existing positions maintained")
        self.add_system_log("Automation session inactive")

    def emergency_close(self):
        """Handle emergency close button click - FIXED MESSAGES"""
        if not self.api_connected:
            QMessageBox.critical(
                self,
                "API Disconnected",
                "API is disconnected - unable to close open orders at Tradier. If you wish to close or cancel these orders, call Tradier at +1 (312) 542-6901",  # noqa: E501
            )
            return

        reply = QMessageBox.critical(
            self,
            "EMERGENCY CLOSE",
            "⚠️ EMERGENCY PROTOCOL ⚠️\n\n"
            "This will IMMEDIATELY:\n"
            "• Close ALL open positions\n"
            "• Cancel ALL pending orders\n"
            "• Stop automated trading\n"
            "• Disconnect from Tradier API\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.add_system_log(
                "🚨 EMERGENCY CLOSE - All positions closed, system stopped",
            )
            self.add_system_log(
                "EMERGENCY PROTOCOL - Close requested by operator",
            )

            self._stop_unified_session_supervisor(flatten=True)
            self._stop_live_pnl_poll()

            self.trading_active = False
            self.connection_info.trading_active = False
            self._paper_start_authorized = False
            self._cancel_start_button_loading_transition()
            self._paper_trading_armed = True
            self._paper_trading_enabled_this_session = True

            self.start_btn.setStyleSheet(
                f"background-color: {COLORS['positive']}; color: black;",
            )
            self.start_btn.setText("START TRADING")
            self._update_mode_buttons()

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.api_connected = False

    # ==========================================================================
    # ENHANCED STATUS MANAGEMENT
    # ==========================================================================
    def update_data_status(self, status_type: str):
        """Update data status display for live, extended-hours, EOD, and fallback states."""
        if status_type in ("LIVE", "REAL-TIME", "PAPER") and is_market_hours():
            self.data_status_label.setText("REAL-TIME")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Real-time market data — live prices")
        elif status_type == "PRE-OPEN":
            self.data_status_label.setText("PRE-OPEN")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["automation_active"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip(
                "Pre-open live snapshot hydrated from Tradier — strategy hunting and entries remain blocked until 10:15 ET",
            )
        elif status_type == "AFTER-HOURS":
            self.data_status_label.setText("AFTER-HRS")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["automation_active"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip(
                "After-hours live snapshot hydrated from Tradier — regular-session strategy hunting and entries are closed",
            )
        elif status_type in ("LIVE", "REAL-TIME", "PAPER"):
            self.data_status_label.setText("EOD")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["warning"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Market closed — showing EOD data")
        elif status_type == "EOD":
            self.data_status_label.setText("EOD")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["warning"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("End-of-day data loaded from Tradier")
        elif status_type == "FROZEN":
            self.data_status_label.setText("FROZEN")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["negative"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Data frozen — waiting for API reconnection")
        else:
            self.data_status_label.setText("NO DATA")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["negative"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("No Tradier market snapshot is available yet")

    def determine_data_status(self) -> str:
        """Determine appropriate data status based on current conditions."""
        market_hours = is_market_hours()
        et_tz = _get_eastern_timezone()

        def _as_et(timestamp: datetime) -> datetime:
            if timestamp.tzinfo is None:
                return et_tz.localize(timestamp)
            return timestamp.astimezone(et_tz)

        last_fetch_time = getattr(self.connection_info, "last_market_data_fetch_time", None)
        if (
            not market_hours
            and getattr(self, "real_data_active", False)
            and last_fetch_time is not None
        ):
            current_et = datetime.now(et_tz)
            try:
                fetch_age_seconds = abs((current_et - _as_et(last_fetch_time)).total_seconds())
            except (AttributeError, TypeError, ValueError):
                fetch_age_seconds = None

            if fetch_age_seconds is not None and fetch_age_seconds <= REALTIME_QUOTE_MAX_AGE_SECONDS and current_et.weekday() < 5:
                current_time = current_et.time()
                if current_time < MARKET_OPEN_TIME:
                    return "PRE-OPEN"
                if current_time > MARKET_CLOSE_TIME:
                    return "AFTER-HOURS"

        if self.api_connected:
            # API is connected
            if market_hours:
                freshest_quote_time = getattr(self.connection_info, "last_successful_data", None)
                if freshest_quote_time is not None:
                    quote_age_seconds = (
                        datetime.now(et_tz) - _as_et(freshest_quote_time)
                    ).total_seconds()
                    if quote_age_seconds <= REALTIME_QUOTE_MAX_AGE_SECONDS:
                        self.connection_info.data_was_live = True
                        return "REAL-TIME"
                    if self.connection_info.data_was_live:
                        return "FROZEN"
                return "EOD"
            return "EOD"
        # API is disconnected
        if self.real_data_active:
            # Using file data - always treat as EOD
            return "EOD"
        if (
            market_hours
            and hasattr(self.connection_info, "data_was_live")
            and self.connection_info.data_was_live
        ):
            # Market hours but no recent successful connection = FROZEN
            if (
                hasattr(self.connection_info, "last_successful_data")
                and self.connection_info.last_successful_data
                and (
                    datetime.now(et_tz) - _as_et(self.connection_info.last_successful_data)
                ).total_seconds()
                < 300
            ):  # 5 minutes
                return "FROZEN"
            return "EOD"
        return "NONE"

    def update_status_indicators(self):
        """Update both status indicators based on current state"""
        # Update data status
        data_status = self.determine_data_status()
        self.update_data_status(data_status)

    def toggle_market_data_provider(self, event):
        """Market data is always Tradier; this handler is a no-op."""
        self.add_system_log("ℹ️ Tradier is the only market data provider")
        self._apply_mkt_provider_display("tradier")

    def _apply_mkt_provider_display(self, provider: str) -> None:
        """Update the market data provider indicator label in the toolbar.

        Color is connection-based: red when disconnected, green when connected.
        """
        if not hasattr(self, "mkt_provider_label"):
            return
        if getattr(self, "mkt_data_connected", False) and is_market_hours():
            color = COLORS["positive"]
        elif getattr(self, "mkt_data_connected", False):
            color = COLORS["warning"]
        else:
            color = COLORS["negative"]
        self.mkt_provider_label.setText(provider.upper() + " DATA")
        self.mkt_provider_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        if hasattr(self, "circuit_breaker_dot") and self.circuit_breaker_dot:
            self.circuit_breaker_dot.setText("●")
            self.circuit_breaker_dot.setStyleSheet(f"color: {COLORS['positive']}; font-size: 14px;")
            self.circuit_breaker_dot.setToolTip("Circuit Breaker Status: NORMAL")

    def _toggle_data_display(self, event):
        """Synthetic market-data toggling is disabled."""
        self.add_system_log("ℹ️ Synthetic market data is disabled")

    def _toggle_mkt_data_connection(self, event):
        """Toggle market data feed connection (⚡ icon click handler)."""
        if self.mkt_data_connected:
            # Disconnect data feed
            self.mkt_data_connected = False
            if self.market_worker:
                self.market_worker.force_disconnect()
            self.add_system_log("🔌 Market data feed manually disconnected")
        else:
            # Connect data feed
            if not is_market_hours():
                QMessageBox.information(
                    self,
                    "Market Closed",
                    "Market is closed. Data feed available during trading hours:\n"
                    "4:00 AM - 4:30 PM ET",
                )
                return
            self.add_system_log("🔄 Connecting market data feed...")
            if self.market_worker and self.market_worker.force_connect():
                self.mkt_data_connected = True
                self.add_system_log("✅ Market data feed connected")
            else:
                self.add_system_log("❌ Failed to connect market data feed")

        import os
        provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        self._apply_mkt_provider_display(provider)
        self.update_status_indicators()

    def _init_simulation_from_real_data(self):
        """Initialize simulation starting from last real market prices"""
        if hasattr(self, "market_data") and self.market_data:
            spy_last = self.market_data.get("SPY", {}).get("last")
            # Use current market data as baseline for simulation
            if isinstance(spy_last, (int, float)):
                self.add_system_log(f"🎯 Simulation baseline: SPY ${spy_last:.2f}")
                return

        self.add_system_log("🎯 Simulation baseline unavailable - awaiting market data")

    def _on_eod_snapshot_fetched(self, success: bool) -> None:
        """Handle the result of the worker's outside-hours EOD price fetch.

        When the worker successfully fetches real last-trade prices from Tradier
        (success=True), activate the real-data patch so the dashboard shows
        genuine EOD figures and the label reads 'EOD'.

        When the fetch fails (success=False) — e.g. credentials missing or API
        unreachable — log a warning and leave the dashboard in a no-data state
        so the trader is never misled about what is being shown.
        """
        if success:
            self.add_system_log("📊 Real EOD data loaded from Tradier — prices are last close")
            self.apply_real_data_patch()
        else:
            self.add_system_log("⚠️ EOD snapshot unavailable — Tradier unreachable or not configured")  # noqa: E501
            self.update_data_status("NONE")

    # ==========================================================================
    # UTILITY METHODS - ENHANCED WITH HEARTBEAT WORKER
    # ==========================================================================
    def _start_metrics_orchestrator(self):
        """Instantiate the S07 CustomMetricsOrchestrator on the main Qt thread.

        Called via QTimer.singleShot so QTimers inside S07 bind to the correct thread.
        auto_start=True in S07.__init__ calls start() automatically, which in turn
        starts the S02 DIX and S04 Black Swan schedulers.
        """
        try:
            from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import get_metrics_orchestrator
            self._metrics_orchestrator = get_metrics_orchestrator()
            # Wire S07 output → custom metric widgets in the Market Overview panel
            self._metrics_orchestrator.metrics_updated.connect(self._on_custom_metrics_updated)
            self._metrics_orchestrator.stress_level_changed.connect(self._on_market_stress_changed)
            self._custom_metrics_live_announced = True
            start_plan = build_metrics_orchestrator_start_plan(
                hydrated_snapshot=self._hydrate_metrics_orchestrator_snapshot()
            )
            self._custom_metrics_live_announced = start_plan.live_announced_after_start
            for message in start_plan.log_messages:
                self.add_system_log(message)
        except Exception as e:
            self.logger.error("Failed to start metrics orchestrator: %s", e, exc_info=True)
            self.add_system_log(f"⚠️ Metrics orchestrator unavailable: {e}")

    def _hydrate_metrics_orchestrator_snapshot(self) -> bool:
        """Backfill Market Overview rows from S07 cached metrics after late connection."""
        orchestrator = getattr(self, "_metrics_orchestrator", None)

        try:
            probe = inspect_metrics_orchestrator_snapshot(orchestrator)
            if probe.snapshot is None or probe.formatter is None:
                return False

            self._on_custom_metrics_updated(probe.formatter(probe.snapshot))
            return True
        except Exception as exc:
            self.logger.debug("Custom metrics snapshot hydrate skipped: %s", exc)
            return False

    def _on_market_stress_changed(self, stress_level: str) -> None:
        """Surface market stress-regime transitions in Autonomous AI Activity."""
        if not is_market_hours():
            return
        level = str(stress_level).strip().upper() or "UNKNOWN"
        self.log_autonomous_event(
            f"S07 STRESS LEVEL → {level}",
            event_type="AGENT_OBSERVATION",
            source="S07",
        )

    def _on_custom_metrics_updated(self, metrics: dict) -> None:
        """Slot for SpyderS07 CustomMetricsOrchestrator.metrics_updated signal.

        S07 emits a nested dict: {"GEX": {"value": <float>, ...}, "DEX": {...}, ...}
        The widget expects raw-dollar values that it then divides by 1e9/"M" to format:
          - GEX: billions (S05 contract) → ×1e9 here → raw dollars → widget ÷1e9 → "B"
          - DEX: millions (S05 contract) → ×1e6 here → raw dollars → widget ÷1e6 → "M"
        """
        self._last_custom_metrics_payload = self._merge_metrics_payload(
            getattr(self, "_last_custom_metrics_payload", {}),
            dict(metrics) if isinstance(metrics, dict) else {},
        )
        self._persist_custom_metrics_snapshot()

        if not getattr(self, "_custom_metrics_live_announced", False):
            start_plan = build_metrics_orchestrator_start_plan(hydrated_snapshot=True)
            self._custom_metrics_live_announced = start_plan.live_announced_after_start
            for message in start_plan.log_messages:
                self.add_system_log(message)

        for s07_key, (widget_key, scale) in self._S07_METRIC_ROUTING.items():
            entry = metrics.get(s07_key)
            widget = self.symbol_widgets.get(widget_key)
            if widget is None:
                continue
            prev_attr = f"_cm_prev_{widget_key}"
            update_plan = build_custom_metric_widget_update_plan(
                entry=entry,
                scale=scale,
                previous_value=getattr(self, prev_attr, None),
            )
            if update_plan is None:
                continue
            if update_plan.next_previous_value is not None:
                setattr(self, prev_attr, update_plan.next_previous_value)

            widget.update_data(update_plan.payload)

        liquidity_entry = metrics.get("LIQUIDITY_DIAGNOSTICS")
        if isinstance(liquidity_entry, dict):
            payload = liquidity_entry.get("value", {})
            self._update_liquidity_diagnostics_panel(payload)

        # Forward TICK/ADD/TRIN/NYMO to the Market Internals dialog if it is open.
        # This ensures the popup always shows the same values as the Market Overview panel.
        dlg = getattr(self, "current_dialog", None)
        if dlg is not None and hasattr(dlg, "on_breadth_updated"):
            breadth_payload = build_custom_metric_breadth_dialog_payload(metrics)
            if breadth_payload is not None:
                dlg.on_breadth_updated(breadth_payload)

        # Update the 5-pill regime bar from live S07 metrics.
        self.update_regime_pills(metrics)

        # Sync REGIME traffic-light button in the SIGNAL MONITOR panel.
        if self.signal_panel is not None:
            signal_panel_plan = build_custom_metric_signal_panel_sync_plan(
                metrics=metrics,
                metric_routing=self._S07_METRIC_ROUTING,
                regime_value=getattr(self, "_regime_value", "—"),
            )
            self.signal_panel.update_regime(
                signal_panel_plan.regime_value,
                signal_panel_plan.swan,
                signal_panel_plan.dix,
                signal_panel_plan.skew,
                signal_panel_plan.gex,
            )
            if signal_panel_plan.live_data:
                self.signal_panel.update_live_data(signal_panel_plan.live_data)

    def _update_liquidity_diagnostics_panel(self, payload: dict) -> None:
        """Update right-panel liquidity diagnostics labels from S07 payload."""
        if self.liquidity_candidates_value is None:
            return

        summary = summarize_liquidity_diagnostics(payload)
        presentation = build_liquidity_diagnostics_panel_presentation(summary)

        self.liquidity_candidates_value.setText(presentation.candidates_text)
        self.liquidity_pass_ratio_value.setText(presentation.pass_ratio_text)
        self.liquidity_freshness_value.setText(presentation.freshness_text)
        self.liquidity_top_failure_value.setText(presentation.top_failure_text)

    def _derive_regime_label(self, metrics: dict) -> tuple[str, str]:
        """Derive a simple market regime label from live S07 metrics.

        Uses SWAN (tail risk), DIX (dark-pool buying), SKEW, and GEX.
        All of these are populated by S07 on every update cycle.
        Returns (label, colour_hex).
        """

        def _val(key: str, default: float) -> float:
            entry = metrics.get(key)
            if not isinstance(entry, dict):
                return default
            v = entry.get("value", default)
            if isinstance(v, float) and math.isnan(v):
                return default
            return float(v)

        swan = _val("SWAN", 1.9)
        dix  = _val("DIX",  42.0)
        skew = _val("SKEW", 120.0)
        gex  = _val("GEX",  0.0)

        # Priority order: extreme risk → high risk → directional → neutral
        if swan >= 2.0:
            return "EXTREME RISK", COLORS["negative"]
        if swan >= 1.95 or skew >= 150:
            return "HIGH RISK", COLORS["negative"]
        if skew >= 140 and dix < 42:
            return "CAUTIOUS", COLORS["warning"]
        if dix >= 46 and gex >= 0 and swan < 1.9:
            return "BULLISH", COLORS["positive"]
        if dix <= 40 and swan >= 1.85:
            return "BEARISH", COLORS["negative"]
        if dix >= 43 and swan < 1.92:
            return "NEUTRAL BULL", COLORS["positive"]
        return "NEUTRAL", COLORS["warning"]

    # ──────────────────────────────────────────────────────────────────
    # Regime pill bar — 5-field display (REGIME / STRESS / STANCE / GATE / DISPATCH)
    # ──────────────────────────────────────────────────────────────────

    def _get_dispatch_state_safe(self) -> dict:
        """Read D31's dispatch state, falling back to IDLE if unavailable.

        D31 lives behind the SessionSupervisor, which is None until the
        operator starts a paper or live session. Before that, return IDLE so
        the pill renders sensibly without raising.
        """
        try:
            sup = getattr(self, "_session_supervisor", None)
            orchestrator = getattr(sup, "orchestrator", None) if sup else None
            if orchestrator is not None and hasattr(orchestrator, "get_dispatch_state"):
                return orchestrator.get_dispatch_state()
        except Exception as exc:  # noqa: BLE001 — pill must never raise
            self.logger.debug("dispatch pill: D31 read failed: %s", exc)
        return {"state": "IDLE", "reason": "no session running", "age_s": None}

    def _get_execution_pill_state_safe(self) -> dict:
        """Read D31's stance/gate execution view, falling back to empty values."""
        try:
            sup = getattr(self, "_session_supervisor", None)
            orchestrator = getattr(sup, "orchestrator", None) if sup else None
            if orchestrator is not None and hasattr(orchestrator, "get_execution_pill_state"):
                state = orchestrator.get_execution_pill_state()
                if isinstance(state, dict):
                    return state
        except Exception as exc:  # noqa: BLE001 — pill must never raise
            self.logger.debug("execution pill read failed: %s", exc)
        return {"regime": "", "stance": "", "gate": "", "gate_key": ""}

    def update_regime_pills(self, metrics: dict) -> None:
        """Derive the regime bar using S07 for display regime and D31 for execution posture.

                Mapping:
                    REGIME    — canonical label (BULL / BEAR / RANGE / VOLATILE / CRISIS / EVENT)
                    STRESS    — S07 stress band (LOW / MEDIUM / HIGH / CRISIS / UNKNOWN)
                    STANCE    — D31 execution stance (BULLISH / CHOPPY / CRISIS)
                    GATE      — D31 policy gate label (Bull Trend / Bear Trend / Range Calm /
                                                                                High Vol / Crisis / Event)
                    DISPATCH  — execution state from D31, with regime-driven HALT priority
                                            (FLOWING / IDLE / BLOCKED / ERROR / HALT)

                v12 changes:
                    - BIAS pill removed (was informational, did not gate execution).
                    - TRADEABLE pill removed; its halt visual is now carried by DISPATCH=HALT
                        (purple), and its permitted-strategy / concurrency tooltip content is
                        now appended to the DISPATCH tooltip in every state.
                    - DISPATCH reads D31's `get_dispatch_state()` directly so operators see
                        *why* trades aren't firing without tailing the decision log.
        """
        if not hasattr(self, "regime_pill"):
            # Pills not yet built (dashboard not fully initialised).
            return
        if not hasattr(self, "_regime_sticky"):
            self._regime_sticky: str | None = None
        if not hasattr(self, "_vix_candidate_regime"):
            self._vix_candidate_regime: str = "RANGE"
            self._vix_candidate_count: int = 0

        vix_snapshot = None
        try:
            import json as _j
            _ld_path = self.data_file
            if _ld_path.exists():
                with open(_ld_path) as _f:
                    vix_snapshot = _j.load(_f)
        except Exception:
            pass

        state_plan = build_regime_pill_state_plan(
            metrics=metrics,
            regime_sticky=self._regime_sticky,
            vix_candidate_regime=self._vix_candidate_regime,
            vix_candidate_count=self._vix_candidate_count,
            vix_snapshot=vix_snapshot,
        )
        swan = state_plan.swan
        _s07_live = state_plan.s07_live
        regime = state_plan.regime
        self._regime_sticky = state_plan.next_regime_sticky
        self._vix_candidate_regime = state_plan.next_vix_candidate_regime
        self._vix_candidate_count = state_plan.next_vix_candidate_count

        execution_truth = self._get_execution_pill_state_safe()
        execution_regime = str(execution_truth.get("regime", "")).strip().lower()
        execution_gate_key = str(execution_truth.get("gate_key", "")).strip().lower()
        fallback_stress = None
        if _s07_live:
            pass
        else:
            try:
                orchestrator = getattr(self, "_metrics_orchestrator", None)
                if orchestrator is not None and hasattr(orchestrator, "get_stress_level"):
                    _stress_obj = orchestrator.get_stress_level()
                    fallback_stress = str(getattr(_stress_obj, "value", _stress_obj)).strip().upper() or "UNKNOWN"
            except Exception as _stress_err:
                self.logger.debug("stress-pill read failed: %s", _stress_err)

        status_plan = build_regime_pill_status_plan(
            regime=regime,
            swan=swan,
            s07_live=_s07_live,
            execution_truth=execution_truth,
            fallback_stress=fallback_stress,
        )
        stance = status_plan.stance
        stress = status_plan.stress
        gate = status_plan.gate

        # DISPATCH pill — execution truth from D31, with regime-driven HALT
        # priority. v12: absorbed the legacy TRADEABLE pill into this tooltip.
        dispatch_plan = build_regime_dispatch_announcement_plan(
            regime=regime,
            raw_dispatch_state=self._get_dispatch_state_safe(),
            last_dispatch_state_key=getattr(self, "_last_dispatch_state_key", ""),
        )
        dispatch_state = dispatch_plan.dispatch_state
        d_label = dispatch_plan.dispatch_label
        if dispatch_plan.should_announce and is_market_hours():
            self._last_dispatch_state_key = dispatch_plan.dispatch_state_key
            self.log_autonomous_event(
                dispatch_plan.autonomous_message,
                event_type="AGENT_OBSERVATION",
                source="D31",
            )
            if dispatch_plan.system_log_message:
                self.add_system_log(dispatch_plan.system_log_message)
        elif dispatch_plan.should_announce:
            self._last_dispatch_state_key = dispatch_plan.dispatch_state_key

        import os as _os
        _pivot_enabled = _os.getenv("SPYDER_ENABLE_PIVOT_MEAN_REVERSION", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        presentation = build_regime_pill_bar_presentation(
            regime=regime,
            stress=stress,
            stance=stance,
            gate=gate,
            dispatch_label=d_label,
            dispatch_reason=dispatch_state.get("reason", ""),
            execution_regime=execution_regime,
            execution_gate_key=execution_gate_key,
            s07_live=_s07_live,
            swan=swan,
            pivot_enabled=_pivot_enabled,
            panel_color=COLORS["panel"],
            border_color=COLORS["border"],
        )

        self._regime_value = regime
        self.regime_pill.setText(presentation.regime_pill.text)
        self.regime_pill.setStyleSheet(presentation.regime_pill.stylesheet)
        self.regime_pill.setToolTip(presentation.regime_pill.tooltip)

        if hasattr(self, "stress_pill"):
            self.stress_pill.setText(presentation.stress_pill.text)
            self.stress_pill.setStyleSheet(presentation.stress_pill.stylesheet)
            self.stress_pill.setToolTip(presentation.stress_pill.tooltip)

        self.stance_pill.setText(presentation.stance_pill.text)
        self.stance_pill.setStyleSheet(presentation.stance_pill.stylesheet)
        self.stance_pill.setToolTip(presentation.stance_pill.tooltip)

        self.gate_pill.setText(presentation.gate_pill.text)
        self.gate_pill.setStyleSheet(presentation.gate_pill.stylesheet)
        self.gate_pill.setToolTip(presentation.gate_pill.tooltip)

        self.dispatch_pill.setText(presentation.dispatch_pill.text)
        self.dispatch_pill.setStyleSheet(presentation.dispatch_pill.stylesheet)
        self.dispatch_pill.setToolTip(presentation.dispatch_pill.tooltip)

        if hasattr(self, "regime_bar_widget") and self.regime_bar_widget is not None:
            self.regime_bar_widget.setStyleSheet(presentation.bar_stylesheet)

    def start_market_worker(self, *, quiet_startup: bool = False, announce: bool = True):
        """Start the enhanced market worker with heartbeat monitoring"""
        if getattr(self, "_shutdown_in_progress", False):
            return
        if getattr(self, "_market_worker_started", False):
            return

        try:
            self._market_worker_started = True
            self.market_thread = QThread()
            self.market_worker = ThreadSafeMarketDataWorker(quiet_startup=quiet_startup)
            self.market_worker.moveToThread(self.market_thread)

            # Connect all signals including new heartbeat signal
            self.market_worker.data_updated.connect(self.on_market_data_updated)
            self.market_worker.connection_status_changed.connect(
                self.on_connection_status_changed,
            )
            self.market_worker.market_data_status_changed.connect(
                self.on_market_data_status_changed,
            )
            self.market_worker.error_occurred.connect(self.on_market_error)
            self.market_worker.heartbeat_received.connect(self.on_heartbeat_received)
            self.market_worker.heartbeat_status_changed.connect(
                self.on_heartbeat_status_changed,
            )  # NEW
            self.market_worker.log_message.connect(
                self.add_system_log,
            )  # NEW: Direct log messages
            self.market_worker.balance_updated.connect(
                self._on_balance_updated,
            )  # NEW: Account balance from Tradier
            self.market_worker.eod_snapshot_fetched.connect(
                self._on_eod_snapshot_fetched,
            )  # Real EOD prices written outside market hours
            self.market_worker.fetch_requested.connect(
                self.market_worker.run_full_fetch,
                Qt.QueuedConnection,
            )  # Safe cross-thread trigger
            self.market_worker.fast_fetch_requested.connect(
                self.market_worker.run_fast_fetch,
                Qt.QueuedConnection,
            )  # Lightweight 10-second quote-only refresh

            self.market_thread.started.connect(self.market_worker.start)
            self.market_thread.finished.connect(self.market_worker.deleteLater)
            self.market_thread.finished.connect(self.market_thread.deleteLater)
            self.market_thread.start()

            if announce:
                self.add_system_log(
                    "🔈 Market data worker started with heartbeat monitoring",
                )

        except Exception as e:
            self._market_worker_started = False
            self.logger.exception("Error starting market worker: %s", e)
            self.add_system_log(f"❌ Market worker error: {e}")

    def setup_timers(self):
        """Setup various timers"""
        # Date/time update timer
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)

        # Chart update timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(30000)

    def _start_decision_flow_timer(self) -> None:
        """Start the compact decision-flow timer once runtime warmup is complete."""
        if getattr(self, "_decision_flow_timer_started", False):
            return
        if QTimer is None:
            return

        self._decision_flow_timer_started = True
        self._decision_flow_timer = QTimer(self)
        self._decision_flow_timer.timeout.connect(self._update_recent_decision_flow_diagnostics)
        self._decision_flow_timer.start(30000)
        QTimer.singleShot(250, self._update_recent_decision_flow_diagnostics)

    def update_datetime(self):
        """Update date/time display"""
        _et_tz = _get_eastern_timezone()
        current_time = datetime.now(_et_tz).strftime("%Y-%m-%d   %H:%M:%S  ET")
        self.datetime_label.setText(current_time)
        self._update_trading_window_compact_label()

    def _update_trading_window_compact_label(self) -> None:
        """Update compact RTH status badge shown beside FLOW/EC/BLOCK."""
        try:
            label = getattr(self, "trading_window_compact_label", None)
            if label is None:
                return

            presentation = build_trading_window_badge_presentation(
                is_open=is_market_hours(),
                colors=COLORS,
            )
            label.setText(presentation.text)
            label.setStyleSheet(presentation.style)
        except Exception as exc:
            self.logger.debug("Could not update RTH compact label: %s", exc)

    def confirm_close_strategy(self, strategy_data: dict):
        """Show confirmation dialog before closing strategy"""
        confirm_plan = build_close_strategy_confirm_plan(
            strategy_data=strategy_data,
            colors=COLORS,
        )
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(confirm_plan.title)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(confirm_plan.text)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)

        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)
        yes_btn.setText(confirm_plan.yes_button_text)
        yes_btn.setStyleSheet(confirm_plan.yes_button_style)

        cancel_btn = msg_box.button(QMessageBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet(confirm_plan.cancel_button_style)

        msg_box.setStyleSheet(confirm_plan.dialog_style)

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self.close_strategy(strategy_data)

    def close_strategy(self, strategy_data: dict):
        """Close all legs of a strategy with market orders.

        Delegates leg parsing and API submission to DashboardOrderManager
        (audit §5).  This method handles only the resulting UX: success dialog,
        error messageboxes, and system log messages.
        """
        strategy_name = strategy_data["strategy"]
        legs_data = strategy_data.get("legs", [])
        num_legs = len(legs_data)

        self.log_system_message(
            f"⚠️ MANUAL OVERRIDE: Closing {strategy_name} strategy ({num_legs} legs)...",
        )

        self._order_manager.set_client(self._get_tradier_client_for_mode())

        try:
            response = self._order_manager.submit_multileg_close(strategy_name, legs_data)
            success_plan = build_close_strategy_success_plan(
                strategy_name=strategy_name,
                num_legs=num_legs,
                response=response,
            )
            self.log_system_message(success_plan.log_message)
            QMessageBox.information(
                self,
                success_plan.dialog_title,
                success_plan.dialog_text,
            )
        except (TradierAPIError if TradierAPIError is not None else Exception) as e:  # noqa: B030
            self.logger.exception(
                "Tradier API error closing strategy '%s': %s", strategy_name, e,
            )
            failure_plan = build_close_strategy_failure_plan(
                failure_kind="tradier_api",
                strategy_name=strategy_name,
                error_text=str(e),
            )
            self.log_system_message(failure_plan.log_message)
            QMessageBox.critical(
                self,
                failure_plan.dialog_title,
                failure_plan.dialog_text,
            )
        except ValueError as e:
            self.logger.exception(
                "Validation error closing strategy '%s': %s", strategy_name, e,
            )
            failure_plan = build_close_strategy_failure_plan(
                failure_kind="validation",
                strategy_name=strategy_name,
                error_text=str(e),
            )
            self.log_system_message(failure_plan.log_message)
            QMessageBox.critical(
                self,
                failure_plan.dialog_title,
                failure_plan.dialog_text,
            )
        except Exception as e:
            self.logger.exception(
                "Unexpected error closing strategy '%s': %s", strategy_name, e,
            )
            failure_plan = build_close_strategy_failure_plan(
                failure_kind="unexpected",
                strategy_name=strategy_name,
                error_text=f"{e!s}",
            )
            self.log_system_message(failure_plan.log_message)
            QMessageBox.critical(
                self,
                failure_plan.dialog_title,
                failure_plan.dialog_text,
            )

    def load_default_risk_parameters(self):
        """Seed current_risk_params for the G09 risk-parameters dialog.

        Note: these are GUI-layer display/filter thresholds consumed by
        SpyderG09_RiskParametersDialog, NOT broker-level limits. In particular
        max_position_size here is in *dollars*, while SpyderE01_RiskManager
        uses max_position_size as a *contract count*. The two live in separate
        namespaces on purpose — do not delegate blindly."""
        self.current_risk_params = {
            "max_position_size": 50000,
            "max_daily_loss": 5000,
            "max_portfolio_delta": 100,
            "max_portfolio_gamma": 50,
            "vix_threshold": 30,
            "correlation_limit": 0.8,
        }

    def _subscribe_to_events(self) -> None:
        """Subscribe to system events for real-time dashboard updates (Phase 5-A).
        
        Subscribes to RISK events from the event bus so the dashboard can display
        live event-clock state updates as they occur during trading.
        """  # noqa: W293
        if getattr(self, "_shutdown_in_progress", False):
            return
        if getattr(self, "_event_subscriptions_started", False):
            return

        self._event_subscriptions_started = True
        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import (
                EventType,
                HandlerType,
                get_event_manager,
            )
  # noqa: W293
            event_manager = get_event_manager()
            subscription_plan = build_event_subscription_plan(
                event_type_cls=EventType,
                handler_type_cls=HandlerType,
            )
            for spec in subscription_plan:
                handler_id = event_manager.subscribe(
                    spec.event_type,
                    getattr(self, spec.handler_attr_name),
                    name=spec.subscription_name,
                    handler_type=spec.handler_type,
                )
                setattr(self, spec.handler_id_attr_name, handler_id)
                self.logger.info(spec.log_message)
        except Exception as e:
            self._event_subscriptions_started = False
            self.logger.warning("⚠️ Event subscription failed (non-blocking): %s", e)

    def _handle_trade_event(self, event: dict) -> None:
        """Handle TRADE events and update execution-health display."""
        try:
            sample = extract_execution_telemetry_sample(event)
            if sample is None:
                return

            with self._execution_telemetry_lock:
                self._execution_telemetry_events.append(sample)

            # Update UI from main thread.
            QTimer.singleShot(0, self._update_execution_health_display)
        except Exception as e:
            self.logger.debug("Execution telemetry processing error (non-blocking): %s", e)

    def _handle_position_updated_event(self, event: dict) -> None:
        """Refresh paper positions after runtime POSITION_UPDATED persistence."""
        try:
            if getattr(self, "trading_mode", None) != TradingMode.PAPER:
                return

            if extract_position_update_symbol(event) is None:
                return

            QMetaObject.invokeMethod(
                self,
                "_refresh_paper_positions_after_update",
                Qt.ConnectionType.QueuedConnection,
            )
        except Exception as e:
            self.logger.debug("Paper position refresh event error (non-blocking): %s", e)

    @Slot()
    def _refresh_paper_positions_after_update(self) -> None:
        """Refresh paper positions immediately and once more after H05 persistence settles."""
        self._refresh_positions_table()
        if QTimer is not None:
            QTimer.singleShot(150, self._refresh_positions_table)

    def _update_execution_health_display(self) -> None:
        """Refresh execution-health labels from rolling telemetry cache."""
        if self.execution_reject_rate_value is None:
            return

        with self._execution_telemetry_lock:
            samples = list(self._execution_telemetry_events)

        presentation = build_execution_health_presentation(samples)
        self.execution_slippage_bps_value.setText(presentation.slippage_bps_text)
        self.execution_fill_latency_value.setText(presentation.fill_latency_text)
        self.execution_reject_rate_value.setText(presentation.reject_rate_text)
        self.execution_partial_fill_value.setText(presentation.partial_fill_text)

    def _get_recent_decision_flow_for_panel(self) -> dict:
        """Return the compact recent D31 decision-flow slice for the active mode."""
        plan = build_recent_decision_flow_fetch_plan(
            live_mode=getattr(self, "trading_mode", None) == TradingMode.LIVE,
            limit=getattr(self, "_decision_flow_recent_limit", 0),
        )
        try:
            diagnostics = getattr(self, "_decision_flow_diagnostics", None)
            if diagnostics is None:
                from Spyder.SpyderQ_Scripts.SpyderQ92_DiagnosticsUtilities import DiagnosticsUtilities

                diagnostics = DiagnosticsUtilities(verbose=False)
                self._decision_flow_diagnostics = diagnostics

            return diagnostics.collect_recent_decision_flow(
                run_mode=plan.run_mode,
                limit=plan.limit,
            )
        except Exception as exc:
            self.logger.debug("Recent decision-flow diagnostics unavailable: %s", exc)
            return plan.fallback_result

    @staticmethod
    def _format_recent_decision_events_for_panel(records: list[dict]) -> str:
        """Format compact recent decision events for the execution-health panel."""
        return format_recent_decision_events(records)

    def _update_recent_decision_flow_diagnostics(self) -> None:
        """Refresh compact recent dispatch/drop diagnostics in the execution-health panel."""
        dispatch_label = getattr(self, "execution_recent_dispatch_value", None)
        drop_label = getattr(self, "execution_recent_drop_value", None)
        if dispatch_label is None or drop_label is None:
            return

        presentation = build_recent_decision_flow_panel_presentation(
            self._get_recent_decision_flow_for_panel()
        )

        dispatch_label.setText(presentation.dispatch_text)
        drop_label.setText(presentation.drop_text)

        if hasattr(dispatch_label, "setToolTip"):
            dispatch_label.setToolTip(presentation.tooltip)
        if hasattr(drop_label, "setToolTip"):
            drop_label.setToolTip(presentation.tooltip)

    def _handle_risk_alert_event(self, event: dict) -> None:
        """Display entry-gate/risk-gate block reasons in dashboard system status."""
        try:
            event_payload = event
            if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
                event_payload = getattr(event, "data")  # noqa: B009

            if not isinstance(event_payload, dict):
                return

            presentation = build_entry_block_alert_presentation(
                event_payload.get("reason"),
                message=event_payload.get("message"),
                detail=event_payload.get("detail"),
            )
            dispatch_plan = build_risk_alert_dispatch_plan(
                presentation=presentation,
                last_digest=self._last_entry_block_message,
                last_timestamp=self._last_entry_block_ts,
                now_monotonic=time.monotonic(),
            )
            if dispatch_plan.should_skip:
                return

            self._last_entry_block_message = dispatch_plan.next_digest
            self._last_entry_block_ts = dispatch_plan.next_timestamp

            QTimer.singleShot(0, lambda: self.log_system_message(dispatch_plan.system_log_message))
            QTimer.singleShot(0, lambda: self._update_entry_block_compact_label(dispatch_plan.compact_display))
        except Exception as e:
            self.logger.debug("Risk-alert display error (non-blocking): %s", e)

    def _update_entry_block_compact_label(self, text: str) -> None:
        """Update compact toolbar label showing latest entry-block reason."""
        try:
            label = getattr(self, "entry_block_compact_label", None)
            if label is None:
                return
            presentation = build_entry_block_compact_presentation(text)
            label.setText(presentation.text)
            label.setToolTip(presentation.tooltip)
            label.setStyleSheet(presentation.style)
        except Exception as e:
            self.logger.debug("Entry-block compact label update failed: %s", e)

    def _handle_risk_event(self, event: dict) -> None:
        """Handle RISK events and update event-clock display.
        
        Args:
            event: Event dict with keys 'type', 'data', 'timestamp', etc.
        """  # noqa: W293
        try:
            plan = build_event_clock_risk_event_plan(
                event,
                timestamp=datetime.now(_get_eastern_timezone()),
            )
            if not plan.should_update or plan.state_kwargs is None:
                return

            with self._event_clock_lock:
                from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState

                self.event_clock_state = EventClockState(**plan.state_kwargs)

            QTimer.singleShot(0, self._update_event_clock_display)
        except Exception as e:
            self.logger.debug("Event processing error (non-blocking): %s", e)

    def _update_event_clock_display(self) -> None:
        """Update event-clock display panel with current state (main thread)."""
        try:
            if self.event_clock_state_label is None and self.event_clock_compact_label is None:
                return
  # noqa: W293
            with self._event_clock_lock:
                state = self.event_clock_state
  # noqa: W293
            presentation = build_event_clock_display_presentation(state)

            if self.event_clock_state_label:
                self.event_clock_state_label.setText(presentation.state_text)
                self.event_clock_state_label.setStyleSheet(presentation.state_style)

            if self.event_clock_compact_label:
                self.event_clock_compact_label.setText(presentation.compact_text)
                self.event_clock_compact_label.setStyleSheet(presentation.compact_style)
  # noqa: W293
            if self.event_clock_policy_label:
                if self.event_clock_windows_label is None:
                    self.event_clock_policy_label.setText(
                        presentation.policy_and_windows_text
                    )
                else:
                    self.event_clock_policy_label.setText(presentation.policy_text)
            if self.event_clock_windows_label:
                self.event_clock_windows_label.setText(presentation.windows_text)
  # noqa: W293
            if self.event_clock_strategies_label:
                self.event_clock_strategies_label.setText(
                    presentation.strategies_text
                )
        except Exception as e:
            self.logger.debug("Display update error (non-blocking): %s", e)

    def _toggle_event_clock_override(self) -> None:
        """Toggle manual event-clock blackout override and notify scheduler."""
        try:
            active = bool(self.event_clock_override_button.isChecked())
            self.event_clock_override_active = active
            plan = build_event_clock_override_plan(active)
            self.event_clock_override_button.setText(plan.button_label)

            from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType
            event_manager = EventManager.get_instance()
            event_manager.emit(
                EventType.RISK,
                {"type": plan.event_name, "payload": plan.event_payload},
                priority="high",
            )
        except Exception as exc:
            self.logger.debug("Manual event-clock override failed: %s", exc)

    def update_risk_parameters(self, params: dict) -> None:
        """Receive updated risk parameters from the G09 Risk Levels dialog.

        Connected to ``RiskParametersDialog.parameters_updated`` by
        ``show_risk_parameters_dialog()`` so that clicking Apply/OK in the
        dialog immediately updates the dashboard's risk state.

        If a paper trading worker is currently running, the new limits are
        forwarded to it immediately so they take effect without a restart.
        """
        if not isinstance(params, dict):
            return
        self.current_risk_params = params
        self.add_system_log(
            f"⚙️ Risk parameters updated — "
            f"Risk/Trade: {params.get('risk_per_trade', '?')}% | "
            f"Max Daily Loss: {params.get('max_daily_loss_pct', '?')}% | "
            f"Max Buying Power: {params.get('max_buying_power_pct', '?')}%"
        )
        # Forward to running paper worker so limits take effect immediately
        if self._paper_worker is not None:
            self._paper_worker.set_risk_params(params)
            # Rebuild the E01 RiskManager with the new limits so
            # validate_signal() reflects the latest dialog settings.
            # Pull the live worker's starting capital so the rescaled dollar
            # limits match what the worker actually trades against.
            live_capital = float(
                getattr(self._paper_worker, "_initial_capital", 100_000.0)
            )
            new_rm = self._build_paper_risk_manager(initial_capital=live_capital)
            if new_rm is not None:
                self._paper_worker.set_risk_manager(new_rm)

    def _build_paper_risk_manager(self, initial_capital: float):
        """Construct a SpyderE01_RiskManager seeded from current_risk_params.

        Maps the G09 dialog's percentage-based dict into E01's absolute-dollar
        risk_limits dict, using *initial_capital* as the reference. Returns
        None when E01 is unavailable or construction fails — the worker will
        then fall back to its local _get_risk_limit() checks only.
        """
        try:
            from Spyder.SpyderE_Risk.SpyderE01_RiskManager import (
                DEFAULT_RISK_LIMITS as e01_default_risk_limits,
                RiskConfig as e01_risk_config,
                RiskManager as e01_risk_manager,
            )
        except ImportError:
            return None

        if e01_risk_manager is None or e01_risk_config is None:
            return None

        mapping_plan = build_paper_risk_limit_mapping_plan(
            default_risk_limits=e01_default_risk_limits,
            current_risk_params=self.current_risk_params,
            initial_capital=initial_capital,
        )
        limits = mapping_plan.risk_limits
        if mapping_plan.warning_message is not None:
            self.logger.warning(mapping_plan.warning_message)

        try:
            cfg = e01_risk_config(risk_limits=limits, enable_real_time_monitoring=False)
            return e01_risk_manager(
                config=cfg,
                connect_api=None,
                order_manager=None,
                tradier_client=self.tradier_client,
            )
        except Exception as exc:
            self.logger.warning("Could not construct E01 RiskManager: %s", exc)
            return None

    def show_risk_parameters(self):
        """Show risk parameters dialog"""
        if risk_dialog_available and show_risk_parameters_dialog:
            show_risk_parameters_dialog(self)
        else:
            p = self.current_risk_params or {}
            QMessageBox.information(
                self,
                "Risk Parameters",
                "Risk Parameters Configuration\n\n"
                f"Max Position Size: ${p.get('max_position_size', 0):,}\n"
                f"Max Daily Loss: ${p.get('max_daily_loss', 0):,}\n"
                f"Max Portfolio Delta: {p.get('max_portfolio_delta', 0)}\n"
                f"Max Portfolio Gamma: {p.get('max_portfolio_gamma', 0)}\n"
                f"VIX Threshold: {p.get('vix_threshold', 0)}\n"
                f"Correlation Limit: {p.get('correlation_limit', 0)}",
            )

    def _append_to_ring_log(self, buffer: list, widget, message: str,
                             max_buffer: int = 100, display_count: int = 20) -> None:
        """Append to a ring buffer and schedule a batched widget refresh."""
        timestamp = datetime.now(_get_eastern_timezone()).strftime("%H:%M:%S")
        append_plan = build_ring_log_append_plan(
            buffer=buffer,
            message=message,
            max_buffer=max_buffer,
            timestamp_text=timestamp,
        )
        buffer[:] = append_plan.next_buffer
        self._schedule_log_widget_refresh(buffer, widget, display_count)

    def _schedule_log_widget_refresh(self, buffer: list, widget, display_count: int) -> None:
        """Coalesce repeated log writes into a single UI refresh."""
        refresh_plan = build_log_widget_refresh_plan(
            has_widget=widget is not None,
            is_system_widget=widget is self.system_log,
            is_automation_widget=widget is self.auto_log,
            system_pending=self._system_log_flush_pending,
            automation_pending=self._automation_log_flush_pending,
        )
        if refresh_plan.action == "skip":
            return

        if refresh_plan.set_system_pending:
            self._system_log_flush_pending = True
        if refresh_plan.set_automation_pending:
            self._automation_log_flush_pending = True

        target = refresh_plan.target or "other"
        if refresh_plan.action == "schedule":
            QTimer.singleShot(
                75,
                lambda: self._flush_log_widget(buffer, widget, display_count, target),
            )
            return

        self._flush_log_widget(buffer, widget, display_count, target)

    def _flush_log_widget(self, buffer: list, widget, display_count: int, target: str) -> None:
        """Render the latest slice of a buffered log widget."""
        try:
            if widget is None:
                return
            widget.setUpdatesEnabled(False)
            widget.clear()
            widget.append("\n".join(reversed(buffer[-display_count:])))
            cursor = widget.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            widget.setTextCursor(cursor)
        finally:
            if widget is not None:
                widget.setUpdatesEnabled(True)
            if target == "system":
                self._system_log_flush_pending = False
            elif target == "automation":
                self._automation_log_flush_pending = False

    def add_system_log(self, message: str):
        """Add message to system log."""
        if self._should_suppress_after_hours_system_log(message):
            return
        if self._should_suppress_opening_warmup_system_log(message):
            return
        self._append_to_ring_log(self.system_logs, self.system_log, message,
                                  max_buffer=200, display_count=200)

    def _is_opening_runtime_warmup_active(self) -> bool:
        """Return True while the pre-open quiet hydration window is active."""
        return bool(
            getattr(self, "_opening_data_warmup_started", False)
            and not getattr(self, "_opening_runtime_warmup_completed", False)
        )

    def _should_suppress_opening_warmup_system_log(self, message: str) -> bool:
        """Hide nonessential operator log lines during the opening hydration window."""
        if not self._is_opening_runtime_warmup_active():
            return False
        return should_suppress_opening_warmup_system_log_text(message)

    def _should_suppress_after_hours_system_log(self, message: str) -> bool:
        """Return True for non-critical messages to hide outside market hours."""
        if not getattr(self, "_quiet_after_hours_logs", True):
            return False

        if is_market_hours():
            return False
        return should_suppress_after_hours_system_log_text(message)

    def log_system_message(self, message: str) -> None:
        """Compatibility wrapper for legacy call sites using the old log method name."""
        try:
            if getattr(self, "system_log", None) is not None:
                self.add_system_log(message)
            elif hasattr(self, "logger") and self.logger is not None:
                self.logger.info(message)
        except Exception:
            if hasattr(self, "logger") and self.logger is not None:
                self.logger.exception("Failed to write system message: %s", message)

    def add_automation_log(
        self,
        message: str,
        event_type: str = "LEGACY_STATUS",
        source: str = "dashboard",
    ):
        """Add a message to Autonomous AI Activity when it is truly autonomous.

        Non-autonomous/status events are automatically routed to System Log.
        """
        plan = build_automation_log_routing_plan(
            message=message,
            event_type=event_type,
            source=source,
            autonomous_event_type_allowlist=_AUTONOMOUS_EVENT_TYPE_ALLOWLIST,
        )
        if plan.route != "automation":
            self.add_system_log(plan.formatted_message)
            return

        self._append_to_ring_log(
            self.automation_logs,
            self.auto_log,
            plan.formatted_message,
            max_buffer=100,
            display_count=100,
        )

    def log_autonomous_event(
        self,
        message: str,
        event_type: str = "AGENT_OBSERVATION",
        source: str = "dashboard",
    ) -> None:
        """Explicit API for autonomous decision/activity events."""
        self.add_automation_log(message, event_type=event_type, source=source)

    def _set_system_log_verbosity(self, mode: str, announce: bool = True) -> None:
        """Set system-log verbosity profile and update related logger levels."""
        plan = build_system_log_verbosity_plan(
            mode=mode,
            announce=announce,
            debug_level=logging.DEBUG,
            normal_level=logging.ERROR,
        )
        self.system_log_mode = plan.selected_mode

        for logger_name in self._signal_noise_loggers:
            logging.getLogger(logger_name).setLevel(plan.logger_level)

        if hasattr(self, "system_log_normal_btn") and self.system_log_normal_btn is not None:
            self.system_log_normal_btn.setChecked(plan.normal_button_checked)

        if hasattr(self, "system_log_debug_btn") and self.system_log_debug_btn is not None:
            self.system_log_debug_btn.setChecked(plan.debug_button_checked)

        if plan.announcement_message is not None:
            self.add_system_log(plan.announcement_message)

    def toggle_system_log_verbosity(self) -> None:
        """Toggle system-log verbosity between NORMAL and DEBUG."""
        new_mode = "DEBUG" if self.system_log_mode == "NORMAL" else "NORMAL"
        self._set_system_log_verbosity(new_mode, announce=True)

    def _resolve_veto_profile_path(self) -> Path:
        """Resolve config profile path used by the dashboard veto toggle."""
        import os

        profile = str(os.environ.get("ENVIRONMENT", "development")).strip().lower()
        config_dir = project_root / "config"

        if profile in {"live", "production", "prod"}:
            return config_dir / "production.json"

        return config_dir / "development.json"

    def _load_veto_controls_state(self) -> bool:
        """Load unified veto-enabled state from config profile with env fallback."""
        import os

        default_enabled = True
        profile_path = self._resolve_veto_profile_path()
        profile_data = None

        if profile_path.exists():
            try:
                loaded_data = json.loads(profile_path.read_text(encoding="utf-8"))
                if isinstance(loaded_data, dict):
                    profile_data = loaded_data
            except Exception:
                pass

        return resolve_veto_controls_enabled_state(
            profile_data=profile_data,
            default_enabled=default_enabled,
            env_values={
                "ENABLE_X16_VETO": os.environ.get("ENABLE_X16_VETO"),
                "ENABLE_Y03_TRADE_VETO": os.environ.get("ENABLE_Y03_TRADE_VETO"),
                "ENABLE_Y05_VETO_CONSUMPTION": os.environ.get("ENABLE_Y05_VETO_CONSUMPTION"),
            },
        )

    def _apply_veto_toggle_button_state(self) -> None:
        """Render veto button state and styling in Advanced Controls."""
        btn = getattr(self, "veto_toggle_btn", None)
        if btn is None:
            return

        enabled = bool(getattr(self, "_veto_controls_enabled", True))
        presentation = build_veto_toggle_button_presentation(enabled)
        btn.setChecked(presentation.checked)
        btn.setText(presentation.text)
        btn.setStyleSheet(presentation.style)
        btn.setToolTip(presentation.tooltip)

    def _persist_veto_controls_state(self, enabled: bool) -> tuple[bool, str]:
        """Persist veto state to profile JSON, env vars, and ConfigManager cache."""
        import os

        profile_path = self._resolve_veto_profile_path()

        try:
            if profile_path.exists():
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            else:
                data = {}

            plan = build_veto_controls_persist_plan(
                existing_data=data,
                enabled=enabled,
            )
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(plan.serialized_profile_text, encoding="utf-8")

            for env_name, env_value in plan.env_updates.items():
                os.environ[env_name] = env_value

            try:
                from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

                cfg = get_config_manager()
                cfg.update(plan.payload, source="dashboard")
            except Exception:
                pass

            return True, str(profile_path)
        except Exception as exc:
            return False, str(exc)

    def _toggle_veto_controls(self) -> None:
        """Toggle veto controls used by X16/Y03/Y05 and persist the setting."""
        next_state = not bool(getattr(self, "_veto_controls_enabled", True))
        success, detail = self._persist_veto_controls_state(next_state)
        plan = build_veto_toggle_result_plan(
            success=success,
            next_state=next_state,
            detail=detail,
        )

        if plan.should_update_enabled_state:
            self._veto_controls_enabled = next_state
        self._apply_veto_toggle_button_state()
        for message in plan.system_log_messages:
            self.add_system_log(message)

    def setup_white_tooltips(self):
        """Apply the white-tooltip theme to this window (delegates to module helper)."""
        try:
            apply_tooltip_theme(QApplication.instance(), self)
        except Exception as e:
            self.add_system_log(f"⚠️ Tooltip styling error: {e}")

    def _refresh_startup_readiness_state(self) -> None:
        """Finish non-critical readiness/config warmup after the first frame."""
        plan = build_startup_readiness_refresh_plan(
            shutdown_in_progress=getattr(self, "_shutdown_in_progress", False),
        )
        if plan.should_skip:
            return
        try:
            def _load_multiplier() -> None:
                self._dji_from_dia_multiplier = self._load_dji_proxy_multiplier()

            def _collect_state() -> None:
                self._startup_readiness_state = self._collect_startup_readiness_state()

            step_handlers = {
                "load_multiplier": _load_multiplier,
                "collect_state": _collect_state,
                "emit_logs": self._emit_startup_readiness_logs,
            }
            for step_name in plan.step_names:
                step_handlers[step_name]()
        except RuntimeError:
            # Window may already be tearing down when delayed warmup fires.
            return

    def _collect_startup_readiness_state(self) -> dict[str, object]:
        """Read readiness-validation outcome from A03 ConfigManager for startup UX."""
        state = build_startup_readiness_base_state()
        state["source"] = "unknown"

        try:
            import os
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()
            env_mode = os.environ.get("TRADING_MODE", "")
            runtime_paper_mode = cfg.get("runtime.paper_mode", None)
            configured_mode = cfg.get("trading.mode", "paper")
            automation_enabled = bool(cfg.get("automation.enabled", True))
            warnings = []
            errors = []
            if hasattr(cfg, "validate_autonomous_readiness_config"):
                validation_mode = build_startup_readiness_state_plan(
                    env_mode=env_mode,
                    runtime_paper_mode=runtime_paper_mode,
                    configured_mode=configured_mode,
                    automation_enabled=automation_enabled,
                    warnings=warnings,
                    errors=errors,
                    market_hours_open=True,
                    preconnect_idle=True,
                ).mode
                result = cfg.validate_autonomous_readiness_config(cfg.config_data, validation_mode)
                warnings = list(result.get("warnings", []))
                errors = list(result.get("errors", []))

            # Startup readiness should explicitly reflect market-hours state so
            # operators can reconcile startup status with start-button gating.
            current_et = datetime.now(_get_eastern_timezone())
            state_plan = build_startup_readiness_state_plan(
                env_mode=env_mode,
                runtime_paper_mode=runtime_paper_mode,
                configured_mode=configured_mode,
                automation_enabled=automation_enabled,
                warnings=warnings,
                errors=errors,
                market_hours_open=is_market_hours(current_et),
                preconnect_idle=_is_preconnect_idle_window(current_et),
            )

            state.update(
                build_startup_readiness_success_state_payload(
                    mode=state_plan.mode,
                    automation_enabled=state_plan.automation_enabled,
                    warnings=state_plan.warnings,
                    errors=state_plan.errors,
                    safe_fallback_applied=state_plan.safe_fallback_applied,
                    live_blocking=state_plan.live_blocking,
                )
            )
            state["source"] = "A03.ConfigManager"
        except Exception as exc:
            state["source"] = f"unavailable: {exc}"

        return state

    def _load_dji_proxy_multiplier(self) -> float:
        """Read configurable DJI proxy scale (DIA -> DJI) from A03 config."""
        default_multiplier = 101.2
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()
            configured = cfg.get("dashboard.toolbar.dji_from_dia_multiplier", default_multiplier)
            return normalize_dji_proxy_multiplier(configured, default_multiplier)
        except Exception:
            return default_multiplier

    def _append_startup_readiness_banner(self, startup_hms: str) -> None:
        """Append readiness banner lines to the startup ring-buffer before UI renders."""
        plan = build_startup_readiness_banner_plan(
            state=self._startup_readiness_state,
            startup_hms=startup_hms,
            preconnect_idle=_is_preconnect_idle_window(),
        )
        self.system_logs.extend(plan.system_log_messages)

    def _emit_startup_readiness_logs(self) -> None:
        """Emit readiness state to visible logs and button styling after widgets exist."""
        plan = build_startup_readiness_log_plan(
            state=self._startup_readiness_state,
            preconnect_idle=_is_preconnect_idle_window(),
            warning_color=COLORS.get("warning", "#e6a817"),
        )
        for message in plan.log_messages:
            self.add_system_log(message)
        if self.start_btn is None or plan.start_button_plan is None:
            return
        self.start_btn.setText(plan.start_button_plan.text)
        self.start_btn.setStyleSheet(plan.start_button_plan.style_sheet)
        self.start_btn.setToolTip(plan.start_button_plan.tool_tip)

    # ------------------------------------------------------------------
    # Snapshot persistence — save symbol values on exit, restore on open
    # ------------------------------------------------------------------
    _SNAPSHOT_FILE: Path = (
        Path.home() / "Projects/Spyder/market_data/dashboard_snapshot.json"
    )
    _METRICS_SNAPSHOT_FILE: Path = (
        Path.home() / "Projects/Spyder/market_data/overview_metrics_snapshot.json"
    )
    # Snapshot age thresholds (seconds)
    _SNAPSHOT_STALE_HOURS = 8  # > 8 h → FROZEN badge (red)
    _SNAPSHOT_EOD_HOURS = 0    # anything younger → EOD badge (yellow)

    @staticmethod
    def _parse_money_text(text: str) -> float:
        """Parse dashboard money labels like '$100,024.40' or '$+0.00'."""
        return parse_money_text(text)

    def _set_account_money_label(self, label, value: float) -> None:
        """Render an unsigned dollar value into an account-panel label."""
        if label is not None:
            label.setText(format_account_money_text(value))

    def _set_account_pnl_label(self, label, value: float) -> None:
        """Render a signed P&L value into an account-panel label."""
        if label is None:
            return

        presentation = build_account_pnl_presentation(value, COLORS)
        label.setText(presentation.text)
        label.setStyleSheet(presentation.style)

    def _set_spyderbox_account_panel_values(
        self,
        *,
        settled: float | None = None,
        buying: float | None = None,
        realized: float | None = None,
        unrealized: float | None = None,
    ) -> None:
        """Update the dedicated SpyderBox account panel without touching live labels."""
        if self.spyderbox_acct_number_lbl:
            self.spyderbox_acct_number_lbl.setText("SpyderBox")

        if settled is not None:
            self._set_account_money_label(self.spyderbox_settled_value, settled)
        if buying is not None:
            self._set_account_money_label(self.spyderbox_buying_value, buying)
        if realized is not None:
            self._set_account_pnl_label(self.spyderbox_realized_value, realized)
        if unrealized is not None:
            self._set_account_pnl_label(self.spyderbox_unrealized_value, unrealized)

    def _capture_account_snapshot_from_labels(self) -> dict:
        """Capture current account-panel numeric values from QLabel text."""
        return capture_account_snapshot_from_texts(
            settled_text=self.settled_value.text() if self.settled_value else "0",
            buying_text=self.buying_value.text() if self.buying_value else "0",
            realized_text=self.realized_value.text() if self.realized_value else "0",
            unrealized_text=self.unrealized_value.text() if self.unrealized_value else "0",
        )

    def _sync_spyderbox_account_labels(self) -> None:
        """Keep the SpyderBox header stable without mirroring live-account values."""
        if self.spyderbox_acct_number_lbl:
            self.spyderbox_acct_number_lbl.setText("SpyderBox")

    def _remember_current_account_snapshot(self, mode: TradingMode | None = None) -> None:
        """Persist current account labels into in-memory per-mode cache."""
        mode_key = mode or self.trading_mode
        self._account_snapshot_by_mode[mode_key] = self._capture_account_snapshot_from_labels()
        self._sync_spyderbox_account_labels()

    def _apply_account_snapshot(self, snapshot: dict) -> None:
        """Apply account snapshot values back into account panel labels."""
        presentation = build_account_snapshot_presentation(snapshot, COLORS)

        if self.settled_value:
            self.settled_value.setText(presentation.settled_text)
        if self.buying_value:
            self.buying_value.setText(presentation.buying_text)
        if self.realized_value:
            self.realized_value.setText(presentation.realized.text)
            self.realized_value.setStyleSheet(presentation.realized.style)
        if self.unrealized_value:
            self.unrealized_value.setText(presentation.unrealized.text)
            self.unrealized_value.setStyleSheet(presentation.unrealized.style)

        self._sync_spyderbox_account_labels()

    def _save_snapshot(self) -> None:
        """Persist current market_data values to disk for next launch."""
        try:
            self._SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Ensure latest account labels are captured for the active mode.
            self._remember_current_account_snapshot()

            payload = build_dashboard_snapshot_payload(
                saved_at=time.time(),
                trading_mode=self.trading_mode.value,
                mode_keys=TradingMode,
                account_snapshot_by_mode=self._account_snapshot_by_mode,
                pnl_stats_by_mode=self._pnl_stats_by_mode,
                market_data=self.market_data,
                reset_mode_names=(TradingMode.PAPER.value,),
            )
            self._SNAPSHOT_FILE.write_text(json.dumps(payload))
            logger.info("Dashboard snapshot saved (%d symbols)", len(payload["data"]))
        except Exception as _snap_err:  # noqa: BLE001
            logger.warning("Could not save dashboard snapshot: %s", _snap_err)

        # Also snapshot the SPY 5-min chart bars for next-session 2-day view
        try:
            import shutil as _shutil
            chart_src = self.data_file.parent / "spy_5min_chart.json"
            chart_dst = self.data_file.parent / "spy_5min_prev_day.json"
            if chart_src.exists():
                _shutil.copy2(chart_src, chart_dst)
                logger.info("SPY 5-min chart snapshot saved for next session")
        except Exception as _chart_snap_err:  # noqa: BLE001
            logger.warning("Could not save SPY chart snapshot: %s", _chart_snap_err)

    @staticmethod
    def _merge_metrics_payload(
        existing_metrics: dict | None,
        incoming_metrics: dict | None,
    ) -> dict[str, dict]:
        """Merge partial Market Overview metric payloads without clearing good cached values."""
        return merge_metrics_payload(existing_metrics, incoming_metrics)

    def _persist_custom_metrics_snapshot(self) -> None:
        """Persist the latest Market Overview metric payload for cold-start restore."""
        payload = getattr(self, "_last_custom_metrics_payload", {})
        if not isinstance(payload, dict) or not payload:
            return

        try:
            self._METRICS_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._METRICS_SNAPSHOT_FILE.write_text(
                json.dumps(
                    {
                        "_saved_at": time.time(),
                        "metrics": payload,
                    },
                    default=str,
                ),
                encoding="utf-8",
            )
        except Exception as metrics_err:  # noqa: BLE001
            logger.debug("Could not save Market Overview metrics snapshot: %s", metrics_err)

    def _build_cached_metrics_fallback_payload(self) -> dict[str, dict]:
        """Build a best-effort metrics payload from persisted snapshots and local caches."""
        persisted_metrics = None
        pca_iv_snapshot = None
        dix_payload = None
        swan_payload = None
        nymo_payload = None
        iv_history_payload = None

        if self._METRICS_SNAPSHOT_FILE.exists():
            try:
                snapshot_payload = json.loads(
                    self._METRICS_SNAPSHOT_FILE.read_text(encoding="utf-8")
                )
                if isinstance(snapshot_payload, dict):
                    persisted_metrics = snapshot_payload.get("metrics")
            except (OSError, json.JSONDecodeError) as metrics_err:
                logger.debug("Could not read persisted metrics snapshot: %s", metrics_err)

        try:
            from SpyderS_Signals.SpyderS14_PCASignals import get_pca_signal_engine

            pca_engine = get_pca_signal_engine()
            pca_iv_snapshot = pca_engine.get_iv_snapshot()
        except Exception as pca_err:  # noqa: BLE001
            logger.debug("Could not build PCA-IV fallback snapshot: %s", pca_err)

        dix_files = sorted(Path("data").glob("dix_history_*.json"))
        if dix_files:
            try:
                loaded_dix_payload = json.loads(dix_files[-1].read_text(encoding="utf-8"))
                if isinstance(loaded_dix_payload, dict):
                    dix_payload = loaded_dix_payload
            except (OSError, json.JSONDecodeError) as dix_err:
                logger.debug("Could not read DIX fallback snapshot: %s", dix_err)

        swan_files = sorted(Path("black_swan_reports").glob("daily_report_*.json"))
        if swan_files:
            try:
                loaded_swan_payload = json.loads(swan_files[-1].read_text(encoding="utf-8"))
                if isinstance(loaded_swan_payload, dict):
                    swan_payload = loaded_swan_payload
            except (OSError, json.JSONDecodeError) as swan_err:
                logger.debug("Could not read SWAN fallback snapshot: %s", swan_err)

        nymo_cache_file = Path("data/cache/nymo_ema_state.json")
        if nymo_cache_file.exists():
            try:
                loaded_nymo_payload = json.loads(nymo_cache_file.read_text(encoding="utf-8"))
                if isinstance(loaded_nymo_payload, dict):
                    nymo_payload = loaded_nymo_payload
            except (OSError, json.JSONDecodeError) as nymo_err:
                logger.debug("Could not read NYMO fallback snapshot: %s", nymo_err)

        iv_history_file = Path("data/cache/spy_iv_history.json")
        if iv_history_file.exists():
            try:
                loaded_iv_history = json.loads(iv_history_file.read_text(encoding="utf-8"))
                if isinstance(loaded_iv_history, list):
                    iv_history_payload = loaded_iv_history
            except (OSError, json.JSONDecodeError, ValueError) as iv_err:
                logger.debug("Could not read IV history fallback snapshot: %s", iv_err)

        return build_cached_metrics_fallback_payload_from_sources(
            persisted_metrics=persisted_metrics,
            pca_iv_snapshot=pca_iv_snapshot,
            dix_payload=dix_payload,
            swan_payload=swan_payload,
            nymo_payload=nymo_payload,
            iv_history_payload=iv_history_payload,
        )

    def _restore_cached_custom_metrics_snapshot(self) -> None:
        """Best-effort Market Overview metric restore for quiet startup."""
        metrics = self._build_cached_metrics_fallback_payload()
        if not metrics:
            return

        prior_live_flag = bool(getattr(self, "_custom_metrics_live_announced", False))
        try:
            self._custom_metrics_live_announced = True
            self._on_custom_metrics_updated(metrics)
        finally:
            self._custom_metrics_live_announced = prior_live_flag

        self.add_system_log(
            f"📦 Restored {len(metrics)} Market Overview metrics from cached snapshot"
        )

    def _load_cached_market_display_snapshot(self) -> tuple[dict | None, str | None]:
        """Best-effort quote cache restore used before runtime startup is enabled."""
        cache_dir = self.data_file.parent
        if is_market_hours():
            candidate_files = (
                (self.data_file, "cached live quotes"),
                (cache_dir / "eod_snapshot.json", "EOD snapshot"),
            )
        else:
            candidate_files = (
                (cache_dir / "eod_snapshot.json", "EOD snapshot"),
                (self.data_file, "cached live quotes"),
            )

        loaded_snapshots: list[tuple[str, object]] = []
        for snapshot_file, label in candidate_files:
            if not snapshot_file.exists():
                continue
            try:
                raw = snapshot_file.read_text(encoding="utf-8")
                if not raw.strip():
                    continue
                payload = json.loads(raw)
            except (OSError, json.JSONDecodeError) as snapshot_err:
                logger.debug(
                    "Could not read startup market snapshot %s: %s",
                    snapshot_file,
                    snapshot_err,
                )
                continue
            loaded_snapshots.append((label, payload))

        return build_cached_market_display_snapshot_result(loaded_snapshots)

    def _hydrate_market_display_from_snapshot(self, data: dict) -> int:
        """Push cached quote data into visible widgets without starting runtime."""
        count = 0
        for sym, entry in data.items():
            if not isinstance(entry, dict):
                continue
            if sym not in self.market_data:
                self.market_data[sym] = {}
            self.market_data[sym].update(entry)
            quote_time = _market_data_datetime_from_epoch_ms(entry.get("timestamp_ms"))
            if quote_time is not None:
                self.market_data[sym]["timestamp"] = quote_time
            if sym in self.symbol_widgets:
                self.symbol_widgets[sym].update_data(entry)
                count += 1

        if self.signal_panel is not None:
            _sp = {}
            for _sym in ("VIX", "SKEW", "CPC"):
                _e = data.get(_sym)
                if isinstance(_e, dict) and _e.get("last") is not None:
                    _sp[_sym] = _e["last"]
            if _sp:
                self.signal_panel.update_live_data(_sp)

        try:
            self.update_toolbar_with_real_data(data)
        except Exception as toolbar_err:  # noqa: BLE001
            logger.debug("Could not restore toolbar from cached snapshot: %s", toolbar_err)

        freshest_quote_time = _freshest_market_data_timestamp(data)
        if freshest_quote_time is not None:
            self.connection_info.last_successful_data = freshest_quote_time
            self.connection_info.data_was_live = False

        return count

    def _restore_snapshot(self) -> None:
        """Load the last snapshot and pre-populate symbol widgets (best-effort)."""
        if getattr(self, "_shutdown_in_progress", False):
            return
        try:
            payload: dict = {}
            saved_at = 0.0
            age_hours = float("inf")
            data: dict = {}

            if self._SNAPSHOT_FILE.exists():
                raw = self._SNAPSHOT_FILE.read_text()
                payload = json.loads(raw)
                saved_at = payload.get("_saved_at", 0.0)
                age_hours = (time.time() - saved_at) / 3600
                data = payload.get("data", {})

            # Restore per-mode account snapshots.
            account_by_mode = payload.get("account_by_mode", {}) or {}
            if isinstance(account_by_mode, dict):
                for mode_name, values in account_by_mode.items():
                    try:
                        mode = TradingMode(mode_name)
                    except Exception:
                        continue
                    if mode == TradingMode.PAPER:
                        continue
                    if isinstance(values, dict):
                        self._account_snapshot_by_mode[mode] = dict(values)

            # Restore per-mode P&L stats snapshots.
            # PAPER P&L stats are simulation/UI state and must not be restored
            # from disk — SpyderBox always starts fresh each session.
            pnl_by_mode = payload.get("pnl_stats_by_mode", {}) or {}
            if isinstance(pnl_by_mode, dict):
                for mode_name, values in pnl_by_mode.items():
                    try:
                        mode = TradingMode(mode_name)
                    except Exception:
                        continue
                    if mode == TradingMode.PAPER:
                        continue
                    if isinstance(values, dict):
                        self._pnl_stats_by_mode[mode] = dict(values)

            if not data:
                cached_data, cached_label = self._load_cached_market_display_snapshot()
                if isinstance(cached_data, dict) and cached_label:
                    count = self._hydrate_market_display_from_snapshot(cached_data)
                    self.update_data_status("EOD" if not is_market_hours() else self.determine_data_status())
                    self.connection_info.market_data_status = (
                        "EOD" if not is_market_hours() else self.determine_data_status()
                    )
                    self.add_system_log(
                        f"📦 Restored {count} symbols from {cached_label} cache"
                    )
                    if self.figure is not None and self.canvas is not None:
                        self.update_chart()
                self._restore_cached_custom_metrics_snapshot()
                saved_account = get_restorable_account_snapshot(
                    self._account_snapshot_by_mode,
                    self.trading_mode,
                    paper_mode=TradingMode.PAPER,
                )
                if saved_account:
                    self._apply_account_snapshot(saved_account)
                return

            count = self._hydrate_market_display_from_snapshot(data)

            # Set appropriate data-status badge
            if age_hours >= self._SNAPSHOT_STALE_HOURS:
                self.update_data_status("FROZEN")
                badge = "FROZEN (stale snapshot)"
            else:
                self.update_data_status("EOD")
                badge = "EOD snapshot"

            import datetime as _dt
            saved_str = _dt.datetime.fromtimestamp(saved_at).strftime("%Y-%m-%d %H:%M:%S")
            self.add_system_log(
                f"📦 Restored {count} symbols from {badge} saved at {saved_str}"
            )
            if self.figure is not None and self.canvas is not None:
                self.update_chart()
            self._restore_cached_custom_metrics_snapshot()

            # Apply saved account values for the active mode after symbols restore.
            saved_account = get_restorable_account_snapshot(
                self._account_snapshot_by_mode,
                self.trading_mode,
                paper_mode=TradingMode.PAPER,
            )
            if saved_account:
                self._apply_account_snapshot(saved_account)
        except Exception as _restore_err:  # noqa: BLE001
            logger.warning("Could not restore dashboard snapshot: %s", _restore_err)

    def closeEvent(self, event):
        """Enhanced close event handler with real data cleanup and heartbeat monitoring"""
        try:
            self._shutdown_in_progress = True
            self._run_close_event_shutdown_sequence(event)

        except Exception as e:
            logger.info("Error during enhanced dashboard close: %s", e)
            event.accept()

    def _save_snapshot_on_shutdown(self) -> None:
        """Persist a single snapshot during shutdown, regardless of quit path."""
        if self._shutdown_snapshot_saved:
            return
        try:
            self._save_snapshot()
            logger.info("Dashboard snapshot saved for PAPER+LIVE on exit")
            try:
                shutdown_message_plan = build_dashboard_shutdown_message_plan()
                self.add_system_log(str(shutdown_message_plan.snapshot_system_message))
            except Exception:  # noqa: BLE001
                # UI may already be tearing down; logger line above remains authoritative.
                pass
        finally:
            self._shutdown_snapshot_saved = True

    def _on_app_about_to_quit(self) -> None:
        """Qt application-level shutdown hook for save-on-exit behavior."""
        self._save_snapshot_on_shutdown()


def _spyder_dashboard_build_pca_iv_details_html(cls, entry: dict) -> str:
    """Build the PCA-IV details dialog HTML for live or seeded states."""
    return build_pca_iv_details_html(entry)


SpyderTradingDashboard._build_pca_iv_details_html = classmethod(
    _spyder_dashboard_build_pca_iv_details_html
)



# ==============================================================================
# STANDALONE FUNCTIONS FOR EXTERNAL USE
# ==============================================================================
def create_spyder_trading_dashboard():
    """Factory function to create SpyderTradingDashboard instance"""
    return SpyderTradingDashboard()


def get_dashboard_with_real_data_integration():
    """Create dashboard with real data integration pre-configured"""
    return SpyderTradingDashboard()



# ==============================================================================
# MAIN EXECUTION - FOR STANDALONE TESTING
# ==============================================================================
def main():
    """Main function for standalone testing"""
    logger.info("=" * 70)
    logger.info("🔥 SPYDER G05 - ENHANCED TRADING DASHBOARD")
    logger.info("=" * 70)
    logger.info("🔗 Tradier API integration")
    logger.info("📡 Tradier market data feeds")
    logger.info("💔💚💙 30-second heartbeat monitoring")
    logger.info("📊 Clean 4-status data display")
    logger.info("=" * 70)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # CRITICAL: Set desktop file name for Wayland/GNOME integration
    # This MUST match the .desktop file name (without .desktop extension)
    # so the window appears under the launcher icon instead of a separate gear icon
    app.setDesktopFileName("spyder-trading-system")

    # Set application identity
    app.setApplicationName("spyder-trading-system")
    app.setOrganizationName("Spyder Trading System")

    # Implement qasync event loop integration for proper asyncio/Qt compatibility
    try:
        import asyncio

        import qasync

        # Create QEventLoop for asyncio integration
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        logger.info("✅ qasync event loop integration enabled - preventing asyncio errors")
        logger.info("🔗 Qt and asyncio event loops properly synchronized")

        # Create a simple event to signal when the app should close
        app_close_event = asyncio.Event()

        # Connect app aboutToQuit signal to our event
        app.aboutToQuit.connect(app_close_event.set)

        try:
            # Create fixed dashboard
            logger.info("🔧 Initializing fixed dashboard with heartbeat monitoring...")
            dashboard = SpyderTradingDashboard()

            # Show dashboard
            dashboard.show()

            # Check real data status
            data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
            if data_file.exists():
                try:
                    with open(data_file) as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    logger.info("✅ Real data detected - SPY: $%s", spy_price)
                except Exception:
                    logger.info("⚠️ Real data file exists but couldn't read it")
            else:
                logger.info("📊 No real data file detected yet - waiting for Tradier snapshots")

            logger.info("\n✅ STATUS BAR FEATURES:")
            logger.info("   • TRADIER EXEC: green=connected, red=disconnected (label color only)")
            logger.info("   • 30-second heartbeat background checks drive connection state")
            logger.info(
                "   • Clean data status: NO DATA, EOD, PRE-OPEN, AFTER-HOURS, LIVE",
            )
            logger.info("   • Market data source: TRADIER DATA")
            logger.info("   • No synthetic market-data fallback is used")
            logger.info("   • Fixed-width status containers (no UI jumping)")

            logger.info("\n🔥 Enhanced Trading Dashboard is ready!")
            logger.info("   Heartbeat checks API connection every 30 seconds\n")
            logger.info("🔄 Running with qasync event loop integration...")

            # Run the event loop until the app closes
            with loop:
                loop.run_until_complete(app_close_event.wait())

            return 0

        except Exception as e:
            logger.info("\n❌ Startup error: %s", e)
            import traceback

            traceback.print_exc()

            # Show error dialog if possible
            try:
                QMessageBox.critical(
                    None,
                    "Fixed Trading Dashboard Error",
                    f"Failed to start Fixed Trading Dashboard:\n\n{e}\n\n"
                    "Please check the console for detailed error information.",
                )
            except Exception as _dlg_err:
                logger.debug("Could not show startup error dialog: %s", _dlg_err)

            return 1

    except ImportError:
        # Fallback to standard event loop if qasync is not available
        logger.info("⚠️ qasync not available - using standard event loop (may have asyncio issues)")
        logger.info("   Install with: pip install qasync")

        try:
            # Create fixed dashboard
            logger.info("🔧 Initializing fixed dashboard with heartbeat monitoring...")
            dashboard = SpyderTradingDashboard()

            # Show dashboard
            dashboard.show()

            # Check real data status
            data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
            if data_file.exists():
                try:
                    with open(data_file) as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    logger.info("✅ Real data detected - SPY: $%s", spy_price)
                except Exception:
                    logger.info("⚠️ Real data file exists but couldn't read it")
            else:
                logger.info("📊 No real data file detected yet - waiting for Tradier snapshots")

            logger.info("\n✅ STATUS BAR FEATURES:")
            logger.info("   • TRADIER EXEC: green=connected, red=disconnected (label color only)")
            logger.info("   • 30-second heartbeat background checks drive connection state")
            logger.info(
                "   • Clean data status: NO DATA, EOD, PRE-OPEN, AFTER-HOURS, LIVE",
            )
            logger.info("   • Market data source: TRADIER DATA")
            logger.info("   • No synthetic market-data fallback is used")
            logger.info("   • Fixed-width status containers (no UI jumping)")

            logger.info("\n🔥 Enhanced Trading Dashboard is ready!")
            logger.info("   Heartbeat checks API connection every 30 seconds\n")

            # Run application with standard event loop
            return app.exec()

        except Exception as e:
            logger.info("\n❌ Startup error: %s", e)
            import traceback

            traceback.print_exc()

            # Show error dialog if possible
            try:
                QMessageBox.critical(
                    None,
                    "Fixed Trading Dashboard Error",
                    f"Failed to start Fixed Trading Dashboard:\n\n{e}\n\n"
                    "Please check the console for detailed error information.",
                )
            except Exception as _dlg_err:
                logger.debug("Could not show startup error dialog: %s", _dlg_err)

            return 1


if __name__ == "__main__":
    sys.exit(main())
