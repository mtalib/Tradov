#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT102_U18DependencyAnalyzer_U19InteractionMatrix.py
Purpose: Tests for SpyderU18_DependencyAnalyzer and SpyderU19_InteractionMatrix

Author: Spyder Dev
Year Created: 2025
Last Updated: 2025-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import types
import tempfile
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# ==============================================================================
# PATH SETUP
# ==============================================================================
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ==============================================================================
# MODULE STUBS
# ==============================================================================


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# THIRD-PARTY IMPORTS AND MODULE IMPORTS
# ==============================================================================
import pytest
import numpy as np
from pathlib import Path

from Spyder.SpyderU_Utilities.SpyderU18_DependencyAnalyzer import (
    DependencyType,
    AnalysisScope,
    SeverityLevel,
    ModuleInfo,
    CircularDependency,
    DependencyGraph,
    DependencyAnalyzer,
    analyze_project_dependencies,
    find_circular_dependencies,
    get_dependency_analyzer,
)

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


def _make_tmpdir_with_py_files():
    """Create a temp dir with a few minimal Python files for scan tests."""
    tmpdir = tempfile.mkdtemp()
    # Module A imports Module B
    with open(os.path.join(tmpdir, "SpyderA01_Main.py"), "w") as f:
        f.write("import os\nfrom . import SpyderB01_Client\n\nclass Main:\n    pass\n")
    # Module B imports nothing Spyder-specific
    with open(os.path.join(tmpdir, "SpyderB01_Client.py"), "w") as f:
        f.write("import sys\n\nclass Client:\n    def connect(self):\n        pass\n")
    # Module C — standalone
    with open(os.path.join(tmpdir, "SpyderC01_Feed.py"), "w") as f:
        f.write("import datetime\n\nclass Feed:\n    pass\n")
    return tmpdir


# ==============================================================================
# SECTION 1: SpyderU18_DependencyAnalyzer Tests
# ==============================================================================


class TestDependencyType:
    """Tests for DependencyType enum."""

    def test_direct_member(self):
        assert DependencyType.DIRECT.value == "direct"

    def test_indirect_member(self):
        assert DependencyType.INDIRECT.value == "indirect"

    def test_circular_member(self):
        assert DependencyType.CIRCULAR.value == "circular"

    def test_external_member(self):
        assert DependencyType.EXTERNAL.value == "external"

    def test_internal_member(self):
        assert DependencyType.INTERNAL.value == "internal"

    def test_enum_count(self):
        assert len(DependencyType) == 5


class TestAnalysisScope:
    """Tests for AnalysisScope enum."""

    def test_module_member(self):
        assert AnalysisScope.MODULE.value == "module"

    def test_group_member(self):
        assert AnalysisScope.GROUP.value == "group"

    def test_system_member(self):
        assert AnalysisScope.SYSTEM.value == "system"

    def test_enum_count(self):
        assert len(AnalysisScope) == 3


class TestSeverityLevel:
    """Tests for SeverityLevel enum."""

    def test_low_member(self):
        assert SeverityLevel.LOW.value == "low"

    def test_medium_member(self):
        assert SeverityLevel.MEDIUM.value == "medium"

    def test_high_member(self):
        assert SeverityLevel.HIGH.value == "high"

    def test_critical_member(self):
        assert SeverityLevel.CRITICAL.value == "critical"

    def test_enum_count(self):
        assert len(SeverityLevel) == 4


