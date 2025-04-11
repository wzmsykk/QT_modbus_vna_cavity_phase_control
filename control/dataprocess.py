import sys
import datetime
from PyQt5 import QtCore, QtGui
from PyQt5.QtGui import QStandardItemModel, QStandardItem
import pandas as pd
import csv
from math import floor
class CavityPhaseModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self, parent)
        self.input_coupler_phase:float=0
        self.designed_offset_per_cell:float=240
        self._phase_round_const:float=360 ###360 for deg, 2Pi for rad
        assert self._phase_round_const>0
        self.current_cavity_id:int=0
        self.previous_cavity_id:int=0
        self._cavity_id_name_string:str="腔ID"
        self._cavity_phase_name_string:str="腔相位"
        self._cavity_position_name_string:str="腔位置"

        self._columnname_ref=["时间","腔ID","腔位置","输入相位","腔相位","单腔相移","目标相位-累计相移","目标相位-单腔相移","目标相位","单腔相移误差","累计相移误差","校准频率(MHz)","湿度(%)","气压(Pa)","腔温(℃)","气温(℃)","真空频率(MHz)","工作温度(℃)"]
        self.columnname=["时间",self._cavity_id_name_string,self._cavity_position_name_string,"输入相位",self._cavity_phase_name_string,"单腔相移","目标相位-累计相移","目标相位-单腔相移","目标相位","单腔相移误差","累计相移误差","校准频率(MHz)","湿度(%)","气压(Pa)","腔温(℃)","气温(℃)","真空频率(MHz)","工作温度(℃)"]
        assert self._list_eq(self._columnname_ref,self.columnname)
        self.setHorizontalHeaderLabels(self.columnname)
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


    def set_current_cavity_id(self,id:int):
        self.previous_cavity_id=self.current_cavity_id
        self.current_cavity_id=id
    def recover_cavity_id(self):
        self.current_cavity_id=self.previous_cavity_id
        return self.current_cavity_id
    def get_ref_phase(self,current_cavity_id):
        if current_cavity_id==1:
            return self.input_coupler_phase
        else:
            ref_cav_id=current_cavity_id-1
            ref_cav_index=self._search_index_from_cavity_id(ref_cav_id)
            if ref_cav_index is None:
                raise ValueError("未找到腔体id:{} 的数据".format(ref_cav_id))
            return float(self.item(ref_cav_index,self._cavity_phase_column_index()).text())


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
        
    def target_phase_single_cell(self,cavity_id):
        #return -180<value<180
        if cavity_id==1:
            target=self.input_coupler_phase-self.designed_offset_per_cell
        elif cavity_id>1:
            target=self.get_ref_phase(cavity_id)-self.designed_offset_per_cell
        else:
            return 0
        if target<-self._phase_round_const/2:
            target+=self._phase_round_const
        elif target>self._phase_round_const/2:
            target-=self._phase_round_const
        return target

    def target_phase_sum(self,cavity_id):
        target=self.input_coupler_phase-int(cavity_id)*self.designed_offset_per_cell
        if target<-self._phase_round_const/2:
            while(target<-self._phase_round_const/2):
                target+=self._phase_round_const
        elif target>self._phase_round_const/2:
            while(target>self._phase_round_const/2):
                target-=self._phase_round_const
        return target
    def target_phase_final(self,cavity_id):
        return (self.target_phase_single_cell(cavity_id)+self.target_phase_sum(cavity_id))/2
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
            cid=int(self.item(i,self._cavity_position_column_index()).text())
            poslist.append(cid)
        return poslist
# if __name__ == '__main__':
#     application = QtGui.QApplication(sys.argv)
#     view = QtGui.QTableView()
#     model = PandasModel(your_pandas_data)
#     view.setModel(model)

#     view.show()
#     sys.exit(application.exec_())