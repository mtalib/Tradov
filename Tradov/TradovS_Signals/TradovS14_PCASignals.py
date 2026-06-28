#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovS_Signals
Module: TradovS14_PCASignals.py
Purpose: PCA proxy custom metrics for TRAD regime monitoring

Author: Tradov Dev
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Description:
    Provides two custom-metric style PCA signals:
    - PCA-PROXY: a real sector-proxy eigenfactor signal built from rolling
      daily returns of TRAD sector ETFs.
        - PCA-IV: a live eigenfactor built from persisted TRAD IV-surface features,
            with placeholder fallback until seeded history is sufficient.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore[assignment]
    _YFINANCE_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler

try:
    from Tradov.TradovB_Broker.TradovB40_TradierClient import create_tradier_client_from_env
    _TRADIER_FACTORY_AVAILABLE = True
except ImportError:
    create_tradier_client_from_env = None  # type: ignore[assignment]
    _TRADIER_FACTORY_AVAILABLE = False


SECTOR_PROXY_SYMBOLS: tuple[str, ...] = (
    "XLC",
    "XLY",
    "XLP",
    "XLE",
    "XLF",
    "XLV",
    "XLI",
    "XLB",
    "XLRE",
    "XLK",
    "XLU",
)
LOOKBACK_DAYS = 252
CALENDAR_LOOKBACK_DAYS = 420
MIN_OBSERVATIONS = 120
SHRINKAGE_ALPHA = 0.20
PCA_PROXY_HISTORY_WINDOW = 20
PCA_IV_HISTORY_WINDOW = 20
PCA_IV_LOOKBACK_WINDOW = 252
PCA_IV_MIN_OBSERVATIONS = 30
PCA_IV_HISTORY_TARGET = 120
PCA_IV_BOOTSTRAP_ROWS = 60
PCA_IV_HISTORY_FILE = Path("data/cache/pca_iv_surface_history/spy_iv_surface_features.jsonl")
PCA_IV_SCALAR_HISTORY_FILE = Path("data/cache/spy_iv_history.json")
PCA_IV_FEATURE_COLUMNS: tuple[str, ...] = (
    "feature_level",
    "feature_front_curve",
    "feature_back_curve",
    "feature_curve_butterfly",
    "feature_term_twist",
    "feature_skew",
    "feature_convexity",
)


@dataclass
class PCAMetricSnapshot:
    """Current PCA custom-metric snapshot."""

    signal_value: float
    previous_value: float
    explained_variance: float
    spectral_gap: float
    dispersion_score: float
    universe_size: int
    confidence: float
    timestamp: datetime
    source: str
    placeholder: bool = False
    status: str = "live"
    details: dict[str, Any] | None = None

    @property
    def change(self) -> float:
        return float(self.signal_value - self.previous_value)


