"""
Spyder Trading System - Main Package

A comprehensive algorithmic trading system for automated trading strategies,
risk management, portfolio optimization, and market analysis.

This package contains all core modules organized by functionality:
- SpyderA_Core: Core trading engine and configuration
- SpyderB_Broker: Broker connectivity and order management
- SpyderC_MarketData: Market data feeds and processing
- SpyderD_Strategies: Trading strategies implementation
- SpyderE_Risk: Risk management and position sizing
- SpyderF_Analysis: Technical and fundamental analysis
- SpyderG_GUI: Graphical user interface components
- SpyderH_Storage: Data storage and database operations
- SpyderI_Integration: External system integrations
- SpyderJ_Alerts: Alert and notification system
- SpyderK_Reports: Reporting and analytics
- SpyderL_ML: Machine learning models
- SpyderM_Monitoring: System monitoring and health checks
- SpyderN_OptionsAnalytics: Options analysis and Greeks
- SpyderO_TradingIntelligence: Trading intelligence and insights
- SpyderP_PortfolioMgmt: Portfolio management
- SpyderQ_Scripts: Utility scripts and tools
- SpyderR_Runtime: Runtime management and orchestration
- SpyderS_Signals: Signal generation and processing
- SpyderT_Testing: Testing utilities and frameworks
- SpyderU_Utilities: Common utilities and helpers
- SpyderV_QuantModels: Quantitative models and analytics
- SpyderX_Agents: AI agents and automation (on-demand, stateless)
- SpyderY_AutoAgents: Autonomous LLM-powered agents (24/7, persistent)
- SpyderZ_Communication: Communication protocols and APIs
"""

import sys as _sys
import importlib.abc as _abc
import importlib.machinery as _machinery

# ==============================================================================
# IMPORT ALIAS HOOK — prevents double-loading of Spyder sub-packages
#
# Many modules use "from Spyder.SpyderX.Module import Y" while others use the
# short form "from SpyderX.Module import Y" (when Spyder/ is on sys.path).
# Without this hook Python loads the same package __init__.py TWICE under two
# different sys.modules keys, doubling the import cost for every dependent
# library (numpy, pandas, scipy, etc.).
#
# This MetaPathFinder redirects the long form to the already-loaded short form
# (and vice versa), so the module code executes exactly once.
# ==============================================================================

class _SpyderAliasImporter(_abc.MetaPathFinder, _abc.Loader):
    """Bidirectional alias between 'Spyder.SpyderX.Y' and 'SpyderX.Y'."""

    @staticmethod
    def _is_short_spyder(name: str) -> bool:
        """Return True for short-form Spyder sub-package names like 'SpyderU_Utilities'."""
        # Must start with 'Spyder' + an uppercase letter (not a dot or end-of-string)
        return len(name) > 6 and name[:6] == "Spyder" and name[6:7].isupper()

    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        # Long-form → short-form: 'Spyder.SpyderX[.Y]' → 'SpyderX[.Y]'
        if fullname.startswith("Spyder.Spyder"):
            short = fullname[len("Spyder."):]  # e.g. 'SpyderU_Utilities.SpyderU01_Logger'
            if short in _sys.modules:
                return _machinery.ModuleSpec(fullname, self)

        # Short-form → long-form: 'SpyderX[.Y]' → 'Spyder.SpyderX[.Y]'
        elif self._is_short_spyder(fullname):
            long = "Spyder." + fullname
            if long in _sys.modules:
                return _machinery.ModuleSpec(fullname, self)

        return None

    def create_module(self, spec: _machinery.ModuleSpec):  # type: ignore[override]
        name = spec.name
        if name.startswith("Spyder.Spyder"):
            short = name[len("Spyder."):]
            return _sys.modules.get(short)
        else:
            long = "Spyder." + name
            return _sys.modules.get(long)

    def exec_module(self, module) -> None:  # type: ignore[override]
        pass  # Already fully initialised — nothing to execute


_sys.meta_path.insert(0, _SpyderAliasImporter())


__version__ = "0.0.0"
__author__ = "Spyder Trading System"
__all__: list[str] = []
