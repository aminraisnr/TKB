# -*- coding: utf-8 -*-
"""Maya-specific utilities and compatibility helpers."""

from __future__ import absolute_import, division, print_function

import sys
import maya.cmds as cmds
from maya import OpenMayaUI as omui


def get_maya_version():
    """Get Maya version as integer (e.g., 2019, 2024)."""
    return int(cmds.about(version=True))


def is_python3():
    """Check if running Python 3."""
    return sys.version_info[0] >= 3


def get_qt_bindings():
    """
    Get appropriate Qt bindings based on Maya version.

    Returns:
        tuple: (QtWidgets, QtCore, QtGui, wrapInstance)
    """
    maya_version = get_maya_version()

    if maya_version >= 2025:
        # Maya 2025+ uses PySide6
        from PySide6 import QtWidgets, QtCore, QtGui
        from shiboken6 import wrapInstance
    elif maya_version >= 2017:
        # Maya 2017-2024 uses PySide2
        from PySide2 import QtWidgets, QtCore, QtGui
        from shiboken2 import wrapInstance
    else:
        # Maya 2016 and earlier uses PySide
        from PySide import QtGui as QtWidgets
        from PySide import QtCore, QtGui
        from shiboken import wrapInstance

    return QtWidgets, QtCore, QtGui, wrapInstance


def get_maya_main_window():
    """Get Maya main window as Qt widget."""
    QtWidgets, QtCore, QtGui, wrapInstance = get_qt_bindings()

    main_window_ptr = omui.MQtUtil.mainWindow()

    if main_window_ptr is not None:
        if is_python3():
            return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
        else:
            return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)

    return None


def get_active_camera():
    """Get camera from the active model panel."""
    panel = cmds.getPanel(withFocus=True)

    if panel and cmds.getPanel(typeOf=panel) == 'modelPanel':
        return cmds.modelPanel(panel, query=True, camera=True)

    return None


def get_camera_shape(camera_transform):
    """Get camera shape node from transform."""
    shapes = cmds.listRelatives(camera_transform, shapes=True, type='camera')
    if shapes:
        return shapes[0]
    return None
