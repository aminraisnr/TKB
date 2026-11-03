# -*- coding: utf-8 -*-
"""Generate grid icons for UI buttons."""

from __future__ import absolute_import, division, print_function

import math

from maya_comp_grids.utils.maya_utils import get_qt_bindings

QtWidgets, QtCore, QtGui, wrapInstance = get_qt_bindings()

ICON_SIZE = 32
PADDING = 3
LINE_COLOR = QtGui.QColor(200, 200, 200)
BG_COLOR = QtGui.QColor(60, 60, 60)

PHI = 1.618


def _create_base_pixmap():
    """Create base pixmap with background."""
    pixmap = QtGui.QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(BG_COLOR)
    return pixmap


def _get_painter(pixmap):
    """Get painter with antialiasing."""
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    pen = QtGui.QPen(LINE_COLOR)
    pen.setWidth(1)
    painter.setPen(pen)
    return painter


def create_off_icon():
    """Create OFF icon (X mark)."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    pen = QtGui.QPen(QtGui.QColor(150, 80, 80))
    pen.setWidth(2)
    painter.setPen(pen)

    p = PADDING + 4
    s = ICON_SIZE - p
    painter.drawLine(p, p, s, s)
    painter.drawLine(s, p, p, s)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_thirds_icon():
    """Create rule of thirds icon."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    w = s - p

    # Vertical lines
    x1 = p + w // 3
    x2 = p + 2 * w // 3
    painter.drawLine(x1, p, x1, s)
    painter.drawLine(x2, p, x2, s)

    # Horizontal lines
    y1 = p + w // 3
    y2 = p + 2 * w // 3
    painter.drawLine(p, y1, s, y1)
    painter.drawLine(p, y2, s, y2)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_phi_icon():
    """Create golden ratio icon."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    w = s - p

    phi_pos = int(w / PHI)
    phi_pos2 = w - phi_pos

    # Vertical lines
    painter.drawLine(p + phi_pos2, p, p + phi_pos2, s)
    painter.drawLine(p + phi_pos, p, p + phi_pos, s)

    # Horizontal lines
    painter.drawLine(p, p + phi_pos2, s, p + phi_pos2)
    painter.drawLine(p, p + phi_pos, s, p + phi_pos)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_center_cross_icon():
    """Create center cross icon."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    c = ICON_SIZE // 2

    painter.drawLine(c, p, c, s)
    painter.drawLine(p, c, s, c)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_diagonals_icon():
    """Create diagonals icon."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING

    painter.drawLine(p, p, s, s)
    painter.drawLine(s, p, p, s)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_spiral_icon(orientation="top_left"):
    """Create golden spiral icon with multiple arcs."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    w = float(s - p)

    # Draw golden spiral with multiple arcs
    # Start from outer rectangle, draw arcs inward
    sizes = []
    size = w
    for _ in range(5):
        sizes.append(size)
        size = size / PHI

    x, y = float(p), float(p)
    for i, size in enumerate(sizes):
        rect_size = size * 2
        if i == 0:
            rect = QtCore.QRectF(x, y, rect_size, rect_size)
            painter.drawArc(rect, 90 * 16, 90 * 16)
        elif i == 1:
            rect = QtCore.QRectF(x + w - rect_size, y, rect_size, rect_size)
            painter.drawArc(rect, 0 * 16, 90 * 16)
        elif i == 2:
            rect = QtCore.QRectF(x + w - rect_size, y + w - rect_size, rect_size, rect_size)
            painter.drawArc(rect, 270 * 16, 90 * 16)
        elif i == 3:
            small_w = w / PHI
            rect = QtCore.QRectF(x, y + w - rect_size, rect_size, rect_size)
            painter.drawArc(rect, 180 * 16, 90 * 16)

    painter.end()

    # Apply mirroring for different orientations
    if orientation != "top_left":
        transform = QtGui.QTransform()
        if orientation == "top_right":
            transform.scale(-1, 1)
            transform.translate(-ICON_SIZE, 0)
        elif orientation == "bottom_left":
            transform.scale(1, -1)
            transform.translate(0, -ICON_SIZE)
        elif orientation == "bottom_right":
            transform.scale(-1, -1)
            transform.translate(-ICON_SIZE, -ICON_SIZE)
        pixmap = pixmap.transformed(transform)

    return QtGui.QIcon(pixmap)


