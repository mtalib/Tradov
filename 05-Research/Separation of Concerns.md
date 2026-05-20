
The "Golden Rule" you're following is known in software engineering as Separation of Concerns (SoC). In the context of a PySide6 app, it essentially means keeping your "Brain" (Logic) separate from your "Face" (UI).  

Since you are running on Ubuntu/Wayland, this separation is even more critical because Wayland’s strict compositor rules and Python’s Global Interpreter Lock (GIL) can lead to a "frozen" interface if your UI thread gets bogged down by heavy calculations.

1. The Core Concept: Layered Architecture
In a well-structured PySide6 app, you typically divide your code into three distinct layers:

The View (The Dashboard): This is your PySide6 code. Its only jobs are to draw widgets, layout the window, and capture user clicks. It shouldn't know how to process data; it should only know who to call.

The Controller/Presenter: This acts as the middleman. When a user clicks a button, the View tells the Controller. The Controller then calls the correct Python module.

The Business Logic (Supporting Modules): These are pure Python modules (.py files) that have zero imports from PySide6. They perform calculations, handle database queries, or talk to the network.

2. Why This is Essential (The "Reasons")
A. Avoiding the "Frozen UI" (The Wayland Factor)
PySide6 runs on a single Main Thread (the GUI thread). If you put a heavy loop—like processing a large CSV or a complex image filter—directly inside a button click function in your dashboard, the app will stop responding to the Wayland compositor.

The Benefit: By keeping logic in separate modules, you can easily move those functions into a QThread or QRunnable. Since the logic is already decoupled, you just run the module's function in the background and use Signals to send the result back to the dashboard.

B. Testing Without the "Clicking"
If your logic is buried inside a PySide6 QMainWindow class, you can only test it by running the whole app and manually clicking buttons.

The Benefit: If your logic is in logic_engine.py, you can write standard Python pytest or unittest scripts to verify your math or data processing automatically, without ever opening a window.

C. Maintenance and Scalability
Imagine you decide to switch from PySide6 to a web interface (like FastAPI) or a mobile framework later.

The Benefit: If your logic is in the dashboard, you have to rewrite everything. If your logic is in supporting modules, you keep 90% of your code and only rewrite the "Face."

D. Readability (The "Thin" UI)
A "Fat" UI file with 2,000 lines of code is a nightmare to debug. A "Thin" UI file that simply connects signals to external functions is easy to read.


Inside your PySide6 Class
def handle_click(self):
    # 50 lines of code calculating taxes, saving to DB, etc.
    result = self.amount * 0.15 
    self.label.setText(f"Tax: {result}")
    
    
    
 # In supporting_module.py
def calculate_tax(amount):
    return amount * 0.15

# Inside your PySide6 Class
from supporting_module import calculate_tax

def handle_click(self):
    # Dashboard only handles the UI update
    val = float(self.input.text())
    result = calculate_tax(val) 
    self.label.setText(f"Tax: {result}")   


3. Spyder G05 Application of SoC
In this repository, the main SoC target has been SpyderG05_TradingDashboard.py. The working rule has been consistent: G05 keeps PySide6 side effects, while small G-series helpers own pure decision, presentation, selection, or ordered-step planning.

Recent startup-readiness extractions followed that rule directly:

G91: startup-readiness visible log and safe-mode start-button presentation for _emit_startup_readiness_logs().

G92: startup-readiness startup-banner copy for _append_startup_readiness_banner().

G93: startup-readiness state assembly for _collect_startup_readiness_state().

G94: post-paint startup-readiness refresh ordering for _refresh_startup_readiness_state().

G95: DJI proxy multiplier normalization for _load_dji_proxy_multiplier().

G96: risk-alert repeated-digest suppression and dispatch payload for _handle_risk_alert_event().

G97: pending-orders gate prompt and outcome copy for _handle_pending_orders_gate().

G98: execution-telemetry event normalization and sample extraction for _handle_trade_event().

G100: POSITION_UPDATED event symbol extraction for _handle_position_updated_event().

G101: recent decision-flow fetch request and fallback shaping for _get_recent_decision_flow_for_panel().

G102: metrics-orchestrator post-hydration start plan for _start_metrics_orchestrator().

G103: LIVE-to-PAPER warning and confirmation dialog copy for _on_mode_btn_clicked().

G104: metrics-orchestrator snapshot probe and formatter capture for _hydrate_metrics_orchestrator_snapshot().

G105: PAPER-to-LIVE critical dialog and typed-confirmation copy for _on_mode_btn_clicked().

G106: per-widget S07 metric payload and previous-value planning for _on_custom_metrics_updated().

G107: signal-panel regime inputs and live S07 sync payload planning for _on_custom_metrics_updated().

G108: Market Internals breadth-dialog payload planning for _on_custom_metrics_updated().

G109: regime-pill state normalization and sticky/VIX fallback planning for update_regime_pills().

G110: regime-pill stance, stress, and gate planning for update_regime_pills().

G111: regime-pill dispatch-state override and announcement planning for update_regime_pills().

G112: close-strategy confirmation dialog copy and styling for confirm_close_strategy().

G113: close-strategy success-path order-id extraction and success UX copy for close_strategy().

G114: close-strategy failure-path UX copy for close_strategy().

G115: dashboard event subscription spec planning with RISK_ALERT fallback for _subscribe_to_events().

G116: event-clock risk-event payload normalization and state kwargs planning for _handle_risk_event().

