import logging
import time
from typing import TypedDict

import minimalmodbus as modbus
import serial.tools.list_ports


class DCConfig(TypedDict):
    "For PZEM-003 / PZEM-017"
    address: int
    current_range: int
    alarm_voltage_high: float
    alarm_voltage_low: float


class DCMeasurement(TypedDict):
    "For PZEM-003 / PZEM-017"
    voltage: float
    current: float
    power: float
    energy: float
    alarm_voltage_high: bool
    alarm_voltage_low: bool


class PZEM0XX:
    def  __init__(self, address: int=1, usb_device_signature: str='1a86:7523',
            address_search_range: int=0x09, timeout: float=0.2):
        """
        @address: modbus slave address
        @usb_device_signature: VID:PID of the USB serial to RS485 converter
        @address_search_range: Possible address range to help troubleshoot bus connections
        Full address search range = 0xf7 (but this leads to long delays when asking for nonexistent address)
        """
        if address == 0:
            raise RuntimeError(f'Cannot use broadcast address 0x00 !')

        candidates = list(serial.tools.list_ports.grep(usb_device_signature))

        if not candidates:
            raise RuntimeError(f'No serial USB device found with signature "{usb_device_signature}" !')

        if len(candidates) > 1:
            raise RuntimeError(f'More than once device found with signature "{usb_device_signature}" !')

        port: str = candidates[0].device

        self.instrument = modbus.Instrument(port, address)
        self.instrument.close_port_after_each_call = True
        self.instrument.serial.baudrate = 9600
        self.instrument.serial.stopbits = modbus.serial.STOPBITS_TWO
        self.instrument.serial.timeout = timeout
        self.instrument.serial.write_timeout = timeout

        try:
            self.get_config()
            time.sleep(timeout)
        except modbus.NoResponseError:
            other_address_found = 0

            for _address in range(1, address_search_range):
                self.instrument.address = _address
                logging.debug(f'Trying modbus address {hex(_address)} ...')
                try:
                    self.get_config()
                    other_address_found = _address
                    break
                except modbus.NoResponseError:
                    continue

            if other_address_found:
                if other_address_found == address:
                    raise RuntimeError(f'PZEM address {hex(address)} has intermittent connection') from None
                raise RuntimeError(f'PZEM address {hex(address)} not found (but found address {hex(other_address_found)} instead)') from None
            else:
                raise RuntimeError('No PZEM device connected!') from None


    def set_debug(self, active: bool):
        self.instrument.debug = active


    def set_address(self, address: int):
        self.instrument.write_register(functioncode=0x06, registeraddress=0x0002, value=address)
        self.instrument.address = address


    def set_current_range(self, range: int):
        register_value = {50:1, 100:0, 200:2, 300:3} [range]
        self.instrument.write_register(functioncode=0x06, registeraddress=0x0003, value=register_value)


    def set_alarm_voltage_high(self, voltage: float):
        self.instrument.write_register(functioncode=0x06, registeraddress=0x0000, value=int(voltage * 100))


    def set_alarm_voltage_low(self, voltage: float):
        self.instrument.write_register(functioncode=0x06, registeraddress=0x0001, value=int(voltage * 100))


    def reset_energy(self) -> None:
        self.instrument._perform_command(functioncode=0x42, payload_to_slave='')


    def get_config(self) -> DCConfig:
        registers = self.instrument.read_registers(functioncode=0x03, registeraddress=0x0000, number_of_registers=4)
        config: DCConfig = {
            'address': registers[2],
            'current_range': {0:100, 1:50, 2:200, 3:300, 4:10}.get(registers[3], 0),
            'alarm_voltage_high': registers[0] / 100,
            'alarm_voltage_low': registers[1] / 100
        }
        return config


    def get_measurement(self) -> DCMeasurement:
        registers = self.instrument.read_registers(functioncode=0x04, registeraddress=0x0000, number_of_registers=8)
        measurement: DCMeasurement = {
            'voltage': registers[0] / 100,
            'current': registers[1] / 100,
            'power': (registers[2] + (registers[3] << 16)) / 10,
            'energy': (registers[4] + (registers[5] << 16)),
            'alarm_voltage_high': registers[6] > 0,
            'alarm_voltage_low': registers[7] > 0,
        }
        return measurement
