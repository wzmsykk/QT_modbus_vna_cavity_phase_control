import sys
import asyncio
import datetime
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5 import QtCore
from qasync import QEventLoop, asyncClose, asyncSlot
from .main_dlg import Ui_Dialog
import control.modbus as modbus
import control.vnc as vnc
import control.dataprocess as dataprocess
import csv


class MainDialog(QDialog):

    def __init__(self, parent=None):

        super(QDialog, self).__init__(parent)

        self.ui = Ui_Dialog()

        self.ui.setupUi(self)

        self.ui.pushButton_setpos.clicked.connect(self.setpos)
        self.ui.pushButton_resetpos.clicked.connect(self.resetpos)
        self.ui.pushButton_savecurr.clicked.connect(self.saveline)
        self.ui.pushButton_deldata.clicked.connect(self.deleteline)
        self.ui.pushButton_export.clicked.connect(self.save_csv)
        self.client: modbus.ModbusClient = None
        self.rm:vnc.ResourceManager = None
        self.inst:vnc.Resource = None
        self.columnname=["时间","腔ID","湿度","气压","腔温","气温","校准频率","VNA读取相位","输入相位","腔间相移","预期相移","累计相移"]
        #self.data = pd.DataFrame(columns=self.columnname)
        
        #self.model = dataprocess.PandasModel(self.data)
        self.model =QStandardItemModel()
        self.model.setColumnCount(len(self.columnname))
        self.model.setHorizontalHeaderLabels(self.columnname)
        self.ui.tableView_data.setModel(self.model)



        self.query_delay=1

    def disable_motor_buttons(self):
        self.ui.pushButton_setpos.setEnabled(False)
        self.ui.pushButton_resetpos.setEnabled(False)
    def enable_motor_buttons(self):
        self.ui.pushButton_setpos.setEnabled(True)
        self.ui.pushButton_resetpos.setEnabled(True)

    def get_humid(self):
        return 0
    def get_pressure(self):
        return 100
    def get_cav_temp(self):
        return 20
    def get_air_temp(self):
        return 20
    def get_calibretaed_cav_freq(self):
        return 2800
    def get_cav_vnc_phase(self):
        return(float(self.ui.lineEdit_phase.text()))
    def get_input_coupler_phase(self):
        return 18.37
    def get_phase_diff_between_cav(self):
        return 120
    def get_expected_phase_offset(self):
        return 999
    def total_phase_offset(self):
        return -999
    @asyncSlot()
    async def setpos(self):
        pos=float(self.ui.lineEdit_relpos.text())
        vel=float(self.ui.lineEdit_relvec.text())
        await modbus.send_rel_pos_vel(self.client,pos,vel)
        await modbus.rel_cmd(self.client)
        self.disable_motor_buttons()
        await modbus.wait_rel_cmd_done(self.client)
        self.enable_motor_buttons()
    @asyncSlot()
    async def resetpos(self):
        await modbus.axis_clear(self.client)
        self.disable_motor_buttons()
        await asyncio.sleep(1)
        await modbus.axis_clear_stop(self.client)
        self.enable_motor_buttons()
    def saveline(self):
        time=datetime.datetime.now()
        # columnname=["时间","腔ID","湿度","气压","腔温","气温","校准频率","VNA读取相位","输入相位","腔间相移","预期相移","累计相移"]
        newline=[str(time),self.ui.spinBox_cavid.value(),self.get_humid(),self.get_pressure(),self.get_cav_temp(),self.get_air_temp(),self.get_calibretaed_cav_freq(),self.get_cav_vnc_phase(),self.get_input_coupler_phase(),self.get_phase_diff_between_cav(),self.get_expected_phase_offset(),self.total_phase_offset()]
        inserted=[QStandardItem(str(item)) for item in newline]
        self.model.appendRow(inserted)
    def deleteline(self):
        rowCount=self.model.rowCount()
        if rowCount>0:
            self.model.removeRow(rowCount-1)
    def save_csv(self):
        
        # 获取模型
        model = self.model
        if model is None:
            return
        
        # 获取保存文件路径
        file_path, _ = QFileDialog.getSaveFileName(
            None, "保存CSV文件", "", "CSV文件 (*.csv)")
        
        if not file_path:
            return  # 用户取消了保存
        
        # 确保文件以.csv结尾
        if not file_path.lower().endswith('.csv'):
            file_path += '.csv'
        
        # 打开文件并写入数据
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            
            # 写入表头
            header = []
            for col in range(model.columnCount()):
                header.append(model.headerData(col, QtCore.Qt.Horizontal))
            writer.writerow(header)
            
            # 写入数据行
            for row in range(model.rowCount()):
                row_data = []
                for col in range(model.columnCount()):
                    item = model.item(row, col)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)

    @asyncClose
    async def closeEvent(self, event):  # noqa:N802
        print("closeEvent")
        await modbus.stop_PC_control(self.client)
        await modbus.stop_async_simple_client(self.client)
        vnc.close_visa_client(self.rm,self.inst)
        self.client = None
        self.rm = None
        self.inst = None
        event.accept()
    async def query_modbus_first(self):
        self.ui.lineEdit_relvec.setText(str(await modbus.read_float(self.client,"PC_M6_Realtive_Vel1")))
        self.ui.lineEdit_relpos.setText(str(await modbus.read_float(self.client,"PC_M6_Realtive_Pos1")))
    async def query_modbus_period(self):
        while True:
            if self.client is None:
                break
            self.ui.lineEdit_realpos.setText(str(await modbus.read_float(self.client,"PC_M6_Act_Pos1")))
            self.ui.lineEdit_realvec.setText(str(await modbus.read_float(self.client,"PC_M6_Act_Vel1")))
            
            print("query_loc:",self.ui.lineEdit_realpos.text())
            print("now sleep")
            await asyncio.sleep(self.query_delay)
    async def query_vnc_period(self):
        while True:
            if self.inst is None:
                break
            print("query_vnc_period")
            result = vnc.query_inst_mark(self.inst)
            fresult=vnc.convert_mark_result(result)
            self.ui.lineEdit_phase.setText(str(fresult))
            print("query_vnc:",self.ui.lineEdit_phase.text())
            await asyncio.sleep(self.query_delay)
    async def start(self):
        event_loop=asyncio.get_event_loop()
        task1=event_loop.create_task(self.start_modbus_client())
        task2=event_loop.create_task(self.start_vnc_client())
        await task1
        await task2
        event_loop.create_task(self.query_modbus_first())
        event_loop.create_task(self.query_modbus_period())
        event_loop.create_task(self.query_vnc_period())
        
    async def start_vnc_client(self):
        self.rm, self.inst = vnc.create_visa_client()
        vnc.set_meas_mode(self.inst)
    async def start_modbus_client(self):
        self.client = await modbus.start_async_simple_client("192.168.1.100",502)
        await modbus.start_PC_control(self.client)
if __name__ == "__main__":
    pass