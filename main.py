
import sys
sys.path.append("imports")

import asyncio
from ui.main_qt import MainDialog
from PyQt5 import QtCore
from qasync import QEventLoop, QApplication

QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True) #enable highdpi scaling
QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True) #use highdpi icons

app = QApplication(sys.argv)

event_loop = QEventLoop(app)
asyncio.set_event_loop(event_loop)

app_close_event = asyncio.Event()
app.aboutToQuit.connect(app_close_event.set)

mainwindow = MainDialog()
mainwindow.show()

event_loop.create_task(mainwindow.start())

event_loop.run_until_complete(app_close_event.wait())
event_loop.close()
