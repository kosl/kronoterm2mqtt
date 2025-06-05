#!/usr/bin/env python3
import pymodbus.client
pymodbus.pymodbus_apply_logging_config("DEBUG")
client = pymodbus.client.ModbusSerialClient("/dev/ttyUSB0", baudrate=115200)
try:
    client.connect()
    rr = client.read_holding_registers(2100, 10, slave=20)
    print(
        'KRONOTERM Temperatures:', [u'{:.1f}\N{DEGREE SIGN}C'.format((t - (t >> 15 << 16)) / 10) for t in rr.registers]
    )
except pymodbus.ModbusException as exc:
    print(f"Received ModbusException({exc}) from library")
client.close()
