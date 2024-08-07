import logging
import time
import asyncio
import itertools

from decimal import Decimal
from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.device import  MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify

from kronoterm2mqtt.api import get_modbus_client

import kronoterm2mqtt
from kronoterm2mqtt.constants import BASE_PATH, DEFAULT_DEVICE_MANUFACTURER
from kronoterm2mqtt.user_settings import UserSettings, HeatPump
from kronoterm2mqtt.expander import ExpanderMqttHandler
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_read_message import ReadHoldingRegistersResponse


logger = logging.getLogger(__name__)


class KronotermMqttHandler:
    def __init__(self, user_settings: UserSettings, verbosity: int):
        self.user_settings = user_settings
        self.heat_pump = self.user_settings.heat_pump
        self.device_name = self.heat_pump.device_name
        self.mqtt_client = get_connected_client(settings=user_settings.mqtt, verbosity=verbosity)
        self.mqtt_client.loop_start()
        self.expander = ExpanderMqttHandler(self.mqtt_client, user_settings, verbosity) if self.user_settings.custom_expander.module_enabled else None
        self.main_device = None
        self.verbosity = verbosity
        self.sensors = dict()
        self.binary_sensors = dict()
        self.enum_sensors = dict()
        self.address_ranges = list()
        self.registers  = dict()

    def init_device(self, verbosity: int):
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
            self.expander.init_device(self.main_device, verbosity)

        definitions = self.heat_pump.get_definitions(verbosity)
        
        parameters = definitions['sensor']

        for parameter in parameters:
            if verbosity > 1:
                print(f'Creating sensor {parameter}')

            address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation!
        
            self.sensors[address] = (
                Sensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=slugify(parameter['name'], '_').lower(),
                    device_class=parameter['device_class'],
                    state_class=parameter['state_class'] if len(parameter['state_class']) else None,
                    unit_of_measurement=parameter['unit_of_measurement'],
                    suggested_display_precision= 1,
                ),
                Decimal(str(parameter['scale'])),
            )

        binary_sensor_definitions = definitions['binary_sensor']
        for parameter in binary_sensor_definitions:
            address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation! 
            self.binary_sensors[address] = BinarySensor(
                device=self.main_device,
                name=parameter['name'],
                uid=slugify(parameter['name'], '_').lower(),
                device_class=parameter['device_class'] if len(parameter['device_class']) else None,
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


        # Prepare ranges of registers for faster reads in blocks
        addresses = set(self.sensors.keys())
        addresses = addresses.union(set(self.binary_sensors.keys()))
        addresses = sorted(addresses.union(set(self.enum_sensors.keys())))
        self.address_ranges = list(self.ranges(list(addresses)))
        if self.verbosity:
            print(f"Addresses: {len(addresses)} Ranges: {len(self.address_ranges)}")



    def ranges(self, i: list) -> list:
        """Prepare intervals of modbus addresses for fetching register groups
        See https://stackoverflow.com/questions/4628333
        """
        for a, b in itertools.groupby(enumerate(i), lambda pair: pair[1] - pair[0]):
            b = list(b)
            yield b[0][1], b[-1][1]

    def read_heat_pump_register_blocks(self, modbus_client, slave_id):
        """In order to minimize Modbus communication the register
        values are fetched in ranges that are computed initially from
        definitions and then read in blocks (ranges)
        """
        for address_start, address_end in self.address_ranges:
            count = address_end - address_start + 1
            response = modbus_client.read_holding_registers(address=address_start, count=count, slave=slave_id)
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

        client = get_modbus_client(self.heat_pump, definitions, self.verbosity)
        slave_id = self.heat_pump.slave_id

        logger.info(f'Publishing Home Assistant MQTT discovery for {self.device_name}')

        if self.main_device is None:
            self.init_device(self.verbosity)
        
        async def update_sensors():
            print("Kronoterm to MQTT publish loop started...")
            while True:
                self.read_heat_pump_register_blocks(client, slave_id)
                for address in self.sensors:
                    sensor, scale = self.sensors[address]
                    value = self.registers[address]
                    value = float(value * scale)
                    sensor.set_state(value)
                    sensor.publish(self.mqtt_client)
                for address in self.binary_sensors:
                    sensor = self.binary_sensors[address]
                    value = self.registers[address]
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

                        
                if self.expander is not None:
                    await self.expander.update_sensors(self.verbosity)

                if self.verbosity:
                    print('\n', flush=True)
                    print('Wait', end='...')
                    for i in range(10, 0, -1):
                        await asyncio.sleep(1)
                        print(i, end='...', flush=True)
                else:
                    await asyncio.sleep(10)

        await asyncio.gather(
            update_sensors(),
        )
