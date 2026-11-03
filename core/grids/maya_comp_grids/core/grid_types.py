# -*- coding: utf-8 -*-
"""Grid type definitions and constants."""

from __future__ import absolute_import, division, print_function


class GridType(object):
    """Enum-like class for grid types. Compatible with Python 2.7."""

    OFF = "off"
    THIRDS = "thirds"
    GOLDEN_PHI = "golden_phi"
    GOLDEN_SPIRAL = "golden_spiral"
    DIAGONALS = "diagonals"
    GOLDEN_TRIANGLES = "golden_triangles"
    SQUARE_4 = "square_4"
    SQUARE_6 = "square_6"
    SQUARE_8 = "square_8"
    CENTER_CROSS = "center_cross"
    SAFE_ACTION = "safe_action"
    SAFE_TITLE = "safe_title"
    SAFE_BOTH = "safe_both"

    @classmethod
    def all_types(cls):
        """Return list of all grid types in display order."""
        return [
            cls.OFF,
            cls.THIRDS,
            cls.GOLDEN_PHI,
            cls.GOLDEN_SPIRAL,
            cls.DIAGONALS,
            cls.GOLDEN_TRIANGLES,
            cls.SQUARE_4,
            cls.SQUARE_6,
            cls.SQUARE_8,
            cls.CENTER_CROSS,
            cls.SAFE_ACTION,
            cls.SAFE_TITLE,
            cls.SAFE_BOTH,
        ]


class SpiralOrientation(object):
    """Orientation options for Golden Spiral."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"

    @classmethod
    def all_orientations(cls):
        return [cls.TOP_LEFT, cls.TOP_RIGHT, cls.BOTTOM_LEFT, cls.BOTTOM_RIGHT]


class TrianglesOrientation(object):
    """Orientation options for Golden Triangles."""

    FORWARD = "forward"
    BACKWARD = "backward"

    @classmethod
    def all_orientations(cls):
        return [cls.FORWARD, cls.BACKWARD]


GRID_DISPLAY_NAMES = {
    GridType.OFF: "Off",
    GridType.THIRDS: "Rule of Thirds",
    GridType.GOLDEN_PHI: "Golden Ratio",
    GridType.GOLDEN_SPIRAL: "Golden Spiral",
    GridType.DIAGONALS: "Diagonal Method",
    GridType.GOLDEN_TRIANGLES: "Golden Triangles",
    GridType.SQUARE_4: "Square Grid 4x4",
    GridType.SQUARE_6: "Square Grid 6x6",
    GridType.SQUARE_8: "Square Grid 8x8",
    GridType.CENTER_CROSS: "Center Cross",
    GridType.SAFE_ACTION: "Safe Action (93%)",
    GridType.SAFE_TITLE: "Safe Title (90%)",
    GridType.SAFE_BOTH: "Safe Both",
}

SPIRAL_DISPLAY_NAMES = {
    SpiralOrientation.TOP_LEFT: "Top-Left",
    SpiralOrientation.TOP_RIGHT: "Top-Right",
    SpiralOrientation.BOTTOM_LEFT: "Bottom-Left",
    SpiralOrientation.BOTTOM_RIGHT: "Bottom-Right",
}

TRIANGLES_DISPLAY_NAMES = {
    TrianglesOrientation.FORWARD: "Forward (/)",
    TrianglesOrientation.BACKWARD: "Backward (\\)",
}

# Mathematical constants
PHI = 1.6180339887498948482
GOLDEN_RATIO = 1.0 / PHI  # ~0.618
GOLDEN_RATIO_COMP = 1.0 - GOLDEN_RATIO  # ~0.382

ACTION_SAFE_MARGIN = 0.93
TITLE_SAFE_MARGIN = 0.90
