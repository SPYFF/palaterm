"""UI widgets for Palaterm."""

from .canvas import CanvasWidget
from .modals import FilePathModal, TextEditModal
from .status_bar import StatusBar
from .panels import (
    AlignCell,
    BorderStylePanel,
    EndingButton,
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
    "FilePathModal",
    "StatusBar",
    "TextEditModal",
    "ToolPicker",
    "SelectModePanel",
    "BorderStylePanel",
    "LineStylePanel",
    "LineEndingsPanel", "EndingButton",
    "TextAlignPanel", "AlignCell",
    "ShapeAlignPanel",
    "LayerPanel",
]
