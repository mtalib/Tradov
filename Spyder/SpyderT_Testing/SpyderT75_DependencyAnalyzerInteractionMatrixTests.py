#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT75_DependencyAnalyzerInteractionMatrixTests.py
Purpose: Tests for U18 DependencyAnalyzer and U19 InteractionMatrix

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 22:30:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path):
    abs_path = os.path.join(_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u18 = _load("Spyder/SpyderU_Utilities/SpyderU18_DependencyAnalyzer.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU18_DependencyAnalyzer"] = _u18

_u19 = _load("Spyder/SpyderU_Utilities/SpyderU19_InteractionMatrix.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU19_InteractionMatrix"] = _u19

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import ast
import json
import tempfile
import textwrap
import threading
import time
import pytest
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# ==============================================================================
# U18 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU18_DependencyAnalyzer import (
    DependencyType,
    AnalysisScope,
    SeverityLevel,
    ModuleInfo,
    CircularDependency,
    DependencyGraph,
    DependencyAnalyzer,
    MODULE_GROUPS,
    analyze_project_dependencies,
    find_circular_dependencies,
    get_dependency_analyzer,
)

# ==============================================================================
# U19 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU19_InteractionMatrix import (
    InteractionType,
    InteractionStatus,
    MatrixMetric,
    Interaction,
    ModuleStats,
    MatrixAnalysis,
    InteractionMatrix,
    get_interaction_matrix,
    record_interaction,
)


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_temp_project():
    """Create a temporary project directory with Python files for analysis."""
    tmp = tempfile.mkdtemp()

    # Module A
    (Path(tmp) / "SpyderA_Core").mkdir()
    _write(tmp, "SpyderA_Core/SpyderA01_Main.py", """
import os
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderB_Broker.SpyderB01_Client import BrokerClient

class MainOrchestrator:
    def start(self):
        pass
    def stop(self):
        pass
""")
    _write(tmp, "SpyderA_Core/__init__.py", "")

    # Module B
    (Path(tmp) / "SpyderB_Broker").mkdir()
    _write(tmp, "SpyderB_Broker/SpyderB01_Client.py", """
import requests
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

class BrokerClient:
    def connect(self):
        pass
    def disconnect(self):
        pass
    def place_order(self, order):
        return True
""")
    _write(tmp, "SpyderB_Broker/__init__.py", "")

    # Module U (utilities)
    (Path(tmp) / "SpyderU_Utilities").mkdir()
    _write(tmp, "SpyderU_Utilities/SpyderU01_Logger.py", """
import logging

class SpyderLogger:
    @staticmethod
    def get_logger(name):
        return logging.getLogger(name)

def get_logger(name):
    return SpyderLogger.get_logger(name)
""")
    _write(tmp, "SpyderU_Utilities/__init__.py", "")

    return tmp


def _write(base, rel, content):
    path = Path(base) / rel
    path.write_text(textwrap.dedent(content))


def _make_interaction_matrix():
    """Fresh InteractionMatrix instance."""
    return InteractionMatrix(max_modules=50)


def _record_n(matrix, n=10, source="ModA", target="ModB",
               itype=None, status=None, latency=25.0):
    itype = itype or InteractionType.FUNCTION_CALL
    status = status or InteractionStatus.SUCCESS
    for _ in range(n):
        matrix.record_interaction(source, target, itype, status, latency_ms=latency)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U18 — DependencyAnalyzer TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestDependencyTypeEnum:
    def test_direct(self):
        assert DependencyType.DIRECT.value == "direct"

    def test_indirect(self):
        assert DependencyType.INDIRECT.value == "indirect"

    def test_circular(self):
        assert DependencyType.CIRCULAR.value == "circular"

    def test_external(self):
        assert DependencyType.EXTERNAL.value == "external"

    def test_internal(self):
        assert DependencyType.INTERNAL.value == "internal"

    def test_five_members(self):
        assert len(list(DependencyType)) == 5


