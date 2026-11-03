# -*- coding: utf-8 -*-
"""Build composition grids using NURBS curves for vector-quality display."""

from __future__ import absolute_import, division, print_function

import math
import maya.cmds as cmds

PHI = (1.0 + math.sqrt(5.0)) / 2.0  # Golden ratio ~1.618


def _get_frame_dimensions(camera_shape, depth=10.0):
    """
    Calculate frame dimensions based on render resolution aspect ratio.
    Returns (half_width, half_height) at given depth from camera.
    """
    # Get render resolution for correct aspect ratio
    render_width = cmds.getAttr("defaultResolution.width")
    render_height = cmds.getAttr("defaultResolution.height")
    render_aspect = float(render_width) / float(render_height)

    # Check if orthographic camera
    is_ortho = cmds.getAttr(camera_shape + ".orthographic")

    if is_ortho:
        # For orthographic cameras, use orthographicWidth
        ortho_width = cmds.getAttr(camera_shape + ".orthographicWidth")
        half_width = ortho_width / 2.0
        half_height = half_width / render_aspect
    else:
        # Get camera parameters for perspective cameras
        focal_length = cmds.getAttr(camera_shape + ".focalLength")
        h_aperture = cmds.getAttr(camera_shape + ".horizontalFilmAperture")

        # Calculate view width at depth using horizontal aperture
        focal_inches = focal_length / 25.4
        half_width = (h_aperture / 2.0) * (depth / focal_inches)

        # Calculate height based on render aspect ratio (not film aperture)
        half_height = half_width / render_aspect

    return half_width, half_height


def create_golden_spiral_curves(camera_shape, name_prefix, color=(1.0, 1.0, 1.0),
                                 depth=10.0, num_iterations=12, orientation="top_left"):
    """
    Create golden spiral using NURBS curves attached to camera.
    Fits a golden rectangle into the frame, then builds connected quarter-circle arcs.

    Args:
        orientation: "top_left", "top_right", "bottom_left", "bottom_right"
    """
    camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

    half_width, half_height = _get_frame_dimensions(camera_shape, depth)

    created_curves = []

    group_name = name_prefix + "_grp"
    if cmds.objExists(group_name):
        cmds.delete(group_name)

    grid_group = cmds.group(empty=True, name=group_name)

    z = -depth
    frame_w = half_width * 2
    frame_h = half_height * 2

    # Draw outer rectangle (full frame)
    rect_curve = _create_rectangle(-half_width, -half_height, frame_w, frame_h, z, name_prefix + "_frame")
    created_curves.append(rect_curve)
    cmds.parent(rect_curve, grid_group)

    # Golden spiral starts from left edge, height = frame height
    # First square is on the left, side = frame_h
    # Total width of golden spiral = frame_h * PHI
    golden_h = frame_h
    golden_w = frame_h * PHI

    # If golden rectangle is wider than frame, scale it down
    if golden_w > frame_w:
        scale = frame_w / golden_w
        golden_w = frame_w
        golden_h = frame_h * scale

    # Position: align to left edge and center vertically
    golden_left = -half_width
    golden_bottom = -golden_h / 2
    golden_top = golden_h / 2

    # First square size = height of golden rectangle
    base_size = golden_h

    # Mirroring will be applied at the end via scale
    mirror_x = 1.0
    mirror_y = 1.0

    if orientation == "top_right":
        mirror_x = -1.0
    elif orientation == "bottom_left":
        mirror_y = -1.0
    elif orientation == "bottom_right":
        mirror_x = -1.0
        mirror_y = -1.0

    # Calculate all square sizes (each = previous / PHI)
    sizes = []
    s = base_size
    for _ in range(num_iterations):
        sizes.append(s)
        s = s / PHI

    # Start position (top-left of golden rectangle)
    cx = golden_left
    cy = golden_top

    for i, sq in enumerate(sizes):
        if sq < 0.0001:
            break

        phase = i % 4

        if phase == 0:
            center_x = cx + sq
            center_y = cy

            line = _create_line(center_x, cy, center_x, cy - sq, z, name_prefix + "_div_" + str(i))
            created_curves.append(line)
            cmds.parent(line, grid_group)

            arc = _create_arc_curve(center_x, center_y, sq, 180, 270, z, name_prefix + "_arc_" + str(i))
            created_curves.append(arc)
            cmds.parent(arc, grid_group)

            cx = cx + sq
            cy = cy - sq

        elif phase == 1:
            center_x = cx
            center_y = cy + sq

            line = _create_line(cx, center_y, cx + sq, center_y, z, name_prefix + "_div_" + str(i))
            created_curves.append(line)
            cmds.parent(line, grid_group)

            arc = _create_arc_curve(center_x, center_y, sq, 270, 360, z, name_prefix + "_arc_" + str(i))
            created_curves.append(arc)
            cmds.parent(arc, grid_group)

            cx = cx + sq
            cy = cy + sq

        elif phase == 2:
            center_x = cx - sq
            center_y = cy

            line = _create_line(center_x, cy, center_x, cy + sq, z, name_prefix + "_div_" + str(i))
            created_curves.append(line)
            cmds.parent(line, grid_group)

            arc = _create_arc_curve(center_x, center_y, sq, 0, 90, z, name_prefix + "_arc_" + str(i))
            created_curves.append(arc)
            cmds.parent(arc, grid_group)

            cx = cx - sq
            cy = cy + sq

        else:  # phase == 3
            center_x = cx
            center_y = cy - sq

            line = _create_line(cx, center_y, cx - sq, center_y, z, name_prefix + "_div_" + str(i))
            created_curves.append(line)
            cmds.parent(line, grid_group)

            arc = _create_arc_curve(center_x, center_y, sq, 90, 180, z, name_prefix + "_arc_" + str(i))
            created_curves.append(arc)
            cmds.parent(arc, grid_group)

            cx = cx - sq
            cy = cy - sq

    cmds.parent(grid_group, camera_transform)
    cmds.setAttr(grid_group + ".translate", 0, 0, 0)
    cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
    # Apply mirroring via scale
    cmds.setAttr(grid_group + ".scale", mirror_x, mirror_y, 1)
    cmds.setAttr(grid_group + ".visibility", lock=False)
    cmds.setAttr(grid_group + ".visibility", 1)

    _set_curves_color(created_curves, color)

    return [grid_group] + created_curves


