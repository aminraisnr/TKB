# -*- coding: utf-8 -*-
"""Grid manager - handles grid state per camera using NURBS curves."""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds

from maya_comp_grids.core.grid_types import (
    GridType, SpiralOrientation, TrianglesOrientation
)
from maya_comp_grids.core import nurbs_grid_builder as builder

GRID_PREFIX = "_compGrid"


class CameraGridState(object):
    """Stores grid settings for a single camera."""

    def __init__(self, camera_name):
        self.camera_name = camera_name
        self.grid_type = GridType.OFF
        self.spiral_orientation = SpiralOrientation.TOP_LEFT
        self.triangles_orientation = TrianglesOrientation.FORWARD
        self.enabled = False
        self.color = (1.0, 1.0, 1.0)
        self.opacity = 1.0
        self.line_width = 1.0
        self.grid_group = None
        self.curves = []


class GridManager(object):
    """
    Singleton manager for composition grids across all cameras.
    Uses NURBS curves for vector-quality display.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._camera_states = {}

    def get_camera_state(self, camera_name):
        """Get or create grid state for camera."""
        if camera_name not in self._camera_states:
            self._camera_states[camera_name] = CameraGridState(camera_name)
        return self._camera_states[camera_name]

    def apply_grid(self, camera_name, grid_type, spiral_orient=None, triangles_orient=None,
                   color=(1.0, 1.0, 1.0), opacity=1.0, line_width=1.0):
        """Apply grid to camera."""
        state = self.get_camera_state(camera_name)
        state.grid_type = grid_type
        state.spiral_orientation = spiral_orient or SpiralOrientation.TOP_LEFT
        state.triangles_orientation = triangles_orient or TrianglesOrientation.FORWARD
        state.color = color
        state.opacity = opacity
        state.line_width = line_width
        state.enabled = (grid_type != GridType.OFF)

        self._remove_grid(camera_name)

        if state.enabled:
            self._create_grid(camera_name, state)

    def remove_grid(self, camera_name):
        """Remove grid from camera."""
        self._remove_grid(camera_name)
        if camera_name in self._camera_states:
            self._camera_states[camera_name].enabled = False
            self._camera_states[camera_name].grid_type = GridType.OFF

    def _get_grid_prefix(self, camera_name):
        """Get grid prefix for camera."""
        short_name = camera_name.split("|")[-1].split(":")[-1]
        return short_name + GRID_PREFIX

    def _remove_grid(self, camera_name):
        """Remove existing grid for camera."""
        prefix = self._get_grid_prefix(camera_name)
        group_name = prefix + "_grp"

        # Try to find grid group by exact name first
        if cmds.objExists(group_name):
            cmds.delete(group_name)
        else:
            # Search for grid group as child of camera or anywhere in scene
            found = cmds.ls("*" + GRID_PREFIX + "_grp", long=True)
            for grp in found:
                # Check if this grid belongs to this camera
                parent = cmds.listRelatives(grp, parent=True, fullPath=True)
                if parent and camera_name in parent[0]:
                    cmds.delete(grp)
                    break
                # Also check by name prefix
                if grp.endswith(group_name) or group_name in grp:
                    cmds.delete(grp)
                    break

        # Restore camera visibility to hidden
        if cmds.objExists(camera_name):
            try:
                cmds.setAttr(camera_name + ".visibility", lock=False)
                cmds.setAttr(camera_name + ".visibility", 0)
            except Exception:
                pass

        # Clear state
        state = self._camera_states.get(camera_name)
        if state:
            state.grid_group = None
            state.curves = []

    def _create_grid(self, camera_name, state):
        """Create grid using NURBS curves."""
        camera_shape = self._get_camera_shape(camera_name)
        if not camera_shape:
            cmds.warning("Cannot find camera shape for: {}".format(camera_name))
            return

        prefix = self._get_grid_prefix(camera_name)
        grid_type = state.grid_type
        color = state.color
        curves = []

        # Create appropriate grid type
        if grid_type == GridType.GOLDEN_SPIRAL:
            curves = builder.create_golden_spiral_curves(
                camera_shape, prefix, color=color,
                orientation=state.spiral_orientation
            )
        elif grid_type == GridType.THIRDS:
            curves = builder.create_thirds_curves(
                camera_shape, prefix, color=color
            )
        elif grid_type == GridType.GOLDEN_PHI:
            curves = builder.create_phi_curves(
                camera_shape, prefix, color=color
            )
        elif grid_type == GridType.CENTER_CROSS:
            curves = builder.create_center_cross_curves(
                camera_shape, prefix, color=color
            )
        elif grid_type == GridType.DIAGONALS:
            curves = builder.create_diagonals_curves(
                camera_shape, prefix, color=color
            )
        elif grid_type == GridType.GOLDEN_TRIANGLES:
            curves = self._create_triangles_curves(
                camera_shape, prefix, color, state.triangles_orientation
            )
        elif grid_type == GridType.SQUARE_4:
            curves = self._create_square_grid_curves(camera_shape, prefix, color, 4)
        elif grid_type == GridType.SQUARE_6:
            curves = self._create_square_grid_curves(camera_shape, prefix, color, 6)
        elif grid_type == GridType.SQUARE_8:
            curves = self._create_square_grid_curves(camera_shape, prefix, color, 8)
        elif grid_type == GridType.SAFE_ACTION:
            curves = self._create_safe_frame_curves(camera_shape, prefix, color, 0.9)
        elif grid_type == GridType.SAFE_TITLE:
            curves = self._create_safe_frame_curves(camera_shape, prefix, color, 0.8)
        elif grid_type == GridType.SAFE_BOTH:
            curves = self._create_safe_both_curves(camera_shape, prefix, color)

        if curves:
            state.grid_group = curves[0]
            state.curves = curves
            # Ensure camera transform is visible so grid is visible
            cmds.setAttr(camera_name + ".visibility", lock=False)
            cmds.setAttr(camera_name + ".visibility", 1)

        # Apply opacity
        self._apply_opacity(state)

    def _create_triangles_curves(self, camera_shape, prefix, color, orientation):
        """Create golden triangles grid."""
        camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

        depth = 100.0
        half_width, half_height = builder._get_frame_dimensions(camera_shape, depth)

        group_name = prefix + "_grp"
        if cmds.objExists(group_name):
            cmds.delete(group_name)

        grid_group = cmds.group(empty=True, name=group_name)
        created_curves = []

        z = -depth

        if orientation == TrianglesOrientation.BACKWARD:
            # Main diagonal top-left to bottom-right
            diag = cmds.curve(name=prefix + "_diag", degree=1,
                             point=[(-half_width, half_height, z), (half_width, -half_height, z)])
            created_curves.append(diag)

            # Perpendiculars from corners to main diagonal
            # From top-right corner
            px1, py1 = self._perp_foot(half_width, half_height, -half_width, half_height, half_width, -half_height)
            perp1 = cmds.curve(name=prefix + "_perp1", degree=1,
                              point=[(half_width, half_height, z), (px1, py1, z)])
            created_curves.append(perp1)

            # From bottom-left corner
            px2, py2 = self._perp_foot(-half_width, -half_height, -half_width, half_height, half_width, -half_height)
            perp2 = cmds.curve(name=prefix + "_perp2", degree=1,
                              point=[(-half_width, -half_height, z), (px2, py2, z)])
            created_curves.append(perp2)
        else:
            # Main diagonal top-right to bottom-left
            diag = cmds.curve(name=prefix + "_diag", degree=1,
                             point=[(half_width, half_height, z), (-half_width, -half_height, z)])
            created_curves.append(diag)

            # From top-left corner
            px1, py1 = self._perp_foot(-half_width, half_height, half_width, half_height, -half_width, -half_height)
            perp1 = cmds.curve(name=prefix + "_perp1", degree=1,
                              point=[(-half_width, half_height, z), (px1, py1, z)])
            created_curves.append(perp1)

            # From bottom-right corner
            px2, py2 = self._perp_foot(half_width, -half_height, half_width, half_height, -half_width, -half_height)
            perp2 = cmds.curve(name=prefix + "_perp2", degree=1,
                              point=[(half_width, -half_height, z), (px2, py2, z)])
            created_curves.append(perp2)

        for curve in created_curves:
            cmds.parent(curve, grid_group)

        cmds.parent(grid_group, camera_transform)
        cmds.setAttr(grid_group + ".translate", 0, 0, 0)
        cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
        cmds.setAttr(grid_group + ".scale", 1, 1, 1)
        cmds.setAttr(grid_group + ".visibility", lock=False)
        cmds.setAttr(grid_group + ".visibility", 1)

        self._set_curves_color(created_curves, color)

        return [grid_group] + created_curves

    def _perp_foot(self, px, py, x1, y1, x2, y2):
        """Calculate perpendicular foot from point to line."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return x1, y1
        t = ((px - x1) * dx + (py - y1) * dy) / float(dx * dx + dy * dy)
        return x1 + t * dx, y1 + t * dy

    def _create_square_grid_curves(self, camera_shape, prefix, color, divisions):
        """Create square grid with given divisions."""
        camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

        depth = 100.0
        half_width, half_height = builder._get_frame_dimensions(camera_shape, depth)

        group_name = prefix + "_grp"
        if cmds.objExists(group_name):
            cmds.delete(group_name)

        grid_group = cmds.group(empty=True, name=group_name)
        created_curves = []
        z = -depth

        # Vertical lines
        for i in range(1, divisions):
            x = -half_width + (2 * half_width) * i / float(divisions)
            line = cmds.curve(name=prefix + "_v" + str(i), degree=1,
                             point=[(x, -half_height, z), (x, half_height, z)])
            created_curves.append(line)
            cmds.parent(line, grid_group)

        # Horizontal lines
        for i in range(1, divisions):
            y = -half_height + (2 * half_height) * i / float(divisions)
            line = cmds.curve(name=prefix + "_h" + str(i), degree=1,
                             point=[(-half_width, y, z), (half_width, y, z)])
            created_curves.append(line)
            cmds.parent(line, grid_group)

        cmds.parent(grid_group, camera_transform)
        cmds.setAttr(grid_group + ".translate", 0, 0, 0)
        cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
        cmds.setAttr(grid_group + ".scale", 1, 1, 1)
        cmds.setAttr(grid_group + ".visibility", lock=False)
        cmds.setAttr(grid_group + ".visibility", 1)

        self._set_curves_color(created_curves, color)

        return [grid_group] + created_curves

    def _create_safe_frame_curves(self, camera_shape, prefix, color, margin):
        """Create safe frame rectangle."""
        camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

        depth = 100.0
        half_width, half_height = builder._get_frame_dimensions(camera_shape, depth)

        group_name = prefix + "_grp"
        if cmds.objExists(group_name):
            cmds.delete(group_name)

        grid_group = cmds.group(empty=True, name=group_name)
        z = -depth

        # Safe frame rectangle
        sw = half_width * margin
        sh = half_height * margin

        rect = cmds.curve(name=prefix + "_frame", degree=1,
                         point=[(-sw, -sh, z), (sw, -sh, z), (sw, sh, z), (-sw, sh, z), (-sw, -sh, z)])

        cmds.parent(rect, grid_group)
        cmds.parent(grid_group, camera_transform)
        cmds.setAttr(grid_group + ".translate", 0, 0, 0)
        cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
        cmds.setAttr(grid_group + ".scale", 1, 1, 1)
        cmds.setAttr(grid_group + ".visibility", lock=False)
        cmds.setAttr(grid_group + ".visibility", 1)

        self._set_curves_color([rect], color)

        return [grid_group, rect]

    def _create_safe_both_curves(self, camera_shape, prefix, color):
        """Create both action and title safe frames."""
        camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

        depth = 100.0
        half_width, half_height = builder._get_frame_dimensions(camera_shape, depth)

        group_name = prefix + "_grp"
        if cmds.objExists(group_name):
            cmds.delete(group_name)

        grid_group = cmds.group(empty=True, name=group_name)
        created_curves = []
        z = -depth

        # Action safe (90%)
        sw1 = half_width * 0.9
        sh1 = half_height * 0.9
        rect1 = cmds.curve(name=prefix + "_action", degree=1,
                          point=[(-sw1, -sh1, z), (sw1, -sh1, z), (sw1, sh1, z), (-sw1, sh1, z), (-sw1, -sh1, z)])
        created_curves.append(rect1)

        # Title safe (80%)
        sw2 = half_width * 0.8
        sh2 = half_height * 0.8
        rect2 = cmds.curve(name=prefix + "_title", degree=1,
                          point=[(-sw2, -sh2, z), (sw2, -sh2, z), (sw2, sh2, z), (-sw2, sh2, z), (-sw2, -sh2, z)])
        created_curves.append(rect2)

        for curve in created_curves:
            cmds.parent(curve, grid_group)

        cmds.parent(grid_group, camera_transform)
        cmds.setAttr(grid_group + ".translate", 0, 0, 0)
        cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
        cmds.setAttr(grid_group + ".scale", 1, 1, 1)
        cmds.setAttr(grid_group + ".visibility", lock=False)
        cmds.setAttr(grid_group + ".visibility", 1)

        self._set_curves_color(created_curves, color)

        return [grid_group] + created_curves

    def _set_curves_color(self, curves, color):
        """Set override color for curves."""
        r, g, b = color

        for curve in curves:
            shapes = cmds.listRelatives(curve, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(shape + ".overrideEnabled", 1)
                cmds.setAttr(shape + ".overrideRGBColors", 1)
                cmds.setAttr(shape + ".overrideColorR", r)
                cmds.setAttr(shape + ".overrideColorG", g)
                cmds.setAttr(shape + ".overrideColorB", b)

    def _apply_opacity(self, state):
        """Apply opacity to curves (not fully supported, adjusts visibility)."""
        # NURBS curves don't have true opacity, but we can simulate with color brightness
        # or use transparency in viewport 2.0
        pass

    def _get_camera_shape(self, camera_name):
        """Get camera shape from transform."""
        if cmds.objectType(camera_name) == "camera":
            return camera_name

        shapes = cmds.listRelatives(camera_name, shapes=True, type="camera")
        if shapes:
            return shapes[0]
        return None

    def get_all_cameras(self):
        """Get list of all cameras in the scene."""
        cameras = cmds.ls(type="camera", long=True) or []
        camera_transforms = []

        for cam in cameras:
            parent = cmds.listRelatives(cam, parent=True, fullPath=True)
            if parent:
                camera_transforms.append(parent[0])

        return camera_transforms

    def update_opacity(self, camera_name, opacity):
        """Update opacity for camera grid."""
        state = self._camera_states.get(camera_name)
        if state:
            state.opacity = opacity
            # NURBS curves don't support opacity directly

    def update_color(self, camera_name, color):
        """Update color for camera grid in realtime."""
        state = self._camera_states.get(camera_name)
        if not state or not state.enabled:
            return

        state.color = color

        # Update color on all curves
        for curve in state.curves:
            if curve and cmds.objExists(curve):
                shapes = cmds.listRelatives(curve, shapes=True) or []
                for shape in shapes:
                    if cmds.objExists(shape):
                        cmds.setAttr(shape + ".overrideColorR", color[0])
                        cmds.setAttr(shape + ".overrideColorG", color[1])
                        cmds.setAttr(shape + ".overrideColorB", color[2])

    def cleanup(self):
        """Remove all grids and reset state."""
        for camera_name in list(self._camera_states.keys()):
            self._remove_grid(camera_name)
        self._camera_states.clear()