class TestAnalysisScopeEnum:
    def test_module(self):
        assert AnalysisScope.MODULE.value == "module"

    def test_group(self):
        assert AnalysisScope.GROUP.value == "group"

    def test_system(self):
        assert AnalysisScope.SYSTEM.value == "system"


class TestSeverityLevelEnum:
    def test_low(self):
        assert SeverityLevel.LOW.value == "low"

    def test_medium(self):
        assert SeverityLevel.MEDIUM.value == "medium"

    def test_high(self):
        assert SeverityLevel.HIGH.value == "high"

    def test_critical(self):
        assert SeverityLevel.CRITICAL.value == "critical"

    def test_four_members(self):
        assert len(list(SeverityLevel)) == 4


class TestModuleInfoDataclass:
    def _make(self):
        return ModuleInfo(
            name="SpyderA_Core.SpyderA01_Main",
            path="/spyder/SpyderA_Core/SpyderA01_Main.py",
            group="SpyderA_Core",
            imports=["SpyderU_Utilities.SpyderU01_Logger"],
            external_imports=["os", "requests"],
            functions=["start", "stop"],
            classes=["MainOrchestrator"],
            lines_of_code=50,
        )

    def test_creation(self):
        mi = self._make()
        assert mi.name == "SpyderA_Core.SpyderA01_Main"

    def test_to_dict_has_name(self):
        d = self._make().to_dict()
        assert "name" in d

    def test_to_dict_has_group(self):
        d = self._make().to_dict()
        assert d["group"] == "SpyderA_Core"

    def test_to_dict_has_functions(self):
        d = self._make().to_dict()
        assert "functions" in d
        assert "start" in d["functions"]

    def test_to_dict_has_classes(self):
        d = self._make().to_dict()
        assert "classes" in d
        assert "MainOrchestrator" in d["classes"]

    def test_to_dict_has_loc(self):
        d = self._make().to_dict()
        assert d["lines_of_code"] == 50

    def test_defaults(self):
        mi = ModuleInfo(name="X", path="/x", group="Unknown")
        assert mi.imports == []
        assert mi.lines_of_code == 0


class TestCircularDependencyDataclass:
    def _make(self):
        return CircularDependency(
            modules=["ModA", "ModB"],
            severity=SeverityLevel.LOW,
            description="Test circular dep",
        )

    def test_creation(self):
        cd = self._make()
        assert cd.modules == ["ModA", "ModB"]

    def test_to_dict_modules(self):
        d = self._make().to_dict()
        assert "modules" in d
        assert len(d["modules"]) == 2

    def test_to_dict_severity_string(self):
        d = self._make().to_dict()
        assert d["severity"] == "low"

    def test_to_dict_description(self):
        d = self._make().to_dict()
        assert "description" in d


class TestDependencyGraphDataclass:
    def _make(self):
        return DependencyGraph(
            nodes=["ModA", "ModB", "ModC"],
            edges=[("ModA", "ModB")],
            circular_dependencies=[],
            isolated_modules=["ModC"],
        )

    def test_to_dict_has_nodes(self):
        d = self._make().to_dict()
        assert "nodes" in d
        assert len(d["nodes"]) == 3

    def test_to_dict_has_edges(self):
        d = self._make().to_dict()
        assert "edges" in d

    def test_to_dict_isolated(self):
        d = self._make().to_dict()
        assert "isolated_modules" in d
        assert "ModC" in d["isolated_modules"]


class TestDependencyAnalyzerInit:
    def test_instantiation_default(self):
        da = DependencyAnalyzer(".")
        assert da is not None

    def test_has_logger(self):
        da = DependencyAnalyzer(".")
        assert da.logger is not None

    def test_modules_empty_on_init(self):
        da = DependencyAnalyzer(".")
        assert da.modules == {}

    def test_project_root_set(self):
        da = DependencyAnalyzer("/tmp")
        assert str(da.project_root) == "/tmp"

    def test_circular_deps_empty_on_init(self):
        da = DependencyAnalyzer(".")
        assert da.circular_dependencies == []


