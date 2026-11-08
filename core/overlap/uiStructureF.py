try:
    # Coba PySide6 (Maya 2025, 2026+)
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import QRegularExpression as QRegExp
    from PySide6.QtGui import QRegularExpressionValidator as QRegExpValidator
    from shiboken6 import wrapInstance
except ImportError:
    # Fallback ke PySide2 (Maya 2017 - 2024)
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import QRegExp
    from PySide2.QtGui import QRegExpValidator
    from shiboken2 import wrapInstance

from maya import cmds


class CustomListWidget(QtWidgets.QListWidget):
    def __init__(self, parent=None):
        super(CustomListWidget, self).__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        menu = QtWidgets.QMenu()
        select_action = menu.addAction('Select')
        update_action = menu.addAction('Update')
        
        action = menu.exec_(self.mapToGlobal(position))
        if action == select_action:
            self.emit_selection()
        elif action == update_action:
            self.emit_update()

    def emit_selection(self):
        selected_items = self.selectedItems()
        item_names = [item.text() for item in selected_items]
        if item_names:
            cmds.select(item_names)

    def emit_update(self):
        print('Update running')
        self.clear()
        overlap_helpers = cmds.ls('Overlap_Helper', '*:Overlap_Helper')
        if overlap_helpers:
            points = cmds.ls('Overlap_Helper_point_*', '*:Overlap_Helper_point_*')
            if points:
                valid_points = [pt for pt in points if cmds.listRelatives(pt, c=True)]
                if valid_points:
                    children = cmds.listRelatives(valid_points, c=True)
                    if children:
                        for child in children:
                            self.addItem(child)
                
                orphans = list(set(valid_points) ^ set(points))
                if orphans:
                    parents = [cmds.listRelatives(o, p=True)[0] for o in orphans]
                    cmds.delete(parents)


