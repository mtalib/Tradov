#!/usr/bin/env python3
"""Focused tests for the S11 TradingView last-price selector path."""

from Spyder.SpyderS_Signals.SpyderS11_TradingViewInternals import (
    TradingViewInternals,
    _CSS_PRICE_FALLBACK,
    _CSS_PRICE_PRIMARY,
    _NAV_TIMEOUT_MS,
)


class _FakeLocator:
    def __init__(self, *, text: str = "", wait_exc: Exception | None = None) -> None:
        self.text = text
        self.wait_exc = wait_exc
        self.wait_calls: list[tuple[str, int]] = []
        self.inner_text_calls: list[int] = []

    @property
    def first(self) -> "_FakeLocator":
        return self

    def wait_for(self, *, state: str, timeout: int) -> None:
        self.wait_calls.append((state, timeout))
        if self.wait_exc is not None:
            raise self.wait_exc

    def inner_text(self, *, timeout: int) -> str:
        self.inner_text_calls.append(timeout)
        return self.text


class _FakePage:
    def __init__(self, locators: dict[str, _FakeLocator]) -> None:
        self._locators = locators
        self.seen_selectors: list[str] = []

    def locator(self, selector: str) -> _FakeLocator:
        self.seen_selectors.append(selector)
        return self._locators[selector]


class _FakeLaunchPage:
    def __init__(self) -> None:
        self.goto_calls: list[tuple[str, str, int]] = []
        self.locator_calls: list[str] = []

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))

    def locator(self, selector: str) -> _FakeLocator:
        self.locator_calls.append(selector)
        raise AssertionError("launch should not probe selectors")


class _FakeContext:
    def __init__(self, page: _FakeLaunchPage) -> None:
        self.page = page
        self.new_page_calls = 0

    def new_page(self) -> _FakeLaunchPage:
        self.new_page_calls += 1
        return self.page


def test_open_symbol_page_only_waits_for_domcontentloaded() -> None:
    page = _FakeLaunchPage()
    context = _FakeContext(page)

    result = TradingViewInternals._open_symbol_page(context, "https://example.test/symbol")

    assert result is page
    assert context.new_page_calls == 1
    assert page.goto_calls == [
        ("https://example.test/symbol", "domcontentloaded", _NAV_TIMEOUT_MS)
    ]
    assert page.locator_calls == []


def test_read_price_text_prefers_primary_selector() -> None:
    primary = _FakeLocator(text="756.12")
    fallback = _FakeLocator(text="755.00")
    page = _FakePage({
        _CSS_PRICE_PRIMARY: primary,
        _CSS_PRICE_FALLBACK: fallback,
    })

    result = TradingViewInternals._read_price_text(page)

    assert result == "756.12"
    assert page.seen_selectors == [_CSS_PRICE_PRIMARY]
    assert primary.wait_calls
    assert fallback.wait_calls == []


def test_read_price_text_falls_back_to_legacy_selector() -> None:
    primary_exc = RuntimeError(
        "Page.wait_for_selector: Timeout 25000ms exceeded.\nCall log:\n  - waiting"
    )
    primary = _FakeLocator(wait_exc=primary_exc)
    fallback = _FakeLocator(text="754.84")
    page = _FakePage({
        _CSS_PRICE_PRIMARY: primary,
        _CSS_PRICE_FALLBACK: fallback,
    })

    result = TradingViewInternals._read_price_text(page)

    assert result == "754.84"
    assert page.seen_selectors == [_CSS_PRICE_PRIMARY, _CSS_PRICE_FALLBACK]
    assert primary.wait_calls
    assert fallback.wait_calls


def test_format_scrape_error_keeps_only_first_line() -> None:
    exc = RuntimeError(
        "Page.wait_for_selector: Timeout 25000ms exceeded.\nCall log:\n  - waiting"
    )

    assert TradingViewInternals._format_scrape_error(exc) == (
        "Page.wait_for_selector: Timeout 25000ms exceeded."
    )
