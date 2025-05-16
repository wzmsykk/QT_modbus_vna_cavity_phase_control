import os
import asyncio
import datetime
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox,QDesktopWidget
from PyQt5.QtCore import pyqtSignal,Qt
from qasync import asyncClose, asyncSlot
from .main_dlg import Ui_Dialog
from .auto_phase_scan_qt import AutoPhaseScanDialog
from .phase_view_qt import PhaseViewDialog
from .motor_control_qt import MotorControlDialog
import control.modbus as modbus
from pymodbus.exceptions import ConnectionException,ModbusIOException
import control.vnc as vnc
from pyvisa.errors import VisaIOError
import control.convertf as convertf
import control.dataprocess as dataprocess

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

class MainWindow(QDialog):
    automode_helper_signal=pyqtSignal(str)
    def __init__(self, parent=None):

        super(QDialog, self).__init__(parent)

        self.ui = Ui_Dialog()

        self.ui.setupUi(self)
        self.setWindowFlags(self.windowFlags()	| Qt.WindowMinimizeButtonHint| Qt.WindowMaximizeButtonHint)
        ########INIT ASYNC MSGBOX
        self.message_box = QMessageBox()
        self.message_box.setText("This is a warning message")
        self.message_box.setWindowTitle("Warning")
        self.message_box.setIcon(QMessageBox.Icon.Warning)
        self.message_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        #self.message_box.finished.connect(self._message_box_results)
        #########INIT AUTO PHASE SCAN DIALOG
        self.auto_scan_dlg = AutoPhaseScanDialog()
        self.auto_scan_dlg.setModal(True)
        #########INIT PHASE VIEW DIALOG
        self.phase_view_dlg = PhaseViewDialog()
        self.ui_phase=self.phase_view_dlg.ui
        
        #########INIT MOTOR CONTROL DIALOG
        self.motor_control_dlg = MotorControlDialog()
        self.ui_motor=self.motor_control_dlg.ui

        #########Show DIALOGS
        self.set_location_in_screen()
        self.phase_view_dlg.show()
        self.motor_control_dlg.show()

        self.client: modbus.ModbusClient.ModbusBaseClient | None= None
        self.rm:vnc.ResourceManager | None= None
        self.inst:vnc.Resource | None= None
        self.app:convertf.ConvertfApp | None= None
        
        #self.data = pd.DataFrame(columns=self.columnname)
        
        #self.model = dataprocess.PandasModel(self.data)
        self.model =dataprocess.CavityPhaseModel()
        self.model.setColumnCount(len(self.model.columnname))
        self.model.setHorizontalHeaderLabels(self.model.columnname)
        self.coupler_calc_input=dataprocess.CouplerCalculation()
        self.coupler_calc_output=dataprocess.CouplerCalculation()
        self.coupler_calc=self.coupler_calc_input
        self.ui.tableView_data.setModel(self.model)

        self.columnname=["时间","腔ID","腔位置","输入相位","腔相位","单腔相移","目标相位-累计相移","目标相位-单腔相移","目标相位","单腔相移误差","累计相移误差","校准频率(MHz)","湿度(%)","气压(Pa)","腔温(℃)","气温(℃)","真空频率(MHz)","工作温度(℃)"]
        assert self.model._list_eq(self.model.columnname,self.columnname)

        self.set_ui_data_dirty()
        self.setup_text()
        
        self.query_delay=1 ## in seconds
        
        self.ui.tabWidget.setTabVisible(3, False) ##hide advanced tab
        self._set_signal_slots()
        self._set_data_edited_signals()
        
    def set_location_in_screen(self):
        ####SET PHASE VIEW DIALOG ON TOP LEFT
        ag = QDesktopWidget().availableGeometry()
        sg = QDesktopWidget().screenGeometry()
        widget_phase= self.phase_view_dlg.geometry()
        x = 0
        y=0
        self.phase_view_dlg.move(x, y)
        ####SET MOTOR CONTROL DIALOG ON TOP RIGHT
        widget_motor= self.motor_control_dlg.geometry()
        x = ag.width() - widget_motor.width()
        y = widget_phase.height()+10
        self.motor_control_dlg.move(x, y)
        ####SET MAIN WINDOW ON BOTTOM LEFT
        widget_main= self.geometry()
        x= 0
        y= widget_phase.height() +50
        self.move(x, y)
        # widget = self.geometry()
        # x = ag.width() - widget.width()
        # y = 2 * ag.height() - sg.height() - widget.height()
        # self.move(x, y)
    def setup_text(self):
        self.ui.lineEdit_max_single_cell_error_abs.setText(str(self.model.max_single_cell_phase_error_abs))
        self.ui.lineEdit_max_sum_error_abs.setText(str(self.model.max_sum_phase_error_abs))
        pass
    async def _show_aysnc_messagebox(self, title:str, message:str):
        self.message_box.show()
        self.message_box.setText(message)
        self.message_box.setWindowTitle(title)
        self.message_box.setIcon(QMessageBox.Icon.Warning)
        self.message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # self.close()

    def _set_signal_slots(self):
        self.ui_motor.pushButton_setpos.clicked.connect(self.setpos_ui)
        self.ui.pushButton_movetocavpos.clicked.connect(self.setpos2cavpos)
        self.ui_motor.pushButton_resetpos.clicked.connect(self.resetpos)
        self.ui.pushButton_savecurr.clicked.connect(self.save_cavity_data_ui)
        self.ui.pushButton_deldata.clicked.connect(self.delete_last_line)
        self.ui.pushButton_export.clicked.connect(self.save_csv_ui)
        self.ui.pushButton_import.clicked.connect(self.read_csv_ui)
        self.ui_motor.pushButton_addmov.clicked.connect(self.addmov)
        self.ui.pushButton_freqcor.clicked.connect(self.freqcor)
        self.ui.radioButton_air.clicked.connect(self.set_airtype)
        self.ui.radioButton_nitro.clicked.connect(self.set_airtype)
        self.ui.checkBox_cavtempasairtemp.clicked.connect(self.set_temp_constraint)
        self.ui.pushButton_setinputphase.clicked.connect(self.set_current_vnc_phase_as_inputphase)
        self.ui.checkBox_lockinputphase.clicked.connect(self.lock_inputphase)
        self.ui.spinBox_cavid.valueChanged.connect(self.ui_update_cavity_id)
        self.ui.pushButton_show_phase_window.clicked.connect(self.phase_view_dlg.show)
        self.ui.pushButton_show_motor_control.clicked.connect(self.motor_control_dlg.show)
        self.ui.spinBox_phase_dialog_fontsize.valueChanged.connect(self.change_phase_dialog_fontsize)
        ##### AUTO CALC
        self.ui.checkBox_auto_calc.clicked.connect(self.ui_set_auto_recalc)
        #self.model.data_changed_signal.connect(self.sync_ui_from_model)

        self.ui.pushButton_record_vnc_phase.clicked.connect(self.set_current_vnc_phase_as_cavity_phase)
        self.ui.pushButton_savecavpos.clicked.connect(self.save_real_position_as_cavity_position)
        self.ui.pushButton_savecavpos_set.clicked.connect(self.save_set_position_as_cavity_position)
        self.ui.pushButton_calc_target_phase.clicked.connect(self.ui_calculate_target_phase)
        self.ui.pushButton_nextcavity.clicked.connect(self.next_cavity)
        self.ui.pushButton_previouscavity.clicked.connect(self.previous_cavity)


        ###RECONNECT BUTTONS
        self.ui.pushButton_reconnectmotor.clicked.connect(self.start_modbus_client_button)
        self.ui.pushButton_reconnectVNC.clicked.connect(self.start_vnc_client_button)

        ###AUTO MODE
        self.ui_motor.checkBox_automode.clicked.connect(self.automode_clicked)
        self.ui_motor.pushButton_autophasescan.clicked.connect(self.ui_auto_phase_scan)
        ###AUTO MODE HELPER
        self.automode_helper_signal.connect(self.automode_helper_slot)

        ###TEXT CHANGED SIGNALS
        self.ui.lineEdit_vnc_phase.textChanged.connect(self.update_vnc_phase_view)
        self.ui.lineEdit_cav_phase.textChanged.connect(self.update_cav_phase_view)
        self.ui.lineEdit_targetphase_average.textChanged.connect(self.update_target_phase_view)
        
        ###COUPLER PHASE CALCULATION
        self.ui.lineEdit_couper_calc_f0_corrected.textEdited.connect(self.update_coupler_calc_step1)
        self.ui.lineEdit_couper_calc_f2pi_3.textEdited.connect(self.update_coupler_calc_step1)
        self.ui.lineEdit_couper_calc_fmean.textEdited.connect(self.update_coupler_calc_step1)
        self.ui.lineEdit_couper_calc_fpi_2.textEdited.connect(self.update_coupler_calc_step1)
        self.ui.lineEdit_c11.textEdited.connect(self.update_coupler_calc_step2)
        self.ui.lineEdit_c12.textEdited.connect(self.update_coupler_calc_step2)
        self.ui.lineEdit_c13.textEdited.connect(self.update_coupler_calc_step2)
        self.ui.lineEdit_c21.textEdited.connect(self.update_coupler_calc_step2)
        self.ui.lineEdit_c22.textEdited.connect(self.update_coupler_calc_step2)
        self.ui.lineEdit_c23.textEdited.connect(self.update_coupler_calc_step2)

        self.ui.radioButton_input_coupler.clicked.connect(self.update_coupler_calc_step0)
        self.ui.radioButton_output_coupler.clicked.connect(self.update_coupler_calc_step0)
    def change_phase_dialog_fontsize(self):
        font=self.ui_phase.lineEdit_vnc_phase_view.font()
        font.setPointSize(self.ui.spinBox_phase_dialog_fontsize.value())
        self.ui_phase.lineEdit_vnc_phase_view.setFont(font)
        self.ui_phase.lineEdit_targetphase_average_view.setFont(font)
        #self.phase_view_dlg.setFixedSize(self.phase_view_dlg.ui.horizontalLayout.sizeHint())
        self.set_location_in_screen()
    def update_coupler_calc_step0(self):
        if self.ui.radioButton_input_coupler.isChecked():
            self.coupler_calc=self.coupler_calc_input
        elif self.ui.radioButton_output_coupler.isChecked():
            self.coupler_calc=self.coupler_calc_output
        self.ui.lineEdit_couper_calc_f0_corrected.setText(str(self.coupler_calc.f0))
        self.ui.lineEdit_couper_calc_f2pi_3.setText(str(self.coupler_calc.fc))
        self.ui.lineEdit_couper_calc_fmean.setText(str(self.coupler_calc.fm))
        self.ui.lineEdit_couper_calc_fpi_2.setText(str(self.coupler_calc.fl))
        self.ui.lineEdit_c11.setText(str(self.coupler_calc.c11))
        self.ui.lineEdit_c12.setText(str(self.coupler_calc.c12))
        self.ui.lineEdit_c13.setText(str(self.coupler_calc.c13))
        self.ui.lineEdit_c21.setText(str(self.coupler_calc.c21))
        self.ui.lineEdit_c22.setText(str(self.coupler_calc.c22))
        self.ui.lineEdit_c23.setText(str(self.coupler_calc.c23))
        self.update_coupler_calc_step1()
    def update_coupler_calc_step1(self):
        try:
            f0=float(self.ui.lineEdit_couper_calc_f0_corrected.text())
            fc=float(self.ui.lineEdit_couper_calc_f2pi_3.text())
            fm=float(self.ui.lineEdit_couper_calc_fmean.text())
            fl=float(self.ui.lineEdit_couper_calc_fpi_2.text())
            self.coupler_calc.f0=f0
            self.coupler_calc.fc=fc
            self.coupler_calc.fm=fm
            self.coupler_calc.fl=fl
            
            self.ui.lineEdit_couper_calc_fpi_2_corrected.setText(str(self.coupler_calc.fc_c))
            self.ui.lineEdit_couper_calc_fmean_corrected.setText(str(self.coupler_calc.fm_c))
            self.ui.lineEdit_couper_calc_f2pi_3_corrected.setText(str(self.coupler_calc.fc_c))
        except:
            return
        self.update_coupler_calc_step2()
    def update_coupler_calc_step2(self):
        try:
            self.coupler_calc.c11=float(self.ui.lineEdit_c11.text())
            self.coupler_calc.c12=float(self.ui.lineEdit_c12.text())
            self.coupler_calc.c13=float(self.ui.lineEdit_c13.text())
            self.coupler_calc.c21=float(self.ui.lineEdit_c21.text())
            self.coupler_calc.c22=float(self.ui.lineEdit_c22.text())
            self.coupler_calc.c23=float(self.ui.lineEdit_c23.text())
            c31=self.coupler_calc.c11-self.coupler_calc.c21
            c32=self.coupler_calc.c12-self.coupler_calc.c22
            c33=self.coupler_calc.c13-self.coupler_calc.c23
            self.ui.lineEdit_c31.setText(str(c31))
            self.ui.lineEdit_c32.setText(str(c32))
            self.ui.lineEdit_c33.setText(str(c33))
            target_phase=self.coupler_calc.c13-self.model.designed_shift_per_cell
            if target_phase>180:
                target_phase=target_phase-360
            elif target_phase<-180:
                target_phase=target_phase+360
            self.ui.lineEdit_coupler_phase_target.setText("{:.3f}".format(round(target_phase,3)))
        except:
            return
        self.update_coupler_calc_step3()
    def update_coupler_calc_step3(self):
        try:
            cv=self.coupler_calc.calculate_coupling_degree()
            self.ui.lineEdit_coupling_value.setText(str(cv))
            err=self.coupler_calc.calculate_coupler_phase_error()
            self.ui.lineEdit_coupler_phase_error.setText(str(err))
        except:
            return
    def update_vnc_phase_view(self):
        try:
            vnc_phase=float(self.ui.lineEdit_vnc_phase.text())
            self.ui_phase.lineEdit_vnc_phase_view.setText("{:.3f}".format(round(vnc_phase,3)))
        except:
            return
    def update_cav_phase_view(self):
        try:
            cav_phase=float(self.ui.lineEdit_cav_phase.text())
            self.ui.lineEdit_cav_phase_view.setText("{:.3f}".format(round(cav_phase,3)))
        except:
            return
    def update_target_phase_view(self):
        try:
            target_phase=float(self.ui.lineEdit_targetphase_average.text())
            self.ui_phase.lineEdit_targetphase_average_view.setText("{:.3f}".format(round(target_phase,3)))
        except:
            return
    def _set_data_edited_signals(self):
        self.ui.lineEdit_cav_phase.textEdited.connect(self.ui_phase_edited)
        self.ui.lineEdit_currcavpos.textEdited.connect(self.ui_pos_edited)
    def set_ui_data_clean(self):
        self.ui.lineEdit_cav_phase.setStyleSheet("")
        self.ui.lineEdit_currcavpos.setStyleSheet("")
        self.ui.lineEdit_cav_phase_view.setStyleSheet("")
        self.ui_data_dirty=False
    def set_ui_data_dirty(self):
        dirty_style="color: rgb(255, 0, 0);"
        self.ui.lineEdit_cav_phase.setStyleSheet(dirty_style)
        self.ui.lineEdit_currcavpos.setStyleSheet(dirty_style)
        self.ui.lineEdit_cav_phase_view.setStyleSheet(dirty_style)
        self.ui_data_dirty=True
    def ui_phase_edited(self):
        dirty_style="color: rgb(255, 0, 0);"
        self.ui.lineEdit_cav_phase.setStyleSheet(dirty_style)
        self.ui.lineEdit_cav_phase_view.setStyleSheet(dirty_style)
        self.ui_data_edited()
    def ui_pos_edited(self):
        self.ui.lineEdit_currcavpos.setStyleSheet("color: rgb(255, 0, 0);")
        self.ui_data_edited()
    def ui_data_edited(self):
        self.ui_data_dirty=True
        if self.auto_recalculates():
            self.update_phase_calc()

    def auto_recalculates(self):
        return self.model.auto_recalculate
        
    def ui_set_auto_recalc(self):
        self.model.auto_recalculate=self.ui.checkBox_auto_calc.isChecked()

    def sync_ui_from_model(self,changed_cavity_id:int,changed_column_list:list):
        ui_current_cavity_id=self.ui.spinBox_cavid.value()
        if ui_current_cavity_id!=changed_cavity_id:
            ##NO NEED TO UPDATE UI
            return
            
        data_dict=self.model.get_dict_by_cavity_id(changed_cavity_id)
        marked_for_update_dict={}
        for key in changed_column_list:
            marked_for_update_dict[key]=data_dict[key]
        self.update_ui_from_dict(marked_for_update_dict)

    def automode_clicked(self):
        if not self.ui.checkBox_lockinputphase.isChecked():
            QMessageBox.warning(None, "警告", 
                            f"未设置初始相位，请设置初始相位后继续。")
            self.ui_motor.checkBox_automode.setChecked(False)
            return
        if self.ui_motor.checkBox_automode.isChecked():
            self.disable_motor_buttons()
            self.disable_vnc_buttons()
            self.disable_data_ui()
            self.ui_motor.pushButton_autophasescan.setEnabled(True)
            QMessageBox.warning(None, "警告", 
                            f"自动模式会覆盖之前保存的相位数据，请先确认数据已经保存。")
        else:
            self.enable_motor_buttons()
            self.enable_vnc_buttons()
            self.enable_data_ui()
            self.ui_motor.pushButton_autophasescan.setEnabled(False)
    @asyncSlot()
    async def ui_auto_phase_scan(self):
        #####DISABLE BUTTON
        self.ui_motor.pushButton_autophasescan.setEnabled(False)
        result=self.auto_scan_dlg.exec_()
        if result==QDialog.Accepted:
            speed=self.auto_scan_dlg.vec
            waitime=self.auto_scan_dlg.waittime
            await self._auto_phase_scan(speed,waitime)
        #####ENABLE BUTTON
        self.ui.pushButton_autophasescan.setEnabled(True)
    @asyncSlot()
    async def _auto_phase_scan(self,speed:float=10.0,waittime:float=5.0):
        #####check status
        unsafe_run=True
        if not self.is_vnc_connected():
            if not unsafe_run:
                self.automode_helper_signal.emit("VNC_DISCONNECTED")
                return
        if not self.is_motor_connected():
            if not unsafe_run:
                self.automode_helper_signal.emit("MODBUS_DISCONNECTED")
                return
        #####GET SAVED CAVITY ID AND POSITION
        cavids=self.model.get_cavity_id_list()
        cavposs=self.model.get_cavity_position_list()
        if len(cavids)==0:
            self.automode_helper_signal.emit("NO_CAVITY_DATA")
            return
        if len(cavposs)==0:
            self.automode_helper_signal.emit("NO_CAVITY_DATA")
            return
        #####DISABLE AUTO CALC
        self.ui.checkBox_auto_calc.setChecked(False)
        #####START SCAN
        vel=speed ##get velocity
        wait_time_pre=waittime
        wait_time_post=1
        scanresults=[]
        for i in range(len(cavids)):
            cavid=cavids[i]
            cavpos=cavposs[i]
            self.ui.spinBox_cavid.setValue(cavid)
            
            await self._setpos(cavpos,vel)
            await asyncio.sleep(wait_time_pre)
            try:
                fresult=vnc.get_phase(self.inst)
            except VisaIOError:
                if not unsafe_run:
                    self.automode_helper_signal.emit("VNC_DISCONNECTED")
                    return
                else:
                    fresult=i*10
            except AttributeError:
                if not unsafe_run:
                    self.automode_helper_signal.emit("VNC_DISCONNECTED")
                    return
                else:
                    fresult=i*10
            await asyncio.sleep(wait_time_post)
            time=datetime.datetime.now()
            self.update_phase_calc()
            self._saveline_reduced(cavid,new=True)
            self.model.update_cav_data_by_dict(cavid,{"腔相位":fresult})
            self.model.update_cav_data_by_dict(cavid,{"时间":str(time)})
            scanresults.append((cavid,fresult))
            
            
        self.automode_helper_signal.emit("SUCCESS")
        self.ui.checkBox_auto_calc.setChecked(True)
        return scanresults
    @asyncSlot(str)
    async def automode_helper_slot(self,event:str="None"):
        if event=="VNC_DISCONNECTED":
            await self._show_aysnc_messagebox("VNC未连接","VNC未连接，请检查连接")
        elif event=="MODBUS_DISCONNECTED":
            await self._show_aysnc_messagebox("电机未连接","电机未连接，请检查连接")
        elif event=="SUCCESS":
            await self._show_aysnc_messagebox("成功","自动模式完成")
        elif event=="NO_CAVITY_DATA":
            await self._show_aysnc_messagebox("错误","没有腔体数据，请先提供位置和ID数据")
        else:
            print(" automode_helper unknown event:",event)
            return

    def disable_data_ui(self):
        self.ui.spinBox_cavid.setEnabled(False)
        self.ui.lineEdit_cav_phase.setEnabled(False)
        self.ui.lineEdit_currcavpos.setEnabled(False)
        self.ui.lineEdit_inputphase.setEnabled(False)
        self.ui.lineEdit_vnc_phase.setEnabled(False)
        self.ui_motor.lineEdit_relpos.setEnabled(False)
        self.ui_motor.lineEdit_relvec.setEnabled(False)
    def enable_data_ui(self):
        self.ui.spinBox_cavid.setEnabled(True)
        self.ui.lineEdit_cav_phase.setEnabled(True)
        self.ui.lineEdit_currcavpos.setEnabled(True)
        self.ui.lineEdit_inputphase.setEnabled(True)
        self.ui.lineEdit_vnc_phase.setEnabled(True)
        self.ui_motor.lineEdit_relpos.setEnabled(True)
        self.ui_motor.lineEdit_relvec.setEnabled(True)
    def disable_motor_buttons(self):
        self.ui_motor.pushButton_setpos.setEnabled(False)
        self.ui_motor.pushButton_resetpos.setEnabled(False)
        self.ui_motor.pushButton_addmov.setEnabled(False)
        self.ui.pushButton_savecavpos.setEnabled(False)
        self.ui.pushButton_movetocavpos.setEnabled(False)
    def enable_motor_buttons(self):
        self.ui_motor.pushButton_setpos.setEnabled(True)
        self.ui_motor.pushButton_resetpos.setEnabled(True)
        self.ui_motor.pushButton_addmov.setEnabled(True)
        self.ui.pushButton_savecavpos.setEnabled(True)
        self.ui.pushButton_movetocavpos.setEnabled(True)
    def is_motor_connected(self):
        if self.client is None:
            return False
        else:
            return True
    def is_vnc_connected(self):
        if self.inst is None:
            return False
        else:
            return True
    def disable_vnc_buttons(self):
        self.ui.pushButton_record_vnc_phase.setEnabled(False)
    def enable_vnc_buttons(self):
        self.ui.pushButton_record_vnc_phase.setEnabled(True)
    def get_cav_id(self):
        return int(self.ui.spinBox_cavid.value())
    def check_input_phase_data_available(self):

        if self.ui.spinBox_cavid.value()>0 and not self.ui.checkBox_lockinputphase.isChecked():
            return False
        else:
            return True
    def ui_check_input_phase_data_available(self):
        if not self.check_input_phase_data_available():
            QMessageBox.critical(None, "错误", 
                            f"未设定输入耦合器相位，请在相位设置中勾选设置完成后重试")
            return False
        else:
            return True
    def current_is_input_coupler(self):
        cavid=int(self.ui.spinBox_cavid.value())
        if cavid==0:
            return True
        else:
            return False
    def next_cavity(self):
        id=int(self.ui.spinBox_cavid.value())

        if not self.model.cavity_id_exists_in_data(id) or self.ui_data_dirty:
            QMessageBox.critical(None, "错误",
                                 f"请先保存当前腔数据")
            return
       
        if float(self.ui_motor.lineEdit_relpos.text())==float(self.ui.lineEdit_currcavpos.text()):
            QMessageBox.critical(None, "错误",
                                f"请先移动电机到下个腔位置")
            return
        
        if self.inst:
            self.ui.lineEdit_currcavpos.setText(str(self.ui_motor.lineEdit_relpos.text()))
        target_cavid=int(self.ui.spinBox_cavid.value())+1
        self.model.set_current_cavity_id(target_cavid)
        if not self.model.cavity_id_exists_in_data(target_cavid):
            self.save_line(target_cavid)
            self.set_ui_data_dirty()
        try:
           self.update_phase_calc()
        except ValueError as err:
            QMessageBox.critical(None, "错误", 
                            err.args[0])
            cavid=self.model.recover_cavity_id()
            self.ui.spinBox_cavid.setValue(cavid)
            return
        self.ui.spinBox_cavid.setValue(target_cavid)
        return
    def previous_cavity(self):
        id=int(self.ui.spinBox_cavid.value())
        if not self.model.cavity_id_exists_in_data(id) or self.ui_data_dirty:
            QMessageBox.critical(None, "错误",
                                 f"请先保存当前腔数据")
            return
        target_id=id-1
        if target_id<1:
            target_id=1
        self.ui.spinBox_cavid.setValue(target_id)
        return
    def ui_update_cavity_id(self):
        if not self.ui_check_input_phase_data_available():
            return
        

        cavid=int(self.ui.spinBox_cavid.value())
        self.model.set_current_cavity_id(cavid)
        if self.model.cavity_id_exists_in_data(cavid):
            ###load cavity data
            dict=self.model.get_dict_by_cavity_id(cavid)
            self.update_ui_from_dict(dict)
            if self.auto_recalculates():
                self.update_phase_calc()
            return
        else:
            cavid=self.model.recover_cavity_id()
            self.ui.spinBox_cavid.setValue(cavid)
            return
        ###### DONT CREATE NEW LINE FROM COMBOBOX, ONLY FROM NEXT CAVITY BUTTON
            self.save_line(cavid)
            self.set_ui_data_dirty()
        try:
           self.update_phase_calc()
        except ValueError as err:
            QMessageBox.critical(None, "错误", 
                            err.args[0])
            cavid=self.model.recover_cavity_id()
            self.ui.spinBox_cavid.setValue(cavid)
            return
        
    def save_cavity_data_ui(self):
        if self.current_is_input_coupler():
            return
        # if 
        self.saveline_ui(new=True)
        if self.auto_recalculates():
            self.update_phase_calc()
        

    def update_phase_calc(self):
        if not self.check_input_phase_data_available():
            return
        cavid=int(self.ui.spinBox_cavid.value())
        # self.model.set_current_cavity_id(cavid)
        if cavid==1 and not self.model.cavity_id_exists_in_data(cavid):
            self.ui.lineEdit_targetphase_average.setText(str(self.model.calc_target_phase_final(cavid)))
            return
        if not self.model.cavity_id_exists_in_data(cavid):
            return 
        try:
            cav_phase=float(self.ui.lineEdit_cav_phase.text())
            self.model.set_cavity_phase(cavid,cav_phase)
        
        except ValueError as err:
            print(err)
            return
        
        if not self.auto_recalculates():
            cavids_marked_for_calc=[cavid]
            self.model.recalculate_phase_all(cavids_marked_for_calc) ###RECAL AGAIN


        self.ui.lineEdit_targetphase_singlecell.setText(str(self.model.get_target_phase_single_cell(cavid)))
        self.ui.lineEdit_single_cell_phase_shift.setText(str(self.model.get_phase_shift(cavid)))
        self.ui.lineEdit_targetphase_sum.setText(str(self.model.get_target_phase_sum(cavid)))
        self.ui.lineEdit_targetphase_average.setText(str(self.model.get_target_phase_final(cavid)))
        
        singlecell_phase_error=self.model.get_phase_error_single_cell(cavid)
        self.ui.lineEdit_singlecell_phase_error.setText(str(singlecell_phase_error))
        if self.model.is_single_cell_phase_error_acceptable(singlecell_phase_error):
            self.ui.lineEdit_singlecell_phase_error.setStyleSheet("background-color: green;")
        else:
            self.ui.lineEdit_singlecell_phase_error.setStyleSheet("background-color: red;")
        sum_phase_error=self.model.get_phase_error_sum(cavid)
        self.ui.lineEdit_sum_phase_error.setText(str(sum_phase_error))
        if self.model.is_sum_phase_error_acceptable(sum_phase_error):
            self.ui.lineEdit_sum_phase_error.setStyleSheet("background-color: green;")
        else:
            self.ui.lineEdit_sum_phase_error.setStyleSheet("background-color: red;")
        return
    
    def ui_calculate_target_phase(self):
        if not self.ui_check_input_phase_data_available():
            return
        cavid=int(self.ui.spinBox_cavid.value())
        if not self.model.cavity_id_exists_in_data(cavid):
            QMessageBox.critical(None, "错误", 
                            f"请先保存当前腔数据")
            return
        try:
            self.update_phase_calc()
        except ValueError as err:
            QMessageBox.critical(None, "错误", 
                            err.args[0])
            return
        QMessageBox.information(None, "计算", 
                            "目标相位计算完成")
        return
    async def _setpos(self,pos,vel):
        if self.client is None:
            return
        if pos>3000:
            pos=3000
        await modbus.send_rel_pos_vel(self.client,pos,vel)
        await modbus.rel_cmd(self.client)
        await modbus.wait_rel_cmd_done(self.client)
        return
    @asyncSlot()
    async def setpos_ui(self):
        try:
            pos=float(self.ui_motor.lineEdit_relpos.text())
            if pos>3000:
                pos=3000
                self.ui_motor.lineEdit_relpos.setText(str(pos))
            vel=float(self.ui_motor.lineEdit_relvec.text())
            self.disable_motor_buttons()
            await self._setpos(pos,vel)
            self.enable_motor_buttons()
            return
        except:
            return
    @asyncSlot()
    async def setpos2cavpos(self):
        try:
            postarget=float(self.ui.lineEdit_currcavpos.text())
            poscurr=float(self.ui_motor.lineEdit_relpos.text())
            if poscurr==postarget:
                return
            self.ui_motor.lineEdit_relpos.setText(str(postarget))
            vel=float(self.ui_motor.lineEdit_relvec.text())
            self.disable_motor_buttons()
            await self._setpos(postarget,vel)
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
            self.ui_motor.lineEdit_relpos.setText("0")
            return
        except:
            return
    @asyncSlot()
    async def addmov(self):

        try: 
            extpos=float(self.ui_motor.lineEdit_movpos.text())
            if extpos>1000:
                extpos=1000
                self.ui_motor.lineEdit_movpos.setText(str(extpos))
            elif extpos<-1000:
                extpos=-1000
                self.ui_motor.lineEdit_movpos.setText(str(extpos))
            pos=float(self.ui_motor.lineEdit_relpos.text())
            newpos=pos+extpos
            self.ui_motor.lineEdit_relpos.setText(str(newpos))
            await self.setpos_ui()
            return
        except:
            return
    def set_airtype(self):
        if self.app is None:
            return
        if self.ui.radioButton_air.isChecked():
            self.app.set_air()
        elif self.ui.radioButton_nitro.isChecked():
            self.app.set_nitrogen()
    def set_temp_constraint(self):
        if self.app is None:
            return
        cond=False
        if self.ui.checkBox_cavtempasairtemp.isChecked():
            cond=True
        self.ui.lineEdit_cavtemp.setEnabled(not cond)
        self.app.set_temp_restraint_cond(cond=cond)
    def get_temp_constraint(self):
        if self.app is None:
            return False
        cond=self.app.get_temp_restraint_cond()
        self.ui.checkBox_cavtempasairtemp.setChecked(cond)
        self.ui.lineEdit_cavtemp.setEnabled(not cond)
        return cond
    
    def set_current_vnc_phase_as_inputphase(self):
        self.ui.lineEdit_inputphase.setText(self.ui.lineEdit_vnc_phase.text())
        
        
    def set_current_vnc_phase_as_cavity_phase(self):
        self.ui.lineEdit_cav_phase.setText(self.ui.lineEdit_vnc_phase.text())
        #self._saveline_reduced(new=True)

    def lock_inputphase(self):
        locked=self.ui.checkBox_lockinputphase.isChecked()
        self.ui.pushButton_setinputphase.setEnabled(not locked)
        self.ui.lineEdit_inputphase.setReadOnly(locked)
        if locked:
            self.model.set_input_coupler_phase(float(self.ui.lineEdit_inputphase.text()))
            self.ui.checkBox_lockinputphase.setStyleSheet("color: rgb(0, 255, 0);")
            if self.auto_recalculates():
                self.update_phase_calc()
        else:
            self.ui.checkBox_lockinputphase.setStyleSheet("color: rgb(255, 0, 0);")
        
        
    def save_real_position_as_cavity_position(self):
        if self.current_is_input_coupler():
            return
        
        self.ui.lineEdit_currcavpos.setText(self.ui_motor.lineEdit_realpos.text())
        # print("currpos:",self.ui.lineEdit_currcavpos.text())
        #self._saveline_reduced()
        pass
    def save_set_position_as_cavity_position(self):
        if self.current_is_input_coupler():
            return
        
        self.ui.lineEdit_currcavpos.setText(self.ui.lineEdit_relpos.text())
        # print("currpos:",self.ui.lineEdit_currcavpos.text())
        #self._saveline_reduced()
        pass
    def freqcor(self):
        self.app.set_rel_humid(float(self.ui.lineEdit_humidity.text()))
        self.app.set_amb_pressure(float(self.ui.lineEdit_airpressure.text()))

        if self.app.get_temp_restraint_cond():
            self.ui.lineEdit_cavtemp.setText(self.ui.lineEdit_airtemp.text())

        self.app.set_cav_temp(float(self.ui.lineEdit_cavtemp.text()))
        self.app.set_amb_temp(float(self.ui.lineEdit_airtemp.text()))
        
        
        self.app.set_origin_freq(float(self.ui.lineEdit_originfreq.text()))
        self.app.set_vac_op_temp(float(self.ui.lineEdit_operate_temp.text()))
        self.app.update_result()
        self.ui.lineEdit_freq_corred.setText(str(self.app.get_results()[0]))
        self.ui.lineEdit_freqoffset.setText(str(self.app.get_results()[1]))
        QMessageBox.information(None, "校准", 
                            "频率数据校准完成")
    def update_ui_from_dict(self,indict):
        ##TO DO
        if "腔相位" in indict.keys():         
            self.ui.lineEdit_cav_phase.setText(str(indict["腔相位"]))
        if "目标相位-累计相移" in indict.keys():
            self.ui.lineEdit_targetphase_sum.setText(str(indict["目标相位-累计相移"]))
        if "目标相位-单腔相移" in indict.keys():
            self.ui.lineEdit_targetphase_singlecell.setText(str(indict["目标相位-单腔相移"]))
        if "单腔相移" in indict.keys():
            self.ui.lineEdit_single_cell_phase_shift.setText(str(indict["单腔相移"]))
        if "腔位置" in indict.keys():
            self.ui.lineEdit_currcavpos.setText(str(indict["腔位置"]))
        if "目标相位" in indict.keys():
            self.ui.lineEdit_targetphase_average.setText(str(indict["目标相位"]))

        self.set_ui_data_clean()####SET CLEAN
        pass
    def save_line(self,cavid):
        if not self.ui_check_input_phase_data_available():
            return
        try:
            self._saveline_reduced(cavid,new=True)
        except ValueError as err:
            print(err)

    def _saveline_reduced(self,cavid,new=False):
        ###save data with no calcs
        if not self.ui_check_input_phase_data_available():
            return
        data=self.model.create_empty_dict()
        if new:
            time=datetime.datetime.now()
            data["时间"]=str(time)
        try:
            data["腔ID"]=cavid
            data["腔位置"]=float(self.ui.lineEdit_currcavpos.text())
            data["输入相位"]=float(self.ui.lineEdit_inputphase.text())
            data["腔相位"]=float(self.ui.lineEdit_cav_phase.text())
            data["校准频率(MHz)"]=float(self.ui.lineEdit_freq_corred.text())
            data["湿度(%)"]=float(self.ui.lineEdit_humidity.text())
            data["气压(Pa)"]=float(self.ui.lineEdit_airpressure.text())
            data["腔温(℃)"]=float(self.ui.lineEdit_cavtemp.text())
            data["气温(℃)"]=float(self.ui.lineEdit_airtemp.text())
            data["真空频率(MHz)"]=float(self.ui.lineEdit_originfreq.text())
            data["工作温度(℃)"]=float(self.ui.lineEdit_operate_temp.text())
            self.model.update_cav_data_by_dict(cavid,data)
            self.set_ui_data_clean()
        except:
            raise ValueError("数据格式错误，请检查输入")
        return

    def saveline_ui(self,new=False):
        ###save with all data
        if not self.ui_check_input_phase_data_available():
            return
        cavid=self.ui.spinBox_cavid.value()
        try:
            self._saveline_reduced(cavid,new=new)
        except ValueError as err:
            QMessageBox.warning(None, "保存失败", 
                            "id:{} 请检查数据格式".format(cavid))
            return
        QMessageBox.information(None, "保存完成", 
                            "id:{} 数据保存完成".format(cavid))
        
        return
    def delete_last_line(self):
        rowCount=self.model.rowCount()

        if rowCount>0:
            row=self.model.takeRow(rowCount-1)
        else:
            return
        removed_id=self.model.get_cavity_id_from_row(row)
        curr_id=int(self.ui.spinBox_cavid.value())
        if removed_id==curr_id:
            self.ui.spinBox_cavid.setValue(int(self.ui.spinBox_cavid.value())-1)
    def read_csv_ui(self):
            
        # 获取模型
        model = self.model
        if model is None:
            return
        
        # 获取文件路径
        file_path, _ = QFileDialog.getOpenFileName(
            None, "加载CSV文件", "", "CSV文件 (*.csv)")
        
        if not file_path:
            return  # 用户取消了保存
        
        try:
            # 打开文件并读取数据
            self.model.read_csv(file_path)
        except PermissionError:
            QMessageBox.critical(None, "错误", "没有读取权限，请确定权限")
            return
        except Exception as e:
            QMessageBox.critical(None, "错误", f"读取文件时出错: {str(e)}")
            return

        # 更新UI
        if self.ui.checkBox_lockinputphase.isChecked():
            self.ui.checkBox_lockinputphase.setChecked(False)

        
        self.ui.lineEdit_inputphase.setText(str(self.model.get_input_coupler_phase()))
        self.ui.checkBox_lockinputphase.setChecked(True)

        self.ui.spinBox_cavid.setValue(1)
        self.ui_update_cavity_id()

        return

    def save_csv_ui(self):
        
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
            self.model.save_csv(file_path)
        except PermissionError:
            QMessageBox.critical(None, "错误", "没有写入权限，请选择其他位置保存")
        except Exception as e:
            QMessageBox.critical(None, "错误", f"保存文件时出错: {str(e)}")
        return
    
    @asyncClose
    async def closeEvent(self, event):  # noqa:N802
        print("Main dialog close event")
        if self.client:
            await modbus.stop_PC_control(self.client)
            await modbus.stop_async_simple_client(self.client)
        if self.rm and self.inst:
            vnc.close_visa_client(self.rm,self.inst)
        self.phase_view_dlg.close()
        self.motor_control_dlg.close()
        self.app.stop_app()
        self.client = None
        self.rm = None
        self.inst = None
        self.app = None
        event.accept()
    async def query_modbus_first(self):
        if self.client is None:
            print("Modbus server failed to connect.")
            return
        self.ui_motor.lineEdit_relvec.setText(str(await modbus.read_float(self.client,"PC_M6_Realtive_Vel1")))
        self.ui_motor.lineEdit_relpos.setText(str(await modbus.read_float(self.client,"PC_M6_Realtive_Pos1")))
    async def query_modbus_period(self):
        while True:
            if self.client:
                self.ui_motor.lineEdit_realpos.setText(str(await modbus.read_float(self.client,"PC_M6_Act_Pos1")))
                self.ui_motor.lineEdit_realvec.setText(str(await modbus.read_float(self.client,"PC_M6_Act_Vel1")))
            
                # print("query_loc:",self.ui.lineEdit_realpos.text())
                # print("now sleep")
            await asyncio.sleep(self.query_delay)
    async def query_vnc_period(self):
        while True:
            if self.inst:
                # print("query_vnc_period")
                fresult=vnc.get_phase(self.inst)
                if not self.ui.checkBox_freeze_phase.isChecked():
                    self.ui.lineEdit_vnc_phase.setText(str(fresult))
                    self.ui.lineEdit_vnc_phase.setStyleSheet("")
                    # print("query_vnc:",self.ui.lineEdit_vnc_phase.text())
                else:
                    self.ui.lineEdit_vnc_phase.setStyleSheet("color: rgb(255, 0, 0);")
            await asyncio.sleep(self.query_delay)
    async def query_app_first(self):
        self.ui.lineEdit_humidity.setText(str(self.app.get_rel_humid()))
        self.ui.lineEdit_airpressure.setText(str(self.app.get_amb_pressure()))
        self.ui.lineEdit_cavtemp.setText(str(self.app.get_cav_temp()))
        self.ui.lineEdit_airtemp.setText(str(self.app.get_amb_temp()))
        self.ui.lineEdit_originfreq.setText(str(self.app.get_origin_freq()))
        self.ui.lineEdit_operate_temp.setText(str(self.app.get_vac_op_temp()))
        self.get_temp_constraint()
        self.app.update_result()
        self.ui.lineEdit_freq_corred.setText(str(self.app.get_results()[0]))
        self.ui.lineEdit_freqoffset.setText(str(self.app.get_results()[1]))
        
    
    async def start(self):
        event_loop=asyncio.get_event_loop()
        task_app=event_loop.create_task(self.start_convertf_app())
        await task_app
        event_loop.create_task(self.query_app_first())
        
        task1=event_loop.create_task(self.start_modbus_client_ui(),name="start_modbus_client")
        task2=event_loop.create_task(self.start_vnc_client_ui(),name="start_vnc_client")
        
        
        await task1
        await task2
        
        await self.query_modbus_first()
        event_loop.create_task(self.query_modbus_period(),name="query_modbus_period")
        event_loop.create_task(self.query_vnc_period(),name="query_vnc_period")
        

    @asyncSlot()
    async def start_vnc_client_button(self):
        result=await self.start_vnc_client_ui(restart=True,retry_times=3)
        return result
    async def start_vnc_client_ui(self,restart=False,retry_times=3):
        result=await self.start_vnc_client(restart,retry_times)
        print("starting_vnc_client:",result)
        self.ui.checkBox_VNCstat.setChecked(result)
    async def start_vnc_client(self,restart=False,retry_times=3):
        if self.inst is not None:
            if restart:
                vnc.close_visa_client(self.rm,self.inst)
            else:
                return True
        for i in range(retry_times):
            try:
                self.rm, self.inst = vnc.create_visa_client()
                vnc.set_meas_mode(self.inst)
            except VisaIOError:
                self.rm, self.inst = None,None
                await asyncio.sleep(1)
                continue

            return True
        return False
    @asyncSlot()
    async def start_modbus_client_button(self):
        result=await self.start_modbus_client_ui(restart=True,retry_times=3)
        return result
    async def start_modbus_client_ui(self,restart=False,retry_times=3):
        result=await self.start_modbus_client(restart,retry_times)
        print("starting_modbus_client:",result)
        self.ui.checkBox_motorstat.setChecked(result)
        return result
    @asyncSlot()
    async def start_modbus_client(self,restart=False,retry_times=3):
        if self.client is not None:
            if restart:
                await modbus.stop_async_simple_client(self.client)
            else:
                return True
        for i in range(retry_times):
            try:
                self.client = await modbus.start_async_simple_client("192.168.1.100",502)
                await modbus.start_PC_control(self.client)
            except ConnectionException:
                self.client = None
                print(f"Try {i} Starting Modbus Client Error:ConnectionException")
                await asyncio.sleep(1)
                continue
            except ModbusIOException:
                self.client = None
                print(f"Try {i} Starting Modbus Client Error:IOException")
                await asyncio.sleep(1)
                continue
            
            return True
        return False    
    async def start_convertf_app(self):
        self.app=convertf.ConvertfApp()

if __name__ == "__main__":
    pass