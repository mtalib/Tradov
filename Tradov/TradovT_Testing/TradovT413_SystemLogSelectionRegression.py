from __future__ import annotations


def test_system_log_view_allows_selection_and_copy():
    import pytest

    pytest.importorskip("PySide6")

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    from Tradov.TradovG_GUI.TradovG20_DashboardBuilder import _ReadOnlyLogView

    app = QApplication.instance() or QApplication([])
    assert app is not None

    widget = _ReadOnlyLogView()
    flags = widget.textInteractionFlags()
    selectable = (
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )

    assert flags & selectable == selectable
    assert widget.focusPolicy() == Qt.FocusPolicy.ClickFocus
    assert widget.isReadOnly() is True
