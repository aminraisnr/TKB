# -*- coding: utf-8 -*-
import maya.cmds as cmds

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui


class AnimBotTweenSliderWidget(QtWidgets.QWidget):
    """Interactive Multi-Mode Tween Slider yang diperluas mendukung Overshoot (-150% s.d. 150%)."""
    # ... isi class kamu yang sudah benar di atas ...
    
    def __init__(self, callback=None, cache_func=None, on_release_func=None, parent=None):
        super(AnimBotTweenSliderWidget, self).__init__(parent)
        self.callback = callback
        self.cache_func = cache_func
        self.on_release_func = on_release_func
        self.setFixedSize(160, 28)
        self.setMouseTracking(True)
        
        self.min_val = -150.0 
        self.max_val = 150.0
        self.value = 0.0 
        self.is_dragging = False
        self._undo_chunk_open = False
        self.cache = {}
        
        self.mode = "blend_neighbors"
        self.mode_label = "TW"

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        
        act_tw = menu.addAction("Tween / Push-Pull (TW/BN)")
        act_ease = menu.addAction("Ease In / Ease Out (EB/EF)")
        act_def = menu.addAction("Blend to Default (DF)")
        menu.addSeparator()
        act_prev = menu.addAction("Blend to Prev Frame (PRV)")
        act_next = menu.addAction("Blend to Next Frame (NXT)")

        action = menu.exec_(self.mapToGlobal(pos))
        if action == act_tw:
            self.mode = "blend_neighbors"
            self.mode_label = "TW"
        elif action == act_ease:
            self.mode = "ease"
            self.mode_label = "EB"
        elif action == act_def:
            self.mode = "default"
            self.mode_label = "DF"
        elif action == act_prev:
            self.mode = "prev_frame"
            self.mode_label = "PRV"
        elif action == act_next:
            self.mode = "next_frame"
            self.mode_label = "NXT"

        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        cy = height / 2.0

        margin = 12
        track_left = margin
        track_right = width - margin
        track_width = track_right - track_left

        dot_color = QtGui.QColor("#e5a823" if self.is_dragging else "#8a8e99")
        dash_color = QtGui.QColor("#c54b27")

        painter.setPen(QtCore.Qt.NoPen)

        painter.setBrush(dot_color)
        painter.drawRect(QtCore.QRectF(track_left - 3, cy - 3, 5, 5))
        painter.drawRect(QtCore.QRectF(track_right - 2, cy - 3, 5, 5))

        num_segments = 14
        accent_indices = [0, 7, 14]
        for i in range(num_segments + 1):
            x = track_left + (i / float(num_segments)) * track_width
            if i in accent_indices:
                painter.setBrush(dash_color)
                painter.drawRect(QtCore.QRectF(x - 2, cy - 1, 4, 2))
            else:
                painter.setBrush(dot_color)
                painter.drawRect(QtCore.QRectF(x - 1, cy - 1, 2, 2))

        val_ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = track_left + (val_ratio * track_width)
        
        handle_w = 24
        handle_h = 22
        handle_rect = QtCore.QRectF(
            handle_x - (handle_w / 2.0),
            cy - (handle_h / 2.0),
            handle_w,
            handle_h
        )

        if self.value < 0 or self.value > 100:
            bg_handle = QtGui.QColor("#d93829")
        elif self.value <= 50:
            bg_handle = QtGui.QColor("#e5a823")
        else:
            bg_handle = QtGui.QColor("#e58c23")

        painter.setBrush(bg_handle)
        painter.setPen(QtGui.QPen(QtGui.QColor("#1a1c20"), 1))
        painter.drawRoundedRect(handle_rect, 4, 4)

        painter.setPen(QtGui.QColor("#ffffff" if (self.value < 0 or self.value > 100) else "#141518"))
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        display_text = "{:.0f}".format(self.value) if self.is_dragging else self.mode_label
        painter.drawText(handle_rect, QtCore.Qt.AlignCenter, display_text)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            try:
                cmds.undoInfo(openChunk=True, chunkName="TKB_TweenMachine")
                self._undo_chunk_open = True
                self.is_dragging = True

                if self.cache_func:
                    self.cache = self.cache_func() or {}

                pos_x = event.position().x() if hasattr(event, 'position') else event.x()
                self._update_value_from_pos(pos_x)
            except Exception as exc:
                self._finish_drag()
                cmds.warning("TKB: Tween slider gagal: {}".format(exc))

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            try:
                pos_x = event.position().x() if hasattr(event, 'position') else event.x()
                self._update_value_from_pos(pos_x)
            except Exception as exc:
                self._finish_drag()
                cmds.warning("TKB: Tween slider gagal: {}".format(exc))

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.is_dragging:
            try:
                if self.on_release_func:
                    self.on_release_func()
            except Exception as exc:
                cmds.warning("TKB: Tween slider gagal saat dilepas: {}".format(exc))
            finally:
                self._finish_drag()

    def _finish_drag(self):
        self.is_dragging = False
        self.value = 0.0
        self.cache = {}

        label_map = {
            "blend_neighbors": "TW",
            "ease": "EB",
            "default": "DF",
            "prev_frame": "PRV",
            "next_frame": "NXT"
        }
        self.mode_label = label_map.get(self.mode, "TW")

        if self._undo_chunk_open:
            self._undo_chunk_open = False
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception as exc:
                cmds.warning("TKB: Gagal menutup undo chunk tween: {}".format(exc))
        self.update()

    def _update_value_from_pos(self, x_pos):
        margin = 12
        track_width = self.width() - (margin * 2)
        rel_x = max(0, min(track_width, x_pos - margin))
        
        norm_ratio = rel_x / float(track_width)
        self.value = self.min_val + (norm_ratio * (self.max_val - self.min_val))

        if self.mode == "blend_neighbors":
            if self.value < 0:
                self.mode_label = "PP-"
            elif self.value > 100:
                self.mode_label = "PP+"
            elif self.value <= 50:
                self.mode_label = "TW"
            else:
                self.mode_label = "BN"
        elif self.mode == "ease":
            self.mode_label = "EB" if self.value <= 50 else "EF"
        elif self.mode == "default":
            self.mode_label = "DF"
        elif self.mode == "prev_frame":
            self.mode_label = "PRV"
        elif self.mode == "next_frame":
            self.mode_label = "NXT"

        self.update()

        if self.callback:
            self.callback(self.value, self.mode, self.cache)