#!/usr/bin/env python3
from __future__ import annotations

"""
TRADOV - Pair-trading corpus policy helpers.

Loads the minimal pair-trading corpus policy from config/pair_trading_corpus_v1.json
and exposes small helpers for allowlist / negative-control checks.
"""

from dataclasses import dataclass, field
import json
import os
import re
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PairCorpusEntry:
    name: str
    leg_a: str | None = None
    leg_b: str | None = None
    sector: str = ""
    pair_type: str = ""
    status: str = ""
    rationale: str = ""

    @property
    def pair_key(self) -> str | None:
        if not self.leg_a or not self.leg_b:
            return None
        return f"{str(self.leg_a).strip().upper()}/{str(self.leg_b).strip().upper()}"


@dataclass(frozen=True)
class PairBundleEntry:
    name: str
    pair_keys: tuple[str, ...] = ()
    regime_tags: tuple[str, ...] = ()
    liquidity_tier: str = "medium"
    description: str = ""
    status: str = ""

    @property
    def normalized_pair_keys(self) -> tuple[str, ...]:
        seen: set[str] = set()
        keys: list[str] = []
        for key in self.pair_keys:
            normalized = str(key or "").strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            keys.append(normalized)
        return tuple(keys)

    @property
    def normalized_regime_tags(self) -> tuple[str, ...]:
        seen: set[str] = set()
        tags: list[str] = []
        for tag in self.regime_tags:
            normalized = str(tag or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tags.append(normalized)
        return tuple(tags)


@dataclass(frozen=True)
class PairBundleSelection:
    bundle_name: str
    reason: str
    score: float
    regime_name: str = ""
    liquidity_hint: float | None = None
    pair_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class PairCorpusPolicy:
    policy_version: str = ""
    schema_version: int = 1
    corpus_mode: str = "minimal"
    description: str = ""
    limits: dict[str, int] = field(default_factory=dict)
    active_pairs: tuple[PairCorpusEntry, ...] = ()
    optional_pairs: tuple[PairCorpusEntry, ...] = ()
    bundles: tuple[PairBundleEntry, ...] = ()
    active_bundle_name: str = ""
    negative_control: PairCorpusEntry | None = None
    selection_filters: dict[str, Any] = field(default_factory=dict)
    exit_criteria: tuple[str, ...] = ()

    @property
    def active_pair_keys(self) -> set[str]:
        return {
            key
            for key in (entry.pair_key for entry in self.active_pairs)
            if key
        }

    @property
    def optional_pair_keys(self) -> set[str]:
        return {
            key
            for key in (entry.pair_key for entry in self.optional_pairs)
            if key
        }

    @property
    def negative_control_pair_keys(self) -> set[str]:
        if self.negative_control is None:
            return set()
        key = self.negative_control.pair_key
        return {key} if key else set()

    def allows_pair_key(self, pair_key: str | None) -> bool:
        if not pair_key:
            return False
        normalized = str(pair_key).strip().upper()
        return normalized in self.active_pair_keys

    def is_negative_control_pair_key(self, pair_key: str | None) -> bool:
        if not pair_key:
            return False
        normalized = str(pair_key).strip().upper()
        return normalized in self.negative_control_pair_keys

    @property
    def bundle_names(self) -> tuple[str, ...]:
        return tuple(bundle.name for bundle in self.bundles if str(bundle.name).strip())

    def get_bundle(self, name: str | None) -> PairBundleEntry | None:
        normalized = str(name or "").strip().lower()
        if not normalized:
            return None
        for bundle in self.bundles:
            if str(bundle.name).strip().lower() == normalized:
                return bundle
        return None

    @staticmethod
    def _regime_tokens(regime_name: str | None) -> set[str]:
        raw = str(regime_name or "").strip().lower()
        if not raw:
            return set()
        return {token for token in re.split(r"[^a-z0-9]+", raw) if token}

    @staticmethod
    def _bundle_liquidity_score(liquidity_tier: str) -> float:
        return {
            "high": 1.0,
            "medium": 0.65,
            "low": 0.35,
        }.get(str(liquidity_tier or "").strip().lower(), 0.5)

    def select_bundle(
        self,
        *,
        regime_name: str | None = None,
        liquidity_hint: float | None = None,
        preferred_bundle_name: str | None = None,
    ) -> PairBundleSelection | None:
        """Choose the best pair bundle for the current regime/liquidity context."""
        if not self.bundles:
            return None

        if preferred_bundle_name:
            preferred = self.get_bundle(preferred_bundle_name)
            if preferred is not None:
                keys = tuple(key for key in preferred.normalized_pair_keys if key in self.active_pair_keys)
                return PairBundleSelection(
                    bundle_name=preferred.name,
                    reason="preferred_bundle",
                    score=1.0,
                    regime_name=str(regime_name or ""),
                    liquidity_hint=liquidity_hint,
                    pair_keys=keys,
                )

        if self.active_bundle_name:
            active = self.get_bundle(self.active_bundle_name)
            if active is not None:
                keys = tuple(key for key in active.normalized_pair_keys if key in self.active_pair_keys)
                return PairBundleSelection(
                    bundle_name=active.name,
                    reason="configured_active_bundle",
                    score=1.0,
                    regime_name=str(regime_name or ""),
                    liquidity_hint=liquidity_hint,
                    pair_keys=keys,
                )

        regime_tokens = self._regime_tokens(regime_name)
        best: PairBundleSelection | None = None
        for bundle in self.bundles:
            keys = tuple(key for key in bundle.normalized_pair_keys if key in self.active_pair_keys)
            if not keys:
                continue
            liquidity_score = self._bundle_liquidity_score(bundle.liquidity_tier)
            if liquidity_hint is not None:
                hint = max(0.0, min(1.0, float(liquidity_hint)))
                liquidity_score = 1.0 - abs(liquidity_score - hint)

            bundle_tags = set(bundle.normalized_regime_tags)
            regime_score = 0.20 if regime_tokens else 0.10
            if regime_tokens and bundle_tags:
                overlap = len(regime_tokens & bundle_tags)
                if overlap > 0:
                    regime_score = min(1.0, 0.55 + 0.15 * overlap)
                elif "crisis" in regime_tokens and liquidity_score >= 0.65:
                    regime_score = 0.45
                elif ("range" in regime_tokens or "choppy" in regime_tokens) and liquidity_score >= 0.5:
                    regime_score = 0.35

            coverage = len(keys) / max(1, len(bundle.normalized_pair_keys))
            score = 0.55 * regime_score + 0.30 * liquidity_score + 0.15 * coverage
            if best is None or score > best.score:
                best = PairBundleSelection(
                    bundle_name=bundle.name,
                    reason="regime_liquidity_match",
                    score=score,
                    regime_name=str(regime_name or ""),
                    liquidity_hint=liquidity_hint,
                    pair_keys=keys,
                )
        return best

    def get_bundle_pair_keys(
        self,
        bundle_name: str | None,
        *,
        only_active: bool = True,
    ) -> tuple[str, ...]:
        bundle = self.get_bundle(bundle_name)
        if bundle is None:
            return ()
        keys = bundle.normalized_pair_keys
        if only_active:
            return tuple(key for key in keys if key in self.active_pair_keys)
        return keys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_pair_corpus_policy_path() -> Path:
    override = str(os.environ.get("TRADOV_PAIR_CORPUS_POLICY_PATH", "")).strip()
    if override:
        return Path(override).expanduser()
    return _repo_root() / "config" / "pair_trading_corpus_v1.json"


def _parse_entry(raw: Any) -> PairCorpusEntry:
    if not isinstance(raw, dict):
        return PairCorpusEntry(name="")
    return PairCorpusEntry(
        name=str(raw.get("name", "") or ""),
        leg_a=(str(raw["leg_a"]).strip().upper() if raw.get("leg_a") not in (None, "") else None),
        leg_b=(str(raw["leg_b"]).strip().upper() if raw.get("leg_b") not in (None, "") else None),
        sector=str(raw.get("sector", "") or ""),
        pair_type=str(raw.get("pair_type", "") or ""),
        status=str(raw.get("status", "") or ""),
        rationale=str(raw.get("rationale", "") or raw.get("selection_rule", "") or ""),
    )


def _policy_from_raw(raw: dict[str, Any]) -> PairCorpusPolicy:
    active_pairs = tuple(_parse_entry(entry) for entry in raw.get("active_pairs", []) or [])
    optional_pairs = tuple(_parse_entry(entry) for entry in raw.get("optional_pairs", []) or [])
    bundles_raw = raw.get("bundles", []) or []
    negative_control_raw = raw.get("negative_control")
    negative_control = _parse_entry(negative_control_raw) if isinstance(negative_control_raw, dict) else None

    limits_raw = raw.get("limits", {})
    limits = limits_raw if isinstance(limits_raw, dict) else {}
    selection_filters_raw = raw.get("selection_filters", {})
    selection_filters = selection_filters_raw if isinstance(selection_filters_raw, dict) else {}
    exit_criteria_raw = raw.get("exit_criteria", [])
    exit_criteria = tuple(str(item) for item in exit_criteria_raw if str(item).strip())

    def _parse_bundle(raw_bundle: Any) -> PairBundleEntry:
        if not isinstance(raw_bundle, dict):
            return PairBundleEntry(name="")
        pair_keys_raw = raw_bundle.get("pair_keys", []) or []
        regime_tags_raw = raw_bundle.get("regime_tags", []) or raw_bundle.get("regimes", []) or []
        return PairBundleEntry(
            name=str(raw_bundle.get("name", "") or ""),
            pair_keys=tuple(str(key).strip().upper() for key in pair_keys_raw if str(key or "").strip()),
            regime_tags=tuple(str(tag).strip().lower() for tag in regime_tags_raw if str(tag or "").strip()),
            liquidity_tier=str(raw_bundle.get("liquidity_tier", "medium") or "medium"),
            description=str(raw_bundle.get("description", "") or ""),
            status=str(raw_bundle.get("status", "") or ""),
        )

    bundles = tuple(_parse_bundle(entry) for entry in bundles_raw)

    return PairCorpusPolicy(
        policy_version=str(raw.get("policy_version", "") or ""),
        schema_version=int(raw.get("schema_version", 1) or 1),
        corpus_mode=str(raw.get("corpus_mode", "minimal") or "minimal"),
        description=str(raw.get("description", "") or ""),
        limits={str(k): int(v) for k, v in limits.items() if isinstance(v, (int, float, str)) and str(v).strip()},
        active_pairs=active_pairs,
        optional_pairs=optional_pairs,
        bundles=bundles,
        active_bundle_name=str(raw.get("active_bundle_name", "") or ""),
        negative_control=negative_control,
        selection_filters=selection_filters,
        exit_criteria=exit_criteria,
    )


def _load_from_config_manager() -> PairCorpusPolicy | None:
    try:
        from Tradov.TradovA_Core.TradovA03_Configuration import get_config_manager
    except Exception:
        return None

    try:
        cfg_mgr = get_config_manager()
    except Exception:
        return None

    if cfg_mgr is None:
        return None

    raw = cfg_mgr.get("autonomous_readiness.pair_corpus_policy")
    if not isinstance(raw, dict) or not raw:
        try:
            from Tradov.TradovA_Core.TradovA03_Configuration import ConfigManager
        except Exception:
            return None

        try:
            repo_config_path = default_pair_corpus_policy_path().parent / "config.json"
            temp_mgr = ConfigManager(config_path=repo_config_path)
        except Exception:
            return None

        raw = temp_mgr.get("autonomous_readiness.pair_corpus_policy")
        if not isinstance(raw, dict) or not raw:
            return None

    return _policy_from_raw(raw)


def load_pair_trading_corpus_policy(policy_path: str | Path | None = None) -> PairCorpusPolicy:
    if policy_path is None:
        from_config = _load_from_config_manager()
        if from_config is not None:
            return from_config

    path = Path(policy_path) if policy_path is not None else default_pair_corpus_policy_path()
    if not path.exists():
        return PairCorpusPolicy()

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, dict):
        return PairCorpusPolicy()

    return _policy_from_raw(raw)


def build_pair_corpus_reload_log_message(policy: PairCorpusPolicy) -> str:
    """Build a concise operator-facing reload message for the system log."""
    active_count = len(policy.active_pair_keys)
    negative_count = len(policy.negative_control_pair_keys)
    active_pairs = ", ".join(sorted(policy.active_pair_keys)) or "none"
    return (
        f"♻️ Pair corpus policy reloaded: {active_count} active pair(s), "
        f"{negative_count} negative-control pair(s) | active={active_pairs}"
    )


__all__ = [
    "PairCorpusEntry",
    "PairBundleEntry",
    "PairBundleSelection",
    "PairCorpusPolicy",
    "build_pair_corpus_reload_log_message",
    "default_pair_corpus_policy_path",
    "load_pair_trading_corpus_policy",
]
