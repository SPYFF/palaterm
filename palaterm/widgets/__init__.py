"""UI widgets for Palaterm."""

from .canvas import CanvasWidget
from .modals import ConfirmModal, FilePathModal, TextEditModal
from .status_bar import StatusBar
from .panels import (
    AlignCell,
    BorderStylePanel,
    CollapsiblePanel,
    ColorPanel,
    EndingButton,
    ExportPanel,
    LayerPanel,
    LineEndingsPanel,
    LineStylePanel,
    SelectModePanel,
    ShapeAlignPanel,
    TextAlignPanel,
    ToolPicker,
)

__all__ = [
    "CanvasWidget",
    "ConfirmModal",
    "FilePathModal",
    "StatusBar",
    "TextEditModal",
    "CollapsiblePanel",
    "ToolPicker",
    "SelectModePanel",
    "BorderStylePanel",
    "LineStylePanel",
    "LineEndingsPanel", "EndingButton",
    "TextAlignPanel", "AlignCell",
    "ShapeAlignPanel",
    "LayerPanel",
    "ColorPanel",
    "ExportPanel",
]
