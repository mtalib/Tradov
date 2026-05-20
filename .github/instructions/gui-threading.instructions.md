---
description: "Use when editing PySide6 GUI, QThread, signal-slot, dashboard, worker, or shutdown logic in SpyderG_GUI. Covers cross-thread signal safety, worker timers, queued shutdown, and keeping the dashboard responsive."
applyTo:
  - "Spyder/SpyderG_GUI/**/*.py"
---
# GUI Threading Guidelines

- Keep blocking work off the GUI thread. Use existing worker, async, or helper boundaries instead of adding network or heavy compute directly in widgets or presenters.
- For cross-thread Qt signals, connect to bound `QObject` methods instead of lambdas so Qt can use queued delivery correctly.
- If a worker lives on a `QThread`, create its `QTimer` instances in that thread and parent them to the worker. Do not stop worker-owned timers directly from the GUI thread.
- During shutdown, disconnect queued fetch or refresh signals before `thread.quit()`, then `wait()` for the thread. Do not leave queued work alive past widget shutdown.
- Prefer existing GUI lifecycle helpers before inventing new shutdown or invoke patterns: [SpyderG18_MarketDataWorker](../../Spyder/SpyderG_GUI/SpyderG18_MarketDataWorker.py), [SpyderG81_MarketWorkerSlotInvokeHelper](../../Spyder/SpyderG_GUI/SpyderG81_MarketWorkerSlotInvokeHelper.py), [SpyderG82_QThreadShutdownHelper](../../Spyder/SpyderG_GUI/SpyderG82_QThreadShutdownHelper.py), [SpyderG88_MarketWorkerShutdownHelper](../../Spyder/SpyderG_GUI/SpyderG88_MarketWorkerShutdownHelper.py), and [SpyderG90_CloseEventShutdownSequenceHelper](../../Spyder/SpyderG_GUI/SpyderG90_CloseEventShutdownSequenceHelper.py).
- When editing G05 dashboard flows, check for startup, loading, and shutdown interactions before widening scope; this area has several thread-affinity and queued-event gotchas.
- References: [Threading Guide](../../02-Standards-Instructions/THREADING_GUIDE.md) and the repository note `pyside6-cross-thread-gotchas.md`.