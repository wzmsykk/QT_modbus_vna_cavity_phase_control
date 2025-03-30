import sys
from PyQt5 import QtCore, QtGui
Qt = QtCore.Qt
from pandas import DataFrame

class PandasModel(QtCore.QAbstractTableModel):
    def __init__(self, data, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data:DataFrame = data

    def rowCount(self, parent=None):
        return len(self._data.values)

    def columnCount(self, parent=None):
        return self._data.columns.size

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role in {QtCore.Qt.DisplayRole, QtCore.Qt.EditRole}:
                return QtCore.QVariant(str(
                    self._data.iloc[index.row()][index.column()]))
        return QtCore.QVariant()
    
    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            
            return '{}'.format(self._data.columns[section])
        return super().headerData(section, orientation, role)

    def appendRow(self, row, count, parent=QtCore.QModelIndex()):
        self.beginInsertRows()
        # do actual data insert
        self.endInsertRows()

# if __name__ == '__main__':
#     application = QtGui.QApplication(sys.argv)
#     view = QtGui.QTableView()
#     model = PandasModel(your_pandas_data)
#     view.setModel(model)

#     view.show()
#     sys.exit(application.exec_())