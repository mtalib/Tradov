#!/usr/bin/env python3
"""
Tests for SpyderU46_SecretsManager

Covers: normalisation, env-var resolution, set/delete, get with default,
required=True error path, and singleton behaviour.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderU_Utilities.SpyderU46_SecretsManager import SecretsManager, get_secrets


class TestSecretsManagerNormalise(unittest.TestCase):
    def setUp(self):
        self.sm = SecretsManager()

    def test_live_only_api_omits_sandbox_token_accessor(self):
        self.assertFalse(hasattr(SecretsManager, "tradier_sandbox_token"))

    def test_get_returns_none_for_unknown_key(self):
        result = self.sm.get("DEFINITELY_NOT_A_REAL_SECRET_XYZ_99")
        self.assertIsNone(result)

    def test_get_returns_default_when_missing(self):
        result = self.sm.get("DEFINITELY_NOT_A_REAL_SECRET_XYZ_99", default="fallback")
        self.assertEqual(result, "fallback")

    def test_required_raises_when_missing(self):
        with self.assertRaises(KeyError):
            self.sm.get("DEFINITELY_NOT_A_REAL_SECRET_XYZ_99", required=True)

    def test_key_normalisation_upper_snake(self):
        """Keys with mixed casing / dashes should resolve identically."""
        os.environ["SPYDER_SECRET_NORM_TEST"] = "hello"
        try:
            self.assertEqual(self.sm.get("norm-test"), "hello")
            self.assertEqual(self.sm.get("NORM_TEST"), "hello")
            self.assertEqual(self.sm.get("norm_test"), "hello")
        finally:
            del os.environ["SPYDER_SECRET_NORM_TEST"]

    def test_env_var_plain_key_resolution(self):
        """Plain env vars (without SPYDER_SECRET_ prefix) are also resolved."""
        os.environ["PLAIN_SECRET_KEY_TEST"] = "plain_value"
        try:
            result = self.sm.get("PLAIN_SECRET_KEY_TEST")
            self.assertEqual(result, "plain_value")
        finally:
            del os.environ["PLAIN_SECRET_KEY_TEST"]

    def test_prefixed_env_var_takes_priority_over_plain(self):
        os.environ["SPYDER_SECRET_PRIO_TEST"] = "prefixed"
        os.environ["PRIO_TEST"] = "plain"
        try:
            self.assertEqual(self.sm.get("PRIO_TEST"), "prefixed")
        finally:
            del os.environ["SPYDER_SECRET_PRIO_TEST"]
            del os.environ["PRIO_TEST"]


class TestSecretsManagerSetDelete(unittest.TestCase):
    def setUp(self):
        # Use a temp in-memory-only secrets manager (no file writes to ~/.spyder)
        self.sm = SecretsManager(secrets_file=None)

    def test_set_and_get_roundtrip(self):
        self.sm.set("TEST_SET_KEY", "test_value")
        self.assertEqual(self.sm.get("TEST_SET_KEY"), "test_value")

    def test_delete_removes_key(self):
        self.sm.set("DELETE_ME", "value")
        self.sm.delete("DELETE_ME")
        self.assertIsNone(self.sm.get("DELETE_ME"))

    def test_delete_nonexistent_key_is_silent(self):
        self.sm.delete("NEVER_SET_THIS_KEY")  # must not raise


class TestGetSecretsSingleton(unittest.TestCase):
    def test_returns_same_instance(self):
        sm1 = get_secrets()
        sm2 = get_secrets()
        self.assertIs(sm1, sm2)

    def test_instance_is_secrets_manager(self):
        self.assertIsInstance(get_secrets(), SecretsManager)


if __name__ == "__main__":
    unittest.main()
