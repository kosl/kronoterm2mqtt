import asyncio
from decimal import Decimal
import itertools
import logging
from typing import Any, Dict, List, Optional, Tuple

from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.select import Select
from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.switch import Switch
from ha_services.mqtt4homeassistant.device import BaseMqttDevice, MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify
from paho.mqtt.client import Client
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_message import ReadHoldingRegistersResponse
from rich import print  # noqa

import kronoterm2mqtt
from kronoterm2mqtt.api import get_modbus_client
from kronoterm2mqtt.constants import DEFAULT_DEVICE_MANUFACTURER, MODBUS_SLAVE_ID
from kronoterm2mqtt.expander import ExpanderMqttHandler
from kronoterm2mqtt.user_settings import UserSettings


logger = logging.getLogger(__name__)


class KronotermMqttHandler:
    def __init__(self, user_settings: UserSettings, verbosity: int):
        self.user_settings = user_settings
        self.verbosity = verbosity
        self.heat_pump = self.user_settings.heat_pump
        self.device_name = self.heat_pump.device_name
        self.mqtt_client = get_connected_client(settings=user_settings.mqtt, verbosity=verbosity)
        self.mqtt_client.loop_start()
        self.modbus_client = None
        self.expander: Optional[ExpanderMqttHandler] = (
            ExpanderMqttHandler(self.mqtt_client, user_settings, verbosity)
            if self.user_settings.custom_expander.module_enabled
            else None
        )
        self.main_device: Optional[MqttDevice] = None
        self.sensors: Dict[int, Tuple[Sensor, Decimal]] = dict()
        self.binary_sensors: Dict[int, Dict[int, BinarySensor]] = dict()
        self.enum_sensors: Dict[int, Tuple[Sensor, Dict[str, List[Any]]]] = dict()
        self.address_ranges: List[Tuple[int, int]] = list()
        self.registers: Dict[int] = dict()
        self.switches: Dict[int, Switch] = dict()
        self.selects: Dict[int, Tuple[Select, Dict[str, List[Any]]]] = dict()

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager, cleaning up resources."""
        if self.verbosity:
            print('\nClosing MQTT and Modbus client.', end='...')

        if self.expander:
            self.expander.stop()
            print('expander stopped', flush=True)

        if self.modbus_client:
            self.modbus_client.close()
            
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        BaseMqttDevice.device_uids = set()  # Reset
        BaseMqttDevice.components = {}  # Global registry of all components

    async def init_device(self):
        """
        Create sensors from definitions.toml add it to device for later
        update in publish process.
        """
        self.main_device = MqttDevice(
            name=self.heat_pump.device_name,
            uid=self.user_settings.mqtt.main_uid,
            manufacturer=DEFAULT_DEVICE_MANUFACTURER,
            model=self.heat_pump.model,
            sw_version=kronoterm2mqtt.__version__,
            config_throttle_sec=self.user_settings.mqtt.publish_config_throttle_seconds,
        )

        if self.expander is not None:
            await self.expander.init_device(self.main_device)

        definitions = self.heat_pump.get_definitions(self.verbosity)

        parameters = definitions['sensor']

        for parameter in parameters:
            if self.verbosity > 1:
                print(f'Creating sensor {parameter}')

            address = parameter['register'] - 1  # KRONOTERM MA_numbering is one-based in documentation!
            scale = parameter['scale']
            precision = len(str(scale)[str(scale).rfind('.') + 1 :]) if scale < 1 else 0  # noqa
            self.sensors[address] = (
                Sensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    device_class=parameter['device_class'],
                    state_class=parameter['state_class'] if len(parameter['state_class']) else None,
                    unit_of_measurement=(
                        parameter['unit_of_measurement'] if len(parameter['unit_of_measurement']) else None
                    ),
                    suggested_display_precision=precision,
                ),
                Decimal(str(parameter['scale'])),
            )

        binary_sensor_definitions = definitions['binary_sensor']
        for parameter in binary_sensor_definitions:
            address = parameter['register'] - 1  # KRONOTERM MA_numbering is one-based in documentation!
            bit = parameter.get('bit')
            self.binary_sensors.setdefault(address, {})[bit] = BinarySensor(
                device=self.main_device,
                name=parameter['name'],
                uid=slugify(parameter['name'], '_').lower(),
                device_class=parameter['device_class'] if len(parameter['device_class']) else None,
            )
        enum_sensor_definitions = definitions['enum_sensor']
        for parameter in enum_sensor_definitions:
            address = parameter['register'] - 1  # KRONOTERM MA_numbering is one-based in documentation!
            self.enum_sensors[address] = (
                Sensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    device_class=None,
                    state_class=None,
                ),
                *parameter['options'],
            )

        if 'switch' in definitions:
            switch_definitions = definitions['switch']
            for parameter in switch_definitions:
                address = parameter['register'] - 1  # KRONOTERM MA_numbering is one-based in documentation!
                switch = Switch(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    callback=self.switch_callback,
                )
                self.switches[address] = switch

        if 'select' in definitions:
            select_definitions = definitions['select']
            for parameter in select_definitions:
                address = parameter['register'] - 1  # KRONOTERM MA_numbering is one-based in documentation!
                options = parameter['options'][0]  # Get first options object
                select = Select(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    default_option=parameter['default_option'],
                    options=tuple(options['values']),
                    callback=self.select_callback,
                )
                self.selects[address] = (select, options)

        # Prepare ranges of registers for faster Modbus reads in blocks
        addresses = sorted(
            list(self.sensors.keys())
            + list(self.binary_sensors.keys())
            + list(self.enum_sensors.keys())
            + list(self.switches.keys())
            + list(self.selects.keys())
        )
        self.address_ranges = list(self.ranges(list(addresses)))
        if self.verbosity > 1:
            print(f'Addresses: {addresses} Ranges: {len(self.address_ranges)}')

    def switch_callback(self, *, client: Client, component: Switch, old_state: str, new_state: str):
        """
        Generic callback for switch state changes.
        """
        logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')

        # Find the address for this switch
        address = None
        for addr, switch in self.switches.items():
            if switch == component:
                address = addr
                break

        if address is None:
            logger.error(f'Could not find address for switch {component.name}')
            return

        value = 1 if new_state == 'ON' else 0
        success = self.modbus_client.write_register(address=address, value=value, device_id=MODBUS_SLAVE_ID)

        if success:
            component.set_state(new_state)
            component.publish_state(client)
        else:
            logger.error(f'Failed to write register for {component.name}')

    def select_callback(self, *, client: Client, component: Select, old_state: str, new_state: str):
        """
        Generic callback for select state changes.
        """
        logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')

        # Find the address and options for this select
        address = None
        options = None
        for addr, (select, select_options) in self.selects.items():
            if select == component:
                address = addr
                options = select_options
                break

        if address is None or options is None:
            logger.error(f'Could not find address or options for select {component.name}')
            return

        # Convert display value to register value
        value = None
        for index, display_value in enumerate(options['values']):
            if display_value == new_state:
                value = options['keys'][index]
                break

        if value is None:
            logger.error(f'Could not find register value for display value {new_state}')
            return

        success = self.modbus_client.write_register(address=address, value=value, device_id=MODBUS_SLAVE_ID)

        if success:
            component.set_state(new_state)
            component.publish_state(client)
        else:
            logger.error(f'Failed to write register for {component.name}')

    def ranges(self, i: list) -> list:
        """Prepare intervals of modbus addresses for fetching register groups
        See https://stackoverflow.com/questions/4628333
        """
        for _, b in itertools.groupby(enumerate(i), lambda pair: pair[1] - pair[0]):
            b = list(b)  # noqa
            yield b[0][1], b[-1][1]  # noqa

    def read_heat_pump_register_blocks(self):
        """In order to minimize Modbus communication the register
        values are fetched in ranges that are computed initially from
        definitions and then read in blocks (ranges)
        """
        for address_start, address_end in self.address_ranges:
            count = address_end - address_start + 1
            response = self.modbus_client.read_holding_registers(
                address=address_start, count=count, device_id=MODBUS_SLAVE_ID
            )
            if isinstance(response, (ExceptionResponse, ModbusIOException)):
                logger.error(f'Error: {response}')
            else:
                assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
                for i in range(count):
                    value = response.registers[i]
                    self.registers[address_start + i] = value - (value >> 15 << 16)  # Convert value to signed integer
        if self.verbosity > 1:
            logger.info(f'Registers: {self.registers}')

    async def publish_loop(self):
        # setup_logging(verbosity=self.verbosity)

        definitions = self.heat_pump.get_definitions(self.verbosity)

        self.modbus_client = get_modbus_client(self.heat_pump, definitions, self.verbosity)

        logger.info(f'Publishing Home Assistant MQTT discovery for {self.device_name}')

        if self.main_device is None:
            await self.init_device()

        print('Kronoterm to MQTT publish loop started...', flush=True)
        while True:
            self.read_heat_pump_register_blocks()
            for address in self.sensors:
                sensor, scale = self.sensors[address]
                value = self.registers[address]
                value = float(scale) * value
                sensor.set_state(value)
                sensor.publish(self.mqtt_client)
            for address in self.binary_sensors:
                for bit, sensor in self.binary_sensors[address].items():
                    value = self.registers[address]
                    if bit is not None:
                        value &= 1 << bit
                    sensor.set_state(sensor.ON if value else sensor.OFF)
                    sensor.publish(self.mqtt_client)
            for address in self.enum_sensors:
                sensor, options = self.enum_sensors[address]
                value = self.registers[address]
                for _index, key in enumerate(options['keys']):
                    if value == key:
                        break
                sensor.set_state(options['values'][_index])
                sensor.publish(self.mqtt_client)
            for address, switch in self.switches.items():
                switch.set_state(switch.ON if self.registers[address] else switch.OFF)
                switch.publish(self.mqtt_client)
                for address, (select, _) in self.selects.items():
                    if address in self.registers and address in self.selects:
                        _, options = self.selects[address]
                        register_value = self.registers[address]
                        # Convert register value to display value
                        display_value = None
                        for index, key in enumerate(options['keys']):
                            if register_value == key:
                                display_value = options['values'][index]
                                break
                        if display_value is not None:
                            select.set_state(display_value)
                            select.publish(self.mqtt_client)

            if self.expander is not None:
                try:
                    await self.expander.update_sensors_and_control(
                      outside_temperature=0.1 * self.registers[2102],  # outside temperature
                      current_desired_dhw_temperature=0.1 * self.registers[2023],  # Current desired DHW temperature
                      additional_source_enabled=self.registers[2015] > 0,  # Additional source activated
                      loop_circulation_status=self.registers[2044] > 0,  # Loop 1 circulation pump status
                      # Loop 1 temperature offset in ECO mode
                      loop_temperature_offset_in_eco_mode=0.1 * self.registers[2046],
                      loop_operation_status_on_schedule=self.registers[2043],  # Loop 1 operation status on schedule
                      working_function=self.registers[2000],  # Heat pump heating=0, standby=5
                    )
                except asyncio.CancelledError as e:
                    logger.warning(f'Expander update cancelled! {e}')
                    raise

            if self.verbosity:
                print('\nWait', end='...', flush=True)
                for i in range(self.user_settings.heat_pump.pooling_interval, 0, -1):
                    await asyncio.sleep(1)
                    print(i, end='...', flush=True)
            else:
                await asyncio.sleep(self.user_settings.heat_pump.pooling_interval)
