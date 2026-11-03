# -*- coding: utf-8 -*-
"""
Maya Composition Grids
A tool for displaying composition grids on Maya cameras.
Compatible with Maya 2019-2026 (Python 2.7 / Python 3.x)
"""

from __future__ import absolute_import, division, print_function

__version__ = "1.0.0"
__author__ = "emelnikov"

def show():
    """Main entry point to show the Composition Grids UI."""
    from maya_comp_grids.ui.main_window import show_window
    return show_window()