def uiStucture(self):
    self.resize(290, 380)
    self.gridLayout = QtWidgets.QGridLayout()
    self.horizontalLayout = QtWidgets.QHBoxLayout()
    
    self.overlapBtn = QtWidgets.QPushButton('Overlap')
    self.horizontalLayout.addWidget(self.overlapBtn)
    self.ctrBtn = QtWidgets.QPushButton('Controller')
    self.horizontalLayout.addWidget(self.ctrBtn)
    self.aboutBtn = QtWidgets.QPushButton('About')
    self.horizontalLayout.addWidget(self.aboutBtn)
    
    self.gridLayout.addLayout(self.horizontalLayout, 0, 0, 1, 1)
    self.PagesStackedWidget = QtWidgets.QStackedWidget()
    
    # Page 1: Overlap
    self.overlapPageHorizontalLayout = QtWidgets.QWidget()
    self.gridLayout_2 = QtWidgets.QGridLayout(self.overlapPageHorizontalLayout)
    
    self.rotationRadioBtn = QtWidgets.QRadioButton('Rotate', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.rotationRadioBtn, 0, 0, 1, 1)
    
    self.addPyisicsCheckBox = QtWidgets.QCheckBox('Physics', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.addPyisicsCheckBox, 0, 3, 1, 1)
    
    self.translateRadioBtn = QtWidgets.QRadioButton('Translate', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.translateRadioBtn, 0, 1, 1, 1)
    
    self.settingsOvelapGridLayout = QtWidgets.QGridLayout()
    
    self.specificAxLabel = QtWidgets.QLabel('Axis', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.specificAxLabel, 0, 0, 1, 1)
    
    self.yzHorizontalLayout = QtWidgets.QHBoxLayout()
    self.xCheckBox = QtWidgets.QCheckBox('X', self.overlapPageHorizontalLayout)
    self.yzHorizontalLayout.addWidget(self.xCheckBox)
    self.yCheckBox = QtWidgets.QCheckBox('Y', self.overlapPageHorizontalLayout)
    self.yzHorizontalLayout.addWidget(self.yCheckBox)
    self.zCheckBox = QtWidgets.QCheckBox('Z', self.overlapPageHorizontalLayout)
    self.yzHorizontalLayout.addWidget(self.zCheckBox)
    self.settingsOvelapGridLayout.addLayout(self.yzHorizontalLayout, 0, 1, 1, 2)
    
    self.stiffnessLabel = QtWidgets.QLabel('Smoothness', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.stiffnessLabel, 1, 0, 1, 1)
    self.stiffnessLineEddit = QtWidgets.QLineEdit('3.0', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.stiffnessLineEddit, 1, 1, 1, 1)
    self.stiffnessSlider = QtWidgets.QSlider(self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.stiffnessSlider, 1, 2, 1, 1)
    
    self.scaleLabel = QtWidgets.QLabel('Scale', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.scaleLabel, 2, 0, 1, 1)
    self.scaleLineEdit = QtWidgets.QLineEdit('1.0', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.scaleLineEdit, 2, 1, 1, 1)
    self.scaleSlider = QtWidgets.QSlider(self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.scaleSlider, 2, 2, 1, 1)
    
    self.overshootLabel = QtWidgets.QLabel('Overshoot', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.overshootLabel, 3, 0, 1, 1)
    self.overshootLineEdit = QtWidgets.QLineEdit('10.0', self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.overshootLineEdit, 3, 1, 1, 1)
    self.overshootSlider = QtWidgets.QSlider(self.overlapPageHorizontalLayout)
    self.settingsOvelapGridLayout.addWidget(self.overshootSlider, 3, 2, 1, 1)
    
    self.gridLayout_2.addLayout(self.settingsOvelapGridLayout, 1, 0, 1, 4)
    
    self.firstCtrBtn = QtWidgets.QCheckBox('Ignore the First Control', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.firstCtrBtn, 2, 0, 1, 3)
    
    self.hierarchyCheckBox = QtWidgets.QCheckBox('Hierarchy', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.hierarchyCheckBox, 3, 0, 1, 3)
    
    self.loopBtn = QtWidgets.QCheckBox('Loop', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.loopBtn, 4, 0, 1, 1)
    
    self.locCheckBox = QtWidgets.QCheckBox('Custom Loc', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.locCheckBox, 0, 2, 1, 1)
    
    self.leyerBtn = QtWidgets.QCheckBox('Add to Animation Layer', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.leyerBtn, 5, 0, 1, 2)
    
    self.createOverlapBtn = QtWidgets.QPushButton('Create', self.overlapPageHorizontalLayout)
    self.gridLayout_2.addWidget(self.createOverlapBtn, 6, 0, 1, 4)
    
    self.PagesStackedWidget.addWidget(self.overlapPageHorizontalLayout)
    
    # Page 2: Controller
    self.ctrHorizontalLayout = QtWidgets.QWidget()
    self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout = QtWidgets.QGridLayout()
    
    self.label_13 = QtWidgets.QLabel('Shape', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.label_13, 0, 0, 1, 1)
    self.cubeRadioButton = QtWidgets.QRadioButton('Cube', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.cubeRadioButton, 0, 1, 1, 1)
    self.sphereRadioButton = QtWidgets.QRadioButton('Sphere', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.sphereRadioButton, 0, 2, 1, 1)
    
    self.nameLineEdit = QtWidgets.QLineEdit(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.nameLineEdit, 0, 4, 1, 2)
    
    self.label_16 = QtWidgets.QLabel('Scale', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.label_16, 1, 0, 1, 1)
    self.scaleCtrLineEdit = QtWidgets.QLineEdit('1.0', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.scaleCtrLineEdit, 1, 1, 1, 1)
    self.scaleCtrSlider = QtWidgets.QSlider(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.scaleCtrSlider, 1, 2, 1, 4)
    
    self.label_17 = QtWidgets.QLabel('Weight', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.label_17, 2, 0, 1, 1)
    self.weightCtrLineEdit = QtWidgets.QLineEdit('1.0', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.weightCtrLineEdit, 2, 1, 1, 1)
    self.weightCtrSlider = QtWidgets.QSlider(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.weightCtrSlider, 2, 2, 1, 4)
    
    self.paintBtn = QtWidgets.QPushButton('Paint', self.ctrHorizontalLayout)
    self.paintBtn.setIcon(QtGui.QIcon(':brush.png'))
    self.ctrSettingGridLayout.addWidget(self.paintBtn, 3, 0, 1, 2)
    
    self.smoothBtn = QtWidgets.QPushButton('Smooth', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.smoothBtn, 3, 2, 1, 3)
    
    self.moreOptionsBtn = QtWidgets.QPushButton(self.ctrHorizontalLayout)
    self.moreOptionsBtn.setIcon(QtGui.QIcon(':menu_options.png'))
    self.ctrSettingGridLayout.addWidget(self.moreOptionsBtn, 3, 5, 1, 1)
    
    self.label_14 = QtWidgets.QLabel('Effect', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.label_14, 4, 0, 1, 1)
    self.effectLineEdit = QtWidgets.QLineEdit('1.0', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.effectLineEdit, 4, 1, 1, 1)
    self.effectCtrSlider = QtWidgets.QSlider(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.effectCtrSlider, 4, 2, 1, 4)
    
    self.label_19 = QtWidgets.QLabel('FalloffMode', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.label_19, 5, 0, 1, 2)
    self.falloffModeComboBox = QtWidgets.QComboBox(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.falloffModeComboBox, 5, 2, 1, 4)
    
    self.label_18 = QtWidgets.QLabel('FalloffCurve', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.label_18, 6, 0, 1, 2)
    self.falloffCurveComboBox = QtWidgets.QComboBox(self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.falloffCurveComboBox, 6, 2, 1, 4)
    
    self.createCtrBtn = QtWidgets.QPushButton('Create', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.createCtrBtn, 7, 0, 1, 3)
    
    self.worldSpaceCheckBox = QtWidgets.QCheckBox('Orient to World Space', self.ctrHorizontalLayout)
    self.ctrSettingGridLayout.addWidget(self.worldSpaceCheckBox, 7, 3, 1, 3)
    
    self.verticalLayout_3.addLayout(self.ctrSettingGridLayout)
    
    self.ctrGroupBox = QtWidgets.QGroupBox(self.ctrHorizontalLayout)
    self.gridLayout_3 = QtWidgets.QGridLayout(self.ctrGroupBox)
    self.ctrList = CustomListWidget(self.ctrGroupBox)
    self.ctrList.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
    self.gridLayout_3.addWidget(self.ctrList, 0, 0, 1, 1)
    self.verticalLayout_3.addWidget(self.ctrGroupBox)
    
    self.PagesStackedWidget.addWidget(self.ctrHorizontalLayout)
    
    # Page 3: About
    self.aboutHorizontalLayout = QtWidgets.QWidget()
    self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.aboutHorizontalLayout)
    self.textEdit = QtWidgets.QTextEdit(self.aboutHorizontalLayout)
    self.verticalLayout_4.addWidget(self.textEdit)
    
    self.Youtube = QtWidgets.QPushButton('Script Tutorial', self.aboutHorizontalLayout)
    self.verticalLayout_4.addWidget(self.Youtube)
    
    self.gumroadBtn = QtWidgets.QPushButton('Script Link on Gumroad', self.aboutHorizontalLayout)
    self.verticalLayout_4.addWidget(self.gumroadBtn)
    
    self.verticalSpacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
    self.verticalLayout_4.addItem(self.verticalSpacer)
    
    self.PagesStackedWidget.addWidget(self.aboutHorizontalLayout)
    self.gridLayout.addWidget(self.PagesStackedWidget, 1, 0, 1, 1)
    
    self.setWindowTitle('Overlap Helper')
    self.setLayout(self.gridLayout)