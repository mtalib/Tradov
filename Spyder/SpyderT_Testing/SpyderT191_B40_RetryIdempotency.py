"""SPEC-4 — B40 retry layer must NOT auto-retry POST/PUT/DELETE on 5xx.

Audit reference: 2026-05-02_Codebase_Audit_v27.md → SPEC-4.

The bug: ``B40._create_session`` (B40:569-574) configures urllib3 ``Retry``
with::

    Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
    )

A ``place_order`` whose 5xx response was actually a successful broker write
will be auto-resubmitted, producing **duplicate option fills** at the
broker. The Tradier ``tag`` idempotency parameter (B40:984) is set from
``Order.tag``, but B02's ``_route_order`` does not populate it for most
call sites — so the dedup safety net is also absent.

Required behavior after SPEC-4:
- ``allowed_methods`` must be restricted to idempotent HTTP methods only:
  ``{"HEAD", "GET", "OPTIONS"}``. POST/PUT/DELETE must be EXCLUDED.
- (Optional, follow-on phase 6b/6c) Order endpoints implement a manual
  idempotent retry that uses Tradier ``tag`` to verify whether the prior
  submission already created an order id.

These tests are RED until SPEC-4 phase 6a ships. Phase 6a is a 1-line edit;
this is the highest-leverage change in the v27 backlog.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_session():
    """Build a TradierClient session via the production constructor path."""
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierClient

    # Construct without hitting Tradier — just exercise _create_session.
    client = TradierClient.__new__(TradierClient)
    client.api_key = "test-key"  # _create_session reads self.api_key
    return client._create_session()


class TestRetryAllowedMethods:
    """SPEC-4 phase 6a: urllib3 Retry must NOT auto-retry order-mutating methods."""

    def test_post_is_not_in_allowed_retry_methods(self):
        """POST must be excluded from urllib3 retry to prevent duplicate fills."""
        session = _make_session()

        adapter = session.get_adapter("https://api.tradier.com")
        retry = adapter.max_retries
        # urllib3.Retry uses either ``allowed_methods`` (newer) or ``method_whitelist`` (older)
        allowed = getattr(retry, "allowed_methods", None) or getattr(retry, "method_whitelist", None)
        allowed_upper = {m.upper() for m in (allowed or [])}

        assert "POST" not in allowed_upper, (
            "SPEC-4 (CRITICAL): urllib3 Retry must NOT auto-retry POST. "
            "A 'failed' POST whose response was actually a successful broker "
            "write produces a DUPLICATE FILL on retry. "
            f"Currently allowed_methods={sorted(allowed_upper)}. "
            "Fix: in B40._create_session, change "
            'allowed_methods=["HEAD","GET","OPTIONS","POST","PUT","DELETE"] '
            'to allowed_methods=["HEAD","GET","OPTIONS"].'
        )

    def test_put_is_not_in_allowed_retry_methods(self):
        """PUT (order modify) must also be excluded."""
        session = _make_session()
        adapter = session.get_adapter("https://api.tradier.com")
        retry = adapter.max_retries
        allowed = getattr(retry, "allowed_methods", None) or getattr(retry, "method_whitelist", None)
        allowed_upper = {m.upper() for m in (allowed or [])}

        assert "PUT" not in allowed_upper, (
            "SPEC-4: urllib3 Retry must NOT auto-retry PUT (used for order modify). "
            f"Got allowed_methods={sorted(allowed_upper)}."
        )

    def test_delete_is_not_in_allowed_retry_methods(self):
        """DELETE (order cancel) must also be excluded."""
        session = _make_session()
        adapter = session.get_adapter("https://api.tradier.com")
        retry = adapter.max_retries
        allowed = getattr(retry, "allowed_methods", None) or getattr(retry, "method_whitelist", None)
        allowed_upper = {m.upper() for m in (allowed or [])}

        assert "DELETE" not in allowed_upper, (
            "SPEC-4: urllib3 Retry must NOT auto-retry DELETE (used for order cancel). "
            "A retried DELETE on an order that already filled in the gap "
            "between request and retry can confuse downstream state. "
            f"Got allowed_methods={sorted(allowed_upper)}."
        )

    def test_safe_methods_are_still_retryable(self):
        """Regression guard: GET/HEAD/OPTIONS must remain retryable for transient errors."""
        session = _make_session()
        adapter = session.get_adapter("https://api.tradier.com")
        retry = adapter.max_retries
        allowed = getattr(retry, "allowed_methods", None) or getattr(retry, "method_whitelist", None)
        allowed_upper = {m.upper() for m in (allowed or [])}

        for safe_method in ("GET", "HEAD", "OPTIONS"):
            assert safe_method in allowed_upper, (
                f"Regression guard: SPEC-4 must NOT remove {safe_method} from retry. "
                f"Idempotent reads should still recover from transient broker hiccups. "
                f"Got allowed_methods={sorted(allowed_upper)}."
            )


class TestRetryStatusForcelistPreserved:
    """Regression guard: SPEC-4 must not change the 5xx status forcelist."""

    def test_5xx_status_forcelist_preserved(self):
        session = _make_session()
        adapter = session.get_adapter("https://api.tradier.com")
        retry = adapter.max_retries

        forcelist = set(retry.status_forcelist or [])
        for code in (429, 500, 502, 503, 504):
            assert code in forcelist, (
                f"Regression guard: status_forcelist must continue to retry on {code}. "
                f"Got status_forcelist={sorted(forcelist)}."
            )


class TestOrderTagIdempotency:
    """SPEC-4 phase 6b: every place_order call must carry a Tradier ``tag``.

    Even with POST removed from the urllib3 retry, application-level retries
    (B02's manual retry path) and SPEC-4 phase 6c's idempotent-retry layer
    require the ``tag`` query param to dedupe at Tradier. The current
    ``place_order`` defaults ``tag=None``, and B02's order construction
    does not populate ``Order.tag`` consistently.

    This test is currently RED and stays RED until B02 sets ``Order.tag``
    on every submit path AND B40 forwards it.
    """

    def test_place_order_propagates_tag_to_payload(self):
        """When a tag is passed, it must appear in the POST payload."""
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
            OrderClass,
            OrderDuration,
            OrderSide,
            OrderType,
            TradierClient,
        )

        client = TradierClient.__new__(TradierClient)
        client.api_key = "test-key"
        client.account_id = "TEST-1"
        client._make_request = MagicMock(return_value={"order": {"id": "BROKER-1"}})

        client.place_order(
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            duration=OrderDuration.DAY,
            order_class=OrderClass.EQUITY,
            tag="spyder-spec4-test",
        )

        # Inspect the recorded _make_request call.
        assert client._make_request.called
        _, kwargs = client._make_request.call_args
        payload = kwargs.get("data", {})
        assert payload.get("tag") == "spyder-spec4-test", (
            f"SPEC-4 phase 6b: Tradier 'tag' must be forwarded as a payload "
            f"field for idempotent dedup. Got payload={payload}."
        )

    def test_place_order_without_tag_logs_warning_or_raises(self):
        """SPEC-4 phase 6b: in live mode, calling place_order without a tag
        should be discouraged (warning at minimum, raise at strict).

        This test is intentionally lenient — it just asserts that the
        implementer DID something to flag the missing-tag case. Adjust the
        assertion when SPEC-4 phase 6b lands.
        """
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
            OrderClass,
            OrderDuration,
            OrderSide,
            OrderType,
            TradierClient,
        )

        client = TradierClient.__new__(TradierClient)
        client.api_key = "test-key"
        client.account_id = "TEST-1"
        client._make_request = MagicMock(return_value={"order": {"id": "BROKER-1"}})

        # Currently this just succeeds silently. SPEC-4 phase 6b should make
        # it loud — either via warning, exception, or explicit no-tag flag.
        with patch.object(client, "_make_request") as patched:
            patched.return_value = {"order": {"id": "BROKER-1"}}
            client.place_order(
                symbol="SPY",
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.MARKET,
                duration=OrderDuration.DAY,
                order_class=OrderClass.EQUITY,
                # NO tag passed.
            )
            payload = patched.call_args.kwargs.get("data", {})

        # SPEC-4 phase 6b acceptance: payload must NOT silently lack 'tag'
        # in live mode — either auto-generate one, or refuse the call.
        # Currently this assertion FAILS because the code accepts tag=None
        # and silently sends a payload without 'tag'.
        assert "tag" in payload, (
            "SPEC-4 phase 6b: place_order called without an explicit tag must "
            "either auto-generate one (preferred) or refuse the call. "
            "Currently the call silently succeeds with no idempotency key, "
            "leaving the order open to duplicate-fill on application-level retries. "
            f"Got payload={payload}."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
