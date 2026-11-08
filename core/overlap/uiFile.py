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

import sys
from importlib import reload
from maya import cmds
from maya.OpenMayaUI import MQtUtil

import uiStructureF
import controllerFile
import overlapFile

reload(uiStructureF)
reload(controllerFile)
reload(overlapFile)

def maya_main_window():
    main_window_ptr = MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

class UI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(UI, self).__init__(parent)
        self.ctr = controllerFile.create_control()
        self.overlap_cls = overlapFile.OVERLAP()
        
        uiStructureF.uiStucture(self)
        self.genralConnectios()
        self.ovelapInit()
        self.ovelapButtonsConnections()
        self.controllerButtons()
        self.controllerConnections()
        self.aboutPageConnections()
        self.show()

    def genralConnectios(self):
        self.overlapBtn.clicked.connect(lambda: self.PagesStackedWidget.setCurrentIndex(0))
        self.ctrBtn.clicked.connect(lambda: self.PagesStackedWidget.setCurrentIndex(1))
        self.aboutBtn.clicked.connect(lambda: self.PagesStackedWidget.setCurrentIndex(2))

    def ovelapInit(self):
        self.rotationRadioBtn.setChecked(True)
        self.leyerBtn.setChecked(True)
        self.xCheckBox.setChecked(True)
        self.yCheckBox.setChecked(True)
        self.zCheckBox.setChecked(True)
        
        regex = QRegExp(r'[0-9]+(\.[0-9]{1,2})?')
        validator = QRegExpValidator(regex)
        self.stiffnessLineEddit.setValidator(validator)
        self.scaleLineEdit.setValidator(validator)
        self.overshootLineEdit.setValidator(validator)

    def ovelapButtonsConnections(self):
        self.createOverlapBtn.clicked.connect(self.createOverlap)

    def controllerButtons(self):
        self.cubeRadioButton.setChecked(True)
        self.falloffModeComboBox.addItems(['Volume', 'Surface'])
        self.falloffModeComboBox.setCurrentIndex(1)
        self.falloffCurveComboBox.addItems(['None', 'Linear', 'Smooth', 'Spline'])
        self.falloffCurveComboBox.setCurrentIndex(3)

    def controllerConnections(self):
        self.createCtrBtn.clicked.connect(self.createCtr)

    def aboutPageConnections(self):
        self.Youtube.clicked.connect(lambda: cmds.showHelp('https://www.youtube.com/', a=True))
        self.gumroadBtn.clicked.connect(lambda: cmds.showHelp('https://gumroad.com/', a=True))

    def stiffnessValue(self):
        try:
            return float(self.stiffnessLineEddit.text())
        except ValueError:
            return 3.0

    def scaleValue(self):
        try:
            return float(self.scaleLineEdit.text())
        except ValueError:
            return 1.0

    def overshootValue(self):
        try:
            return float(self.overshootLineEdit.text())
        except ValueError:
            return 10.0

    def getAxisState(self):
        self.overlap_cls.tx = self.xCheckBox.isChecked()
        self.overlap_cls.ty = self.yCheckBox.isChecked()
        self.overlap_cls.tz = self.zCheckBox.isChecked()

    def createOverlap(self):
        self.overlap_cls.translate = not self.rotationRadioBtn.isChecked()
        self.overlap_cls.specific_axis_state = self.locCheckBox.isChecked()
        
        if not self.locCheckBox.isChecked():
            if not (self.xCheckBox.isChecked() or self.yCheckBox.isChecked() or self.zCheckBox.isChecked()):
                cmds.warning("Overlap Helper: Pilih minimal satu Axis (X, Y, atau Z)!")
                return
        
        self.getAxisState()
        self.overlap_cls.physics_on = self.addPyisicsCheckBox.isChecked()
        self.overlap_cls.stiffness = self.stiffnessValue()
        self.overlap_cls.timeScale = max(0.1, (0.9 - self.stiffnessValue()) + 0.2)
        
        if self.translateRadioBtn.isChecked():
            self.overlap_cls.Scale_ = 10000
        else:
            self.overlap_cls.Scale_ = self.scaleValue()

        self.overlap_cls.smoothness = self.overshootValue()
        self.overlap_cls.weight = 0.9
        self.overlap_cls.dont_use_first_ctrl = self.firstCtrBtn.isChecked() if self.firstCtrBtn.isEnabled() else False
        self.overlap_cls.loop = self.loopBtn.isChecked()
        self.overlap_cls.bake_on_layer = self.leyerBtn.isChecked()
        
        self.overlap_cls.start()

    def createCtr(self):
        self.ctr.run_sel()

def show_ui():
    return UI(maya_main_window())