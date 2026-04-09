#!/usr/bin/env python3
"""
Tests for SpyderJ03_WebhookNotifier

Covers: Severity enum, WebhookField dataclass, WebhookNotifier construction,
send_* methods with no URLs configured (must not raise), and singleton get_notifier().
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderJ_Alerts.SpyderJ03_WebhookNotifier import (
    Severity,
    WebhookField,
    WebhookNotifier,
    get_notifier,
)


class TestSeverityEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Severity.INFO.value, "info")
        self.assertEqual(Severity.WARNING.value, "warning")
        self.assertEqual(Severity.CRITICAL.value, "critical")

    def test_is_str_enum(self):
        self.assertIsInstance(Severity.INFO, str)


class TestWebhookField(unittest.TestCase):
    def test_construction(self):
        f = WebhookField(title="Symbol", value="SPY")
        self.assertEqual(f.title, "Symbol")
        self.assertEqual(f.value, "SPY")


class TestWebhookNotifierNoUrls(unittest.TestCase):
    """When no webhook URLs are configured, all send methods must be silent."""

    def setUp(self):
        # Ensure no webhook env vars are set
        for env_key in ("SPYDER_SLACK_WEBHOOK_URL", "SPYDER_TEAMS_WEBHOOK_URL",
                        "SPYDER_DISCORD_WEBHOOK_URL"):
            os.environ.pop(env_key, None)
        self.notifier = WebhookNotifier()

    def test_send_does_not_raise(self):
        self.notifier.send(
            title="Test Alert",
            message="This is a test",
            severity=Severity.INFO,
        )

    def test_send_with_fields_does_not_raise(self):
        self.notifier.send(
            title="Risk Breach",
            message="Delta limit exceeded",
            severity=Severity.CRITICAL,
            fields=[WebhookField("Symbol", "SPY"), WebhookField("Delta", "0.85")],
        )

    def test_send_warning_does_not_raise(self):
        self.notifier.send(
            message="Margin warning",
            severity=Severity.WARNING,
        )

    def test_configured_platforms_empty_when_no_urls(self):
        platforms = self.notifier.configured_platforms()
        self.assertEqual(platforms, [])


class TestWebhookNotifierWithSlack(unittest.TestCase):
    """With a fake Slack URL configured, send() should attempt delivery
    but log the failure without raising."""

    def setUp(self):
        os.environ["SPYDER_SLACK_WEBHOOK_URL"] = "http://localhost:0/fake_slack"
        self.notifier = WebhookNotifier()

    def tearDown(self):
        os.environ.pop("SPYDER_SLACK_WEBHOOK_URL", None)

    def test_send_with_invalid_url_does_not_raise(self):
        self.notifier.send(
            title="Test",
            message="Message body",
            severity=Severity.INFO,
        )

    def test_slack_in_configured_platforms(self):
        platforms = self.notifier.configured_platforms()
        self.assertIn("slack", platforms)


class TestGetNotifierSingleton(unittest.TestCase):
    def test_same_instance(self):
        n1 = get_notifier()
        n2 = get_notifier()
        self.assertIs(n1, n2)

    def test_is_notifier_type(self):
        self.assertIsInstance(get_notifier(), WebhookNotifier)


if __name__ == "__main__":
    unittest.main()
