import asyncio
import struct
import time
import os
from numpy import require
import pymodbus.client as ModbusClient
from pymodbus.exceptions import ConnectionException
from pymodbus import (
    FramerType,
    ModbusException,
    pymodbus_apply_logging_config,
)
mapdict={
        "PC_Control":{"address":"QX400.3","loc_name":"PC控制","dtype":"bool"},
        "HMI_Control":{"address":"QX400.4","loc_name":"HMI控制","dtype":"bool"},
        "Input_Estop":{"address":"QX300.0","loc_name":"急停信号","dtype":"bool"},
        "Input_Reset":{"address":"QX300.1","loc_name":"复位信号","dtype":"bool"},
        "Input_Reverse3":{"address":"QX300.2","loc_name":"HMI复位","dtype":"bool"},
        "Start":{"address":"QX400.0","loc_name":"启动","dtype":"bool"},
        "Reset":{"address":"QX400.1","loc_name":"复位","dtype":"bool"},
        "Stop":{"address":"QX400.2","loc_name":"停止","dtype":"bool"},
        "Error_Sign":{"address":"QX410.0","loc_name":"故障标志位","dtype":"bool"},
        "Emergency_Stop":{"address":"QX410.1","loc_name":"急停中","dtype":"bool"},
        "Axis_Clear_Pos6":{"address":"QX421.5","loc_name":"直线电机轴清除位置","dtype":"bool"},
        "PC_M6_Enable":{"address":"QX6600.0","loc_name":"直线电机轴使能","dtype":"bool"},
        "PC_M6_Ready":{"address":"QX6600.1","loc_name":"直线电机轴就绪","dtype":"bool"},
        "PC_M6_Stop_Done":{"address":"QX6600.2","loc_name":"直线电机轴停止完成","dtype":"bool"},
        "PC_M6_Reset":{"address":"QX6600.3","loc_name":"直线电机轴复位","dtype":"bool"},
        "PC_M6_Reset_done":{"address":"QX6600.4","loc_name":"直线电机轴复位完成","dtype":"bool"},
        "PC_M6_JOG_Positive":{"address":"QX6600.5","loc_name":"直线电机轴正转","dtype":"bool"},
        "PC_M6_JOG_Negative":{"address":"QX6600.6","loc_name":"直线电机轴反转","dtype":"bool"},
        "PC_M6_Realtive_Command":{"address":"QX6601.0","loc_name":"直线电机轴相对定位命令","dtype":"bool"},
        "PC_M6_Realtive_Done":{"address":"QX6601.1","loc_name":"直线电机轴相对定位完成","dtype":"bool"},
        "PC_M6_SetPOS_Command":{"address":"QX6601.2","loc_name":"直线电机轴设定位置命令","dtype":"bool"},
        "PC_M6_SetPOS_DONE":{"address":"QX6601.3","loc_name":"直线电机轴设定位置完成","dtype":"bool"},
        "PC_M6_Act_Pos1":{"address":"MW3304","loc_name":"直线电机轴实际位置1","dtype":"int16","next_var":"PC_M6_Act_Pos2","full_loc_name":"直线电机轴实际位置"},
        "PC_M6_Act_Pos2":{"address":"MW3305","loc_name":"直线电机轴实际位置2","dtype":"int16","prev_var":"PC_M6_Act_Pos1"},
        "PC_M6_Act_Vel1":{"address":"MW3306","loc_name":"直线电机轴实际速度1","dtype":"int16","next_var":"PC_M6_Act_Vel2","full_loc_name":"直线电机轴实际速度"},
        "PC_M6_Act_Vel2":{"address":"MW3307","loc_name":"直线电机轴实际速度2","dtype":"int16","prev_var":"PC_M6_Act_Vel1"},
        "PC_M6_JOG_Speed1":{"address":"MW4600","loc_name":"直线电机轴点动速度1","dtype":"int16","next_var":"PC_M6_JOG_Speed2","full_loc_name":"直线电机轴点动速度"},
        "PC_M6_JOG_Speed2":{"address":"MW4601","loc_name":"直线电机轴点动速度2","dtype":"int16","prev_var":"PC_M6_JOG_Speed1"},
        "PC_M6_Realtive_Pos1":{"address":"MW4602","loc_name":"直线电机轴相对位置1","dtype":"int16","next_var":"PC_M6_Realtive_Pos2","full_loc_name":"直线电机轴相对位置"},
        "PC_M6_Realtive_Pos2":{"address":"MW4603","loc_name":"直线电机轴相对位置2","dtype":"int16","prev_var":"PC_M6_Realtive_Pos1"},
        "PC_M6_Realtive_Vel1":{"address":"MW4604","loc_name":"直线电机轴相对速度1","dtype":"int16","next_var":"PC_M6_Realtive_Vel2","full_loc_name":"直线电机轴相对速度"},
        "PC_M6_Realtive_Vel2":{"address":"MW4605","loc_name":"直线电机轴相对速度2","dtype":"int16","prev_var":"PC_M6_Realtive_Vel1"},
    }

