# -*- coding: utf-8 -*-
"""Main window for Composition Grids tool - Modern icon-based UI."""

from __future__ import absolute_import, division, print_function

from functools import partial
import maya.cmds as cmds
from maya import OpenMayaUI as omui

from maya_comp_grids.utils.maya_utils import get_maya_main_window, get_qt_bindings
from maya_comp_grids.core.grid_types import (
    GridType, SpiralOrientation, TrianglesOrientation,
    GRID_DISPLAY_NAMES, SPIRAL_DISPLAY_NAMES, TRIANGLES_DISPLAY_NAMES
)
from maya_comp_grids.core.grid_manager import GridManager
from maya_comp_grids.ui.icons_generator import get_icon

QtWidgets, QtCore, QtGui, wrapInstance = get_qt_bindings()


WINDOW_OBJECT_NAME = "compGridsWindow"

DARK_STYLESHEET = """
QWidget#mainWidget {
    background-color: #3c3c3c;
}
QLabel {
    color: #cccccc;
}
QComboBox {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 20px;
}
QComboBox:hover {
    border: 1px solid #777777;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #cccccc;
    selection-background-color: #505050;
}
QPushButton {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #404040;
    border: 1px solid #777777;
}
QPushButton:pressed {
    background-color: #505050;
}
QToolButton {
    background-color: #2d2d2d;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 2px;
}
QToolButton:hover {
    background-color: #404040;
    border: 1px solid #777777;
}
QToolButton:pressed, QToolButton:checked {
    background-color: #505050;
    border: 1px solid #888888;
}
QToolButton::menu-indicator {
    image: none;
    width: 0px;
}
QMenu {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #555555;
}
QMenu::item {
    padding: 6px 20px;
}
QMenu::item:selected {
    background-color: #505050;
}
QFrame[frameShape="4"] {
    color: #555555;
}
QToolTip {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #555555;
    padding: 4px;
}
"""


