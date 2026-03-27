from decimal import Decimal
import logging

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_message import ReadHoldingRegistersResponse
from rich import (
    print,
)
from rich.pretty import pprint

from kronoterm2mqtt.api import get_modbus_client
from kronoterm2mqtt.cli_app import app
from kronoterm2mqtt.constants import MODBUS_SLAVE_ID

# from kronoterm2mqtt.probe_usb_ports import print_parameter_values, probe_one_port
from kronoterm2mqtt.user_settings import HeatPump, get_user_settings


logger = logging.getLogger(__name__)


def probe_one_port(heat_pump, definitions, verbosity):
    client = get_modbus_client(heat_pump, definitions, verbosity)

    parameters = definitions['sensor']
    if verbosity > 1:
        pprint(parameters)

    print_parameter_values(client, parameters, verbosity)


@app.command
# @Click.option('--max-port', default=10, help='Maximum USB port number')
# @click.option('--port-template', default='/dev/ttyUSB{i}', help='USB device path template')
def probe_usb_ports(verbosity: TyroVerbosityArgType, max_port: int = 10, port_template: str = '/dev/ttyUSB{i}'):
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


def print_parameter_values(client, parameters, verbosity):
    for parameter in parameters:
        print(f'{parameter["name"]:>50}', end=' ')
        address = parameter['register'] - 1  # KRONOTERM MA_numbering is one-based in documentation!
        if verbosity:
            print(f'(Register dec: {address:02} hex: {address:04x})', end=' ')
        response = client.read_holding_registers(address=address, count=1, device_id=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            value = response.registers[0]
            # if count > 1:
            #    value += response.registers[1] * 65536

            scale = Decimal(str(parameter['scale']))
            value = (value - (value >> 15 << 16)) * scale  # Convert value to signed integer
            print(f'{value} [blue]{parameter.get("unit_of_measurement", "")}')
    print('\n')


def print_binary_sensor_values(client, parameters, verbosity):
    for parameter in parameters:
        print(f'{parameter["name"]:>50}', end=' ')
        address = parameter['register'] - 1
        bit = parameter.get('bit')
        if verbosity:
            bit_info = f' bit:{bit}' if bit is not None else ''
            print(f'(Register dec: {address:02} hex: {address:04x}{bit_info})', end=' ')
        response = client.read_holding_registers(address=address, count=1, device_id=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            raw_value = response.registers[0]
            if bit is not None:
                value = bool(raw_value & (1 << bit))
            else:
                value = bool(raw_value)
            state = '[green]ON[/green]' if value else '[red]OFF[/red]'
            print(f'{state} [dim](raw: {raw_value})[/dim]')
    print('\n')


def print_enum_sensor_values(client, parameters, verbosity):
    for parameter in parameters:
        print(f'{parameter["name"]:>50}', end=' ')
        address = parameter['register'] - 1
        if verbosity:
            print(f'(Register dec: {address:02} hex: {address:04x})', end=' ')
        response = client.read_holding_registers(address=address, count=1, device_id=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            raw_value = response.registers[0]
            options = parameter['options'][0] if isinstance(parameter['options'], list) else parameter['options']
            display_value = None
            for index, key in enumerate(options['keys']):
                if key == raw_value:
                    display_value = options['values'][index]
                    break
            if display_value is not None:
                print(f'[green]{display_value}[/green] [dim](raw: {raw_value})[/dim]')
            else:
                print(f'[yellow]unknown[/yellow] [dim](raw: {raw_value})[/dim]')
    print('\n')


def print_switch_values(client, parameters, verbosity):
    for parameter in parameters:
        print(f'{parameter["name"]:>50}', end=' ')
        address = parameter['register'] - 1
        if verbosity:
            print(f'(Register dec: {address:02} hex: {address:04x})', end=' ')
        response = client.read_holding_registers(address=address, count=1, device_id=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            raw_value = response.registers[0]
            state = '[green]ON[/green]' if raw_value else '[red]OFF[/red]'
            print(f'{state} [dim](raw: {raw_value})[/dim]')
    print('\n')


def print_select_values(client, parameters, verbosity):
    for parameter in parameters:
        print(f'{parameter["name"]:>50}', end=' ')
        address = parameter['register'] - 1
        if verbosity:
            print(f'(Register dec: {address:02} hex: {address:04x})', end=' ')
        response = client.read_holding_registers(address=address, count=1, device_id=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            raw_value = response.registers[0]
            options = parameter['options'][0] if isinstance(parameter['options'], list) else parameter['options']
            display_value = None
            for index, key in enumerate(options['keys']):
                if key == raw_value:
                    display_value = options['values'][index]
                    break
            if display_value is not None:
                print(f'[green]{display_value}[/green] [dim](raw: {raw_value})[/dim]')
            else:
                print(f'[yellow]unknown[/yellow] [dim](raw: {raw_value})[/dim]')
    print('\n')


@app.command
def print_values(verbosity: TyroVerbosityArgType):
    """
    Print all values from the definition
    """
    setup_logging(verbosity=verbosity)

    user_settings = get_user_settings(verbosity)
    heat_pump: HeatPump = user_settings.heat_pump
    definitions = heat_pump.get_definitions(verbosity)

    client = get_modbus_client(heat_pump, definitions, verbosity)

    print('[bold]--- Sensors ---[/bold]')
    parameters = definitions['sensor']
    if verbosity > 1:
        pprint(parameters)
    print_parameter_values(client, parameters, verbosity)

    if 'binary_sensor' in definitions:
        print('[bold]--- Binary Sensors ---[/bold]')
        print_binary_sensor_values(client, definitions['binary_sensor'], verbosity)

    if 'enum_sensor' in definitions:
        print('[bold]--- Enum Sensors ---[/bold]')
        print_enum_sensor_values(client, definitions['enum_sensor'], verbosity)

    if 'switch' in definitions:
        print('[bold]--- Switches ---[/bold]')
        print_switch_values(client, definitions['switch'], verbosity)

    if 'select' in definitions:
        print('[bold]--- Selects ---[/bold]')
        print_select_values(client, definitions['select'], verbosity)


@app.command
def print_registers(verbosity: TyroVerbosityArgType):
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

        response = client.read_holding_registers(address=address, count=1, device_id=MODBUS_SLAVE_ID)
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