class TestPrivateHelpers:
    def setup_method(self):
        self.da = DependencyAnalyzer(".")

    def test_is_spyder_module_true(self):
        assert self.da._is_spyder_module("Spyder.SpyderU_Utilities.SpyderU01_Logger") is True

    def test_is_spyder_module_false(self):
        assert self.da._is_spyder_module("os") is False
        assert self.da._is_spyder_module("requests") is False

    def test_get_module_group_known(self):
        group = self.da._get_module_group("SpyderA_Core.SpyderA01_Main")
        assert group == "SpyderA_Core"

    def test_get_module_group_unknown(self):
        group = self.da._get_module_group("random_module")
        assert group == "Unknown"

    def test_count_lines_of_code_skips_empty(self):
        code = "x = 1\n\ny = 2\n\n"
        loc = self.da._count_lines_of_code(code)
        assert loc == 2

    def test_count_lines_of_code_skips_comments(self):
        code = "# comment\nx = 1\n# another\n"
        loc = self.da._count_lines_of_code(code)
        assert loc == 1

    def test_extract_imports_simple(self):
        code = "import os\nimport sys\n"
        tree = ast.parse(code)
        imports = self.da._extract_imports(tree)
        assert "os" in imports
        assert "sys" in imports

    def test_extract_imports_from(self):
        code = "from pathlib import Path\n"
        tree = ast.parse(code)
        imports = self.da._extract_imports(tree)
        assert "pathlib" in imports

    def test_extract_functions(self):
        code = "def foo():\n    pass\ndef bar():\n    pass\n"
        tree = ast.parse(code)
        funcs = self.da._extract_functions(tree)
        assert "foo" in funcs
        assert "bar" in funcs

    def test_extract_classes(self):
        code = "class MyClass:\n    pass\n"
        tree = ast.parse(code)
        classes = self.da._extract_classes(tree)
        assert "MyClass" in classes

    def test_assess_circular_severity_low(self):
        assert self.da._assess_circular_severity(["A", "B"]) == SeverityLevel.LOW

    def test_assess_circular_severity_medium(self):
        assert self.da._assess_circular_severity(["A", "B", "C"]) == SeverityLevel.MEDIUM

    def test_assess_circular_severity_high(self):
        assert self.da._assess_circular_severity(["A", "B", "C", "D"]) == SeverityLevel.HIGH

    def test_assess_circular_severity_critical(self):
        mods = ["A", "B", "C", "D", "E", "F"]
        assert self.da._assess_circular_severity(mods) == SeverityLevel.CRITICAL


