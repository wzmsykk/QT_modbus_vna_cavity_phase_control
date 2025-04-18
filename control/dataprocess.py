
import datetime
from PyQt5 import QtCore
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import pyqtSignal
import pandas as pd
import csv

class CavityPhaseModel(QStandardItemModel):
    phase_data_changed_signal=pyqtSignal(int)###int:cavity_id
    data_changed_signal=pyqtSignal(int,list)###int:cavity_id list:changed_column_names
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self, parent)
        self.input_coupler_phase:float=0
        self.designed_shift_per_cell:float=240
        self._phase_round_const:float=360 ###360 for deg, 2Pi for rad
        assert self._phase_round_const>0
        self.current_cavity_id:int=0
        self.previous_cavity_id:int=0
        self._cavity_id_name_string:str="腔ID"
        self._cavity_phase_name_string:str="腔相位"
        self._cavity_position_name_string:str="腔位置"
        self._phase_error_sum_name_string:str="累计相移误差"
        self._columnname_ref=["时间","腔ID","腔位置","输入相位","腔相位","单腔相移","目标相位-累计相移","目标相位-单腔相移","目标相位","单腔相移误差","累计相移误差","校准频率(MHz)","湿度(%)","气压(Pa)","腔温(℃)","气温(℃)","真空频率(MHz)","工作温度(℃)"]
        self.columnname=["时间",self._cavity_id_name_string,self._cavity_position_name_string,"输入相位",self._cavity_phase_name_string,"单腔相移","目标相位-累计相移","目标相位-单腔相移","目标相位","单腔相移误差","累计相移误差","校准频率(MHz)","湿度(%)","气压(Pa)","腔温(℃)","气温(℃)","真空频率(MHz)","工作温度(℃)"]
        assert self._list_eq(self._columnname_ref,self.columnname)
        self.setHorizontalHeaderLabels(self.columnname)

        self.data_dirty_list=[]
        self.auto_recalculate=True

        self.phase_data_changed_signal.connect(self._on_phase_data_changed)
        self.itemChanged.connect(self._on_item_changed)
    def _list_eq(self,list1,list2):
        if len(list1)!=len(list2):
            return False
        for i in range(len(list1)):
            if list1[i]!=list2[i]:
                return False
        return True
    def _reset_data(self):
        self.clear()
        self.setHorizontalHeaderLabels(self.columnname)
        self.setColumnCount(len(self.columnname))
        self.setRowCount(0)
        self.data_dirty_list.clear()
    def _on_phase_data_changed(self,cavity_id:int):
        self.data_dirty_list.append(cavity_id)
        if self.auto_recalculate:
            self.recalculate_phase_all()
    def _on_item_changed(self,item:QStandardItem):
        if item is None:
            return
        if item.text() is None:
            return
        if self.rowCount()==0:
            return
        cavity_id=int(self.item(item.row(),self._cavity_id_column_index()).text())
        if item.column()==self._cavity_phase_column_index():
            self.phase_data_changed(cavity_id)
            
        elif item.column()==self._cavity_position_column_index():
            self.data_changed(cavity_id,changed_column_names=[self._cavity_position_name_string])

    def data_changed(self,cavity_id:int,changed_column_names:list=[]):
        self.data_changed_signal.emit(cavity_id,changed_column_names)
    def phase_data_changed(self,cavity_id:int):
        self.phase_data_changed_signal.emit(cavity_id)
        self.data_changed(cavity_id,changed_column_names=[self._cavity_phase_name_string])
    def set_current_cavity_id(self,id:int):
        self.previous_cavity_id=self.current_cavity_id
        self.current_cavity_id=id
    def recover_cavity_id(self):
        self.current_cavity_id=self.previous_cavity_id
        return self.current_cavity_id
    def get_phase_by_cavity_id(self,cavity_id:int):
        cav_index=self._search_index_from_cavity_id(cavity_id)
        if cav_index is None:
                raise ValueError("未找到腔体id:{} 的数据".format(cav_index))
        return float(self.item(cav_index,self._cavity_phase_column_index()).text())
    def get_ref_phase(self,current_cavity_id):

        if current_cavity_id==1:
            return self.input_coupler_phase
        else:
            ref_cav_id=current_cavity_id-1
            return float(self.get_phase_by_cavity_id(ref_cav_id))
    def get_ref_phase_error_sum(self,current_cavity_id):
        if current_cavity_id==1:
            return 0
        else:
            ref_cav_id=current_cavity_id-1
            return float(self.get_phase_error_sum(ref_cav_id))
    def update_cav_data_by_dict(self,cavity_id:int,data:dict):
        ###check if already exists
        
        sresult=self._search_index_from_cavity_id(cavity_id)
        if sresult is None:
            row_index=self._search_insert_row_loc(cavity_id)
            items=self.create_empty_row()
            newitems=self._update_row_items(items,data)
            self.insertRow(row_index,newitems)
        else:
            row_index=self._search_insert_row_loc(cavity_id)
            items=self.takeRow(row_index)
            newitems=self._update_row_items(items,data)
            self.insertRow(row_index,newitems)
        print("cav_id:",cavity_id,"row_index",row_index)

        self.phase_data_changed(cavity_id)
        return
    def create_empty_row(self):
        time=datetime.datetime.now()
        newline=[]

        newline.append(str(time))##时间
        for i in range(len(self.columnname)-1):
            newline.append(0)
        newline=[QStandardItem(str(item)) for item in newline]
        return newline
    def create_empty_dict(self):
        dict={}
        for key in self.columnname:
            dict[key]=None
        return dict
    def _update_row_items(self,items:list,data:dict):
        for key,item in data.items():
            index=self.columnname.index(key)
            items[index]=QStandardItem(str(item))
        return items

    def _get_column_index(self,column_name:str):
        index=self.columnname.index(column_name)
        return index
    def _cavity_id_column_index(self):
        return self._get_column_index(self._cavity_id_name_string)
    def _cavity_position_column_index(self):
        return self._get_column_index(self._cavity_position_name_string)
    def _cavity_phase_column_index(self):
        return self._get_column_index(self._cavity_phase_name_string)
    def _cavity_phase_error_sum_column_index(self):
        return self._get_column_index(self._phase_error_sum_name_string)
    def _search_index_from_cavity_id(self,cavity_id):
        rowCount=self.rowCount()
        if rowCount==0:
            return None
        for i in range(rowCount):
            cid=int(self.item(i,self._cavity_id_column_index()).text())
            if cid==cavity_id:
                return i
        return None
    def _search_insert_row_loc(self,cavity_id):
        rowCount=self.rowCount()
        if rowCount==0:
            return 0
        prefered_ins_index=0
        for i in range(rowCount):
            cid=int(self.item(i,self._cavity_id_column_index()).text())
            if cid<cavity_id:
                prefered_ins_index=i
            elif cid==cavity_id:
                prefered_ins_index=i
                return prefered_ins_index
            else:
                return prefered_ins_index
        return rowCount ###should be in new line
    def cavity_id_exists_in_data(self,cavity_id):
        result=self._search_index_from_cavity_id(cavity_id)
        if result is None:
            return False
        else:
            return True
    def get_row_by_cavity_id(self,cavity_id):
        if not self.cavity_id_exists_in_data(cavity_id):
            return None
        rowidx=self._search_index_from_cavity_id(cavity_id)
        row=[]
        for i in range(len(self.columnname)):
            row.append(self.item(rowidx,i))
        return row
    def get_dict_by_cavity_id(self,cavity_id):
        if not self.cavity_id_exists_in_data(cavity_id):
            return None
        dict=self.create_empty_dict()
        row=self.get_row_by_cavity_id(cavity_id)
        for i in range(len(row)):
            dict[self.columnname[i]]=row[i].text()
        return dict
    def get_cavity_id_from_row(self,row:list[QStandardItem]):
        cindex=self._cavity_id_column_index()
        return int(row[cindex].text())
    def get_cavity_position_from_row(self,row:list[QStandardItem]):
        cindex=self._cavity_position_column_index()
        return int(row[cindex].text())
    def calc_phase_shift(self,cavity_id,cav_phase):
        if cavity_id==1:
            shift=self.input_coupler_phase-cav_phase
        elif cavity_id>1:
            shift=self.get_ref_phase(cavity_id)-cav_phase
        else:
            return 0
        if shift<0:
            shift+=self._phase_round_const
        elif shift>self._phase_round_const:
            shift-=self._phase_round_const
        return shift
    def _calc_phase_error_single_cell(self,cavity_id,cav_phase):
        
        shift=self.get_ref_phase(cavity_id)-cav_phase
        if shift<0:
            shift+=self._phase_round_const
        elif shift>self._phase_round_const:
            shift-=self._phase_round_const
        error=shift-self.designed_shift_per_cell
        error/=2
        return error
    def calc_phase_error_sum_simple(self,cavity_id:int,cav_phase_error:float):
        previous_sum=self.get_ref_phase_error_sum(cavity_id)
        return previous_sum+cav_phase_error
    def calc_phase_error_sum_full(self,cavity_id):
        sum=0
        for i in range(0,cavity_id):
            cav_phase=float(self.item(i,self._cavity_phase_column_index()).text())
            shift=self._calc_phase_error_single_cell(i+1,cav_phase) ###cavid=i+1 since cavity_id starts from 1
            sum+=shift
        return sum
    def calc_target_phase_single_cell(self,cavity_id):
        #return -180<value<180
        if cavity_id==1:
            target=self.input_coupler_phase-self.designed_shift_per_cell
        elif cavity_id>1:
            target=self.get_ref_phase(cavity_id)-self.designed_shift_per_cell
        else:
            return 0
        if target<-self._phase_round_const/2:
            target+=self._phase_round_const
        elif target>self._phase_round_const/2:
            target-=self._phase_round_const
        return target

    def calc_target_phase_sum(self,cavity_id):
        target=self.input_coupler_phase-int(cavity_id)*self.designed_shift_per_cell
        if target<-self._phase_round_const/2:
            while(target<-self._phase_round_const/2):
                target+=self._phase_round_const
        elif target>self._phase_round_const/2:
            while(target>self._phase_round_const/2):
                target-=self._phase_round_const
        return target
    def calc_target_phase_final(self,cavity_id):
        return (self.calc_target_phase_single_cell(cavity_id)+self.calc_target_phase_sum(cavity_id))/2
    def save_csv(self,file_path:str):
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # 写入表头
                header = []
                for col in range(self.columnCount()):
                    header.append(self.headerData(col, QtCore.Qt.Horizontal))
                writer.writerow(header)
                
                # 写入数据行
                for row in range(self.rowCount()):
                    row_data = []
                    for col in range(self.columnCount()):
                        item = self.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)

    def read_csv(self,file_path:str):
        self._reset_data()
        df=pd.read_csv(file_path,header=0)
        columns=df.columns.tolist()
        if not self._list_eq(columns,self.columnname):
            raise ValueError("CSV文件列名不匹配")
        for i in range(len(df)):
            row=df.iloc[i]
            qrow=[QStandardItem(str(item)) for item in row]
            self.insertRow(i,qrow)
    def get_cavity_id_list(self):
        rowCount=self.rowCount()
        if rowCount==0:
            return None
        idlist=[]
        for i in range(rowCount):
            cid=int(self.item(i,self._cavity_id_column_index()).text())
            idlist.append(cid)
        return idlist
    def get_cavity_position_list(self):
        rowCount=self.rowCount()
        if rowCount==0:
            return None
        poslist=[]
        for i in range(rowCount):
            cid=float(self.item(i,self._cavity_position_column_index()).text())
            poslist.append(cid)
        return poslist
    def set_cavity_phase(self,cavity_id:int,phase:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self._cavity_phase_column_index()
        row[index].setText(str(phase))

        self.phase_data_changed(cavity_id)

    def set_phase_shift(self,cavity_id:int,phase_shift:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("单腔相移")
        row[index].setText(str(phase_shift))
    def get_phase_shift(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("单腔相移")
        return float(row[index].text())
    def record_input_coupler_phase(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("输入相位")
        row[index].setText(str(self.input_coupler_phase))
    def set_input_coupler_phase(self,phase:float):
        self.input_coupler_phase=phase
        if self.rowCount()==0:
            return
        else:
            self.recalculate_phase_all(dirty_cavids=[1])
        return
    def get_input_coupler_phase(self):
        return self.input_coupler_phase
    def set_target_phase_final(self,cavity_id:int,target_phase:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("目标相位")
        row[index].setText(str(target_phase))
    def get_target_phase_final(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("目标相位")
        return float(row[index].text())
    def set_target_phase_single_cell(self,cavity_id:int,target_phase:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("目标相位-单腔相移")
        row[index].setText(str(target_phase))
    def get_target_phase_single_cell(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("目标相位-单腔相移")
        return float(row[index].text())
    def set_target_phase_sum(self,cavity_id:int,target_phase:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("目标相位-累计相移")
        row[index].setText(str(target_phase))
    def get_target_phase_sum(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("目标相位-累计相移")
        return float(row[index].text())
    def set_phase_error_single_cell(self,cavity_id:int,phase_error:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("单腔相移误差")
        row[index].setText(str(phase_error))
    def get_phase_error_single_cell(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("单腔相移误差")
        return float(row[index].text())
    def set_phase_error_sum(self,cavity_id:int,phase_error:float):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("累计相移误差")
        row[index].setText(str(phase_error))
    def get_phase_error_sum(self,cavity_id:int):
        row=self.get_row_by_cavity_id(cavity_id)
        if row is None:
            raise ValueError("腔体ID:{}不存在".format(cavity_id))
        index=self.columnname.index("累计相移误差")
        return float(row[index].text())
    def equation(self):
        pass
    def recalculate_phase_all(self,dirty_cavids:list[int]|int=None):
        list_to_process=self.data_dirty_list.copy()
        if len(list_to_process)==0:
            return
        if isinstance(dirty_cavids,int):
            list_to_process.append(dirty_cavids)
        elif isinstance(dirty_cavids,list):
            list_to_process+=dirty_cavids

        mincavid=min(list_to_process)
        maxcavid=self.get_cavity_id_list()[-1]
        for cavid in range(mincavid,maxcavid+1):
            phase=self.get_phase_by_cavity_id(cavid)

            self.record_input_coupler_phase(cavid)
            ####CALC PHASE SHIFT
            phase_shift=self.calc_phase_shift(cavid,phase)
            self.set_phase_shift(cavid,phase_shift)
            self.set_target_phase_single_cell(cavid,self.calc_target_phase_single_cell(cavid))
            self.set_target_phase_sum(cavid,self.calc_target_phase_sum(cavid))
            self.set_target_phase_final(cavid,self.calc_target_phase_final(cavid))
            ####CALC PHASE ERROR
            phase_error_single=self._calc_phase_error_single_cell(cavid,phase)
            self.set_phase_error_single_cell(cavid,phase_error_single)
            phase_error_sum=self.calc_phase_error_sum_simple(cavid,phase_error_single)
            self.set_phase_error_sum(cavid,phase_error_sum)

        self.data_dirty_list.clear()
# if __name__ == '__main__':
#     application = QtGui.QApplication(sys.argv)
#     view = QtGui.QTableView()
#     model = PandasModel(your_pandas_data)
#     view.setModel(model)

#     view.show()
#     sys.exit(application.exec_())