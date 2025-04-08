import logging
from decimal import Decimal

import rich_click
import rich_click as click
from cli_base.cli_tools.verbosity import OPTION_KWARGS_VERBOSE, setup_logging
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_message import ReadHoldingRegistersResponse
from rich import get_console  # noqa
from rich import print  # noqa; noqa
from rich.pretty import pprint

from kronoterm2mqtt.api import get_modbus_client
from kronoterm2mqtt.cli_app import cli
#from kronoterm2mqtt.probe_usb_ports import print_parameter_values, probe_one_port
from kronoterm2mqtt.user_settings import HeatPump, get_user_settings

from kronoterm2mqtt.api import get_modbus_client
from kronoterm2mqtt.constants import MODBUS_SLAVE_ID

logger = logging.getLogger(__name__)


def probe_one_port(heat_pump, definitions, verbosity):
    client = get_modbus_client(heat_pump, definitions, verbosity)

    parameters = definitions['sensor']
    if verbosity > 1:
        pprint(parameters)

    print_parameter_values(client, parameters, verbosity)


@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
@click.option('--max-port', default=10, help='Maximum USB port number')
@click.option('--port-template', default='/dev/ttyUSB{i}', help='USB device path template')
def probe_usb_ports(verbosity: int, max_port: int, port_template: str):
    """
    Probe through the USB ports and print the values from definition
    """
    setup_logging(verbosity=verbosity)

    systemd_settings = get_user_settings(verbosity)
    heat_pump: HeatPump = systemd_settings.heat_pump
    definitions = heat_pump.get_definitions(verbosity)

    for port_number in range(0, max_port):
        port = port_template.format(i=port_number)
        print(f'Probe port: {port}...')

        heat_pump.port = port
        try:
            probe_one_port(heat_pump, definitions, verbosity)
        except Exception as err:
            print(f'ERROR: {err}')


def print_parameter_values(client, parameters,  verbosity):
    for parameter in parameters:
        print(f'{parameter["name"]:>30}', end=' ')
        address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation!
        if verbosity:
            print(f'(Register dec: {address:02} hex: {address:04x})', end=' ')
        response = client.read_holding_registers(address=address, count=1, slave=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            value = response.registers[0]
            #if count > 1:
            #    value += response.registers[1] * 65536

            scale = Decimal(str(parameter['scale']))
            value = value * scale
            print(f'{value} [blue]{parameter.get("unit_of_measurement", "")}')
    print('\n')

            
@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def print_values(verbosity: int):
    """
    Print all values from the definition
    """
    setup_logging(verbosity=verbosity)

    user_settings = get_user_settings(verbosity)
    heat_pump: HeatPump = user_settings.heat_pump
    definitions = heat_pump.get_definitions(verbosity)

    client = get_modbus_client(heat_pump, definitions, verbosity)

    parameters = definitions['sensor']
    if verbosity > 1:
        pprint(parameters)

    print_parameter_values(client, parameters, verbosity)


@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def print_registers(verbosity: int):
    """
    Print RAW modbus register data
    """
    setup_logging(verbosity=verbosity)

    user_settings = get_user_settings(verbosity)
    heat_pump: HeatPump = user_settings.heat_pump
    definitions = heat_pump.get_definitions(verbosity)

    client = get_modbus_client(heat_pump, definitions, verbosity)

    parameters = definitions['sensor']
    if verbosity > 1:
        pprint(parameters)

    error_count = 0
    address = 2000
    while error_count < 5:
        print(f'[blue]Read register[/blue] dec: {address:02} hex: {address:04x} ->', end=' ')

        response = client.read_holding_registers(address=address, count=1, slave=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
            error_count += 1
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            for value in response.registers:
                print(f'[green]Result[/green]: dec:{value:05} hex:{value:08x}', end=' ')
            print()

        address += 1
        if address > 3030:
            break