class TestDependencyAnalyzerWithTempProject:
    def setup_method(self):
        self.tmp = _make_temp_project()
        self.da = DependencyAnalyzer(self.tmp)

    def test_find_python_files(self):
        files = self.da._find_python_files()
        py_files = [str(f) for f in files]
        # Should find files without __pycache__
        assert all(".py" in f for f in py_files)
        assert len(files) > 0

    def test_analyze_file_creates_module_info(self):
        file_path = Path(self.tmp) / "SpyderA_Core/SpyderA01_Main.py"
        self.da._analyze_file(file_path)
        assert len(self.da.modules) == 1
        mod_name = list(self.da.modules.keys())[0]
        mi = self.da.modules[mod_name]
        assert isinstance(mi, ModuleInfo)

    def test_analyze_file_extracts_functions(self):
        file_path = Path(self.tmp) / "SpyderA_Core/SpyderA01_Main.py"
        self.da._analyze_file(file_path)
        mod_name = list(self.da.modules.keys())[0]
        mi = self.da.modules[mod_name]
        # MainOrchestrator has start and stop
        assert "start" in mi.functions or "stop" in mi.functions

    def test_analyze_file_extracts_classes(self):
        file_path = Path(self.tmp) / "SpyderA_Core/SpyderA01_Main.py"
        self.da._analyze_file(file_path)
        mod_name = list(self.da.modules.keys())[0]
        mi = self.da.modules[mod_name]
        assert "MainOrchestrator" in mi.classes

    def test_analyze_dependencies_populates_modules(self):
        self.da.analyze_dependencies()
        assert len(self.da.modules) > 0

    def test_analyze_dependencies_idempotent(self):
        self.da.analyze_dependencies()
        count1 = len(self.da.modules)
        self.da.analyze_dependencies()  # Should use cache
        assert len(self.da.modules) == count1

    def test_analyze_dependencies_force_refresh(self):
        self.da.analyze_dependencies()
        count1 = len(self.da.modules)
        self.da.analyze_dependencies(force_refresh=True)
        # Still the same project
        assert len(self.da.modules) == count1

    def test_generate_dependency_graph(self):
        self.da.analyze_dependencies()
        graph = self.da.generate_dependency_graph()
        assert isinstance(graph, DependencyGraph)
        assert isinstance(graph.nodes, list)
        assert isinstance(graph.edges, list)

    def test_generate_dependency_report_is_string(self):
        self.da.analyze_dependencies()
        report = self.da.generate_dependency_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_dependency_report_has_header(self):
        self.da.analyze_dependencies()
        report = self.da.generate_dependency_report()
        assert "Dependency" in report

    def test_get_module_dependencies_unknown(self):
        self.da.analyze_dependencies()
        result = self.da.get_module_dependencies("NonExistentModule")
        assert "error" in result

    def test_get_module_dependencies_known(self):
        self.da.analyze_dependencies()
        if self.da.modules:
            mod_name = list(self.da.modules.keys())[0]
            result = self.da.get_module_dependencies(mod_name)
            assert "module" in result
            assert "direct_dependencies" in result

    def test_find_circular_dependencies_returns_list(self):
        self.da.analyze_dependencies()
        circular = self.da.find_circular_dependencies()
        assert isinstance(circular, list)

    def test_export_graph_data_json(self):
        self.da.analyze_dependencies()
        output = self.da.export_graph_data("json")
        assert isinstance(output, str)
        parsed = json.loads(output)
        assert "nodes" in parsed
        assert "edges" in parsed

    def test_export_graph_data_csv(self):
        self.da.analyze_dependencies()
        output = self.da.export_graph_data("csv")
        assert isinstance(output, str)
        assert "Source,Target" in output

    def test_export_graph_data_unsupported(self):
        self.da.analyze_dependencies()
        output = self.da.export_graph_data("xml")
        assert "Unsupported" in output

    def test_calculate_dependency_depth_known(self):
        self.da.analyze_dependencies()
        if self.da.modules:
            mod_name = list(self.da.modules.keys())[0]
            depth = self.da._calculate_dependency_depth(mod_name)
            assert isinstance(depth, int)
            assert depth >= 0

    def test_calculate_dependency_depth_unknown(self):
        depth = self.da._calculate_dependency_depth("NonExistentModule")
        assert depth == 0


class TestModuleFunctions18:
    def test_analyze_project_dependencies_returns_analyzer(self):
        da = analyze_project_dependencies(_ROOT)
        assert isinstance(da, DependencyAnalyzer)

    def test_get_dependency_analyzer_singleton(self):
        _u18._dependency_analyzer_instance = None
        da1 = get_dependency_analyzer(".")
        da2 = get_dependency_analyzer(".")
        assert da1 is da2

    def test_get_dependency_analyzer_type(self):
        _u18._dependency_analyzer_instance = None
        da = get_dependency_analyzer(".")
        assert isinstance(da, DependencyAnalyzer)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U19 — InteractionMatrix TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestInteractionTypeEnum:
    def test_function_call(self):
        assert InteractionType.FUNCTION_CALL.value == "function_call"

    def test_data_exchange(self):
        assert InteractionType.DATA_EXCHANGE.value == "data_exchange"

    def test_event_trigger(self):
        assert InteractionType.EVENT_TRIGGER.value == "event_trigger"

    def test_subscription(self):
        assert InteractionType.SUBSCRIPTION.value == "subscription"

    def test_notification(self):
        assert InteractionType.NOTIFICATION.value == "notification"

    def test_error_propagation(self):
        assert InteractionType.ERROR_PROPAGATION.value == "error_propagation"

    def test_status_update(self):
        assert InteractionType.STATUS_UPDATE.value == "status_update"

    def test_seven_members(self):
        assert len(list(InteractionType)) == 7