G117: manual event-clock override label and emitted event payload planning for _toggle_event_clock_override().

G118: G09-to-E01 paper risk-limit overlay planning for _build_paper_risk_manager().

G119: ring-log append/truncate planning and buffered refresh routing for _append_to_ring_log() and _schedule_log_widget_refresh().

G120: opening-warmup and after-hours system-log suppression prefix matching for _should_suppress_opening_warmup_system_log() and _should_suppress_after_hours_system_log().

G121: automation-log route selection and formatted message planning for add_automation_log().

G122: system-log verbosity mode, logger level, button checked state, and announcement planning for _set_system_log_verbosity().

G123: veto-toggle button checked/text/style/tooltip presentation for _apply_veto_toggle_button_state().

G124: veto-toggle persistence outcome planning for _toggle_veto_controls().

G125: veto-controls enabled-state resolution from parsed profile data and env fallback for _load_veto_controls_state().

G126: veto-controls persistence merge, serialized profile text, and env update planning for _persist_veto_controls_state().

G127: startup-readiness default-state and success-envelope shaping for _collect_startup_readiness_state().

G128: dashboard snapshot payload shaping for _save_snapshot().

G129: Market Overview metrics payload merge logic for _merge_metrics_payload().

G130: cached Market Overview fallback normalization for _build_cached_metrics_fallback_payload().

G131: startup market snapshot merge precedence and source-label synthesis for _load_cached_market_display_snapshot().

G132: cached chart-candle selection and 900-bar clamping for _load_chart_candles_from_cache().

G133: cached chart bar timestamp parsing, target-date selection, and OHLCV series shaping for update_chart().

G102 follow-up reuse: first-live-metrics announcement in _on_custom_metrics_updated() now uses the same helper-backed active-start copy as _start_metrics_orchestrator().

The same pattern was already applied to the dashboard shutdown tail, where G82 through G90 reduced closeEvent() to thin orchestration plus local error handling.

4. Practical Boundary Rule Used in Spyder
Keep these responsibilities in G05:

PySide6 widget mutation, add_system_log() calls, event.accept(), timer start/stop, thread stop/quit/terminate, QMetaObject.invokeMethod(), logger calls, config-manager access, and exception-tolerance behavior.

Move these responsibilities into helpers:

Fixed operator-facing copy, filtered warning lists, normalized mode/blocking decisions, ordered method-step plans, and small pure state/presentation payloads.

5. Validation Pattern Used for Each Seam
Each extraction is kept small and is validated immediately in two stages:

Focused validation first: one local wrapper test in G05 plus one helper-only test file.

Bounded regression second: SpyderT153_G05_GoNoGoCheck.py plus SpyderT2*_G*.py, excluding SpyderT212_G05_PaperPositionFallback.py.

Recent dashboard helper checkpoints:

G91: focused 100 passed, 16 warnings; bounded 312 passed, 74 warnings.

G92: focused 54 passed, 16 warnings; bounded 316 passed, 74 warnings.

G93: focused 55 passed, 16 warnings; bounded 320 passed, 74 warnings.

G94: focused 50 passed, 16 warnings; bounded 323 passed, 74 warnings.

G95: focused 55 passed, 16 warnings; bounded 326 passed, 74 warnings.

G96: focused 6 passed, 16 warnings; bounded 327 passed, 74 warnings.

G97: focused 4 passed, 16 warnings; bounded 327 passed, 74 warnings.

G98: focused 5 passed, 16 warnings; bounded 327 passed, 74 warnings.

G100: focused 5 passed, 16 warnings; bounded 327 passed, 74 warnings.

G101: focused 7 passed, 16 warnings; bounded 327 passed, 74 warnings.

G102: focused 5 passed, 16 warnings; bounded 327 passed, 74 warnings.

G103: focused 4 passed, 16 warnings; bounded 327 passed, 74 warnings.

G104: focused 6 passed, 16 warnings; bounded 327 passed, 74 warnings.

G105: focused 5 passed, 16 warnings; bounded 327 passed, 74 warnings.

G106: focused 7 passed, 16 warnings; bounded 328 passed, 74 warnings.

G107: focused 6 passed, 16 warnings; bounded 328 passed, 74 warnings.

G108: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G109: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G111: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G112: focused 3 passed, 16 warnings; bounded 328 passed, 74 warnings.

G113: focused 2 passed, 16 warnings; bounded 328 passed, 74 warnings.

G114: focused 3 passed, 16 warnings; bounded 328 passed, 74 warnings.

G115: focused 3 passed, 16 warnings; bounded 328 passed, 74 warnings.

G116: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G117: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G118: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G119: focused 7 passed, 16 warnings; bounded 328 passed, 74 warnings.

G120: focused 10 passed, 16 warnings; bounded 328 passed, 74 warnings.

G121: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G122: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G123: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G124: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G125: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G126: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G127: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G128: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G129: focused 4 passed, 16 warnings; bounded 328 passed, 74 warnings.

G130: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G131: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G132: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G133: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G110: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G111: focused 5 passed, 16 warnings; bounded 328 passed, 74 warnings.

G102 follow-up reuse: focused 2 passed, 16 warnings; bounded 328 passed, 74 warnings.

This is the practical meaning of Separation of Concerns in this codebase: make the dashboard thinner one local seam at a time, keep the UI truthful and side-effectful, and move everything else that can be made pure into small testable helpers.
