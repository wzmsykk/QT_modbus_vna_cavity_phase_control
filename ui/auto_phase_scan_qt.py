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
    def on_accept(self):
        self.vec = float(self.ui.lineEdit_relvec.text())
        self.waittime = float(self.ui.lineEdit_waittime.text())
        if self.vec < 0:
            self.vec = 10
        if self.waittime < 0:
            self.waittime = 5
    def _set_signal_slots(self):
        self.ui.buttonBox.accepted.connect(self.on_accept)
        self.ui.buttonBox.rejected.connect(self.on_cancel)
    def on_cancel(self):
        self.ui.lineEdit_relvec.setText(str(self.vec))
        self.ui.lineEdit_waittime.setText(str(self.waittime))

        