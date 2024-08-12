import logging
import time
import asyncio
import itertools

from decimal import Decimal
from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.switch import Switch
from ha_services.mqtt4homeassistant.device import  MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify
from paho.mqtt.client import Client

from kronoterm2mqtt.api import get_modbus_client

import kronoterm2mqtt
from kronoterm2mqtt.constants import BASE_PATH, DEFAULT_DEVICE_MANUFACTURER, MODBUS_SLAVE_ID
from kronoterm2mqtt.user_settings import UserSettings, HeatPump
from kronoterm2mqtt.expander import ExpanderMqttHandler
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_read_message import ReadHoldingRegistersResponse
from pymodbus.pdu.register_write_message import WriteSingleRegisterResponse


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
        self.expander = ExpanderMqttHandler(self.mqtt_client, user_settings, verbosity) if self.user_settings.custom_expander.module_enabled else None
        self.main_device = None
        self.sensors = dict()
        self.binary_sensors = dict()
        self.enum_sensors = dict()
        self.address_ranges = list()
        self.registers  = dict()
        self.dhw_circulation_switch: Switch = None
        self.additional_source_switch: Switch = None

    async def init_device(self, event_loop, verbosity: int):
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
            await self.expander.init_device(event_loop, self.main_device, verbosity)

        definitions = self.heat_pump.get_definitions(verbosity)
        
        parameters = definitions['sensor']

        for parameter in parameters:
            if verbosity > 1:
                print(f'Creating sensor {parameter}')

            address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation!
            scale = parameter['scale']
            precision = len(str(scale)[str(scale).rfind('.')+1:]) if scale < 1 else 0
            self.sensors[address] = (
                Sensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    device_class=parameter['device_class'],
                    state_class=parameter['state_class'] if len(parameter['state_class']) else None,
                    unit_of_measurement=parameter['unit_of_measurement'],
                    suggested_display_precision=precision,
                ),
                Decimal(str(parameter['scale'])),
            )

        binary_sensor_definitions = definitions['binary_sensor']
        for parameter in binary_sensor_definitions:
            address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation!
            self.binary_sensors[address] = (
                BinarySensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    device_class=parameter['device_class'] if len(parameter['device_class']) else None,
                ),
                parameter.get('bit'),
            )
        enum_sensor_definitions = definitions['enum_sensor']
        for parameter in enum_sensor_definitions:
            address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation!
            self.enum_sensors[address] = (
                Sensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    device_class='enum',
                    state_class=None,
                ),
                *parameter['options'],
            )

        self.dhw_circulation_switch = Switch(
            device=self.main_device,
            name='Circulation of sanitary water',
            uid='dhw_circulation_switch',
            callback=self.dhw_circulation_callback,
            )
        self.additional_source_switch = Switch(
            device=self.main_device,
            name='Additional Source',
            uid='additional_source_switch',
            callback=self.additional_source_callback,
            )
            

        # Prepare ranges of registers for faster reads in blocks
        addresses = set(self.sensors.keys())
        addresses = addresses.union(set(self.binary_sensors.keys()))
        addresses.add(2327) # DHW circulation switch
        addresses.add(2015) # Additional source switch
        addresses = sorted(addresses.union(set(self.enum_sensors.keys())))
        self.address_ranges = list(self.ranges(list(addresses)))
        if self.verbosity:
            print(f"Addresses: {len(addresses)} Ranges: {len(self.address_ranges)}")

    def dhw_circulation_callback(self, *, client: Client, component: Switch, old_state: str, new_state: str):
        """Switches on (manually) circulation of sanitary water for 5 minutes.
        The switch turnes off automatically after 5 minutes and the DHW circulation pump stops.
        Note that register 2028 is not documented!
        """
        logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')

        value = 1 if new_state == 'ON' else 0
        response = self.modbus_client.write_register(address=2327, value=value, slave=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, WriteSingleRegisterResponse), f'{response=}'
        component.set_state(new_state)
        component.publish_state(client)

    def additional_source_callback(self, *, client: Client, component: Switch, old_state: str, new_state: str):
        """Switches on (manually) additional heating source.
        """
        logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')

        value = 1 if new_state == 'ON' else 0
        response = self.modbus_client.write_register(address=2015, value=value, slave=MODBUS_SLAVE_ID)
        if isinstance(response, (ExceptionResponse, ModbusIOException)):
            print('Error:', response)
        else:
            assert isinstance(response, WriteSingleRegisterResponse), f'{response=}'
        component.set_state(new_state)
        component.publish_state(client)
    


    def ranges(self, i: list) -> list:
        """Prepare intervals of modbus addresses for fetching register groups
        See https://stackoverflow.com/questions/4628333
        """
        for a, b in itertools.groupby(enumerate(i), lambda pair: pair[1] - pair[0]):
            b = list(b)
            yield b[0][1], b[-1][1]

    def read_heat_pump_register_blocks(self):
        """In order to minimize Modbus communication the register
        values are fetched in ranges that are computed initially from
        definitions and then read in blocks (ranges)
        """
        for address_start, address_end in self.address_ranges:
            count = address_end - address_start + 1
            response = self.modbus_client.read_holding_registers(address=address_start, count=count, slave=MODBUS_SLAVE_ID)
            if isinstance(response, (ExceptionResponse, ModbusIOException)):
                print('Error:', response)
            else:
                assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
                for i in range(count):
                    value = response.registers[i]
                    self.registers[address_start+i] = value
        if self.verbosity:
            print(f"Registers: {self.registers}")

        
    async def publish_loop(self):

        #setup_logging(verbosity=verbosity)

        definitions = self.heat_pump.get_definitions(self.verbosity)

        self.modbus_client = get_modbus_client(self.heat_pump, definitions, self.verbosity)

        logger.info(f'Publishing Home Assistant MQTT discovery for {self.device_name}')

        event_loop = asyncio.get_event_loop()
        
        if self.main_device is None:
            await self.init_device(event_loop, self.verbosity)

        switches =  { 2327: self.dhw_circulation_switch,
                      2015: self.additional_source_switch}
        
        async def update_sensors(event_loop):
            print("Kronoterm to MQTT publish loop started...")
            while True:
                self.read_heat_pump_register_blocks()
                for address in self.sensors:
                    sensor, scale = self.sensors[address]
                    value = self.registers[address]
                    value = float(scale)*(value if scale > 0 else 65536-value)
                    sensor.set_state(value)
                    sensor.publish(self.mqtt_client)
                for address in self.binary_sensors:
                    sensor, bit = self.binary_sensors[address]
                    value = self.registers[address]
                    if bit is not None:
                        value &= 1 << bit
                    sensor.set_state(sensor.ON if value else sensor.OFF)
                    sensor.publish(self.mqtt_client)
                for address in self.enum_sensors:
                    sensor, options = self.enum_sensors[address]
                    value = self.registers[address]
                    for index, key in enumerate(options['keys']):
                        if value == key:
                            break
                    sensor.set_state(options['values'][index])
                    sensor.publish(self.mqtt_client)

                for address, switch in switches.items():
                    switch.set_state(switch.ON if self.registers[address] else switch.OFF)
                    switch.publish(self.mqtt_client)
                        
                if self.expander is not None:
                    await self.expander.update_sensors_and_control(
                        0.1*self.registers[2102], # outside temperature
                        0.1*self.registers[2023], # Current desired DHW temperature
                        self.registers[2015] > 0, # Additional source activated
                        self.registers[2054] > 0, # loop 2 pump status
                        -0.1*(65536-self.registers[2046]), # Loop 1 temperature offset in ECO mode
                        self.registers[2043], # Loop 1 operation status on schedule
                    )

                if self.verbosity:
                    print('\n', flush=True)
                    print('Wait', end='...')
                    for i in range(10, 0, -1):
                        await asyncio.sleep(1)
                        print(i, end='...', flush=True)
                else:
                    await asyncio.sleep(10)

        await update_sensors(event_loop)