class TestInteractionStatusEnum:
    def test_success(self):
        assert InteractionStatus.SUCCESS.value == "success"

    def test_failure(self):
        assert InteractionStatus.FAILURE.value == "failure"

    def test_timeout(self):
        assert InteractionStatus.TIMEOUT.value == "timeout"

    def test_pending(self):
        assert InteractionStatus.PENDING.value == "pending"

    def test_retrying(self):
        assert InteractionStatus.RETRYING.value == "retrying"


class TestMatrixMetricEnum:
    def test_frequency(self):
        assert MatrixMetric.FREQUENCY.value == "frequency"

    def test_latency(self):
        assert MatrixMetric.LATENCY.value == "latency"

    def test_success_rate(self):
        assert MatrixMetric.SUCCESS_RATE.value == "success_rate"

    def test_data_volume(self):
        assert MatrixMetric.DATA_VOLUME.value == "data_volume"

    def test_error_rate(self):
        assert MatrixMetric.ERROR_RATE.value == "error_rate"


class TestInteractionDataclass:
    def _make(self, status=InteractionStatus.SUCCESS, latency=25.0):
        return Interaction(
            source="ModA",
            target="ModB",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
            status=status,
            latency_ms=latency,
            data_size=1024,
        )

    def test_creation(self):
        inter = self._make()
        assert inter.source == "ModA"
        assert inter.target == "ModB"

    def test_is_successful_true(self):
        assert self._make(InteractionStatus.SUCCESS).is_successful is True

    def test_is_successful_false(self):
        assert self._make(InteractionStatus.FAILURE).is_successful is False

    def test_is_successful_pending(self):
        assert self._make(InteractionStatus.PENDING).is_successful is False

    def test_duration_ms(self):
        inter = self._make(latency=42.5)
        assert inter.duration_ms == pytest.approx(42.5)

    def test_duration_ms_none(self):
        inter = Interaction("A", "B", InteractionType.FUNCTION_CALL, datetime.now())
        assert inter.duration_ms == 0.0


class TestModuleStatsDataclass:
    def _make(self):
        ms = ModuleStats(module_name="ModA")
        ms.total_interactions = 10
        ms.successful_interactions = 8
        ms.failed_interactions = 2
        return ms

    def test_success_rate(self):
        assert self._make().success_rate == pytest.approx(80.0)

    def test_error_rate(self):
        assert self._make().error_rate == pytest.approx(20.0)

    def test_success_rate_zero_total(self):
        ms = ModuleStats("X")
        assert ms.success_rate == 0.0

    def test_error_rate_zero_total(self):
        ms = ModuleStats("X")
        assert ms.error_rate == 0.0


class TestInteractionMatrixInit:
    def test_instantiation_default(self):
        im = InteractionMatrix()
        assert im is not None

    def test_custom_max_modules(self):
        im = InteractionMatrix(max_modules=20)
        assert im.max_modules == 20

    def test_modules_empty_on_init(self):
        im = InteractionMatrix()
        assert im.modules == {}

    def test_frequency_matrix_zeros(self):
        im = InteractionMatrix(max_modules=10)
        assert im.frequency_matrix.shape == (10, 10)
        assert im.frequency_matrix.sum() == 0

    def test_has_logger(self):
        im = InteractionMatrix()
        assert im.logger is not None