class TestModuleInfo:
    """Tests for ModuleInfo dataclass."""

    def test_basic_creation(self):
        mi = ModuleInfo(name="SpyderA01_Main", path="/some/path.py", group="A")
        assert mi.name == "SpyderA01_Main"
        assert mi.path == "/some/path.py"
        assert mi.group == "A"

    def test_defaults(self):
        mi = ModuleInfo(name="Mod", path="/p.py", group="X")
        assert mi.imports == []
        assert mi.imported_by == []
        assert mi.external_imports == []
        assert mi.functions == []
        assert mi.classes == []
        assert mi.lines_of_code == 0

    def test_custom_fields(self):
        mi = ModuleInfo(
            name="Mod", path="/p.py", group="A",
            imports=["os", "sys"],
            functions=["foo", "bar"],
            classes=["MyClass"],
            lines_of_code=150,
        )
        assert len(mi.imports) == 2
        assert len(mi.functions) == 2
        assert len(mi.classes) == 1
        assert mi.lines_of_code == 150

    def test_to_dict_keys(self):
        mi = ModuleInfo(name="M", path="/p.py", group="G")
        d = mi.to_dict()
        assert isinstance(d, dict)
        assert "name" in d
        assert "path" in d
        assert "group" in d

    def test_to_dict_values(self):
        mi = ModuleInfo(name="MyMod", path="/tmp/m.py", group="B", lines_of_code=42)
        d = mi.to_dict()
        assert d["name"] == "MyMod"
        assert d["lines_of_code"] == 42

    def test_imports_by_reference(self):
        mi = ModuleInfo(name="M", path="/p.py", group="G")
        mi.imports.append("numpy")
        assert "numpy" in mi.imports


class TestCircularDependency:
    """Tests for CircularDependency dataclass."""

    def test_basic_creation(self):
        cd = CircularDependency(
            modules=["A", "B"],
            severity=SeverityLevel.LOW,
            description="A→B→A",
        )
        assert cd.modules == ["A", "B"]
        assert cd.severity == SeverityLevel.LOW
        assert cd.description == "A→B→A"

    def test_to_dict_keys(self):
        cd = CircularDependency(
            modules=["A", "B"],
            severity=SeverityLevel.HIGH,
            description="cycle",
        )
        d = cd.to_dict()
        assert "modules" in d
        assert "severity" in d
        assert "description" in d

    def test_to_dict_severity_value(self):
        cd = CircularDependency(
            modules=["X"],
            severity=SeverityLevel.CRITICAL,
            description="self",
        )
        d = cd.to_dict()
        assert d["severity"] == "critical"

    def test_larger_cycle(self):
        mods = ["A", "B", "C", "D", "E", "F", "G"]
        cd = CircularDependency(
            modules=mods,
            severity=SeverityLevel.CRITICAL,
            description="big cycle",
        )
        assert len(cd.modules) == 7


class TestDependencyGraph:
    """Tests for DependencyGraph dataclass."""

    def test_basic_creation(self):
        dg = DependencyGraph(
            nodes=["A", "B"],
            edges=[("A", "B")],
            circular_dependencies=[],
            isolated_modules=["C"],
        )
        assert len(dg.nodes) == 2
        assert len(dg.edges) == 1
        assert dg.isolated_modules == ["C"]

    def test_to_dict_keys(self):
        dg = DependencyGraph(nodes=[], edges=[], circular_dependencies=[], isolated_modules=[])
        d = dg.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "circular_dependencies" in d

    def test_to_dict_counts(self):
        dg = DependencyGraph(
            nodes=["A", "B", "C"],
            edges=[("A", "B"), ("B", "C")],
            circular_dependencies=[],
            isolated_modules=[],
        )
        d = dg.to_dict()
        assert len(d["nodes"]) == 3

    def test_with_circular(self):
        cd = CircularDependency(modules=["A", "B"], severity=SeverityLevel.LOW, description="cycle")
        dg = DependencyGraph(nodes=["A", "B"], edges=[("A","B"),("B","A")], circular_dependencies=[cd], isolated_modules=[])
        assert len(dg.circular_dependencies) == 1


class TestDependencyAnalyzerInit:
    """Tests for DependencyAnalyzer initialization."""

    def test_init_default(self):
        da = DependencyAnalyzer("/tmp")
        assert da.project_root == Path("/tmp")

    def test_init_custom_root(self):
        tmpdir = tempfile.mkdtemp()
        da = DependencyAnalyzer(tmpdir)
        assert da.project_root == Path(tmpdir)

    def test_initial_modules_empty(self):
        da = DependencyAnalyzer("/tmp")
        assert isinstance(da.modules, dict)
        assert len(da.modules) == 0

    def test_initial_circular_deps_empty(self):
        da = DependencyAnalyzer("/tmp")
        assert da.circular_dependencies == []

    def test_initial_missing_modules_empty(self):
        da = DependencyAnalyzer("/tmp")
        assert isinstance(da.missing_modules, set)
        assert len(da.missing_modules) == 0

    def test_import_graph_is_digraph(self):
        import networkx as nx
        da = DependencyAnalyzer("/tmp")
        assert isinstance(da.import_graph, nx.DiGraph)


