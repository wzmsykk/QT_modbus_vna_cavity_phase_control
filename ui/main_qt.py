import sys,os
import asyncio
import datetime
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5 import QtCore
from qasync import QEventLoop, asyncClose, asyncSlot
from .main_dlg import Ui_Dialog
import control.modbus as modbus
import control.vnc as vnc
import control.convertf as convertf
import csv

def is_file_locked(filepath):
    """检查文件是否被其他程序占用"""
    if not os.path.exists(filepath):
        return False
    
    try:
        # 尝试以独占模式打开文件
        with open(filepath, 'a', encoding='utf-8') as f:
            pass
        return False
    except IOError:
        return True

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
        self.ui.pushButton_addmov.clicked.connect(self.addmov)
        self.client: modbus.ModbusClient = None
        self.rm:vnc.ResourceManager = None
        self.inst:vnc.Resource = None
        self.app:convertf.ConvertfApp = None
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
        self.ui.pushButton_addmov.setEnabled(False)
    def enable_motor_buttons(self):
        self.ui.pushButton_setpos.setEnabled(True)
        self.ui.pushButton_resetpos.setEnabled(True)
        self.ui.pushButton_addmov.setEnabled(True)

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
        try:
            pos=float(self.ui.lineEdit_relpos.text())
            vel=float(self.ui.lineEdit_relvec.text())
            await modbus.send_rel_pos_vel(self.client,pos,vel)
            await modbus.rel_cmd(self.client)
            self.disable_motor_buttons()
            await modbus.wait_rel_cmd_done(self.client)
            self.enable_motor_buttons()
            return
        except:
            return
    @asyncSlot()
    async def resetpos(self):
        try:
            await modbus.axis_clear(self.client)
            self.disable_motor_buttons()
            await asyncio.sleep(1)
            await modbus.axis_clear_stop(self.client)
            self.enable_motor_buttons()
            return
        except:
            return
    @asyncSlot()
    async def addmov(self):

        try: 
            extpos=float(self.ui.lineEdit_movpos.text())
            if extpos>1000:
                extpos=1000
                self.ui.lineEdit_movpos.setText(str(extpos))
            elif extpos<-1000:
                extpos=-1000
                self.ui.lineEdit_movpos.setText(str(extpos))
            pos=float(self.ui.lineEdit_relpos.text())
            newpos=pos+extpos
            self.ui.lineEdit_relpos.setText(str(newpos))
            await self.setpos()
            return
        except:
            return
        

    def saveline(self):
        time=datetime.datetime.now()
        # columnname=["时间","腔ID","湿度","气压","腔温","气温","校准频率","VNA读取相位","输入相位","腔间相移","预期相移","累计相移"]
        newline=[]
        newline.append(str(time))##时间
        newline.append(self.ui.spinBox_cavid.value())##腔ID
        newline.append(self.app.get_rel_humid())##湿度
        newline.append(self.app.get_amb_pressure())##气压
        newline.append(self.app.get_cav_temp())##腔温
        newline.append(self.app.get_amb_temp())##气温
        newline.append(self.app.get_results()[0])##校准频率
        newline.append(vnc.get_phase(self.inst))###VNA读取相位
        newline.append(self.get_input_coupler_phase())##输入相位
        newline.append(self.get_phase_diff_between_cav())##腔间相移
        newline.append(self.get_expected_phase_offset())##预期相移
        newline.append(self.total_phase_offset())##累计相移
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
        
        if os.path.exists(file_path) and is_file_locked(file_path):
            QMessageBox.critical(None, "错误", 
                            f"文件 {os.path.basename(file_path)} 正被其他程序占用，请关闭后重试")
            return
        try:
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
        except PermissionError:
            QMessageBox.critical(None, "错误", "没有写入权限，请选择其他位置保存")
        except Exception as e:
            QMessageBox.critical(None, "错误", f"保存文件时出错: {str(e)}")
        return
    
    @asyncClose
    async def closeEvent(self, event):  # noqa:N802
        print("closeEvent")
        await modbus.stop_PC_control(self.client)
        await modbus.stop_async_simple_client(self.client)
        vnc.close_visa_client(self.rm,self.inst)
        self.app.stop_app()
        self.client = None
        self.rm = None
        self.inst = None
        self.app = None
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
            fresult=vnc.get_phase(self.inst)
            self.ui.lineEdit_phase.setText(str(fresult))
            print("query_vnc:",self.ui.lineEdit_phase.text())
            await asyncio.sleep(self.query_delay)
    async def query_app_first(self):
        self.ui.lineEdit_humidity.setText(str(self.app.get_rel_humid()))
        self.ui.lineEdit_airpressure.setText(str(self.app.get_amb_pressure()))
        self.ui.lineEdit_cavtemp.setText(str(self.app.get_cav_temp()))
        self.ui.lineEdit_airtemp.setText(str(self.app.get_amb_temp()))
        self.ui.lineEdit_measuredfreq.setText(str(self.app.get_cav_freq()))
        self.ui.lineEdit_freq_corred.setText(str(self.app.get_results()[0]))
        self.ui.lineEdit_freqoffset.setText(str(self.app.get_results()[1]))
    async def start(self):
        event_loop=asyncio.get_event_loop()
        task1=event_loop.create_task(self.start_modbus_client())
        task2=event_loop.create_task(self.start_vnc_client())
        task3=event_loop.create_task(self.start_convertf_app())
        await task1
        await task2
        await task3
        event_loop.create_task(self.query_modbus_first())
        event_loop.create_task(self.query_modbus_period())
        event_loop.create_task(self.query_vnc_period())
        event_loop.create_task(self.query_app_first())

    async def start_vnc_client(self):
        self.rm, self.inst = vnc.create_visa_client()
        vnc.set_meas_mode(self.inst)
    async def start_modbus_client(self):
        self.client = await modbus.start_async_simple_client("192.168.1.100",502)
        await modbus.start_PC_control(self.client)
    async def start_convertf_app(self):
        self.app=convertf.ConvertfApp()

if __name__ == "__main__":
    pass