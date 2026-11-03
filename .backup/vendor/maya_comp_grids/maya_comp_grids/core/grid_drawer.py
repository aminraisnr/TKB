# -*- coding: utf-8 -*-
"""Grid drawing functions for Maya viewports."""

from __future__ import absolute_import, division, print_function

from maya_comp_grids.core.grid_types import (
    GridType, SpiralOrientation, TrianglesOrientation,
    GOLDEN_RATIO, GOLDEN_RATIO_COMP, ACTION_SAFE_MARGIN, TITLE_SAFE_MARGIN, PHI
)


def get_grid_lines(grid_type, width, height, spiral_orient=None, triangles_orient=None):
    """
    Calculate grid lines for given dimensions.

    Args:
        grid_type: GridType value
        width: Frame width
        height: Frame height
        spiral_orient: SpiralOrientation value (for golden spiral)
        triangles_orient: TrianglesOrientation value (for golden triangles)

    Returns:
        List of line tuples: [(x1, y1, x2, y2), ...]
    """
    if grid_type == GridType.OFF:
        return []
    elif grid_type == GridType.THIRDS:
        return _get_thirds_lines(width, height)
    elif grid_type == GridType.GOLDEN_PHI:
        return _get_golden_phi_lines(width, height)
    elif grid_type == GridType.DIAGONALS:
        return _get_diagonal_lines(width, height)
    elif grid_type == GridType.GOLDEN_TRIANGLES:
        return _get_golden_triangles_lines(width, height, triangles_orient)
    elif grid_type == GridType.SQUARE_4:
        return _get_square_grid_lines(width, height, 4)
    elif grid_type == GridType.SQUARE_6:
        return _get_square_grid_lines(width, height, 6)
    elif grid_type == GridType.SQUARE_8:
        return _get_square_grid_lines(width, height, 8)
    elif grid_type == GridType.CENTER_CROSS:
        return _get_center_cross_lines(width, height)
    elif grid_type == GridType.SAFE_ACTION:
        return _get_safe_frame_lines(width, height, ACTION_SAFE_MARGIN)
    elif grid_type == GridType.SAFE_TITLE:
        return _get_safe_frame_lines(width, height, TITLE_SAFE_MARGIN)
    elif grid_type == GridType.SAFE_BOTH:
        return (_get_safe_frame_lines(width, height, ACTION_SAFE_MARGIN) +
                _get_safe_frame_lines(width, height, TITLE_SAFE_MARGIN))
    elif grid_type == GridType.GOLDEN_SPIRAL:
        return _get_golden_spiral_data(width, height, spiral_orient)

    return []


def _get_thirds_lines(width, height):
    """Rule of thirds: 3x3 grid."""
    lines = []
    third_w = width / 3.0
    third_h = height / 3.0

    # Vertical lines
    lines.append((third_w, 0, third_w, height))
    lines.append((2 * third_w, 0, 2 * third_w, height))

    # Horizontal lines
    lines.append((0, third_h, width, third_h))
    lines.append((0, 2 * third_h, width, 2 * third_h))

    return lines


def _get_golden_phi_lines(width, height):
    """Golden ratio grid using phi proportions."""
    lines = []

    # Vertical lines at golden ratio positions
    lines.append((width * GOLDEN_RATIO_COMP, 0, width * GOLDEN_RATIO_COMP, height))
    lines.append((width * GOLDEN_RATIO, 0, width * GOLDEN_RATIO, height))

    # Horizontal lines at golden ratio positions
    lines.append((0, height * GOLDEN_RATIO_COMP, width, height * GOLDEN_RATIO_COMP))
    lines.append((0, height * GOLDEN_RATIO, width, height * GOLDEN_RATIO))

    return lines


def _get_diagonal_lines(width, height):
    """Two diagonals from corner to corner."""
    return [
        (0, 0, width, height),
        (width, 0, 0, height),
    ]