def create_triangles_icon(orientation="forward"):
    """Create golden triangles icon."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    w = s - p
    cx = (p + s) // 2
    cy = (p + s) // 2

    if orientation == "forward":
        # Main diagonal from top-right to bottom-left
        painter.drawLine(s, p, p, s)
        # Lines from corners to diagonal (perpendicular)
        painter.drawLine(p, p, cx, cy)
        painter.drawLine(s, s, cx, cy)
        # Small perpendicular lines showing the triangles
        offset = w // 4
        painter.drawLine(p + offset, p, cx - offset // 2, cy - offset // 2)
        painter.drawLine(s - offset, s, cx + offset // 2, cy + offset // 2)
    else:
        # Main diagonal from top-left to bottom-right
        painter.drawLine(p, p, s, s)
        # Lines from corners to diagonal (perpendicular)
        painter.drawLine(s, p, cx, cy)
        painter.drawLine(p, s, cx, cy)
        # Small perpendicular lines showing the triangles
        offset = w // 4
        painter.drawLine(s - offset, p, cx + offset // 2, cy - offset // 2)
        painter.drawLine(p + offset, s, cx - offset // 2, cy + offset // 2)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_square_grid_icon(divisions):
    """Create square grid icon."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    w = s - p

    # Draw grid lines
    for i in range(1, divisions):
        pos = p + w * i // divisions
        painter.drawLine(pos, p, pos, s)
        painter.drawLine(p, pos, s, pos)

    painter.end()
    return QtGui.QIcon(pixmap)


def create_safe_frame_icon(margins):
    """Create safe frame icon. margins is list of margin values (0.9, 0.8, etc)."""
    pixmap = _create_base_pixmap()
    painter = _get_painter(pixmap)

    p = PADDING
    s = ICON_SIZE - PADDING
    w = s - p
    cx = ICON_SIZE // 2
    cy = ICON_SIZE // 2

    for margin in margins:
        hw = int(w * margin / 2)
        hh = int(w * margin / 2)
        painter.drawRect(cx - hw, cy - hh, hw * 2, hh * 2)

    painter.end()
    return QtGui.QIcon(pixmap)


# Cache for icons
_icon_cache = {}


def get_icon(icon_type, variant=None):
    """Get icon from cache or create it."""
    key = (icon_type, variant)

    if key not in _icon_cache:
        if icon_type == "off":
            _icon_cache[key] = create_off_icon()
        elif icon_type == "thirds":
            _icon_cache[key] = create_thirds_icon()
        elif icon_type == "phi":
            _icon_cache[key] = create_phi_icon()
        elif icon_type == "center_cross":
            _icon_cache[key] = create_center_cross_icon()
        elif icon_type == "diagonals":
            _icon_cache[key] = create_diagonals_icon()
        elif icon_type == "spiral":
            _icon_cache[key] = create_spiral_icon(variant or "top_left")
        elif icon_type == "triangles":
            _icon_cache[key] = create_triangles_icon(variant or "forward")
        elif icon_type == "square_4":
            _icon_cache[key] = create_square_grid_icon(4)
        elif icon_type == "square_6":
            _icon_cache[key] = create_square_grid_icon(6)
        elif icon_type == "square_8":
            _icon_cache[key] = create_square_grid_icon(8)
        elif icon_type == "safe_action":
            _icon_cache[key] = create_safe_frame_icon([0.9])
        elif icon_type == "safe_title":
            _icon_cache[key] = create_safe_frame_icon([0.8])
        elif icon_type == "safe_both":
            _icon_cache[key] = create_safe_frame_icon([0.9, 0.8])

    return _icon_cache.get(key)
