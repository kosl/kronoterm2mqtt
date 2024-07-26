import dataclasses
import logging
from decimal import Decimal

from cli_base.systemd.data_classes import BaseSystemdServiceInfo, BaseSystemdServiceTemplateContext

import ha_services
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.select import Select
from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.switch import Switch
from ha_services.mqtt4homeassistant.data_classes import MqttSettings
from ha_services.mqtt4homeassistant.device import MainMqttDevice, MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client


from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer.rtu_framer import ModbusRtuFramer
from pymodbus.pdu import ExceptionResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from rich.pretty import pprint

from kronoterm2mqtt.user_settings import HeatPump


logger = logging.getLogger(__name__)


def get_modbus_client(heat_pump: HeatPump, definitions: dict, verbosity: int) -> ModbusSerialClient:
    conn_settings = definitions['connection']

    print(f'Connect to {heat_pump.port}...')
    conn_kwargs = dict(
        baudrate=conn_settings['baudrate'],
        bytesize=conn_settings['bytesize'],
        parity=conn_settings['parity'],
        stopbits=conn_settings['stopbits'],
        timeout=heat_pump.timeout,
        retry_on_empty=heat_pump.retry_on_empty,
    )
    if verbosity:
        print('Connection arguments:')
        pprint(conn_kwargs)

    client = ModbusSerialClient(heat_pump.port, framer=ModbusRtuFramer, broadcast_enable=False, **conn_kwargs)
    if verbosity > 1:
        print('connected:', client.connect())
        print(client)

    return client