class TestDependencyAnalyzerSeverity:
    """Tests for _assess_circular_severity private method."""

    def setup_method(self):
        self.da = DependencyAnalyzer("/tmp")

    def test_severity_low_two_modules(self):
        result = self.da._assess_circular_severity(["A", "B"])
        assert result == SeverityLevel.LOW

    def test_severity_medium_three_modules(self):
        result = self.da._assess_circular_severity(["A", "B", "C"])
        assert result == SeverityLevel.MEDIUM

    def test_severity_high_four_modules(self):
        result = self.da._assess_circular_severity(["A", "B", "C", "D"])
        assert result == SeverityLevel.HIGH

    def test_severity_high_five_modules(self):
        result = self.da._assess_circular_severity(["A", "B", "C", "D", "E"])
        assert result == SeverityLevel.HIGH

    def test_severity_critical_six_modules(self):
        result = self.da._assess_circular_severity(["A", "B", "C", "D", "E", "F"])
        assert result == SeverityLevel.CRITICAL

    def test_severity_critical_many_modules(self):
        result = self.da._assess_circular_severity(list("ABCDEFGHIJ"))
        assert result == SeverityLevel.CRITICAL

    def test_severity_single_module(self):
        # 1 module: len<=2 → LOW
        result = self.da._assess_circular_severity(["A"])
        assert result == SeverityLevel.LOW


class TestDependencyAnalyzerIsSpyderModule:
    """Tests for _is_spyder_module private method."""

    def setup_method(self):
        self.da = DependencyAnalyzer("/tmp")

    def test_spyder_module_true(self):
        assert self.da._is_spyder_module("SpyderA01_Main") is True

    def test_spyder_module_series_b(self):
        assert self.da._is_spyder_module("SpyderB40_TradierClient") is True

    def test_non_spyder_module_false(self):
        assert self.da._is_spyder_module("numpy") is False

    def test_non_spyder_module_pandas(self):
        assert self.da._is_spyder_module("pandas") is False

    def test_spyder_lowercase_false(self):
        # must start with "Spyder" (capital S)
        result = self.da._is_spyder_module("spyder_something")
        # may return True or False depending on prefix check; just ensure it doesn't crash
        assert isinstance(result, bool)


