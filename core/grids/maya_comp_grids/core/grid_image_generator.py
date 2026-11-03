# -*- coding: utf-8 -*-
"""Generate grid images using Qt."""

from __future__ import absolute_import, division, print_function

import os
import math

from maya_comp_grids.utils.maya_utils import get_qt_bindings
from maya_comp_grids.core.grid_types import (
    GridType, SpiralOrientation, TrianglesOrientation,
    GOLDEN_RATIO, GOLDEN_RATIO_COMP, ACTION_SAFE_MARGIN, TITLE_SAFE_MARGIN, PHI
)

QtWidgets, QtCore, QtGui, wrapInstance = get_qt_bindings()

# Image dimensions (power of 2 for texture efficiency)
IMAGE_WIDTH = 2048
IMAGE_HEIGHT = 2048


def generate_grid_image(path, grid_type, spiral_orient=None, triangles_orient=None,
                        color=(1.0, 1.0, 1.0), line_width=2):
    """
    Generate a grid image and save to path.

    Args:
        path: Output file path (PNG)
        grid_type: GridType value
        spiral_orient: SpiralOrientation value
        triangles_orient: TrianglesOrientation value
        color: RGB tuple (0-1 range)
        line_width: Line width in pixels
    """
    # Create transparent image
    image = QtGui.QImage(IMAGE_WIDTH, IMAGE_HEIGHT, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)

    # Create painter
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

    # Set pen
    r = int(color[0] * 255)
    g = int(color[1] * 255)
    b = int(color[2] * 255)
    pen = QtGui.QPen(QtGui.QColor(r, g, b, 255))
    pen.setWidth(line_width)
    painter.setPen(pen)

    # Draw grid based on type
    w = IMAGE_WIDTH
    h = IMAGE_HEIGHT

    if grid_type == GridType.THIRDS:
        _draw_thirds(painter, w, h)
    elif grid_type == GridType.GOLDEN_PHI:
        _draw_golden_phi(painter, w, h)
    elif grid_type == GridType.DIAGONALS:
        _draw_diagonals(painter, w, h)
    elif grid_type == GridType.GOLDEN_TRIANGLES:
        _draw_golden_triangles(painter, w, h, triangles_orient)
    elif grid_type == GridType.SQUARE_4:
        _draw_square_grid(painter, w, h, 4)
    elif grid_type == GridType.SQUARE_6:
        _draw_square_grid(painter, w, h, 6)
    elif grid_type == GridType.SQUARE_8:
        _draw_square_grid(painter, w, h, 8)
    elif grid_type == GridType.CENTER_CROSS:
        _draw_center_cross(painter, w, h)
    elif grid_type == GridType.SAFE_ACTION:
        _draw_safe_frame(painter, w, h, ACTION_SAFE_MARGIN)
    elif grid_type == GridType.SAFE_TITLE:
        _draw_safe_frame(painter, w, h, TITLE_SAFE_MARGIN)
    elif grid_type == GridType.SAFE_BOTH:
        _draw_safe_frame(painter, w, h, ACTION_SAFE_MARGIN)
        _draw_safe_frame(painter, w, h, TITLE_SAFE_MARGIN)
    elif grid_type == GridType.GOLDEN_SPIRAL:
        _draw_golden_spiral(painter, w, h, spiral_orient)

    painter.end()

    # Ensure directory exists
    dir_path = os.path.dirname(path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    # Save image
    image.save(path, "PNG")


def _draw_thirds(painter, w, h):
    """Draw rule of thirds grid."""
    # Vertical lines
    x1 = int(w / 3.0)
    x2 = int(2.0 * w / 3.0)
    painter.drawLine(x1, 0, x1, h)
    painter.drawLine(x2, 0, x2, h)

    # Horizontal lines
    y1 = int(h / 3.0)
    y2 = int(2.0 * h / 3.0)
    painter.drawLine(0, y1, w, y1)
    painter.drawLine(0, y2, w, y2)


def _draw_golden_phi(painter, w, h):
    """Draw golden ratio grid."""
    # Vertical lines
    x1 = int(w * GOLDEN_RATIO_COMP)
    x2 = int(w * GOLDEN_RATIO)
    painter.drawLine(x1, 0, x1, h)
    painter.drawLine(x2, 0, x2, h)

    # Horizontal lines
    y1 = int(h * GOLDEN_RATIO_COMP)
    y2 = int(h * GOLDEN_RATIO)
    painter.drawLine(0, y1, w, y1)
    painter.drawLine(0, y2, w, y2)


def _draw_diagonals(painter, w, h):
    """Draw diagonal lines."""
    painter.drawLine(0, 0, w, h)
    painter.drawLine(w, 0, 0, h)


def _draw_golden_triangles(painter, w, h, orientation):
    """Draw golden triangles."""
    if orientation == TrianglesOrientation.BACKWARD:
        # Main diagonal top-left to bottom-right
        painter.drawLine(0, 0, w, h)
        # Perpendiculars
        px1, py1 = _perp_foot(w, 0, 0, 0, w, h)
        painter.drawLine(w, 0, int(px1), int(py1))
        px2, py2 = _perp_foot(0, h, 0, 0, w, h)
        painter.drawLine(0, h, int(px2), int(py2))
    else:
        # Main diagonal top-right to bottom-left
        painter.drawLine(w, 0, 0, h)
        # Perpendiculars
        px1, py1 = _perp_foot(0, 0, w, 0, 0, h)
        painter.drawLine(0, 0, int(px1), int(py1))
        px2, py2 = _perp_foot(w, h, w, 0, 0, h)
        painter.drawLine(w, h, int(px2), int(py2))


def _perp_foot(px, py, x1, y1, x2, y2):
    """Calculate perpendicular foot from point to line."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / float(dx * dx + dy * dy)
    return x1 + t * dx, y1 + t * dy


def _draw_square_grid(painter, w, h, divisions):
    """Draw square grid."""
    # Vertical lines
    for i in range(1, divisions):
        x = int(w * i / float(divisions))
        painter.drawLine(x, 0, x, h)

    # Horizontal lines
    for i in range(1, divisions):
        y = int(h * i / float(divisions))
        painter.drawLine(0, y, w, y)


def _draw_center_cross(painter, w, h):
    """Draw center cross."""
    cx = w // 2
    cy = h // 2
    painter.drawLine(cx, 0, cx, h)
    painter.drawLine(0, cy, w, cy)


def _draw_safe_frame(painter, w, h, margin):
    """Draw safe frame rectangle."""
    offset_x = int(w * (1.0 - margin) / 2.0)
    offset_y = int(h * (1.0 - margin) / 2.0)

    rect = QtCore.QRect(offset_x, offset_y, w - 2 * offset_x, h - 2 * offset_y)
    painter.drawRect(rect)


def _draw_golden_spiral(painter, w, h, orientation):
    """Draw golden spiral."""
    # Use QPainterPath for smooth arcs
    path = QtGui.QPainterPath()

    # Build spiral from golden rectangles
    rect_w = float(w)
    rect_h = float(h)
    x = 0.0
    y = 0.0

    # Determine rotation sequence based on orientation
    if orientation == SpiralOrientation.TOP_LEFT:
        rotations = [0, 1, 2, 3]
    elif orientation == SpiralOrientation.TOP_RIGHT:
        rotations = [1, 2, 3, 0]
    elif orientation == SpiralOrientation.BOTTOM_LEFT:
        rotations = [3, 0, 1, 2]
    else:  # BOTTOM_RIGHT
        rotations = [2, 3, 0, 1]

    # Generate spiral arcs
    for i in range(12):
        if rect_w < 1 or rect_h < 1:
            break

        rot = rotations[i % 4]

        if rot == 0:
            # Arc in bottom-left corner
            new_w = rect_w / PHI
            arc_rect = QtCore.QRectF(x, y + rect_h - rect_w + new_w, (rect_w - new_w) * 2, (rect_w - new_w) * 2)
            path.arcMoveTo(arc_rect, 90)
            path.arcTo(arc_rect, 90, 90)
            rect_w = new_w
        elif rot == 1:
            # Arc in bottom-right corner
            new_h = rect_h / PHI
            arc_rect = QtCore.QRectF(x + rect_w - (rect_h - new_h) * 2, y + new_h, (rect_h - new_h) * 2, (rect_h - new_h) * 2)
            path.arcMoveTo(arc_rect, 180)
            path.arcTo(arc_rect, 180, 90)
            y = y + new_h
            rect_h = rect_h - new_h
        elif rot == 2:
            # Arc in top-right corner
            new_w = rect_w / PHI
            arc_rect = QtCore.QRectF(x + new_w, y - (rect_w - new_w), (rect_w - new_w) * 2, (rect_w - new_w) * 2)
            path.arcMoveTo(arc_rect, 270)
            path.arcTo(arc_rect, 270, 90)
            x = x + new_w
            rect_w = rect_w - new_w
        else:  # rot == 3
            # Arc in top-left corner
            new_h = rect_h / PHI
            arc_rect = QtCore.QRectF(x - (rect_h - new_h), y, (rect_h - new_h) * 2, (rect_h - new_h) * 2)
            path.arcMoveTo(arc_rect, 0)
            path.arcTo(arc_rect, 0, 90)
            rect_h = new_h

    painter.drawPath(path)