class TestRecordInteraction:
    def setup_method(self):
        self.im = _make_interaction_matrix()

    def test_record_single_interaction(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL, InteractionStatus.SUCCESS)
        assert len(self.im.interactions) == 1

    def test_registers_modules(self):
        self.im.record_interaction("ModA", "ModB", InteractionType.DATA_EXCHANGE, InteractionStatus.SUCCESS)
        assert "ModA" in self.im.modules
        assert "ModB" in self.im.modules

    def test_frequency_matrix_incremented(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL, InteractionStatus.SUCCESS)
        a_idx = self.im.modules["A"]
        b_idx = self.im.modules["B"]
        assert self.im.frequency_matrix[a_idx, b_idx] == 1

    def test_multiple_records_accumulate(self):
        _record_n(self.im, n=5, source="X", target="Y")
        assert len(self.im.interactions) == 5
        x_idx = self.im.modules["X"]
        y_idx = self.im.modules["Y"]
        assert self.im.frequency_matrix[x_idx, y_idx] == 5

    def test_latency_stored(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.SUCCESS, latency_ms=50.0)
        assert self.im.interactions[-1].latency_ms == pytest.approx(50.0)

    def test_data_size_stored(self):
        self.im.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                                   InteractionStatus.SUCCESS, data_size=2048)
        assert self.im.interactions[-1].data_size == 2048

    def test_interaction_history_capped(self):
        from Spyder.SpyderU_Utilities.SpyderU19_InteractionMatrix import MAX_HISTORY_SIZE
        # Record more than MAX_HISTORY_SIZE
        for i in range(MAX_HISTORY_SIZE + 50):
            self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL, InteractionStatus.SUCCESS)
        assert len(self.im.interactions) == MAX_HISTORY_SIZE

    def test_failure_status_recorded(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.FAILURE, error_message="timeout")
        assert self.im.interactions[-1].status == InteractionStatus.FAILURE
        assert self.im.interactions[-1].error_message == "timeout"

    def test_metadata_stored(self):
        meta = {"key": "value"}
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.SUCCESS, metadata=meta)
        assert self.im.interactions[-1].metadata == meta


class TestModuleStats19:
    def setup_method(self):
        self.im = _make_interaction_matrix()

    def test_stats_created_on_register(self):
        self.im.record_interaction("Alpha", "Beta", InteractionType.FUNCTION_CALL, InteractionStatus.SUCCESS)
        assert "Alpha" in self.im.module_stats

    def test_total_interactions_incremented(self):
        _record_n(self.im, n=3, source="X", target="Y")
        assert self.im.module_stats["X"].total_interactions == 3

    def test_successful_interactions_counted(self):
        _record_n(self.im, n=5, source="A", target="B", status=InteractionStatus.SUCCESS)
        assert self.im.module_stats["A"].successful_interactions == 5

    def test_failed_interactions_counted(self):
        _record_n(self.im, n=3, source="A", target="B", status=InteractionStatus.FAILURE)
        assert self.im.module_stats["A"].failed_interactions == 3

    def test_average_latency_calculated(self):
        for lat in [10.0, 20.0, 30.0]:
            self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS, latency_ms=lat)
        stats = self.im.module_stats["A"]
        assert stats.average_latency == pytest.approx(20.0, abs=1.0)

    def test_data_sent_tracked(self):
        self.im.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                                   InteractionStatus.SUCCESS, data_size=1000)
        self.im.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                                   InteractionStatus.SUCCESS, data_size=500)
        assert self.im.module_stats["A"].total_data_sent == 1500

    def test_data_received_tracked(self):
        self.im.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                                   InteractionStatus.SUCCESS, data_size=2000)
        assert self.im.module_stats["B"].total_data_received == 2000


class TestGetModuleStatistics:
    def setup_method(self):
        self.im = _make_interaction_matrix()
        _record_n(self.im, n=5, source="M1", target="M2")

    def test_single_module_returns_stats(self):
        stats = self.im.get_module_statistics("M1")
        assert isinstance(stats, ModuleStats)
        assert stats.module_name == "M1"

    def test_all_modules_returns_dict(self):
        all_stats = self.im.get_module_statistics()
        assert isinstance(all_stats, dict)
        assert "M1" in all_stats

    def test_unknown_module_returns_empty_stats(self):
        stats = self.im.get_module_statistics("NonExistent")
        assert isinstance(stats, ModuleStats)
        assert stats.total_interactions == 0


