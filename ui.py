# TKB/ui.py
import os
import sys
import re
import importlib
import importlib.util
import maya.cmds as cmds

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui

WSC_ID = "TKB_HorizontalWSC"
GLOBAL_TKB_WIDGET = None

ANIMBOT_STYLE = """
QWidget#TKB_MainWidget {
    background-color: #212328;
    border-radius: 6px;
}

QToolButton {
    background-color: #2b2e35;
    color: #e0e0e0;
    border: 1px solid #1a1c20;
    border-radius: 5px;
    padding: 3px;
    font-size: 11px;
    font-weight: bold;
}

QToolButton:hover {
    background-color: #3b404b;
    border: 1px solid #00b4d8;
}

QToolButton:pressed {
    background-color: #0081a7;
    border: 1px solid #00b4d8;
    color: #ffffff;
}

QLineEdit#NudgeAmountField {
    background-color: #2b2e35;
    color: #00b4d8;
    border: 1px solid #1a1c20;
    border-radius: 5px;
    padding: 2px;
    font-size: 11px;
    font-weight: bold;
}

QLineEdit#NudgeAmountField:focus {
    border: 1px solid #00b4d8;
    background-color: #212328;
}

QMenu {
    background-color: #212328;
    color: #e0e0e0;
    border: 1px solid #00b4d8;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 4px 16px;
    border-radius: 3px;
    font-size: 11px;
}

QMenu::item:selected {
    background-color: #0081a7;
    color: #ffffff;
}

QFrame[frameShape="4"], QFrame[frameShape="5"] {
    background-color: #383c46;
    border: none;
    width: 1px;
    margin: 3px 2px;
}
"""

class AnimBotTweenSliderWidget(QtWidgets.QWidget):
    """Interactive Multi-Mode Tween Slider (-50% s.d. 150%)."""
    
    def __init__(self, callback=None, cache_func=None, parent=None):
        super(AnimBotTweenSliderWidget, self).__init__(parent)
        self.callback = callback
        self.cache_func = cache_func
        self.setFixedSize(160, 28)
        self.setMouseTracking(True)
        
        self.min_val = -50.0
        self.max_val = 150.0
        self.value = 50.0
        self.is_dragging = False
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
        for i in range(num_segments + 1):
            x = track_left + (i / float(num_segments)) * track_width
            if i in [3, 7, 11]:
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
        painter.drawText(handle_rect, QtCore.Qt.AlignCenter, self.mode_label)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_dragging = True
            cmds.undoInfo(openChunk=True)
            
            if self.cache_func:
                self.cache = self.cache_func() or {}

            pos_x = event.position().x() if hasattr(event, 'position') else event.x()
            self._update_value_from_pos(pos_x)

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            pos_x = event.position().x() if hasattr(event, 'position') else event.x()
            self._update_value_from_pos(pos_x)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_dragging = False
            cmds.undoInfo(closeChunk=True)
            self.value = 50.0
            self.cache = {}
            
            label_map = {
                "blend_neighbors": "TW",
                "ease": "EB",
                "default": "DF",
                "prev_frame": "PRV",
                "next_frame": "NXT"
            }
            self.mode_label = label_map.get(self.mode, "TW")
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


class TKBToolbarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TKBToolbarWidget, self).__init__(parent)
        self.setObjectName("TKB_MainWidget")
        self.setStyleSheet(ANIMBOT_STYLE)
        
        self.TKB_DIR = os.path.dirname(__file__)
        self.icon_path = os.path.join(self.TKB_DIR, "icons").replace("\\", "/")
        self._tween_module = None
        
        self._init_ui()

    def _get_tween_module(self):
        if self._tween_module is None:
            folder_path = os.path.join(self.TKB_DIR, "core", "tween machine").replace("\\", "/")
            if folder_path not in sys.path:
                sys.path.insert(0, folder_path)
            
            target_file = "tweenSlider.py" if os.path.exists(os.path.join(folder_path, "tweenSlider.py")) else "tweenSlider313.py"
            file_path = os.path.join(folder_path, target_file).replace("\\", "/")
            
            module_name = "tkb_core_tween_machine"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            self._tween_module = mod
        return self._tween_module

    def _get_tween_cache(self):
        mod = self._get_tween_module()
        if mod and hasattr(mod, "get_neighbor_cache"):
            return mod.get_neighbor_cache()
        return {}

    def _on_tween_slider_drag(self, val, mode, cache=None):
        mod = self._get_tween_module()
        if not mod:
            return

        func_map = {
            "blend_neighbors": "performBlendToNeighbors",
            "ease": "performBlendToEase",
            "default": "performBlendToDefault",
            "prev_frame": "performBlendToFrame",
            "next_frame": "performBlendToFrame"
        }
        
        func_name = func_map.get(mode, "performBlendToNeighbors")
        if hasattr(mod, func_name):
            func = getattr(mod, func_name)
            kwargs = {"percent": val, "is_realtime": True, "cache": cache}
            if mode == "prev_frame":
                kwargs["target_neighbor"] = "prev"
            elif mode == "next_frame":
                kwargs["target_neighbor"] = "next"
            
            func(**kwargs)

    def _run_core_script(self, folder_name, main_file=None, func_name=None, *args, **kwargs):
        def wrapper():
            try:
                folder_path = os.path.join(self.TKB_DIR, "core", folder_name).replace("\\", "/")
                if folder_path not in sys.path:
                    sys.path.insert(0, folder_path)

                target_file = main_file
                if not target_file:
                    if os.path.exists(os.path.join(folder_path, "tweenSlider.py")):
                        target_file = "tweenSlider.py"
                    elif os.path.exists(os.path.join(folder_path, "tweenSlider313.py")):
                        target_file = "tweenSlider313.py"
                    elif os.path.exists(os.path.join(folder_path, f"{folder_name}.py")):
                        target_file = f"{folder_name}.py"

                if not target_file:
                    return

                file_path = os.path.join(folder_path, target_file).replace("\\", "/")
                module_name = f"tkb_core_{folder_name.replace(' ', '_')}"
                
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                
                if func_name and hasattr(mod, func_name):
                    func = getattr(mod, func_name)
                    return func(*args, **kwargs)
                
                for f in ["run", "show", "main", "start", "performBlendToNeighbors"]:
                    if hasattr(mod, f):
                        return getattr(mod, f)(*args, **kwargs)
            except Exception as e:
                cmds.warning(f"TKB: Gagal menjalankan {folder_name} -> {e}")
        return wrapper

    def _trigger_nudge_keys(self, direction):
        try:
            val_text = self.nudge_input.text()
            amount = float(val_text) if val_text else 1.0
        except ValueError:
            amount = 1.0

        nudge_amount = -amount if direction == "left" else amount
        self._run_core_script("nudge keys", main_file="nudge_keys.py", func_name="nudge_keys_by_amount", amount=nudge_amount)()

    def _create_nudge_widget(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        btn_left = QtWidgets.QToolButton()
        btn_left.setText("<")
        btn_left.setToolTip("Nudge Keys Backward (Mundur)")
        btn_left.setFixedSize(22, 28)
        btn_left.clicked.connect(lambda: self._trigger_nudge_keys("left"))

        self.nudge_input = QtWidgets.QLineEdit()
        self.nudge_input.setObjectName("NudgeAmountField")
        self.nudge_input.setText("10")
        self.nudge_input.setAlignment(QtCore.Qt.AlignCenter)
        self.nudge_input.setToolTip("Masukkan Jumlah Frame Pergeseran Keyframe")
        self.nudge_input.setFixedSize(32, 28)
        self.nudge_input.setValidator(QtGui.QDoubleValidator())

        btn_right = QtWidgets.QToolButton()
        btn_right.setText(">")
        btn_right.setToolTip("Nudge Keys Forward (Maju)")
        btn_right.setFixedSize(22, 28)
        btn_right.clicked.connect(lambda: self._trigger_nudge_keys("right"))

        layout.addWidget(btn_left)
        layout.addWidget(self.nudge_input)
        layout.addWidget(btn_right)

        container.setFixedWidth(80)
        return container

    def _run_overlap_helper(self):
        try:
            oh_base_path = os.path.join(self.TKB_DIR, "core", "overlap").replace("\\", "/")
            py_ver = f"{sys.version_info[0]}{sys.version_info[1]}"
            oh_version_path = os.path.join(oh_base_path, py_ver).replace("\\", "/")
            
            if not os.path.exists(oh_version_path):
                available_folders = [f for f in os.listdir(oh_base_path) if os.path.isdir(os.path.join(oh_base_path, f))]
                available_folders.sort(key=lambda x: [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', x)], reverse=True)
                if available_folders:
                    py_ver = available_folders[0]
                    oh_version_path = os.path.join(oh_base_path, py_ver).replace("\\", "/")

            if oh_version_path not in sys.path: 
                sys.path.insert(0, oh_version_path)
            if oh_base_path not in sys.path: 
                sys.path.insert(0, oh_base_path)

            for m in list(sys.modules.keys()):
                if m == "uiFile" or m.startswith("uiFile."):
                    del sys.modules[m]

            import uiFile
            importlib.reload(uiFile)
        except Exception as e:
            cmds.warning(f"TKB: Gagal menjalankan OverlapHelper -> {e}")

    def _get_icon(self, fname):
        p = os.path.join(self.icon_path, fname).replace("\\", "/")
        if os.path.exists(p) and fname:
            return QtGui.QIcon(p)
        return QtGui.QIcon()

    def _create_align_btn(self):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon("mix.png")
        
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText("ALIGN")
            
        btn.setToolTip("ALIGN (Klik kiri/kanan untuk opsi)")
        btn.setFixedSize(28, 28)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        
        menu = QtWidgets.QMenu(btn)
        menu.addAction("Align All (Current Frame)", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=True, all_keys=False))
        menu.addAction("Align Position Only", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=False, all_keys=False))
        menu.addAction("Align Rotation Only", self._run_core_script("align", func_name="align_to_last", translate=False, rotate=True, all_keys=False))
        
        menu.addSeparator()
        
        menu.addAction("⚡ Align All Keys (Multi-Frame)", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=True, all_keys=True))
        menu.addAction("⚡ Align Position All Keys", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=False, all_keys=True))
        menu.addAction("⚡ Align Rotation All Keys", self._run_core_script("align", func_name="align_to_last", translate=False, rotate=True, all_keys=True))
        
        btn.setMenu(menu)
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: menu.exec_(b.mapToGlobal(pos)))
        
        return btn

    def _create_motion_trail_btn(self):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon("motion_trail.png")
        
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText("MT")
            
        btn.setToolTip("MOTION TRAIL")
        btn.setFixedSize(28, 28)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        btn.clicked.connect(self._run_core_script("motion trail", func_name="create_motion_trail"))
        
        menu = QtWidgets.QMenu(btn)
        menu.addAction("Create Motion Trail", self._run_core_script("motion trail", func_name="create_motion_trail"))
        menu.addAction("Remove Selected Trail", self._run_core_script("motion trail", func_name="remove_motion_trail"))
        menu.addSeparator()
        menu.addAction("Clear All Trails", self._run_core_script("motion trail", func_name="clear_all_trails"))
        
        btn.setMenu(menu)
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: menu.exec_(b.mapToGlobal(pos)))
        
        return btn

    def _create_btn(self, icon_file, tooltip, func, text=""):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon(icon_file)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText(text if text else tooltip[:3].upper())
            
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        btn.clicked.connect(func)
        return btn

    def _create_separator(self):
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        return sep

    def _init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(6, 3, 6, 3)
        main_layout.setSpacing(4)
        main_layout.setAlignment(QtCore.Qt.AlignCenter)

        # --- GRUP 1: Camera Tools ---
        main_layout.addWidget(self._create_btn("cam.png", "CAM>PERSP", self._run_core_script("cam to persp", func_name="cam_to_persp_self_test")))
        main_layout.addWidget(self._create_btn("charcam.png", "CHAR>CAM", self._run_core_script("char to cam", func_name="char_to_cam_dynamic_test")))
        main_layout.addWidget(self._create_btn("grid.png", "MAYA COMP GRIDS", self._run_core_script("grids", main_file="comp_grids_launcher.py", func_name="show"), text="CG"))

        main_layout.addWidget(self._create_separator())

        # --- GRUP 2: Transform & Utility ---
        # TWEEN SLIDER HIGH PERFORMANCE
        self.tween_slider = AnimBotTweenSliderWidget(
            callback=self._on_tween_slider_drag,
            cache_func=self._get_tween_cache
        )
        self.tween_slider.setToolTip("Tween Slider (Klik Kanan untuk Mengganti Mode)")
        main_layout.addWidget(self.tween_slider)
        
        # ALIGN DAN LAIN-LAIN
        main_layout.addWidget(self._create_align_btn())
        main_layout.addWidget(self._create_btn("reset.png", "RESET", self._run_core_script("reset", func_name="reset_selected")))
        main_layout.addWidget(self._create_btn("null.png", "NULL", self._run_core_script("null", func_name="create_null")))
        main_layout.addWidget(self._create_btn("step_snap.png", "SS", self._run_core_script("step snap", func_name="ss")))
        main_layout.addWidget(self._create_btn("Remove.png", "RemoveTangent", self._run_core_script("remove parent", func_name="remove_all_constraints_from_selection")))
        main_layout.addWidget(self._create_btn("bacth.png", "anaknya dulu baru ibu", self._run_core_script("bacth parent", func_name="batch_parent_constraint_rigs")))
        main_layout.addWidget(self._create_btn("gpu.png", "GPU CACHE", self._run_core_script("gpu cache", func_name="create_gpu_cache")))
        main_layout.addWidget(self._create_nudge_widget())

        main_layout.addWidget(self._create_separator())

        # --- GRUP 3: Selection Sets ---
        main_layout.addWidget(self._create_btn("select_all.png", "SELECT ALL", self._run_core_script("select all", func_name="select_all_multi")))
        main_layout.addWidget(self._create_btn("hier.png", "CTRL SELECT", self._run_core_script("smart select", func_name="smart_select")))
        main_layout.addWidget(self._create_btn("Mata.png", "MATA SELECT", self._run_core_script("select eyes", func_name="eyeselect")))
        main_layout.addWidget(self._create_btn("Mulut.png", "MULUT SELECT", self._run_core_script("select mouth", func_name="mouthselect")))

        main_layout.addWidget(self._create_separator())

        # --- GRUP 4: Script & Engine ---
        main_layout.addWidget(self._create_btn("paie.png", "PAIE SYSTEM", self._run_core_script("copy anim")))
        main_layout.addWidget(self._create_btn("pose2shelf.png", "pose2shelf", self._run_core_script("pose2mel", func_name="pose2shelf_ui")))
        main_layout.addWidget(self._create_btn("OverlapHelperIcon.png", "OVERLAP HELPER", self._run_overlap_helper))
        main_layout.addWidget(self._create_motion_trail_btn())
        main_layout.addWidget(self._create_btn("refresh.png", "REFRESH EVAL", self._run_core_script("refresh", func_name="refresh_evaluation_mode")))


