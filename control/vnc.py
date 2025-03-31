import pyvisa
from pyvisa import ResourceManager
from pyvisa.resources import Resource
def create_visa_client():

    rm = pyvisa.ResourceManager() 
    inst = rm.open_resource('TCPIP0::LINAC::hislip_PXI0_CHASSIS1_SLOT1_INDEX0::INSTR') 
    inst.timeout = 20000 
    return rm, inst
  
def close_visa_client(rm:ResourceManager, inst:Resource):
    inst.close()
    rm.close()

def query_visa_client(inst:Resource, cmd:str):
    result = inst.query(cmd)
    return result

def query_inst_name(inst:Resource):
    name = inst.query("*IDN?")
    return name

def query_inst_calc(inst:Resource):
    result = inst.query("CALC:PAR:CAT?")
    return result
def set_meas_mode(inst:Resource):
    inst.write("CALC:PAR:SEL 'S21'")
    inst.write("CALC:MEAS:FORM PHASe")
    inst.write("CALC:MEAS:MARK:STAT ON")
def query_inst_mark(inst:Resource):
    result = inst.query("CALC:MARK:Y?")
    return result
def convert_mark_result(result:str):
    
    fresult=float(result.split(",")[0])
    return fresult

def get_phase(inst:Resource):
    result = query_inst_mark(inst)
    fresult=convert_mark_result(result)
    return fresult
# print(f"S21:{fresult}dB")