class TitleBar(QtWidgets.QWidget):
    """Custom dark title bar with drag support."""

    def __init__(self, parent, title="Composition Grids"):
        super(TitleBar, self).__init__(parent)
        self.parent_window = parent
        self._drag_pos = None

        self.setFixedHeight(24)
        self.setStyleSheet("background-color: #3c3c3c;")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)

        # Title label
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Close button
        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c42b1c;
                color: white;
                border-radius: 2px;
            }
        """)
        self.close_btn.clicked.connect(self.parent_window.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self._drag_pos is not None:
            self.parent_window.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class GridButton(QtWidgets.QToolButton):
    """Custom tool button for grid selection."""

    grid_selected = QtCore.Signal(object, object)

    def __init__(self, grid_type, icon_key, tooltip, variants=None, parent=None):
        super(GridButton, self).__init__(parent)

        self.grid_type = grid_type
        self.icon_key = icon_key
        self.variants = variants
        self.current_variant = None
        self._help_text = tooltip

        self.setFixedSize(40, 40)
        self.setIconSize(QtCore.QSize(32, 32))
        self.setToolTip(tooltip)
        self.setCheckable(True)

        icon = get_icon(icon_key)
        if icon:
            self.setIcon(icon)

        if variants:
            self._setup_menu()
            self.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)

        self.clicked.connect(self._on_clicked)

    def _setup_menu(self):
        """Setup dropdown menu for variants."""
        menu = QtWidgets.QMenu(self)

        for variant_value, variant_name in self.variants:
            action = menu.addAction(variant_name)
            action.setData(variant_value)

            icon = get_icon(self.icon_key, variant_value)
            if icon:
                action.setIcon(icon)

            action.triggered.connect(partial(self._on_variant_selected, variant_value))

        self.setMenu(menu)

    def _on_clicked(self):
        """Handle button click."""
        self.grid_selected.emit(self.grid_type, self.current_variant)

    def _on_variant_selected(self, variant, checked=False):
        """Handle variant selection from menu."""
        self.current_variant = variant

        icon = get_icon(self.icon_key, variant)
        if icon:
            self.setIcon(icon)

        self.grid_selected.emit(self.grid_type, variant)


class CompGridsWindow(QtWidgets.QDialog):
    """Main window for Composition Grids tool."""

    def __init__(self, parent=None, active_camera=None):
        super(CompGridsWindow, self).__init__(parent)

        self._initial_camera = active_camera  # Camera from viewport before window opened

        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("Composition Grids")

        # Frameless window
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("background-color: #3c3c3c;")
        self.setFixedWidth(100)

        self.grid_manager = GridManager()
        self._current_color = (1.0, 1.0, 1.0)
        self._grid_buttons = []
        self._active_button = None

        self._build_ui()
        self._connect_signals()
        self._refresh_camera_list()

    def _build_ui(self):
        """Build the UI layout."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = TitleBar(self, "Comp Grids")
        main_layout.addWidget(self.title_bar)

        # Main content widget
        content_widget = QtWidgets.QWidget()
        content_widget.setObjectName("mainWidget")
        content_widget.setStyleSheet(DARK_STYLESHEET)
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(2)

        # Camera selection row
        camera_row = QtWidgets.QHBoxLayout()
        camera_row.setSpacing(2)
        camera_row.setAlignment(QtCore.Qt.AlignVCenter)
        self.camera_combo = QtWidgets.QComboBox()
        self.camera_combo.setToolTip("Select Camera")
        self.refresh_btn = QtWidgets.QPushButton("R")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setToolTip("Refresh")
        camera_row.addWidget(self.camera_combo, 1, QtCore.Qt.AlignVCenter)
        camera_row.addWidget(self.refresh_btn, 0, QtCore.Qt.AlignVCenter)
        content_layout.addLayout(camera_row)

        # Separator
        content_layout.addWidget(self._create_separator())

        # Grid buttons in 2 columns
        grid_layout = QtWidgets.QGridLayout()
        grid_layout.setSpacing(5)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        # Define all buttons: (grid_type, icon_key, tooltip, variants, row, col)
        buttons_data = [
            # Row 0
            (GridType.OFF, "off", "OFF", None, 0, 0),
            (GridType.CENTER_CROSS, "center_cross", "Center Cross", None, 0, 1),
            # Row 1
            (GridType.THIRDS, "thirds", "Rule of Thirds", None, 1, 0),
            (GridType.GOLDEN_PHI, "phi", "Golden Ratio", None, 1, 1),
            # Row 2
            (GridType.DIAGONALS, "diagonals", "Diagonals", None, 2, 0),
            (GridType.GOLDEN_TRIANGLES, "triangles", "Golden Triangles", [
                (TrianglesOrientation.FORWARD, "Forward (/)"),
                (TrianglesOrientation.BACKWARD, "Backward (\\)"),
            ], 2, 1),
            # Row 3
            (GridType.GOLDEN_SPIRAL, "spiral", "Golden Spiral", [
                (SpiralOrientation.TOP_LEFT, "Top-Right"),
                (SpiralOrientation.TOP_RIGHT, "Top-Left"),
                (SpiralOrientation.BOTTOM_LEFT, "Bottom-Right"),
                (SpiralOrientation.BOTTOM_RIGHT, "Bottom-Left"),
            ], 3, 0),
            (None, None, None, None, 3, 1),  # Empty slot
            # Row 4 - Square grids
            (GridType.SQUARE_4, "square_4", "Grid 4x4", None, 4, 0),
            (GridType.SQUARE_6, "square_6", "Grid 6x6", None, 4, 1),
            # Row 5
            (GridType.SQUARE_8, "square_8", "Grid 8x8", None, 5, 0),
            (None, None, None, None, 5, 1),  # Empty slot
            # Row 6 - Safe frames
            (GridType.SAFE_ACTION, "safe_action", "Action Safe 90%", None, 6, 0),
            (GridType.SAFE_TITLE, "safe_title", "Title Safe 80%", None, 6, 1),
            # Row 7
            (GridType.SAFE_BOTH, "safe_both", "Action + Title", None, 7, 0),
            (None, None, None, None, 7, 1),  # Color button slot
        ]

        for data in buttons_data:
            grid_type, icon_key, tooltip, variants, row, col = data
            if grid_type is None:
                continue

            btn = GridButton(grid_type, icon_key, tooltip, variants)
            if grid_type == GridType.GOLDEN_SPIRAL:
                btn.current_variant = SpiralOrientation.TOP_LEFT
            elif grid_type == GridType.GOLDEN_TRIANGLES:
                btn.current_variant = TrianglesOrientation.FORWARD

            self._grid_buttons.append(btn)
            grid_layout.addWidget(btn, row, col)

        # Color button in last row, right column
        self.color_btn = QtWidgets.QPushButton()
        self.color_btn.setFixedSize(40, 40)
        self.color_btn.setToolTip("Grid Color")
        self._update_color_button()
        grid_layout.addWidget(self.color_btn, 7, 1)

        content_layout.addLayout(grid_layout)
        content_layout.addStretch()

        # Author label
        author_label = QtWidgets.QLabel("by e.ov")
        author_label.setAlignment(QtCore.Qt.AlignCenter)
        author_label.setStyleSheet("color: #aaaaaa; font-size: 9px; padding: 4px;")
        content_layout.addWidget(author_label)

        main_layout.addWidget(content_widget)

    def _create_separator(self):
        """Create a horizontal separator line."""
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setStyleSheet("color: #555555;")
        return line

    def _update_color_button(self):
        """Update color button appearance."""
        r = int(self._current_color[0] * 255)
        g = int(self._current_color[1] * 255)
        b = int(self._current_color[2] * 255)
        self.color_btn.setStyleSheet(
            "background-color: rgb({}, {}, {}); border: 1px solid #777; border-radius: 4px;".format(r, g, b)
        )

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        self.refresh_btn.clicked.connect(self._refresh_camera_list)
        self.color_btn.clicked.connect(self._on_color_clicked)

        for btn in self._grid_buttons:
            btn.grid_selected.connect(self._on_grid_selected)

    def _refresh_camera_list(self):
        """Refresh the camera dropdown list."""
        self.camera_combo.clear()

        cameras = self.grid_manager.get_all_cameras()
        for cam in cameras:
            short_name = cam.split('|')[-1]
            self.camera_combo.addItem(short_name, cam)

        # Select active viewport camera
        self._select_active_camera()

    def _select_active_camera(self):
        """Select the camera from the active viewport or one with existing grid."""
        try:
            # First priority: use camera captured before window opened
            if self._initial_camera:
                for i in range(self.camera_combo.count()):
                    item_data = self.camera_combo.itemData(i)
                    if item_data and (self._initial_camera in item_data or
                                      item_data.endswith('|' + self._initial_camera)):
                        self.camera_combo.setCurrentIndex(i)
                        return

            # Second: find a camera that already has a grid in scene
            for i in range(self.camera_combo.count()):
                item_data = self.camera_combo.itemData(i)
                if item_data:
                    short_name = item_data.split("|")[-1].split(":")[-1]
                    grid_group = short_name + "_compGrid_grp"
                    if cmds.objExists(grid_group) or cmds.ls("*" + grid_group, long=True):
                        self.camera_combo.setCurrentIndex(i)
                        return
        except Exception:
            pass

    def _get_current_camera(self):
        """Get currently selected camera."""
        index = self.camera_combo.currentIndex()
        if index >= 0:
            return self.camera_combo.itemData(index)
        return None

    def _on_grid_selected(self, grid_type, variant):
        """Handle grid button selection."""
        sender = self.sender()
        for btn in self._grid_buttons:
            btn.setChecked(btn == sender and grid_type != GridType.OFF)

        self._active_button = sender if grid_type != GridType.OFF else None

        camera = self._get_current_camera()
        if not camera:
            cmds.warning("No camera selected.")
            return

        spiral_orient = None
        triangles_orient = None

        if grid_type == GridType.GOLDEN_SPIRAL:
            spiral_orient = variant or SpiralOrientation.TOP_LEFT
        elif grid_type == GridType.GOLDEN_TRIANGLES:
            triangles_orient = variant or TrianglesOrientation.FORWARD

        self.grid_manager.apply_grid(
            camera,
            grid_type,
            spiral_orient=spiral_orient,
            triangles_orient=triangles_orient,
            color=self._current_color
        )

        if grid_type == GridType.OFF:
            msg = "Grid removed"
        else:
            msg = "{} applied".format(GRID_DISPLAY_NAMES.get(grid_type, "Grid"))

        cmds.inViewMessage(amg=msg, pos='topCenter', fade=True)

    def _on_color_clicked(self):
        """Open color picker dialog."""
        r = int(self._current_color[0] * 255)
        g = int(self._current_color[1] * 255)
        b = int(self._current_color[2] * 255)
        current = QtGui.QColor(r, g, b)

        color = QtWidgets.QColorDialog.getColor(current, self, "Select Grid Color")

        if color.isValid():
            self._current_color = (color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0)
            self._update_color_button()

            camera = self._get_current_camera()
            if camera:
                self.grid_manager.update_color(camera, self._current_color)

    def closeEvent(self, event):
        """Handle window close."""
        super(CompGridsWindow, self).closeEvent(event)


def _get_active_viewport_camera():
    """Get camera from active viewport BEFORE window steals focus."""
    try:
        panel = cmds.getPanel(withFocus=True)
        if panel and cmds.getPanel(typeOf=panel) == 'modelPanel':
            return cmds.modelPanel(panel, q=True, camera=True)
    except Exception:
        pass
    return None


def show_window():
    """Show the Composition Grids window."""
    # Get active camera BEFORE creating window (focus will shift)
    active_camera = _get_active_viewport_camera()

    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT_NAME:
            widget.close()
            widget.deleteLater()

    parent = get_maya_main_window()
    window = CompGridsWindow(parent, active_camera=active_camera)
    window.show()

    return window
