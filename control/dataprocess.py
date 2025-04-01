import sys
from PyQt5 import QtCore, QtGui
Qt = QtCore.Qt

class DataHelper():
    def __init__(self):
        self.input_coupler_phase=0
        self.designed_offset_per_cell=270
    

# if __name__ == '__main__':
#     application = QtGui.QApplication(sys.argv)
#     view = QtGui.QTableView()
#     model = PandasModel(your_pandas_data)
#     view.setModel(model)

#     view.show()
#     sys.exit(application.exec_())