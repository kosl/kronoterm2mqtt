import logging

from pymodbus.client import ModbusSerialClient
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
    )
    if verbosity:
        print('Connection arguments:')
        pprint(conn_kwargs)

    client = ModbusSerialClient(heat_pump.port, **conn_kwargs)
    if verbosity > 1:
        print('connected:', client.connect())
        print(client)

    return client
