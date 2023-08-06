import glob
import sys
from typing import TypedDict

from pymodbus.client import ModbusSerialClient



class DeviceConfig(TypedDict):
    address: int
    current_range: int
    alarm_voltage_high: float
    alarm_voltage_low: float


class DeviceMeasurement(TypedDict):
    voltage: float
    current: float
    power: float
    energy: float
    alarm_voltage_high: bool
    alarm_voltage_low: bool


def get_client() -> ModbusSerialClient:
    if sys.platform.startswith('linux'):
        prefix = '/dev/ttyUSB'
    elif sys.platform.startswith('darwin'):
        prefix = '/dev/cu.usbserial'
    else:
        raise RuntimeError(f'Unsupported platform: {sys.platform}')

    files = glob.glob(f'{prefix}*')

    for file in files:
        client = ModbusSerialClient(file, baudrate=9600, stopbits=2)
        if client.connect():
            return client

    raise RuntimeError('No USB serial to RS485 device found! (or all devices are busy)')


def set_device_address(client: ModbusSerialClient, address: int, existing_address: int=0):
    client.write_register(2, address, slave=existing_address)


def reset_device_energy(client: ModbusSerialClient, address: int=0):
    ...


def get_device_config(client: ModbusSerialClient, address: int=0) -> DeviceConfig:
    holding = client.read_holding_registers(address=0, count=4, unit=1, slave=address)
    config: DeviceConfig = {
        'address': holding.getRegister(2),
        'current_range': {0:100, 1:50, 2:200, 3:300, 4:10}.get(holding.getRegister(3), 0),
        'alarm_voltage_high': holding.getRegister(0) / 100,
        'alarm_voltage_low': holding.getRegister(1) / 100
    }
    return config


def get_device_measurement(client: ModbusSerialClient, address: int=0) -> DeviceMeasurement:
    input = client.read_input_registers(address=0, count=8, unit=1, slave=address)
    measurement: DeviceMeasurement = {
        'voltage': input.getRegister(0) / 100,
        'current': input.getRegister(1) / 100,
        'power': (input.getRegister(2) + (input.getRegister(3) << 16)) / 10,
        'energy': (input.getRegister(4) + (input.getRegister(5) << 16)),
        'alarm_voltage_high': input.getRegister(6) > 0,
        'alarm_voltage_low': input.getRegister(7) > 0,
    }
    return measurement
