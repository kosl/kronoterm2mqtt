import logging

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from rich.pretty import pprint

from kronoterm2mqtt.user_settings import HeatPump


logger = logging.getLogger(__name__)


def get_modbus_client(heat_pump: HeatPump, definitions: dict, verbosity: int) -> ModbusSerialClient | ModbusTcpClient:
    print(f'Connect to {heat_pump.port}...')

    if heat_pump.port[0] == '/':  # Serial client starting with /dev
        conn_settings = definitions['connection']

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
    else:  # TCP client as Host IP address or host name with optional :port
        host_port = heat_pump.port.rsplit(':', 1)
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 502
        client = ModbusTcpClient(host=host, port=port)
        
    if verbosity > 1:
       print('connected:', client.connect())
       print(client)

    return client