def two_short_to_float(high,low):
    return u_two_short_to_float_V1(high,low)
def float_to_two_short(f):
    return u_float_to_two_short_V1(f)
def u_two_short_to_float_V1(high,low):
    return struct.unpack('f', struct.pack('<HH',low,high))[0]
def u_float_to_two_short_V1(f):
    low,high=struct.unpack('<HH', struct.pack('f', f))
    return high,low
def u_two_short_to_float_V2(high,low):
    return float(high*65536+low)/10
def u_float_to_two_short_V2(f):
    f=f*10
    return int(f/65536),int(f%65536)
def translate_address_string(address_string:str):
    if address_string.startswith("QX"):
        address = address_string[2:].split(".")
        address=int(address[0])*8+int(address[1])
    elif address_string.startswith("MW"):
        address = int(address_string[2:])        
    else:
        raise ValueError("address_string should start with QX or MW")
    if not 0<=address<=65535:
            raise ValueError("address should be between 0 and 65535")
    #print(address)
    return address
def get_address(varname):
    return translate_address_string(mapdict[varname]["address"])
async def write_bool(client: ModbusClient.ModbusBaseClient, varname, value:bool, slave=1):
    rr=await client.write_coil(get_address(varname), value, slave=slave)
    return rr
async def read_bool(client: ModbusClient.ModbusBaseClient, varname, slave=1):
    try:
        rr = await client.read_coils(get_address(varname), count=1, slave=1)
    except ModbusException as exc:
        print(f"Received ModbusException({exc}) from library")
        client.close()
        return
    if rr.isError():
        print(f"Received exception from device ({rr})")
        # THIS IS NOT A PYTHON EXCEPTION, but a valid modbus message
        client.close()
        return
    return rr.bits[0]
async def write_float(client: ModbusClient.ModbusBaseClient, varname, value:float, slave=1):
    high,low=float_to_two_short(value)
    rr=await client.write_registers(get_address(varname), [low,high], slave=slave)
    return rr
async def read_float(client: ModbusClient.ModbusBaseClient, varname, slave=1):
    try:
        rr = await client.read_holding_registers(get_address(varname), count=2, slave=1)
    except ModbusException as exc:
        print(f"Received ModbusException({exc}) from library")
        client.close()
        return
    if rr.isError():
        print(f"Received exception from device ({rr})")
        # THIS IS NOT A PYTHON EXCEPTION, but a valid modbus message
        client.close()
        return
    return two_short_to_float(high=rr.registers[1],low=rr.registers[0])
async def start_async_simple_client(host, port, framer=FramerType.SOCKET, refresh_time=0.25):
    """Run async client."""
    # activate debugging
    #pymodbus_apply_logging_config("DEBUG")

    print("get client")
    client: ModbusClient.ModbusBaseClient

    client = ModbusClient.AsyncModbusTcpClient(
        host=host,
        port=port,
        framer=framer,
        # timeout=10,
        # retries=3,
        # source_address=("192.168.1.100", 0),
    )
    

    print("connect to server")
    await client.connect()
    # test client is connected
    if not client.connected:
        raise ConnectionException
    
    print("connected")
    return client
async def start_PC_control(client):
    await write_bool(client,"PC_Control",True)
    await write_bool(client,"HMI_Control",False)
async def stop_PC_control(client):
    await write_bool(client,"PC_Control",False)
    await write_bool(client,"HMI_Control",True)
async def stop_async_simple_client(client):
    client.close()
    print("client closed")