def build_tkb_ui(*args):
    global GLOBAL_TKB_WIDGET
    
    wsc_ptr = omui.MQtUtil.findControl(WSC_ID)
    if not wsc_ptr:
        return
        
    wsc_widget = wrapInstance(int(wsc_ptr), QtWidgets.QWidget)

    if wsc_widget.layout():
        old_layout = wsc_widget.layout()
        QtWidgets.QWidget().setLayout(old_layout)

    layout = QtWidgets.QVBoxLayout(wsc_widget)
    layout.setContentsMargins(0, 0, 0, 0)

    GLOBAL_TKB_WIDGET = TKBToolbarWidget(parent=wsc_widget)
    layout.addWidget(GLOBAL_TKB_WIDGET)


def UI():
    if cmds.workspaceControl(WSC_ID, exists=True):
        cmds.deleteUI(WSC_ID)

    # ---------------------------------------------------------
    # LAUNCH WORKSPACE CONTROL
    # ---------------------------------------------------------
    cmds.workspaceControl(
        WSC_ID,
        label="AMINNN TOOLS COY",
        retain=False,
        dockToMainWindow=("bottom", 1),
        initialHeight=38,
        uiScript="import TKB.ui as tkb_ui; tkb_ui.build_tkb_ui()"
    )

    build_tkb_ui()
    cmds.workspaceControl(WSC_ID, e=True, restore=True)

def show():
    UI()