def _create_rectangle(x, y, w, h, z, name):
    """Create a rectangle curve."""
    points = [
        (x, y, z),
        (x + w, y, z),
        (x + w, y + h, z),
        (x, y + h, z),
        (x, y, z)  # Close
    ]

    curve = cmds.curve(
        name=name,
        degree=1,
        point=points
    )
    return curve


def _create_line(x1, y1, x2, y2, z, name):
    """Create a line curve."""
    curve = cmds.curve(
        name=name,
        degree=1,
        point=[(x1, y1, z), (x2, y2, z)]
    )
    return curve


def _create_arc_curve(center_x, center_y, radius, start_angle, end_angle, depth, name):
    """Create an arc curve using points."""
    # Generate points along arc
    num_points = 24  # Smooth arc
    points = []

    angle_range = end_angle - start_angle
    for i in range(num_points + 1):
        t = i / float(num_points)
        angle = math.radians(start_angle + t * angle_range)
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        points.append((x, y, depth))

    curve = cmds.curve(
        name=name,
        degree=3,  # Cubic for smoothness
        point=points
    )
    return curve


def _set_curves_color(curves, color):
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


def create_thirds_curves(camera_shape, name_prefix, color=(1.0, 1.0, 1.0), depth=10.0):
    """Create rule of thirds grid using NURBS curves."""
    camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

    half_width, half_height = _get_frame_dimensions(camera_shape, depth)

    created_curves = []
    group_name = name_prefix + "_grp"
    if cmds.objExists(group_name):
        cmds.delete(group_name)

    grid_group = cmds.group(empty=True, name=group_name)

    # Vertical lines at 1/3 and 2/3
    x1 = -half_width + (2 * half_width) / 3.0
    x2 = -half_width + 2 * (2 * half_width) / 3.0

    line1 = _create_line(x1, -half_height, x1, half_height, -depth, name_prefix + "_v1")
    line2 = _create_line(x2, -half_height, x2, half_height, -depth, name_prefix + "_v2")

    # Horizontal lines at 1/3 and 2/3
    y1 = -half_height + (2 * half_height) / 3.0
    y2 = -half_height + 2 * (2 * half_height) / 3.0

    line3 = _create_line(-half_width, y1, half_width, y1, -depth, name_prefix + "_h1")
    line4 = _create_line(-half_width, y2, half_width, y2, -depth, name_prefix + "_h2")

    for line in [line1, line2, line3, line4]:
        created_curves.append(line)
        cmds.parent(line, grid_group)

    cmds.parent(grid_group, camera_transform)
    cmds.setAttr(grid_group + ".translate", 0, 0, 0)
    cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
    cmds.setAttr(grid_group + ".scale", 1, 1, 1)
    cmds.setAttr(grid_group + ".visibility", lock=False)
    cmds.setAttr(grid_group + ".visibility", 1)

    _set_curves_color(created_curves, color)

    return [grid_group] + created_curves


