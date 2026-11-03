# -*- coding: utf-8 -*-
"""
Composition Grids Launcher for Maya

Place this file and the 'maya_comp_grids' folder in your Maya scripts directory:
  Windows: C:\\Users\\<USERNAME>\\Documents\\maya\\<VERSION>\\scripts\\
  macOS:   /Users/<USERNAME>/Library/Preferences/Autodesk/maya/<VERSION>/scripts/
  Linux:   /home/<USERNAME>/maya/<VERSION>/scripts/

Usage in Maya Script Editor (Python):
  import comp_grids_launcher
  comp_grids_launcher.show()
"""

from __future__ import absolute_import, division, print_function

import sys
import os


def _add_project_path():
    """Add scripts path to sys.path if not already present."""
    scripts_path = os.path.dirname(os.path.abspath(__file__))

    if scripts_path in sys.path:
        sys.path.remove(scripts_path)
    sys.path.insert(0, scripts_path)


def show():
    """Show Composition Grids window."""
    _add_project_path()

    # Force reload for development
    modules_to_reload = [m for m in sys.modules.keys() if m.startswith('maya_comp_grids')]
    for mod_name in modules_to_reload:
        del sys.modules[mod_name]

    import maya_comp_grids
    return maya_comp_grids.show()


if __name__ == "__main__":
    show()
