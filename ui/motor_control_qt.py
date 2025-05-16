from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt
from .motor_control_dlg import Ui_Dialog
class MotorControlDialog(QDialog):
    def __init__(self, parent=None):

        super(QDialog, self).__init__(parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        windowflags=self.windowFlags() & ~Qt.WindowCloseButtonHint
        self.setWindowFlags(windowflags	| Qt.WindowMinimizeButtonHint|Qt.WindowStaysOnTopHint )