class PCASignalEngine:
    """Compute proxy PCA signals and surface-feature PCA metrics."""

    def __init__(
        self,
        iv_surface_history_path: Path | str | None = None,
        iv_scalar_history_path: Path | str | None = None,
    ) -> None:
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self._proxy_cache: PCAMetricSnapshot | None = None
        self._proxy_cache_date: str = ""
        self._iv_surface_history_path = (
            Path(iv_surface_history_path)
            if iv_surface_history_path is not None
            else PCA_IV_HISTORY_FILE
        )
        self._iv_scalar_history_path = (
            Path(iv_scalar_history_path)
            if iv_scalar_history_path is not None
            else PCA_IV_SCALAR_HISTORY_FILE
        )
        self._iv_surface_history_path.parent.mkdir(parents=True, exist_ok=True)
        self._iv_surface_history_count = 0
        self._iv_surface_history_first_ts = ""
        self._iv_surface_history_last_ts = ""
        self._iv_surface_last_write_ts = ""
        self._iv_snapshot_cache: PCAMetricSnapshot | None = None
        self._iv_snapshot_cache_key: tuple[str, int] = ("", 0)
        self._load_iv_surface_history_state()
        self._bootstrap_iv_surface_history_from_scalar_history()

    def get_proxy_snapshot(self) -> PCAMetricSnapshot:
        """Return the current PCA-PROXY snapshot, cached by calendar day."""
        today = datetime.now(UTC).date().isoformat()
        if self._proxy_cache is not None and self._proxy_cache_date == today:
            return self._proxy_cache

        snapshot = self._build_proxy_snapshot()
        self._proxy_cache = snapshot
        self._proxy_cache_date = today
        return snapshot

    def get_iv_snapshot(self) -> PCAMetricSnapshot:
        """Return the live PCA-IV snapshot when seeded history is sufficient."""
        cache_key = (self._iv_surface_history_last_ts, self._iv_surface_history_count)
        if self._iv_snapshot_cache is not None and self._iv_snapshot_cache_key == cache_key:
            return self._iv_snapshot_cache

        if self._iv_surface_history_count < PCA_IV_MIN_OBSERVATIONS:
            snapshot = self.get_iv_placeholder_snapshot()
        else:
            try:
                snapshot = self._build_iv_snapshot()
            except Exception as exc:
                self.error_handler.handle_error(exc, {"method": "_build_iv_snapshot"})
                self.logger.warning("PCA-IV falling back to seed-state placeholder: %s", exc)
                storage_status = self.get_iv_surface_storage_status()
                snapshot = PCAMetricSnapshot(
                    signal_value=0.0,
                    previous_value=0.0,
                    explained_variance=0.0,
                    spectral_gap=0.0,
                    dispersion_score=0.0,
                    universe_size=0,
                    confidence=0.0,
                    timestamp=datetime.now(UTC),
                    source="fallback",
                    placeholder=True,
                    status="fallback",
                    details={
                        "message": "PCA-IV live computation is temporarily unavailable.",
                        "target_surface": "moneyness x dte implied-vol grid",
                        "error": str(exc),
                        **storage_status,
                    },
                )

        self._iv_snapshot_cache = snapshot
        self._iv_snapshot_cache_key = cache_key
        return snapshot

    def get_iv_placeholder_snapshot(self) -> PCAMetricSnapshot:
        """Return the placeholder PCA-IV snapshot."""
        now = datetime.now(UTC)
        storage_status = self.get_iv_surface_storage_status()
        stored_snapshots = int(storage_status.get("stored_snapshots", 0) or 0)
        phase = str(storage_status.get("phase") or "placeholder")
        if stored_snapshots > 0:
            message = (
                "History seeding is active for the future TRAD IV-surface PCA factor model."
            )
        else:
            message = "Reserved for future TRAD IV-surface PCA factor model."
        return PCAMetricSnapshot(
            signal_value=0.0,
            previous_value=0.0,
            explained_variance=0.0,
            spectral_gap=0.0,
            dispersion_score=0.0,
            universe_size=0,
            confidence=0.0,
            timestamp=now,
            source="placeholder",
            placeholder=True,
            status="placeholder",
            details={
                "message": message,
                "target_surface": "moneyness x dte implied-vol grid",
                "phase": phase,
                **storage_status,
            },
        )

    def get_iv_surface_storage_status(self) -> dict[str, Any]:
        """Return current persistent-history status for future PCA-IV work."""
        progress = 0.0
        if PCA_IV_HISTORY_TARGET > 0:
            progress = min(
                1.0,
                self._iv_surface_history_count / float(PCA_IV_HISTORY_TARGET),
            )

        if self._iv_surface_history_count <= 0:
            phase = "placeholder"
        elif self._iv_surface_history_count < PCA_IV_MIN_OBSERVATIONS:
            phase = "history-seeding"
        elif self._iv_surface_history_count < PCA_IV_HISTORY_TARGET:
            phase = "live-seeding"
        else:
            phase = "live-ready"

        return {
            "history_path": self._iv_surface_history_path.as_posix(),
            "stored_snapshots": self._iv_surface_history_count,
            "first_snapshot_ts": self._iv_surface_history_first_ts or None,
            "last_snapshot_ts": self._iv_surface_history_last_ts or None,
            "min_live_snapshots": PCA_IV_MIN_OBSERVATIONS,
            "target_snapshots": PCA_IV_HISTORY_TARGET,
            "readiness_progress": progress,
            "phase": phase,
            "feature_columns": list(PCA_IV_FEATURE_COLUMNS),
        }

    def record_iv_surface_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Persist a compact TRAD surface snapshot for future PCA-IV training."""
        if not isinstance(snapshot, dict):
            return self.get_iv_surface_storage_status()

        snapshot_ts = str(snapshot.get("snapshot_ts") or "").strip()
        if not snapshot_ts or snapshot_ts == self._iv_surface_last_write_ts:
            return self.get_iv_surface_storage_status()

        normalized = self._normalize_iv_surface_snapshot(snapshot)
        try:
            with self._iv_surface_history_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(normalized, sort_keys=True))
                handle.write("\n")
            self._update_iv_surface_storage_state(snapshot_ts)
            self._iv_snapshot_cache = None
            self._iv_snapshot_cache_key = ("", 0)
        except Exception as exc:
            self.logger.debug("PCA-IV history seed write failed: %s", exc)

        return self.get_iv_surface_storage_status()

    def _build_iv_snapshot(self) -> PCAMetricSnapshot:
        """Compute the first live PCA-IV signal from persisted surface features."""
        storage_status = self.get_iv_surface_storage_status()
        feature_frame = self._load_iv_surface_feature_frame().tail(PCA_IV_LOOKBACK_WINDOW)

        feature_means = feature_frame.mean()
        feature_stds = feature_frame.std(ddof=0).replace(0.0, np.nan)
        valid_columns = [
            column
            for column in feature_frame.columns
            if not pd.isna(feature_stds.get(column))
        ]
        if len(valid_columns) < 3:
            raise ValueError("insufficient PCA-IV feature coverage after standardization")

        standardized = (feature_frame[valid_columns] - feature_means[valid_columns]) / feature_stds[valid_columns]
        standardized = standardized.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if standardized.shape[0] < PCA_IV_MIN_OBSERVATIONS:
            raise ValueError(
                f"insufficient standardized PCA-IV history rows={standardized.shape[0]}"
            )

        matrix = standardized.to_numpy(dtype=float)
        corr = np.corrcoef(matrix, rowvar=False)
        if not np.isfinite(corr).all():
            raise ValueError("PCA-IV correlation matrix contains non-finite values")

        shrunk = ((1.0 - SHRINKAGE_ALPHA) * corr) + (SHRINKAGE_ALPHA * np.eye(corr.shape[0]))
        eigvals, eigvecs = np.linalg.eigh(shrunk)
        order = np.argsort(eigvals)[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]

        feature_names = list(standardized.columns)
        level_index = feature_names.index("feature_level") if "feature_level" in feature_names else 0
        pc1 = eigvecs[:, 0]
        if pc1[level_index] < 0:
            pc1 = -pc1

        pc2 = eigvecs[:, 1]
        latest_score = float(matrix[-1] @ pc1)
        previous_score = float(matrix[-2] @ pc1) if matrix.shape[0] >= 2 else latest_score
        dispersion_score = float(abs(matrix[-1] @ pc2))

        total_variance = float(np.sum(eigvals)) if eigvals.size else 0.0
        explained_variance = float(eigvals[0] / total_variance) if total_variance > 0 else 0.0
        spectral_gap = float(eigvals[0] - eigvals[1]) if eigvals.size >= 2 else 0.0
        confidence = max(0.0, min(1.0, explained_variance * 1.20))

        composite_signal = latest_score * (0.5 + explained_variance)
        composite_series = (matrix @ pc1) * (0.5 + explained_variance)
        recent_window = min(PCA_IV_HISTORY_WINDOW, composite_series.shape[0])
        recent_history = [float(value) for value in composite_series[-recent_window:]]
        recent_dates = [index.date().isoformat() for index in standardized.index[-recent_window:]]

        latest_row = feature_frame.loc[standardized.index[-1]]
        regime_band, regime_color, regime_note = self._classify_iv_regime(
            composite_signal,
            dispersion_score,
            float(latest_row.get("feature_level", float("nan"))),
        )
        pc1_loadings = {
            name: float(loading)
            for name, loading in sorted(
                zip(feature_names, pc1, strict=False),
                key=lambda item: abs(item[1]),
                reverse=True,
            )
        }

        latest_timestamp = standardized.index[-1].to_pydatetime()
        return PCAMetricSnapshot(
            signal_value=float(composite_signal),
            previous_value=float(previous_score * (0.5 + explained_variance)),
            explained_variance=explained_variance,
            spectral_gap=spectral_gap,
            dispersion_score=dispersion_score,
            universe_size=int(len(feature_names)),
            confidence=confidence,
            timestamp=latest_timestamp,
            source="surface-history",
            status="live",
            details={
                "pc1_score": latest_score,
                "pc2_abs": dispersion_score,
                "pc1_loadings": pc1_loadings,
                "active_features": feature_names,
                "row_count": int(standardized.shape[0]),
                "recent_signal_history": recent_history,
                "recent_signal_dates": recent_dates,
                "history_window": recent_window,
                "regime_band": regime_band,
                "regime_color": regime_color,
                "regime_note": regime_note,
                "feature_level": float(latest_row.get("feature_level", float("nan"))),
                "feature_skew": float(latest_row.get("feature_skew", float("nan"))),
                "feature_convexity": float(latest_row.get("feature_convexity", float("nan"))),
                **storage_status,
            },
        )

    def _build_proxy_snapshot(self) -> PCAMetricSnapshot:
        """Compute the rolling sector-proxy PCA signal."""
        now = datetime.now(UTC)
        try:
            prices, source = self._load_price_matrix(SECTOR_PROXY_SYMBOLS)
            returns = np.log(prices).diff().dropna(how="any")

            if returns.shape[0] < MIN_OBSERVATIONS or returns.shape[1] < 3:
                raise ValueError(
                    f"insufficient proxy history rows={returns.shape[0]} cols={returns.shape[1]}"
                )

            returns = returns.tail(LOOKBACK_DAYS)
            standardized = (returns - returns.mean()) / returns.std(ddof=0)
            standardized = standardized.replace([np.inf, -np.inf], np.nan).dropna(how="any")
            if standardized.shape[0] < MIN_OBSERVATIONS:
                raise ValueError(
                    f"insufficient standardized proxy history rows={standardized.shape[0]}"
                )

            matrix = standardized.to_numpy(dtype=float)
            corr = np.corrcoef(matrix, rowvar=False)
            if not np.isfinite(corr).all():
                raise ValueError("proxy correlation matrix contains non-finite values")

            # Apply simple diagonal shrinkage to stabilize loadings.
            n_assets = corr.shape[0]
            shrunk = ((1.0 - SHRINKAGE_ALPHA) * corr) + (SHRINKAGE_ALPHA * np.eye(n_assets))
            eigvals, eigvecs = np.linalg.eigh(shrunk)
            order = np.argsort(eigvals)[::-1]
            eigvals = eigvals[order]
            eigvecs = eigvecs[:, order]

            pc1 = eigvecs[:, 0]
            if np.sum(pc1) < 0:
                pc1 = -pc1

            pc2 = eigvecs[:, 1]
            latest_score = float(matrix[-1] @ pc1)
            previous_score = float(matrix[-2] @ pc1) if matrix.shape[0] >= 2 else latest_score
            dispersion_score = float(abs(matrix[-1] @ pc2))

            total_variance = float(np.sum(eigvals)) if eigvals.size else 0.0
            explained_variance = float(eigvals[0] / total_variance) if total_variance > 0 else 0.0
            spectral_gap = float(eigvals[0] - eigvals[1]) if eigvals.size >= 2 else 0.0
            confidence = max(0.0, min(1.0, explained_variance * 1.25))

            composite_signal = latest_score * (0.5 + explained_variance)
            composite_series = (matrix @ pc1) * (0.5 + explained_variance)
            recent_window = min(PCA_PROXY_HISTORY_WINDOW, composite_series.shape[0])
            recent_history = [
                float(value) for value in composite_series[-recent_window:]
            ]
            recent_dates = [
                index.date().isoformat()
                for index in standardized.index[-recent_window:]
            ]
            regime_band, regime_color, regime_note = self._classify_proxy_regime(
                composite_signal,
                dispersion_score,
                explained_variance,
            )

            return PCAMetricSnapshot(
                signal_value=float(composite_signal),
                previous_value=float(previous_score * (0.5 + explained_variance)),
                explained_variance=explained_variance,
                spectral_gap=spectral_gap,
                dispersion_score=dispersion_score,
                universe_size=int(matrix.shape[1]),
                confidence=confidence,
                timestamp=now,
                source=source,
                details={
                    "pc1_score": latest_score,
                    "pc2_abs": dispersion_score,
                    "symbols": list(standardized.columns),
                    "recent_signal_history": recent_history,
                    "recent_signal_dates": recent_dates,
                    "history_window": recent_window,
                    "regime_band": regime_band,
                    "regime_color": regime_color,
                    "regime_note": regime_note,
                },
            )

        except Exception as exc:
            self.error_handler.handle_error(exc, {"method": "_build_proxy_snapshot"})
            self.logger.warning("PCA proxy falling back to neutral placeholder: %s", exc)
            return PCAMetricSnapshot(
                signal_value=0.0,
                previous_value=0.0,
                explained_variance=0.0,
                spectral_gap=0.0,
                dispersion_score=0.0,
                universe_size=0,
                confidence=0.0,
                timestamp=now,
                source="fallback",
                status="fallback",
                details={"error": str(exc)},
            )

    def _load_price_matrix(self, symbols: tuple[str, ...]) -> tuple[pd.DataFrame, str]:
        """Load a close-price matrix using Tradier first, yfinance fallback second."""
        tradier_prices = self._load_prices_from_tradier(symbols)
        if tradier_prices is not None and tradier_prices.shape[1] >= 3:
            return tradier_prices, "tradier"

        yfinance_prices = self._load_prices_from_yfinance(symbols)
        if yfinance_prices is not None and yfinance_prices.shape[1] >= 3:
            return yfinance_prices, "yfinance"

        raise ValueError("no PCA proxy price matrix available from Tradier or yfinance")

    def _load_prices_from_tradier(self, symbols: tuple[str, ...]) -> pd.DataFrame | None:
        """Load daily historical closes from Tradier when configured."""
        if not _TRADIER_FACTORY_AVAILABLE or create_tradier_client_from_env is None:
            return None

        api_key = str(os.getenv("TRADIER_LIVE_API_KEY", "")).strip()
        if not api_key:
            return None

        try:
            client = create_tradier_client_from_env()
        except Exception as exc:
            self.logger.debug("PCA proxy Tradier client unavailable: %s", exc)
            return None

        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=CALENDAR_LOOKBACK_DAYS)
        series_by_symbol: dict[str, pd.Series] = {}

        for symbol in symbols:
            try:
                response = client.get_historical_quotes(
                    symbol,
                    interval="daily",
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                )
                rows = response.get("history", {}).get("day", [])
                if not rows:
                    continue

                dates: list[pd.Timestamp] = []
                closes: list[float] = []
                for row in rows:
                    close = row.get("close")
                    date_str = row.get("date")
                    if close is None or date_str is None:
                        continue
                    close_value = float(close)
                    if close_value <= 0:
                        continue
                    dates.append(pd.Timestamp(date_str))
                    closes.append(close_value)

                if len(closes) >= MIN_OBSERVATIONS:
                    series_by_symbol[symbol] = pd.Series(closes, index=dates, dtype=float)
            except Exception as exc:
                self.logger.debug("PCA proxy Tradier history failed for %s: %s", symbol, exc)

        if len(series_by_symbol) < 3:
            return None

        prices = pd.DataFrame(series_by_symbol).sort_index().dropna(how="any")
        return prices if not prices.empty else None

    def _load_prices_from_yfinance(self, symbols: tuple[str, ...]) -> pd.DataFrame | None:
        """Load daily close prices from yfinance as a fallback."""
        if not _YFINANCE_AVAILABLE or yf is None:
            return None

        try:
            frame = yf.download(
                list(symbols),
                period="18mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:
            self.logger.debug("PCA proxy yfinance download failed: %s", exc)
            return None

        if frame is None or frame.empty:
            return None

        if isinstance(frame.columns, pd.MultiIndex):
            if "Close" not in frame.columns.get_level_values(0):
                return None
            closes = frame["Close"].copy()
        else:
            close_col = "Close" if "Close" in frame.columns else "close"
            if close_col not in frame.columns:
                return None
            closes = frame[[close_col]].rename(columns={close_col: symbols[0]})

        closes = closes.sort_index().dropna(axis=1, how="all").dropna(how="any")
        return closes if closes.shape[1] >= 3 else None

    def _load_iv_surface_history_state(self) -> None:
        """Load compact persistence metadata for the PCA-IV seed history."""
        if not self._iv_surface_history_path.exists():
            return

        count = 0
        first_snapshot_ts = ""
        last_snapshot_ts = ""
        try:
            with self._iv_surface_history_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue

                    count += 1
                    snapshot_ts = str(payload.get("snapshot_ts") or "").strip()
                    if not first_snapshot_ts and snapshot_ts:
                        first_snapshot_ts = snapshot_ts
                    if snapshot_ts:
                        last_snapshot_ts = snapshot_ts

            self._iv_surface_history_count = count
            self._iv_surface_history_first_ts = first_snapshot_ts
            self._iv_surface_history_last_ts = last_snapshot_ts
            self._iv_surface_last_write_ts = last_snapshot_ts
        except Exception as exc:
            self.logger.debug("PCA-IV history state unavailable: %s", exc)

    def _bootstrap_iv_surface_history_from_scalar_history(self) -> None:
        """Bootstrap PCA-IV history from scalar TRAD IV history when empty."""
        if self._iv_surface_history_count > 0:
            return

        rows = self._build_scalar_iv_bootstrap_rows()
        if len(rows) < PCA_IV_MIN_OBSERVATIONS:
            return

        try:
            with self._iv_surface_history_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, sort_keys=True))
                    handle.write("\n")
            self._load_iv_surface_history_state()
            self._iv_snapshot_cache = None
            self._iv_snapshot_cache_key = ("", 0)
            self.logger.info(
                "PCA-IV bootstrapped %d rows from scalar IV history",
                len(rows),
            )
        except Exception as exc:
            self.logger.debug("PCA-IV bootstrap unavailable: %s", exc)

    def _build_scalar_iv_bootstrap_rows(self) -> list[dict[str, Any]]:
        """Convert scalar TRAD IV history into approximate PCA-IV feature rows."""
        if not self._iv_scalar_history_path.exists():
            return []

        try:
            payload = json.loads(self._iv_scalar_history_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.debug("PCA-IV scalar history unreadable: %s", exc)
            return []

        if not isinstance(payload, list):
            return []

        series_by_date: dict[pd.Timestamp, float] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                continue

            date_str = str(entry.get("date") or "").strip()
            level = self._normalize_scalar_iv_level(entry.get("iv"))
            if not date_str or not math.isfinite(level) or level <= 0.0:
                continue

            timestamp = pd.to_datetime(date_str, utc=True, errors="coerce")
            if pd.isna(timestamp):
                continue
            series_by_date[pd.Timestamp(timestamp)] = float(level)

        if len(series_by_date) < PCA_IV_MIN_OBSERVATIONS:
            return []

        scalar_iv = pd.Series(series_by_date, dtype=float).sort_index()
        short_change = scalar_iv.diff(1)
        medium_trend = scalar_iv.rolling(window=5, min_periods=5).mean()
        long_trend = scalar_iv.rolling(window=21, min_periods=21).mean()
        long_change = scalar_iv.diff(5) / 5.0
        change_accel = short_change.diff(1)
        level_zscore = (
            (scalar_iv - long_trend)
            / scalar_iv.rolling(window=10, min_periods=10).std(ddof=0).replace(0.0, np.nan)
        )
        change_vol = short_change.rolling(window=5, min_periods=5).std(ddof=0)

        feature_frame = pd.DataFrame(
            {
                "feature_level": scalar_iv,
                "feature_front_curve": short_change,
                "feature_back_curve": medium_trend - long_trend,
                "feature_curve_butterfly": change_accel,
                "feature_term_twist": short_change - long_change,
                "feature_skew": level_zscore,
                "feature_convexity": change_vol,
            }
        )
        feature_frame = feature_frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if feature_frame.shape[0] < PCA_IV_MIN_OBSERVATIONS:
            return []

        feature_frame = feature_frame.tail(PCA_IV_BOOTSTRAP_ROWS)
        bootstrap_rows: list[dict[str, Any]] = []
        for timestamp, row in feature_frame.iterrows():
            feature_level = float(row["feature_level"])
            feature_front_curve = float(row["feature_front_curve"])
            feature_back_curve = float(row["feature_back_curve"])
            feature_curve_butterfly = float(row["feature_curve_butterfly"])
            feature_term_twist = float(row["feature_term_twist"])
            feature_skew = float(row["feature_skew"])
            feature_convexity = float(row["feature_convexity"])
            atm_iv_0dte = max(feature_level + feature_front_curve, 0.01)
            atm_iv_1dte = max(feature_level + (feature_front_curve * 0.8), 0.01)
            atm_iv_7dte = max(feature_level, 0.01)
            atm_iv_30dte = max(feature_level - feature_back_curve, 0.01)
            term_slope_0_7 = feature_front_curve / (7.0 / 365.0)
            term_slope_7_30 = feature_back_curve / (23.0 / 365.0)

            bootstrap_rows.append(
                {
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "snapshot_ts": timestamp.to_pydatetime().isoformat(),
                    "underlying": "TRAD",
                    "feature_vector_version": "v1",
                    "bootstrap_source": self._iv_scalar_history_path.as_posix(),
                    "bootstrap_kind": "scalar-iv-history",
                    "atm_iv_0dte": atm_iv_0dte,
                    "atm_iv_1dte": atm_iv_1dte,
                    "atm_iv_7dte": atm_iv_7dte,
                    "atm_iv_30dte": atm_iv_30dte,
                    "term_slope_0_7": term_slope_0_7,
                    "term_slope_7_30": term_slope_7_30,
                    "rr_25d": feature_skew,
                    "fly_25d": feature_convexity,
                    "surface_confidence": 0.35,
                    "surface_age_ms": 86_400_000.0,
                    "feature_level": feature_level,
                    "feature_front_curve": feature_front_curve,
                    "feature_back_curve": feature_back_curve,
                    "feature_curve_butterfly": feature_curve_butterfly,
                    "feature_term_twist": feature_term_twist,
                    "feature_skew": feature_skew,
                    "feature_convexity": feature_convexity,
                }
            )

        return bootstrap_rows

    def _load_iv_surface_feature_frame(self) -> pd.DataFrame:
        """Load the persisted IV-surface feature history as a clean DataFrame."""
        rows_by_ts: dict[str, dict[str, Any]] = {}
        if not self._iv_surface_history_path.exists():
            raise ValueError("PCA-IV history file is missing")

        with self._iv_surface_history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue

                snapshot_ts = str(payload.get("snapshot_ts") or "").strip()
                if not snapshot_ts:
                    continue
                rows_by_ts[snapshot_ts] = {
                    "snapshot_ts": snapshot_ts,
                    **{
                        column: self._coerce_float(payload.get(column))
                        for column in PCA_IV_FEATURE_COLUMNS
                    },
                }

        if len(rows_by_ts) < PCA_IV_MIN_OBSERVATIONS:
            raise ValueError(f"insufficient PCA-IV history rows={len(rows_by_ts)}")

        frame = pd.DataFrame(rows_by_ts.values())
        frame["snapshot_ts"] = pd.to_datetime(frame["snapshot_ts"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["snapshot_ts"]).sort_values("snapshot_ts")
        frame = frame.set_index("snapshot_ts")
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if frame.shape[0] < PCA_IV_MIN_OBSERVATIONS:
            raise ValueError(f"insufficient clean PCA-IV history rows={frame.shape[0]}")
        return frame

    def _update_iv_surface_storage_state(self, snapshot_ts: str) -> None:
        """Update cached metadata after a successful JSONL append."""
        self._iv_surface_history_count += 1
        if not self._iv_surface_history_first_ts:
            self._iv_surface_history_first_ts = snapshot_ts
        self._iv_surface_history_last_ts = snapshot_ts
        self._iv_surface_last_write_ts = snapshot_ts

    def _normalize_iv_surface_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Convert the live term-structure snapshot into a PCA-ready feature row."""
        atm_iv_0dte = self._coerce_float(snapshot.get("atm_iv_0dte"))
        atm_iv_1dte = self._coerce_float(snapshot.get("atm_iv_1dte"))
        atm_iv_7dte = self._coerce_float(snapshot.get("atm_iv_7dte"))
        atm_iv_30dte = self._coerce_float(snapshot.get("atm_iv_30dte"))
        term_slope_0_7 = self._coerce_float(snapshot.get("term_slope_0_7"))
        term_slope_7_30 = self._coerce_float(snapshot.get("term_slope_7_30"))
        rr_25d = self._coerce_float(snapshot.get("rr_25d"))
        fly_25d = self._coerce_float(snapshot.get("fly_25d"))
        surface_confidence = self._coerce_float(snapshot.get("surface_confidence"))
        surface_age_ms = self._coerce_float(snapshot.get("surface_age_ms"))

        feature_front_curve = None
        feature_back_curve = None
        feature_curve_butterfly = None
        feature_term_twist = None
        if math.isfinite(atm_iv_0dte) and math.isfinite(atm_iv_7dte):
            feature_front_curve = atm_iv_0dte - atm_iv_7dte
        if math.isfinite(atm_iv_7dte) and math.isfinite(atm_iv_30dte):
            feature_back_curve = atm_iv_7dte - atm_iv_30dte
        if (
            math.isfinite(atm_iv_0dte)
            and math.isfinite(atm_iv_7dte)
            and math.isfinite(atm_iv_30dte)
        ):
            feature_curve_butterfly = atm_iv_0dte - (2.0 * atm_iv_7dte) + atm_iv_30dte
        if math.isfinite(term_slope_0_7) and math.isfinite(term_slope_7_30):
            feature_term_twist = term_slope_0_7 - term_slope_7_30

        return {
            "recorded_at": datetime.now(UTC).isoformat(),
            "snapshot_ts": str(snapshot.get("snapshot_ts") or ""),
            "underlying": str(snapshot.get("underlying") or "TRAD"),
            "feature_vector_version": "v1",
            "atm_iv_0dte": atm_iv_0dte,
            "atm_iv_1dte": atm_iv_1dte,
            "atm_iv_7dte": atm_iv_7dte,
            "atm_iv_30dte": atm_iv_30dte,
            "term_slope_0_7": term_slope_0_7,
            "term_slope_7_30": term_slope_7_30,
            "rr_25d": rr_25d,
            "fly_25d": fly_25d,
            "surface_confidence": surface_confidence,
            "surface_age_ms": surface_age_ms,
            "feature_level": atm_iv_7dte,
            "feature_front_curve": feature_front_curve,
            "feature_back_curve": feature_back_curve,
            "feature_curve_butterfly": feature_curve_butterfly,
            "feature_term_twist": feature_term_twist,
            "feature_skew": rr_25d,
            "feature_convexity": fly_25d,
        }

    @staticmethod
    def _coerce_float(value: Any) -> float:
        """Convert arbitrary values to float with NaN fallback."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("nan")

    @staticmethod
    def _normalize_scalar_iv_level(value: Any) -> float:
        """Normalize scalar IV history to the decimal scale used by surface snapshots."""
        iv_value = PCASignalEngine._coerce_float(value)
        if not math.isfinite(iv_value) or iv_value <= 0.0:
            return float("nan")
        if iv_value > 1.5:
            return iv_value / 100.0
        return iv_value

    @staticmethod
    def _classify_proxy_regime(
        composite_signal: float,
        dispersion_score: float,
        explained_variance: float,
    ) -> tuple[str, str, str]:
        """Map the latest proxy snapshot into a compact dialog badge."""
        if dispersion_score >= max(0.85, abs(composite_signal) * 0.85):
            return (
                "Rotation",
                "#f2b134",
                "Cross-sector dispersion is elevated relative to the common factor.",
            )
        if composite_signal >= 0.75 and explained_variance >= 0.35:
            return (
                "Positive impulse",
                "#5cffa0",
                "The dominant sector factor is broad and currently pushing upward.",
            )
        if composite_signal <= -0.75 and explained_variance >= 0.35:
            return (
                "Negative impulse",
                "#ff6b6b",
                "The dominant sector factor is broad and currently pushing downward.",
            )
        return (
            "Balanced",
            "#9bb",
            "The common factor is present, but internal breadth is still mixed.",
        )

    @staticmethod
    def _classify_iv_regime(
        composite_signal: float,
        dispersion_score: float,
        feature_level: float,
    ) -> tuple[str, str, str]:
        """Map the latest IV-surface factor into a compact dialog badge."""
        if dispersion_score >= max(0.75, abs(composite_signal) * 0.80):
            return (
                "Surface twist",
                "#f2b134",
                "Secondary curvature and skew effects are large relative to the main IV factor.",
            )
        if composite_signal >= 0.75 or feature_level >= 0.24:
            return (
                "Stress expansion",
                "#FF073A",
                "The dominant IV surface factor is aligned with higher-volatility conditions.",
            )
        if composite_signal <= -0.75 or feature_level <= 0.16:
            return (
                "Compression",
                "#5cffa0",
                "The surface is aligning with lower-volatility compression and normalization.",
            )
        return (
            "Balanced",
            "#9bb",
            "The IV surface factor is active, but not strongly directional yet.",
        )


_pca_engine_instance: PCASignalEngine | None = None


def get_pca_signal_engine() -> PCASignalEngine:
    """Return the module-level PCA signal engine singleton."""
    global _pca_engine_instance
    if _pca_engine_instance is None:
        _pca_engine_instance = PCASignalEngine()
    return _pca_engine_instance