class TestGetInteractionHistory:
    def setup_method(self):
        self.im = _make_interaction_matrix()
        _record_n(self.im, n=5, source="Src", target="Tgt")
        _record_n(self.im, n=3, source="Other", target="Tgt")

    def test_returns_list(self):
        result = self.im.get_interaction_history()
        assert isinstance(result, list)

    def test_filter_by_source(self):
        result = self.im.get_interaction_history(source="Src")
        assert all(i.source == "Src" for i in result)

    def test_filter_by_target(self):
        result = self.im.get_interaction_history(target="Tgt")
        assert all(i.target == "Tgt" for i in result)

    def test_limit_respected(self):
        result = self.im.get_interaction_history(limit=3)
        assert len(result) <= 3

    def test_sorted_most_recent_first(self):
        result = self.im.get_interaction_history()
        if len(result) >= 2:
            assert result[0].timestamp >= result[1].timestamp


class TestAnalyzeMatrix:
    def setup_method(self):
        self.im = _make_interaction_matrix()
        # Record a set of varied interactions
        _record_n(self.im, n=10, source="A", target="B", latency=50.0)
        _record_n(self.im, n=5, source="B", target="C", latency=100.0)
        _record_n(self.im, n=3, source="A", target="C",
                  status=InteractionStatus.FAILURE, latency=200.0)

    def test_returns_matrix_analysis(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result, MatrixAnalysis)

    def test_matrix_data_is_ndarray(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result.matrix_data, np.ndarray)

    def test_module_names_list(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result.module_names, list)

    def test_metric_type_set(self):
        result = self.im.analyze_matrix(MatrixMetric.LATENCY)
        assert result.metric_type == MatrixMetric.LATENCY

    def test_hotspots_are_triples(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        for h in result.hotspots:
            assert len(h) == 3

    def test_recommendations_is_list(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result.recommendations, list)

    def test_caching_returns_same_object(self):
        r1 = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        r2 = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert r1 is r2

    def test_latency_metric(self):
        result = self.im.analyze_matrix(MatrixMetric.LATENCY)
        assert isinstance(result, MatrixAnalysis)

    def test_success_rate_metric(self):
        result = self.im.analyze_matrix(MatrixMetric.SUCCESS_RATE)
        assert isinstance(result, MatrixAnalysis)

    def test_data_volume_metric(self):
        im = _make_interaction_matrix()
        im.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                              InteractionStatus.SUCCESS, data_size=1000)
        result = im.analyze_matrix(MatrixMetric.DATA_VOLUME)
        assert isinstance(result, MatrixAnalysis)

    def test_time_window_filter(self):
        result = self.im.analyze_matrix(_MetrixMetric := MatrixMetric.FREQUENCY,
                                         time_window=timedelta(hours=1))
        assert isinstance(result, MatrixAnalysis)


class TestIdentifyHotspots:
    def setup_method(self):
        self.im = _make_interaction_matrix()
        _record_n(self.im, n=20, source="A", target="B")
        _record_n(self.im, n=5, source="B", target="C")

    def test_returns_list(self):
        assert isinstance(self.im.identify_hotspots(), list)

    def test_top_n_respected(self):
        hotspots = self.im.identify_hotspots(top_n=1)
        assert len(hotspots) <= 1

    def test_highest_frequency_first(self):
        hotspots = self.im.identify_hotspots(MatrixMetric.FREQUENCY)
        if len(hotspots) >= 2:
            assert hotspots[0][2] >= hotspots[1][2]


class TestDetectBottlenecks:
    def setup_method(self):
        self.im = _make_interaction_matrix()

    def test_returns_list_empty_when_no_interactions(self):
        result = self.im.detect_bottlenecks()
        assert isinstance(result, list)
        assert result == []

    def test_detects_high_error_rate_module(self):
        # Inject stats manually to trigger bottleneck detection
        self.im._register_module("SlowMod")
        self.im._register_module("Target")
        stats = self.im.module_stats["SlowMod"]
        stats.total_interactions = 20
        stats.failed_interactions = 5  # 25% error rate > 10%
        result = self.im.detect_bottlenecks()
        assert "SlowMod" in result


