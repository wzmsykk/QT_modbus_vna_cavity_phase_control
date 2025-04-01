import pywinauto
from pywinauto import application

class ConvertfApp():
    def __init__(self):
        self.app=self.start_app()
        self.ctype="v2a"
        self.set_temp_celsius()
        self.set_pressure_Pa()
        self.set_air()
        self.set_convert_type(ctype=self.ctype)
        pass
    def start_app(self):
        app = application.Application()
        app.start(cmd_line='data/CONVERTF.EXE')
        main_window=app["Resonant Frequency Conversion"]
        main_window.wait("visible", timeout=10)
        main_window.minimize()
        return app
    def stop_app(self):
        self.app["Resonant Frequency Conversion"]['Stop programButton'].click()
    def set_temp_celsius(self):
        self.app["Resonant Frequency Conversion"]['degrees C'].click()
    def set_pressure_mBar(self):
        self.app["Resonant Frequency Conversion"]['mBarRadioButton'].click()
    def set_pressure_Pa(self):
        self.app["Resonant Frequency Conversion"]['PaRadioButton'].click()
    def set_air(self):
        self.app["Resonant Frequency Conversion"]["AirRadioButton"].click()
    def set_nitrogen(self):
        self.app["Resonant Frequency Conversion"]["NitrogenRadioButton"].click()
    def get_rel_humid(self):
        return self.app["Resonant Frequency Conversion"]["Rel. humidity (%):Edit"].texts()[0]
    def set_rel_humid(self,rel_humid_percent:float):
        if rel_humid_percent<0:
            rel_humid_percent=0
        elif rel_humid_percent>100:
            rel_humid_percent=100
        self.app["Resonant Frequency Conversion"]["Rel. humidity (%):Edit"].set_text(str(rel_humid_percent))

    def get_vac_op_temp(self):
        return self.app["Resonant Frequency Conversion"]["Edit"].texts()[0]
    def set_vac_op_temp(self,temp:float):
        self.app["Resonant Frequency Conversion"]["Edit"].set_text(str(temp))

    def get_amb_temp(self):
        return self.app["Resonant Frequency Conversion"]["Edit2"].texts()[0]
    def set_amb_temp(self,temp:float):
        self.app["Resonant Frequency Conversion"]["Edit2"].set_text(str(temp))

    def get_amb_pressure(self):
        return self.app["Resonant Frequency Conversion"]["Edit3"].texts()[0]
    def set_amb_pressure(self,pressure:float):
        self.app["Resonant Frequency Conversion"]["Edit3"].set_text(str(pressure))

    def get_cav_temp(self):
        return self.app["Resonant Frequency Conversion"]["Edit6"].texts()[0]    
    def set_cav_temp(self,temp:float):
        self.app["Resonant Frequency Conversion"]["Edit6"].set_text(str(temp))

    def get_origin_freq(self):
        return self.app["Resonant Frequency Conversion"]["Edit5"].texts()[0]      
    def set_origin_freq(self,freq:float):
        self.app["Resonant Frequency Conversion"]["Edit5"].set_text(str(freq))
        
    def set_temp_restraint_cond(self,cond:bool=False):
        if cond:
            self.app["Resonant Frequency Conversion"]["CheckBox"].check()
        else:
            self.app["Resonant Frequency Conversion"]["CheckBox"].uncheck()
    def get_temp_restraint_cond(self):
        cond=self.app["Resonant Frequency Conversion"]["CheckBox"].is_checked()
        return cond
    def update_result(self):
        self.app["Resonant Frequency Conversion"]['Update resultsButton'].click()
    def set_convert_type(self,ctype="v2a"):
        self.ctype=ctype
        if ctype=="v2a":
            ####vaccum to ambient
            self.app["Resonant Frequency Conversion"]['Vacuum frequency to ambient frequencyRadioButton'].click()
            
        elif ctype=="a2v":
            ####ambient to vaccum
            self.app["Resonant Frequency Conversion"]['Ambient frequency to vacuum frequencyRadioButton'].click()
        return

    def get_results(self):
        result=self.app["Resonant Frequency Conversion"]['Edit8'].texts()
        freq=float(result[1].split()[3])
        offset=float(result[2].split()[3])
        return freq,offset