async def query_all_registers(client: ModbusClient.ModbusBaseClient):
    for key,value in mapdict.items():
        if value["dtype"]=="bool":
            try:
                # See all calls in client_calls.py
                rr = await client.read_coils(translate_address_string(value["address"]), count=1, slave=1)
            except ModbusException as exc:
                print(f"Received ModbusException({exc}) from library")
                client.close()
                return
            if rr.isError():
                print(f"Received exception from device ({rr})")
                # THIS IS NOT A PYTHON EXCEPTION, but a valid modbus message
                client.close()
                return
            print(f"Got {key} {value["loc_name"]} bool: {rr.bits[0]}")
        elif value["dtype"]=="int16":
            if "prev_var" in value:
                pass
            elif "next_var" in value:
                address01=translate_address_string(value["address"])
                address02=translate_address_string(mapdict[value["next_var"]]["address"])
                key2=value["next_var"]
                try:
                    rr1 = await client.read_holding_registers(address01, count=1, slave=1) 
                    rr2 = await client.read_holding_registers(address02, count=1, slave=1)
                except ModbusException as exc:
                    print(f"Received ModbusException({exc}) from library")
                    client.close()
                    return
                if rr.isError():
                    print(f"Received exception from device ({rr})")
                    # THIS IS NOT A PYTHON EXCEPTION, but a valid modbus message
                    client.close()
                    return
                i16_in1 = client.convert_from_registers(rr1.registers, data_type=client.DATATYPE.UINT16)
                i16_in2 = client.convert_from_registers(rr2.registers, data_type=client.DATATYPE.UINT16)
                # print(f"Got {key} int16: {i16_in1}")
                # print(f"Got {key2} int16: {i16_in2}")
                f32_oout = two_short_to_float(high=i16_in2,low=i16_in1)
                print(f"Got {value["full_loc_name"]} float: {f32_oout}")
            else:
                address=translate_address_string(value["address"])
                try:
                    rr = await client.read_holding_registers(address, count=1, slave=1)
                except ModbusException as exc:
                    print(f"Received ModbusException({exc}) from library")
                    client.close()
                    return
                if rr.isError():
                    print(f"Received exception from device ({rr})")
                    # THIS IS NOT A PYTHON EXCEPTION, but a valid modbus message
                    client.close()
                    return
                i16_v1 = client.convert_from_registers(rr1.registers, data_type=client.DATATYPE.INT16)
                print(f"Got {key} {value["loc_name"]} int16: {i16_v1}")
async def send_rel_pos_vel(client,rel_pos,rel_vel):
    await write_bool(client,"PC_M6_Enable",True)       #直线电机轴使能
    #await write_bool(client,"Axis_Clear_Pos6",False)    #直线电机轴清除位置
    await write_float(client,"PC_M6_Realtive_Pos1",rel_pos) #设定直线电机轴相对位置
    await write_float(client,"PC_M6_Realtive_Vel1",rel_vel) #设定直线电机轴相对速度
async def rel_cmd(client):
    await write_bool(client,"PC_M6_Realtive_Command",True) #直线电机轴相对定位命令
async def wait_rel_cmd_done(client):
    while True:
        result = await read_bool(client,"PC_M6_Realtive_Done")
        if result:
            await write_bool(client,"PC_M6_Realtive_Command",False) #直线电机轴相对定位命令
            break
        await asyncio.sleep(0.1)
    print("rel cmd done")
async def run_async_simple_client(host, port, framer=FramerType.SOCKET, refresh_time=0.25):
    """Run async client."""
    # activate debugging
    #pymodbus_apply_logging_config("DEBUG")

    print("get client")
    client: ModbusClient.ModbusBaseClient

    client = ModbusClient.AsyncModbusTcpClient(
        host=host,
        port=port,
        framer=framer,
        # timeout=10,
        # retries=3,
        # source_address=("192.168.1.100", 0),
    )
    

    print("connect to server")
    await client.connect()
    # test client is connected
    assert client.connected
    print("get and verify data")
    print("close connection")
    client.close()
    
# asyncio.run(
# run_async_simple_client("tcp", "192.168.1.100", 5020), debug=True
# )

async def reset_ALL(client):
    await write_bool(client,"Reset",True)
    #await write_bool(client,"PC_M6_Reset",True)       #直线电机轴复位
    #await write_bool(client,"Axis_Clear_Pos6",True)    #直线电机轴清除位置
async def wait_reset_done(client):
    while True:
        result = await read_bool(client,"PC_M6_Reset_done")
        if result:
            break
        await asyncio.sleep(0.1)
    print("reset done")
    
async def axis_clear(client):
    await write_bool(client,"Axis_Clear_Pos6",True)    #直线电机轴清除位置
async def axis_clear_stop(client):
    await write_bool(client,"Axis_Clear_Pos6",False)    #直线电机轴清除位置
async def main():
    client = await start_async_simple_client("192.168.1.100",502)
    query_only=True
    if query_only:
        await query_all_registers(client)
        #await axis_clear_stop(client)
        await stop_async_simple_client(client)
        return
    await start_PC_control(client)
    await query_all_registers(client)
    #await reset_ALL(client)
    #await wait_reset_done(client)
    #await axis_clear_done(client)
    await send_rel_pos_vel(client,-100,10)
    print("-----------------")
    await query_all_registers(client)
    print("-----------------")
    await rel_cmd(client)
    await wait_rel_cmd_done(client)
    await query_all_registers(client)
    await stop_PC_control(client)
    await stop_async_simple_client(client)

if __name__ == "__main__":
    asyncio.run(main())