def create_phi_curves(camera_shape, name_prefix, color=(1.0, 1.0, 1.0), depth=10.0):
    """Create golden ratio (phi) grid using NURBS curves."""
    camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

    half_width, half_height = _get_frame_dimensions(camera_shape, depth)

    created_curves = []
    group_name = name_prefix + "_grp"
    if cmds.objExists(group_name):
        cmds.delete(group_name)

    grid_group = cmds.group(empty=True, name=group_name)

    # Golden ratio positions: 1/phi and 1 - 1/phi
    phi_ratio = 1.0 / PHI  # ~0.618

    # Vertical lines
    x1 = -half_width + (2 * half_width) * (1 - phi_ratio)
    x2 = -half_width + (2 * half_width) * phi_ratio

    line1 = _create_line(x1, -half_height, x1, half_height, -depth, name_prefix + "_v1")
    line2 = _create_line(x2, -half_height, x2, half_height, -depth, name_prefix + "_v2")

    # Horizontal lines
    y1 = -half_height + (2 * half_height) * (1 - phi_ratio)
    y2 = -half_height + (2 * half_height) * phi_ratio

    line3 = _create_line(-half_width, y1, half_width, y1, -depth, name_prefix + "_h1")
    line4 = _create_line(-half_width, y2, half_width, y2, -depth, name_prefix + "_h2")

    for line in [line1, line2, line3, line4]:
        created_curves.append(line)
        cmds.parent(line, grid_group)

    cmds.parent(grid_group, camera_transform)
    cmds.setAttr(grid_group + ".translate", 0, 0, 0)
    cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
    cmds.setAttr(grid_group + ".scale", 1, 1, 1)
    cmds.setAttr(grid_group + ".visibility", lock=False)
    cmds.setAttr(grid_group + ".visibility", 1)

    _set_curves_color(created_curves, color)

    return [grid_group] + created_curves


def create_center_cross_curves(camera_shape, name_prefix, color=(1.0, 1.0, 1.0), depth=10.0):
    """Create center cross using NURBS curves."""
    camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

    half_width, half_height = _get_frame_dimensions(camera_shape, depth)

    created_curves = []
    group_name = name_prefix + "_grp"
    if cmds.objExists(group_name):
        cmds.delete(group_name)

    grid_group = cmds.group(empty=True, name=group_name)

    # Vertical center line
    line1 = _create_line(0, -half_height, 0, half_height, -depth, name_prefix + "_v")
    # Horizontal center line
    line2 = _create_line(-half_width, 0, half_width, 0, -depth, name_prefix + "_h")

    for line in [line1, line2]:
        created_curves.append(line)
        cmds.parent(line, grid_group)

    cmds.parent(grid_group, camera_transform)
    cmds.setAttr(grid_group + ".translate", 0, 0, 0)
    cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
    cmds.setAttr(grid_group + ".scale", 1, 1, 1)
    cmds.setAttr(grid_group + ".visibility", lock=False)
    cmds.setAttr(grid_group + ".visibility", 1)

    _set_curves_color(created_curves, color)

    return [grid_group] + created_curves


def create_diagonals_curves(camera_shape, name_prefix, color=(1.0, 1.0, 1.0), depth=10.0):
    """Create diagonal lines using NURBS curves."""
    camera_transform = cmds.listRelatives(camera_shape, parent=True, fullPath=True)[0]

    half_width, half_height = _get_frame_dimensions(camera_shape, depth)

    created_curves = []
    group_name = name_prefix + "_grp"
    if cmds.objExists(group_name):
        cmds.delete(group_name)

    grid_group = cmds.group(empty=True, name=group_name)

    # Diagonal from top-left to bottom-right
    line1 = _create_line(-half_width, half_height, half_width, -half_height, -depth, name_prefix + "_d1")
    # Diagonal from top-right to bottom-left
    line2 = _create_line(half_width, half_height, -half_width, -half_height, -depth, name_prefix + "_d2")

    for line in [line1, line2]:
        created_curves.append(line)
        cmds.parent(line, grid_group)

    cmds.parent(grid_group, camera_transform)
    cmds.setAttr(grid_group + ".translate", 0, 0, 0)
    cmds.setAttr(grid_group + ".rotate", 0, 0, 0)
    cmds.setAttr(grid_group + ".scale", 1, 1, 1)
    cmds.setAttr(grid_group + ".visibility", lock=False)
    cmds.setAttr(grid_group + ".visibility", 1)

    _set_curves_color(created_curves, color)

    return [grid_group] + created_curves


def delete_grid_curves(name_prefix):
    """Delete all curves with given prefix."""
    group_name = name_prefix + "_grp"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
