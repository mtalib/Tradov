# Kronos Foundation Model — Integration Research & Task Brief

**Date:** April 20, 2026  
**Status:** Research / Future Consideration  
**Priority:** Medium  
**Effort Estimate:** 3–5 weeks (research → fine-tune → paper validation)  
**Source:** [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)  
**Paper:** [arXiv:2508.02739](https://arxiv.org/abs/2508.02739) — accepted AAAI 2026

---

## What Is Kronos?

Kronos is the first open-source foundation model purpose-built for financial candlestick (K-line / OHLCV) data. Developed by researchers at Tsinghua University and accepted at AAAI 2026, it uses a two-stage architecture:

1. **Hierarchical Tokenizer** — quantises continuous OHLCV data into discrete tokens optimised for financial price sequences
2. **Autoregressive Transformer** — pre-trained on data from 45+ global exchanges; produces probabilistic multi-step OHLCV forecasts

It is not a general-purpose time-series model — it is specifically designed for the statistical properties of financial market data (high noise, fat tails, non-stationarity).

**GitHub:** https://github.com/shiyu-coder/Kronos  
**Hugging Face:** https://huggingface.co/NeoQuasar  
**Live demo:** BTC/USDT 24-hour forecast — https://shiyu-coder.github.io/Kronos-demo/  
**License:** MIT ✅ (no AGPL conflict with Tradov policy)  
**Stars (at time of research):** 19,600+ | Forks: 3,600+

---

## Model Variants

| Model | Tokenizer | Context | Parameters | Available |
|---|---|---|---|---|
| Kronos-mini | Kronos-Tokenizer-2k | 2,048 | 4.1M | ✅ HuggingFace |
| Kronos-small | Kronos-Tokenizer-base | 512 | 24.7M | ✅ HuggingFace |
| Kronos-base | Kronos-Tokenizer-base | 512 | 102.3M | ✅ HuggingFace |
| Kronos-large | Kronos-Tokenizer-base | 512 | 499.2M | ❌ Not released |

**Recommended starting point:** `Kronos-base` (102M) for signal quality; `Kronos-small` (24.7M) if GPU memory is constrained.

---

## Why This Matters for Tradov

### The Gap Kronos Fills

Tradov's current ML layer (`TradovL_ML`) relies on traditional models:
- `TradovL12_RandomForestEnsemble.py` — ensemble classification
- `TradovL13_LSTMPricer.py` — deep learning for IV surface prediction
- `TradovL15_MomentPredictor.py` — short-term momentum scoring

None of these are pre-trained on a broad financial data distribution. Each is trained from scratch on Tradov's available data, which means they require substantial historical data to generalise and are sensitive to overfitting on limited SPY history.

Kronos provides a **foundation model baseline** — a rich prior over price dynamics learned from 45+ exchanges — that can be fine-tuned on SPY-specific data with far less data than training from scratch.

### What Kronos Outputs

Given a lookback window of OHLCV bars, Kronos returns forecasted bars for a specified prediction horizon. From those forecasts, Tradov can derive:

| Derived Signal | Use in Tradov |
|---|---|
| Forecasted close Δ% | Directional bias (bull/bear) for strategy gating |
| Forecasted high − low range | Proxy for expected daily move / synthetic IV |
| Probabilistic fan (multiple samples) | Implied move distribution → credit spread strike selection |
| Regime-change signal | When forecast distribution widens sharply → elevated risk alert |

---

## Proposed Integration Architecture

```
TradovC08_SPYFeed (live OHLCV bars)
        │
        ▼
TradovL20_KronosAdapter (NEW MODULE)
  ├── Loads KronosPredictor from HuggingFace / local checkpoint
  ├── Maintains rolling lookback buffer (400 bars recommended)
  ├── Calls predictor.predict() on each new bar close
  ├── Emits: {direction_bias, implied_move_estimate, confidence}
  └── Scheduled via TradovA04_Scheduler (bar-close trigger)
        │
        ├──▶ TradovF09_EntryFilters     — blocks entries against forecast
        ├──▶ TradovD30_RegimeGatedSelector — weights strategy by confidence
        ├──▶ TradovD25_UnifiedCreditSpreadEngine — informs strike width
        └──▶ TradovI02_EventRouter      — publishes KronosSignal event
```

**New module:** `TradovL_ML/TradovL20_KronosAdapter.py`  
**New test file:** `TradovT_Testing/TradovT120_KronosAdapter_Test.py`

---

## Integration Steps (Ordered Task List)

### Phase 1 — Research & Validation (1 week)

- [ ] Install Kronos dependencies in `.venv`: `pip install transformers torch huggingface_hub`
- [ ] Download `Kronos-base` and `Kronos-Tokenizer-base` from HuggingFace: `NeoQuasar/Kronos-base`
- [ ] Run `examples/prediction_example.py` on a sample SPY OHLCV CSV (verify the model runs locally)
- [ ] Benchmark GPU inference latency on the development machine (target: <500ms per bar)
- [ ] Confirm `Kronos-mini` (2,048 context) is usable for longer intraday lookbacks

### Phase 2 — SPY Fine-Tuning (1–2 weeks)

- [ ] Export 2–3 years of SPY 5-minute OHLCV from Massive API historical data via `TradovC02_HistoricalData`
- [ ] Format into Qlib-compatible dataset or direct CSV pipeline for `finetune_csv/`
- [ ] Fine-tune Kronos-Tokenizer on SPY data: `torchrun finetune/train_tokenizer.py`
- [ ] Fine-tune Kronos-Predictor on SPY data: `torchrun finetune/train_predictor.py`
- [ ] Evaluate on held-out SPY test period (2024 data recommended as out-of-sample)
- [ ] Confirm IC (Information Coefficient) > 0.05 on SPY 1-day and 5-day horizons before proceeding

### Phase 3 — Tradov Adapter Development (1 week)

- [ ] Implement `TradovL20_KronosAdapter.py`:
  - `KronosAdapter` class wrapping `KronosPredictor`
  - Rolling OHLCV buffer management (thread-safe)
  - `get_signal()` → returns `KronosSignal(direction_bias, implied_move, confidence, timestamp)`
  - `TradovLogger` throughout; no `print()` statements
  - Scheduled refresh via `TradovA04_Scheduler` on 1-min / 5-min bar close
- [ ] Implement `TradovT120_KronosAdapter_Test.py` with mock OHLCV data
- [ ] Wire `KronosSignal` events into `TradovI02_EventRouter`

### Phase 4 — Strategy Integration (1 week)

- [ ] Add Kronos direction filter to `TradovF09_EntryFilters` (configurable, off by default)
- [ ] Add implied-move estimate to `TradovD25_UnifiedCreditSpreadEngine` strike width logic
- [ ] Add Kronos confidence score to `TradovD30_RegimeGatedSelector` weighting
- [ ] Feature-flagged via `TradovU11_FeatureFlags` — `ENABLE_KRONOS_SIGNALS = false` default

### Phase 5 — Paper Trading Validation (ongoing)

- [ ] Run with `ENABLE_KRONOS_SIGNALS = true` in paper mode via `TradovR02_PaperEngine`
- [ ] Compare paper P&L and Sharpe with and without Kronos signals over 4-week window
- [ ] Promote to live only if signal attribution shows statistically significant improvement (p < 0.05)

---

## Technical Requirements

### Dependencies to Add

```
# requirements-ai.txt additions
kronos @ git+https://github.com/shiyu-coder/Kronos.git
# OR install directly:
transformers>=4.40.0
huggingface_hub>=0.23.0
# (torch already in requirements-ai.txt)
```

### Hardware

- **GPU preferred** — NVIDIA GPU with ≥6GB VRAM for `Kronos-base`
- **CPU fallback** — `Kronos-mini` (4.1M) runs acceptably on CPU for development/testing
- Auto-device detection is built into `KronosPredictor`

### Data Contract

```python
# Input DataFrame contract (from TradovC08_SPYFeed)
columns_required = ['open', 'high', 'low', 'close']
columns_optional = ['volume']  # 'amount' not available from Tradier/Massive; fill with 0
lookback_bars = 400            # recommended; must not exceed max_context=512 for small/base
```

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Kronos trained on global equity/crypto data — SPY options-specific dynamics may differ | Medium | Mandatory SPY fine-tuning (Phase 2) before any signal use |
| Model inference latency causing bar-close timing issues | Medium | Run asynchronously via `TradovA04_Scheduler`; never block order path |
| Overfitting during fine-tuning on limited SPY data | Medium | Use walk-forward validation in `TradovF12_AdvancedBacktestingEngine` |
| Kronos signals conflict with existing `TradovL` models | Low | Feature-flagged; Kronos signals are additive, not replacement |
| HuggingFace model availability / API outage | Low | Cache model weights locally after first download; no runtime HF dependency |
| Kronos-large (499M) not yet released | Low | Use Kronos-base (102M); revisit when large is available |

---

## What Kronos Does NOT Replace

It is important to scope this correctly. Kronos is an **upstream directional signal** only. It cannot replace:

- `TradovN_OptionsAnalytics` — options pricing, Greeks, IV surface (requires options chain data, not OHLCV)
- `TradovE_Risk` — all risk management, position sizing, circuit breakers
- `TradovB_Broker` — order execution
- `TradovD_Strategies` — strategy logic, entry/exit rules

Kronos slots in as one additional signal source among many, gated by `TradovF09_EntryFilters` and `TradovU11_FeatureFlags`. No existing module is deprecated or removed.

---

## Competitive Context

Similar financial foundation models for comparison if evaluation is needed:

| Model | Focus | Notes |
|---|---|---|
| **Kronos** (shiyu-coder) | OHLCV candlestick forecasting | Best fit for Tradov's SPY bar-level signals |
| TimesFM (Google DeepMind) | General time-series | Not finance-specific; no OHLCV tokenizer |
| Lag-Llama | Probabilistic TS | General univariate; no multi-dimensional OHLCV |
| FinGPT | Financial NLP | Text/sentiment only; not price prediction |
| BloombergGPT | Financial LLM | Text only; extremely large; proprietary |

Kronos is the only open-source model specifically designed for OHLCV multi-dimensional price sequences with a financial-domain tokenizer. It is the correct tool for this use case among current open-source options.

---

## Decision Criteria for Proceeding

Before committing Phase 3–5 engineering effort, validate these gates:

1. **Local inference confirmed** — model runs in `.venv` on development hardware
2. **SPY IC ≥ 0.05** — information coefficient on held-out SPY test data after fine-tuning
3. **Latency < 500ms** — inference time acceptable for bar-close scheduling
4. **Paper mode improvement** — ≥+0.10 Sharpe improvement over 4-week paper window with Kronos enabled

If any gate fails, park the integration and re-evaluate when `Kronos-large` (499M) is released or when additional SPY training data is available.

---

## References

- GitHub: https://github.com/shiyu-coder/Kronos
- Paper: https://arxiv.org/abs/2508.02739
- HuggingFace: https://huggingface.co/NeoQuasar
- Live demo: https://shiyu-coder.github.io/Kronos-demo/
- AAAI 2026 acceptance confirmed November 2025

---

*Research compiled: April 20, 2026 — Tradov Project*