def _get_golden_triangles_lines(width, height, orientation=None):
    """Golden triangles: main diagonal + perpendiculars from other corners."""
    if orientation is None:
        orientation = TrianglesOrientation.FORWARD

    lines = []

    if orientation == TrianglesOrientation.FORWARD:
        # Main diagonal from top-left to bottom-right
        lines.append((0, 0, width, height))
        # Perpendicular from top-right
        px1, py1 = _perpendicular_foot(width, 0, 0, 0, width, height)
        lines.append((width, 0, px1, py1))
        # Perpendicular from bottom-left
        px2, py2 = _perpendicular_foot(0, height, 0, 0, width, height)
        lines.append((0, height, px2, py2))
    else:
        # Main diagonal from top-right to bottom-left
        lines.append((width, 0, 0, height))
        # Perpendicular from top-left
        px1, py1 = _perpendicular_foot(0, 0, width, 0, 0, height)
        lines.append((0, 0, px1, py1))
        # Perpendicular from bottom-right
        px2, py2 = _perpendicular_foot(width, height, width, 0, 0, height)
        lines.append((width, height, px2, py2))

    return lines


def _perpendicular_foot(px, py, x1, y1, x2, y2):
    """Calculate the foot of perpendicular from point (px, py) to line (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return x1, y1

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)

    foot_x = x1 + t * dx
    foot_y = y1 + t * dy

    return foot_x, foot_y


def _get_square_grid_lines(width, height, divisions):
    """Square grid with N x N divisions."""
    lines = []

    step_w = width / float(divisions)
    step_h = height / float(divisions)

    # Vertical lines
    for i in range(1, divisions):
        x = i * step_w
        lines.append((x, 0, x, height))

    # Horizontal lines
    for i in range(1, divisions):
        y = i * step_h
        lines.append((0, y, width, y))

    return lines


def _get_center_cross_lines(width, height):
    """Center cross: one vertical + one horizontal through center."""
    cx = width / 2.0
    cy = height / 2.0

    return [
        (cx, 0, cx, height),
        (0, cy, width, cy),
    ]


def _get_safe_frame_lines(width, height, margin):
    """Safe frame rectangle at given margin percentage."""
    offset_x = width * (1.0 - margin) / 2.0
    offset_y = height * (1.0 - margin) / 2.0

    x1 = offset_x
    y1 = offset_y
    x2 = width - offset_x
    y2 = height - offset_y

    return [
        (x1, y1, x2, y1),  # Top
        (x2, y1, x2, y2),  # Right
        (x2, y2, x1, y2),  # Bottom
        (x1, y2, x1, y1),  # Left
    ]


def _get_golden_spiral_data(width, height, orientation=None):
    """
    Calculate golden spiral arc data.
    Returns list of arc definitions for drawing.

    For golden spiral we return special data structure:
    [("arc", cx, cy, radius, start_angle, sweep_angle), ...]
    """
    if orientation is None:
        orientation = SpiralOrientation.TOP_LEFT

    arcs = []

    # Determine the shorter side to fit golden rectangles
    if width > height:
        base_size = height
    else:
        base_size = width

    # Starting rectangle dimensions
    rect_w = width
    rect_h = height

    # Starting position based on orientation
    if orientation == SpiralOrientation.TOP_LEFT:
        x, y = 0, 0
        angles = [180, 270, 0, 90]  # Rotation sequence
        flip_h, flip_v = False, False
    elif orientation == SpiralOrientation.TOP_RIGHT:
        x, y = width, 0
        angles = [270, 180, 90, 0]
        flip_h, flip_v = True, False
    elif orientation == SpiralOrientation.BOTTOM_LEFT:
        x, y = 0, height
        angles = [90, 0, 270, 180]
        flip_h, flip_v = False, True
    else:  # BOTTOM_RIGHT
        x, y = width, height
        angles = [0, 90, 180, 270]
        flip_h, flip_v = True, True

    # Generate spiral arcs (4-5 iterations is usually enough)
    iterations = 6
    current_size = max(width, height)

    for i in range(iterations):
        if current_size < 1:
            break

        radius = current_size / PHI
        start_angle = angles[i % 4]

        arcs.append(("arc", x, y, radius, start_angle, 90))

        # Move to next position and shrink
        current_size = current_size / PHI

    return arcs