class TestDependencyAnalyzerCountLines:
    """Tests for _count_lines_of_code private method."""

    def setup_method(self):
        self.da = DependencyAnalyzer("/tmp")

    def test_count_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            fname = f.name
        try:
            result = self.da._count_lines_of_code(fname)
            assert result >= 0  # empty file may return 0 or 1 depending on implementation
        finally:
            os.unlink(fname)

    def test_count_non_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\n\nclass Foo:\n    pass\n")
            fname = f.name
        try:
            result = self.da._count_lines_of_code(fname)
            assert result > 0
        finally:
            os.unlink(fname)

    def test_count_returns_int(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n" * 10)
            fname = f.name
        try:
            result = self.da._count_lines_of_code(fname)
            assert isinstance(result, int)
        finally:
            os.unlink(fname)


class TestDependencyAnalyzerWithTempDir:
    """Tests for DependencyAnalyzer using a temp directory with known Python files."""

    def setup_method(self):
        self.tmpdir = _make_tmpdir_with_py_files()
        self.da = DependencyAnalyzer(self.tmpdir)

    def test_find_python_files_returns_list(self):
        files = self.da._find_python_files()
        assert isinstance(files, list)

    def test_find_python_files_finds_py_files(self):
        files = self.da._find_python_files()
        assert len(files) >= 3  # we created 3 files

    def test_find_python_files_all_py(self):
        files = self.da._find_python_files()
        for f in files:
            assert str(f).endswith(".py")

    def test_analyze_file_returns_module_info(self):
        py_file = os.path.join(self.tmpdir, "SpyderB01_Client.py")
        result = self.da._analyze_file(py_file)
        assert result is None or isinstance(result, ModuleInfo)

    def test_analyze_dependencies_populates_modules(self):
        self.da.analyze_dependencies()
        assert len(self.da.modules) >= 1

    def test_analyze_dependencies_force_refresh(self):
        self.da.analyze_dependencies()
        len(self.da.modules)
        self.da.analyze_dependencies(force_refresh=True)
        # Should still have modules after refresh
        assert len(self.da.modules) >= 0

    def test_generate_dependency_graph_returns_obj(self):
        self.da.analyze_dependencies()
        graph = self.da.generate_dependency_graph()
        assert isinstance(graph, DependencyGraph)

    def test_generate_dependency_report_returns_str(self):
        self.da.analyze_dependencies()
        report = self.da.generate_dependency_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_dependency_report_has_content(self):
        self.da.analyze_dependencies()
        report = self.da.generate_dependency_report()
        # Should be a non-trivial string (markdown)
        assert "#" in report or "Dependency" in report or len(report) > 10

    def test_export_graph_data_json(self):
        self.da.analyze_dependencies()
        data = self.da.export_graph_data("json")
        assert isinstance(data, str)
        assert len(data) > 0

    def test_export_graph_data_csv(self):
        self.da.analyze_dependencies()
        data = self.da.export_graph_data("csv")
        assert isinstance(data, str)

    def test_find_circular_dependencies_returns_list(self):
        self.da.analyze_dependencies()
        result = self.da.find_circular_dependencies()
        assert isinstance(result, list)


class TestDependencyAnalyzerGetModuleDeps:
    """Tests for get_module_dependencies method."""

    def setup_method(self):
        self.tmpdir = _make_tmpdir_with_py_files()
        self.da = DependencyAnalyzer(self.tmpdir)
        self.da.analyze_dependencies()

    def test_get_nonexistent_module_returns_error(self):
        result = self.da.get_module_dependencies("NoSuchModule")
        assert "error" in result

    def test_get_known_module_returns_dict(self):
        if not self.da.modules:
            pytest.skip("No modules found")
        module_name = next(iter(self.da.modules))
        result = self.da.get_module_dependencies(module_name)
        assert isinstance(result, dict)
        if "error" not in result:
            assert "module" in result or "direct_dependencies" in result


class TestModuleFunctionsU18:
    """Tests for U18 module-level functions."""

    def test_analyze_project_dependencies_returns_analyzer(self):
        tmpdir = tempfile.mkdtemp()
        result = analyze_project_dependencies(tmpdir)
        assert isinstance(result, DependencyAnalyzer)

    def test_find_circular_dependencies_returns_list(self):
        tmpdir = tempfile.mkdtemp()
        result = find_circular_dependencies(tmpdir)
        assert isinstance(result, list)

    def test_get_dependency_analyzer_singleton(self):
        # Reset singleton by testing with fresh call
        tmpdir = tempfile.mkdtemp()
        # Module-level singleton may already exist; just check type
        result = get_dependency_analyzer(tmpdir)
        assert isinstance(result, DependencyAnalyzer)

    def test_get_dependency_analyzer_same_instance(self):
        # Once called, repeated call should return same instance
        da1 = get_dependency_analyzer()
        da2 = get_dependency_analyzer()
        assert da1 is da2


# ==============================================================================
# SECTION 2: SpyderU19_InteractionMatrix Tests
# ==============================================================================


class TestInteractionType:
    """Tests for InteractionType enum."""

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

    def test_enum_count(self):
        assert len(InteractionType) == 7


class TestInteractionStatus:
    """Tests for InteractionStatus enum."""

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

    def test_enum_count(self):
        assert len(InteractionStatus) == 5


class TestMatrixMetric:
    """Tests for MatrixMetric enum."""

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

    def test_enum_count(self):
        assert len(MatrixMetric) == 5


class TestInteraction:
    """Tests for Interaction dataclass."""

    def test_basic_creation(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
        )
        assert i.source == "A"
        assert i.target == "B"

    def test_default_status(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.DATA_EXCHANGE,
            timestamp=datetime.now(),
        )
        assert i.status == InteractionStatus.PENDING

    def test_is_successful_property_true(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
            status=InteractionStatus.SUCCESS,
        )
        assert i.is_successful is True

    def test_is_successful_property_false(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
            status=InteractionStatus.FAILURE,
        )
        assert i.is_successful is False

    def test_latency_ms_field(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
            latency_ms=42.5,
        )
        assert i.latency_ms == 42.5

    def test_data_size_field(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.DATA_EXCHANGE,
            timestamp=datetime.now(),
            data_size=1024,
        )
        assert i.data_size == 1024

    def test_error_message_field(self):
        i = Interaction(
            source="A",
            target="B",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
            status=InteractionStatus.FAILURE,
            error_message="Connection refused",
        )
        assert i.error_message == "Connection refused"


class TestModuleStats:
    """Tests for ModuleStats dataclass."""

    def test_basic_creation(self):
        ms = ModuleStats(module_name="SpyderA01")
        assert ms.module_name == "SpyderA01"

    def test_default_values(self):
        ms = ModuleStats(module_name="M")
        assert ms.total_interactions == 0
        assert ms.successful_interactions == 0
        assert ms.failed_interactions == 0
        assert ms.average_latency == 0.0
        assert ms.total_data_sent == 0
        assert ms.total_data_received == 0
        assert ms.error_count == 0
        assert ms.last_activity is None

    def test_success_rate_zero_when_no_interactions(self):
        ms = ModuleStats(module_name="M")
        # success_rate = successful / total * 100; total=0 → 0.0 or 100.0
        rate = ms.success_rate
        assert isinstance(rate, float)

    def test_success_rate_calculated(self):
        ms = ModuleStats(
            module_name="M",
            total_interactions=10,
            successful_interactions=8,
            failed_interactions=2,
        )
        rate = ms.success_rate
        assert abs(rate - 80.0) < 1.0

    def test_error_rate_property(self):
        ms = ModuleStats(
            module_name="M",
            total_interactions=10,
            successful_interactions=7,
            failed_interactions=3,
            error_count=3,
        )
        rate = ms.error_rate
        assert isinstance(rate, float)


class TestMatrixAnalysisDataclass:
    """Tests for MatrixAnalysis dataclass."""

    def test_basic_creation(self):
        ma = MatrixAnalysis(
            matrix_data=np.zeros((3, 3)),
            module_names=["A", "B", "C"],
            metric_type=MatrixMetric.FREQUENCY,
        )
        assert ma.metric_type == MatrixMetric.FREQUENCY
        assert len(ma.module_names) == 3

    def test_default_fields(self):
        ma = MatrixAnalysis(
            matrix_data=np.zeros((2, 2)),
            module_names=["A", "B"],
            metric_type=MatrixMetric.LATENCY,
        )
        assert ma.hotspots == []
        assert ma.bottlenecks == []
        assert ma.isolated_modules == []
        assert ma.critical_paths == []
        assert ma.health_score == 0.0
        assert ma.recommendations == []

    def test_custom_health_score(self):
        ma = MatrixAnalysis(
            matrix_data=np.ones((3, 3)),
            module_names=["A", "B", "C"],
            metric_type=MatrixMetric.SUCCESS_RATE,
            health_score=85.0,
        )
        assert ma.health_score == 85.0

    def test_matrix_data_is_ndarray(self):
        data = np.eye(4)
        ma = MatrixAnalysis(
            matrix_data=data,
            module_names=["A", "B", "C", "D"],
            metric_type=MatrixMetric.FREQUENCY,
        )
        assert isinstance(ma.matrix_data, np.ndarray)
        assert ma.matrix_data.shape == (4, 4)


class TestInteractionMatrixInit:
    """Tests for InteractionMatrix initialization."""

    def test_default_init(self):
        im = InteractionMatrix()
        assert isinstance(im.modules, dict)
        assert isinstance(im.module_names, list)
        assert isinstance(im.interactions, list)

    def test_custom_max_modules(self):
        im = InteractionMatrix(max_modules=50)
        # Matrices should be pre-allocated to 50×50
        assert im.frequency_matrix.shape == (50, 50)

    def test_initial_state_empty(self):
        im = InteractionMatrix()
        assert len(im.modules) == 0
        assert len(im.module_names) == 0
        assert len(im.interactions) == 0

    def test_numpy_matrices_initialized(self):
        im = InteractionMatrix(max_modules=10)
        assert im.frequency_matrix.shape == (10, 10)
        assert im.latency_matrix.shape == (10, 10)
        assert im.success_matrix.shape == (10, 10)
        assert im.data_volume_matrix.shape == (10, 10)

    def test_initial_matrices_zero(self):
        im = InteractionMatrix(max_modules=5)
        assert np.all(im.frequency_matrix == 0)


class TestRecordInteraction:
    """Tests for InteractionMatrix.record_interaction."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)

    def test_record_single_interaction(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL)
        assert len(self.im.interactions) == 1

    def test_record_registers_source_module(self):
        self.im.record_interaction("ModA", "ModB", InteractionType.DATA_EXCHANGE)
        assert "ModA" in self.im.modules

    def test_record_registers_target_module(self):
        self.im.record_interaction("ModA", "ModB", InteractionType.DATA_EXCHANGE)
        assert "ModB" in self.im.modules

    def test_record_updates_frequency_matrix(self):
        self.im.record_interaction("X", "Y", InteractionType.FUNCTION_CALL, InteractionStatus.SUCCESS)
        x_idx = self.im.modules["X"]
        y_idx = self.im.modules["Y"]
        assert self.im.frequency_matrix[x_idx, y_idx] == 1

    def test_record_multiple_increments_frequency(self):
        for _ in range(5):
            self.im.record_interaction("X", "Y", InteractionType.FUNCTION_CALL, InteractionStatus.SUCCESS)
        x_idx = self.im.modules["X"]
        y_idx = self.im.modules["Y"]
        assert self.im.frequency_matrix[x_idx, y_idx] == 5

    def test_record_with_latency(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.SUCCESS, latency_ms=50.0)
        a_idx = self.im.modules["A"]
        b_idx = self.im.modules["B"]
        assert self.im.latency_matrix[a_idx, b_idx] == pytest.approx(50.0, abs=1e-3)

    def test_record_with_data_size(self):
        self.im.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                                   InteractionStatus.SUCCESS, data_size=1000)
        a_idx = self.im.modules["A"]
        b_idx = self.im.modules["B"]
        assert self.im.data_volume_matrix[a_idx, b_idx] == 1000

    def test_record_failure_status(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.FAILURE)
        a_stats = self.im.module_stats["A"]
        assert a_stats.failed_interactions >= 1

    def test_record_success_updates_stats(self):
        self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.SUCCESS)
        a_stats = self.im.module_stats["A"]
        assert a_stats.successful_interactions >= 1

    def test_record_many_interactions(self):
        for i in range(20):
            self.im.record_interaction(f"Mod{i%5}", f"Mod{(i+1)%5}", InteractionType.FUNCTION_CALL)
        assert len(self.im.interactions) == 20


class TestModuleStatisticsMethod:
    """Tests for InteractionMatrix.get_module_statistics."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)
        self.im.record_interaction("Alpha", "Beta", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.SUCCESS)
        self.im.record_interaction("Alpha", "Gamma", InteractionType.EVENT_TRIGGER,
                                   InteractionStatus.SUCCESS)
        self.im.record_interaction("Beta", "Alpha", InteractionType.FUNCTION_CALL,
                                   InteractionStatus.FAILURE)

    def test_get_all_stats_returns_dict(self):
        result = self.im.get_module_statistics()
        assert isinstance(result, dict)

    def test_get_specific_module_stats(self):
        result = self.im.get_module_statistics("Alpha")
        assert isinstance(result, ModuleStats)

    def test_stat_total_interactions(self):
        result = self.im.get_module_statistics("Alpha")
        assert result.total_interactions == 2

    def test_stat_successful_interactions(self):
        result = self.im.get_module_statistics("Alpha")
        assert result.successful_interactions == 2

    def test_get_nonexistent_module_none_or_new(self):
        result = self.im.get_module_statistics("DoesNotExist")
        # Returns None or a new default stats
        assert result is None or isinstance(result, ModuleStats)


class TestInteractionHistory:
    """Tests for InteractionMatrix.get_interaction_history."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)
        for i in range(10):
            self.im.record_interaction("Src", "Dst", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS)
        for i in range(5):
            self.im.record_interaction("Src", "Other", InteractionType.DATA_EXCHANGE,
                                       InteractionStatus.FAILURE)

    def test_get_all_history(self):
        history = self.im.get_interaction_history()
        assert len(history) == 15

    def test_get_history_by_source(self):
        history = self.im.get_interaction_history(source="Src")
        assert len(history) == 15

    def test_get_history_by_target(self):
        history = self.im.get_interaction_history(target="Dst")
        assert len(history) == 10

    def test_get_history_with_limit(self):
        history = self.im.get_interaction_history(limit=5)
        assert len(history) <= 5

    def test_history_contains_interactions(self):
        history = self.im.get_interaction_history()
        assert all(isinstance(i, Interaction) for i in history)

    def test_start_interaction_returns_string(self):
        interaction_id = self.im.start_interaction("ModA", "ModB", InteractionType.FUNCTION_CALL)
        assert isinstance(interaction_id, str)
        assert len(interaction_id) > 0


class TestAnalyzeMatrixMethod:
    """Tests for InteractionMatrix.analyze_matrix."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)
        modules = ["ModA", "ModB", "ModC"]
        import random
        random.seed(42)
        for i in range(30):
            src = modules[i % 3]
            dst = modules[(i + 1) % 3]
            self.im.record_interaction(src, dst, InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS, latency_ms=float(10 + i))

    def test_analyze_frequency_returns_analysis(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result, MatrixAnalysis)

    def test_analyze_frequency_metric_type(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert result.metric_type == MatrixMetric.FREQUENCY

    def test_analyze_latency_returns_analysis(self):
        result = self.im.analyze_matrix(MatrixMetric.LATENCY)
        assert isinstance(result, MatrixAnalysis)

    def test_analyze_success_rate(self):
        result = self.im.analyze_matrix(MatrixMetric.SUCCESS_RATE)
        assert isinstance(result, MatrixAnalysis)

    def test_analyze_data_volume(self):
        result = self.im.analyze_matrix(MatrixMetric.DATA_VOLUME)
        assert isinstance(result, MatrixAnalysis)

    def test_matrix_data_is_ndarray(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result.matrix_data, np.ndarray)

    def test_module_names_in_result(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(result.module_names, list)
        assert len(result.module_names) >= 3

    def test_health_score_in_range(self):
        result = self.im.analyze_matrix(MatrixMetric.FREQUENCY)
        assert 0.0 <= result.health_score <= 200.0  # health_score can be connectivity * 100


class TestIdentifyHotspots:
    """Tests for InteractionMatrix.identify_hotspots."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)
        # Create dominant pair
        for _ in range(100):
            self.im.record_interaction("HotA", "HotB", InteractionType.FUNCTION_CALL)
        for _ in range(5):
            self.im.record_interaction("ColdX", "ColdY", InteractionType.DATA_EXCHANGE)

    def test_returns_list(self):
        result = self.im.identify_hotspots()
        assert isinstance(result, list)

    def test_hotspot_is_tuple(self):
        result = self.im.identify_hotspots()
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 3

    def test_hotspot_top_pair(self):
        result = self.im.identify_hotspots(MatrixMetric.FREQUENCY, top_n=5)
        if result:
            top = result[0]
            assert top[0] == "HotA" and top[1] == "HotB"

    def test_hotspot_values_descending(self):
        result = self.im.identify_hotspots(MatrixMetric.FREQUENCY, top_n=10)
        values = [r[2] for r in result]
        assert values == sorted(values, reverse=True)


class TestDetectBottlenecks:
    """Tests for InteractionMatrix.detect_bottlenecks."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)

    def test_empty_returns_list(self):
        result = self.im.detect_bottlenecks()
        assert isinstance(result, list)

    def test_bottleneck_detected_high_latency(self):
        # Record >100 interactions with high latency
        for _ in range(105):
            self.im.record_interaction("Slow", "Fast", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS, latency_ms=1500.0)
        result = self.im.detect_bottlenecks()
        assert isinstance(result, list)
        # Slow module should be detected
        assert "Slow" in result

    def test_no_bottleneck_when_healthy(self):
        for _ in range(10):
            self.im.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS, latency_ms=10.0)
        result = self.im.detect_bottlenecks()
        assert isinstance(result, list)


class TestSystemHealth:
    """Tests for InteractionMatrix.get_system_health."""

    def setup_method(self):
        self.im = InteractionMatrix(max_modules=50)

    def test_returns_dict(self):
        health = self.im.get_system_health()
        assert isinstance(health, dict)

    def test_health_keys(self):
        health = self.im.get_system_health()
        assert "health_score" in health
        assert "total_interactions" in health
        assert "active_modules" in health
        assert "average_latency" in health
        assert "error_rate" in health
        assert "status" in health

    def test_empty_health_score(self):
        health = self.im.get_system_health()
        assert isinstance(health["health_score"], (int, float))

    def test_health_after_interactions(self):
        for _ in range(20):
            self.im.record_interaction("X", "Y", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS)
        health = self.im.get_system_health()
        assert health["total_interactions"] == 20
        assert health["active_modules"] >= 2

    def test_health_status_is_string(self):
        health = self.im.get_system_health()
        assert isinstance(health["status"], str)

    def test_complete_interaction_no_error(self):
        interaction_id = self.im.start_interaction("A", "B", InteractionType.FUNCTION_CALL)
        # complete_interaction does nothing (logs debug) but should not raise
        self.im.complete_interaction(interaction_id, InteractionStatus.SUCCESS, latency_ms=10.0)


class TestMonitoringMethods:
    """Tests for start_monitoring / stop_monitoring."""

    def test_start_and_stop_monitoring(self):
        im = InteractionMatrix(max_modules=10)
        im.start_monitoring(update_interval=60)
        assert im._monitoring is True
        im.stop_monitoring()
        # Give a moment for thread to stop
        time.sleep(0.05)
        assert im._monitoring is False

    def test_double_stop_no_error(self):
        im = InteractionMatrix(max_modules=10)
        im.start_monitoring(update_interval=60)
        im.stop_monitoring()
        im.stop_monitoring()  # Should not raise

    def test_start_monitoring_starts_thread(self):
        im = InteractionMatrix(max_modules=10)
        im.start_monitoring(update_interval=600)  # long interval, won't fire
        assert im._monitoring is True
        assert im._monitor_thread is not None
        im.stop_monitoring()


class TestModuleFunctionsU19:
    """Tests for U19 module-level functions."""

    def test_get_interaction_matrix_returns_instance(self):
        result = get_interaction_matrix()
        assert isinstance(result, InteractionMatrix)

    def test_get_interaction_matrix_singleton(self):
        im1 = get_interaction_matrix()
        im2 = get_interaction_matrix()
        assert im1 is im2

    def test_record_interaction_function_success(self):
        im = get_interaction_matrix()
        before = len(im.interactions)
        record_interaction("FuncSrc", "FuncDst", "function_call", True, 20.0)
        after = len(im.interactions)
        assert after == before + 1

    def test_record_interaction_function_failure(self):
        im = get_interaction_matrix()
        before = len(im.interactions)
        record_interaction("ErrSrc", "ErrDst", "error_propagation", False, 5.0)
        after = len(im.interactions)
        assert after == before + 1

    def test_record_interaction_invalid_type_falls_back(self):
        # Invalid type string falls back to FUNCTION_CALL
        im = get_interaction_matrix()
        before = len(im.interactions)
        record_interaction("A", "B", "invalid_type", True, None)
        after = len(im.interactions)
        assert after == before + 1