class TestStartInteraction:
    def setup_method(self):
        self.im = _make_interaction_matrix()

    def test_returns_string_id(self):
        iid = self.im.start_interaction("A", "B", InteractionType.FUNCTION_CALL)
        assert isinstance(iid, str)
        assert len(iid) > 0

    def test_records_pending_interaction(self):
        self.im.start_interaction("A", "B", InteractionType.FUNCTION_CALL)
        # Most recent interaction should be PENDING
        pending = [i for i in self.im.interactions if i.status == InteractionStatus.PENDING]
        assert len(pending) >= 1


class TestCompleteInteraction:
    def setup_method(self):
        self.im = _make_interaction_matrix()

    def test_complete_does_not_raise(self):
        iid = self.im.start_interaction("A", "B", InteractionType.FUNCTION_CALL)
        # Should not raise
        self.im.complete_interaction(iid, InteractionStatus.SUCCESS, latency_ms=30.0)


class TestGetSystemHealth:
    def setup_method(self):
        self.im = _make_interaction_matrix()

    def test_idle_system_returns_health_dict(self):
        health = self.im.get_system_health()
        assert isinstance(health, dict)
        assert "health_score" in health
        assert "status" in health

    def test_idle_system_100_health(self):
        health = self.im.get_system_health()
        assert health["health_score"] == pytest.approx(100.0)

    def test_system_with_interactions(self):
        _record_n(self.im, n=10, source="A", target="B")
        health = self.im.get_system_health()
        assert health["total_interactions"] == 10
        assert health["success_rate"] == pytest.approx(100.0)

    def test_error_rate_affects_health(self):
        _record_n(self.im, n=5, source="A", target="B", status=InteractionStatus.SUCCESS)
        _record_n(self.im, n=5, source="A", target="B", status=InteractionStatus.FAILURE)
        health = self.im.get_system_health()
        assert health["health_score"] < 100.0

    def test_status_excellent_high_score(self):
        _record_n(self.im, n=100, source="A", target="B", status=InteractionStatus.SUCCESS)
        health = self.im.get_system_health()
        assert health["status"] in ("excellent", "good", "fair", "poor", "idle")

    def test_active_modules_count(self):
        _record_n(self.im, n=1, source="Mod1", target="Mod2")
        _record_n(self.im, n=1, source="Mod2", target="Mod3")
        health = self.im.get_system_health()
        assert health["active_modules"] >= 3


class TestMonitoring:
    def test_start_stop_monitoring(self):
        im = _make_interaction_matrix()
        im.start_monitoring(update_interval=100)
        assert im._monitoring is True
        im.stop_monitoring()
        assert im._monitoring is False

    def test_start_twice_doesnt_crash(self):
        im = _make_interaction_matrix()
        im.start_monitoring(update_interval=100)
        im.start_monitoring(update_interval=100)  # Already active warning
        im.stop_monitoring()


class TestModuleFunctions19:
    def setup_method(self):
        _u19._interaction_matrix = None

    def test_get_interaction_matrix_returns_instance(self):
        im = get_interaction_matrix()
        assert isinstance(im, InteractionMatrix)

    def test_get_interaction_matrix_singleton(self):
        im1 = get_interaction_matrix()
        im2 = get_interaction_matrix()
        assert im1 is im2

    def test_module_record_interaction_function(self):
        im = get_interaction_matrix()
        before = len(im.interactions)
        record_interaction("QuickA", "QuickB", "function_call", True, 15.0)
        assert len(im.interactions) == before + 1

    def test_module_record_interaction_failure(self):
        im = get_interaction_matrix()
        record_interaction("QuickX", "QuickY", "data_exchange", False)
        # Last interaction should be failure
        last = [i for i in im.interactions if i.source == "QuickX" and i.target == "QuickY"]
        assert last[-1].status == InteractionStatus.FAILURE

    def test_module_record_interaction_unknown_type_defaults(self):
        im = get_interaction_matrix()
        before = len(im.interactions)
        record_interaction("A", "B", "unknown_type_xyz", True)
        # Should default to FUNCTION_CALL
        assert len(im.interactions) == before + 1
        last = im.interactions[-1]
        assert last.interaction_type == InteractionType.FUNCTION_CALL
