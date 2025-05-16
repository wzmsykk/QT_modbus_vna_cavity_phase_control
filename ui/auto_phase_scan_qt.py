from PyQt5.QtWidgets import QDialog
from .auto_phase_scan_dlg import Ui_Dialog
class AutoPhaseScanDialog(QDialog):
    def __init__(self, parent=None):

        super(QDialog, self).__init__(parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.vec=10
        self.waittime=5
        self._set_signal_slots()
    def _set_signal_slots(self):
        self.ui.lineEdit_relvec.textEdited.connect(self._on_relvec_changed)
        self.ui.lineEdit_waittime.textEdited.connect(self._on_waittime_changed)
    def _on_relvec_changed(self):
        try:
            self.vec = float(self.ui.lineEdit_relvec.text())
        except ValueError:
            return
        if self.vec < 0:
            self.vec = 10
    def _on_waittime_changed(self):
        try:
            self.waittime = float(self.ui.lineEdit_waittime.text())
        except ValueError:
            return
        if self.waittime < 0:
            self.waittime = 5