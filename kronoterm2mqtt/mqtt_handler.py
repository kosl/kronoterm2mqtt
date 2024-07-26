import logging
import time

from decimal import Decimal
from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.device import MainMqttDevice, MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from kronoterm2mqtt.api import get_modbus_client

import kronoterm2mqtt
from kronoterm2mqtt.user_settings import UserSettings, HeatPump
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse


logger = logging.getLogger(__name__)


class KronotermMqttHandler:
    def __init__(self, user_settings: UserSettings, verbosity: int):
        self.user_settings = user_settings
        self.device_name = user_settings.device_name
        self.heat_pump = self.user_settings.heat_pump
        self.mqtt_client = get_connected_client(settings=user_settings.mqtt, verbosity=verbosity)
        self.mqtt_client.loop_start()
        self.main_device = None
        self.verbosity = verbosity
        self.sensors = dict()

    def init_device(self, verbosity: int):
        """
        Create sensors from definitions.toml add it to device for later
        update in publish process.
        """
        self.main_device = MqttDevice(
            name=self.device_name,
            uid=self.device_name,
            manufacturer='KRONOTERM',
            model='ETERA',
            sw_version=kronoterm2mqtt.__version__,
            config_throttle_sec=self.user_settings.mqtt.publish_config_throttle_seconds,
        )
        if self.user_settings.custom_expander.module_enabled:
            self.mqtt_device = MqttDevice(
                main_device=self.main_device,
                name="Custom expander",
                uid="expander",
                manufacturer='DIY',
                sw_version=kronoterm2mqtt.__version__,
                config_throttle_sec=self.user_settings.mqtt.publish_config_throttle_seconds,
            )


        definitions = self.heat_pump.get_definitions(verbosity)
        
        parameters = definitions['sensor']

        for parameter in parameters:
            if verbosity:
                print(f'Creating sensor {parameter}')

            address = parameter['register'] - 1 # KRONOTERM MA_numbering is one-based in documentation!
        
            self.sensors[address] = (
                Sensor(
                    device=self.main_device,
                    name=parameter['name'],
                    uid=parameter['uid'],
                    state_class=parameter['state_class'],
                    unit_of_measurement=parameter['unit_of_measurement'],
                    suggested_display_precision= 1,
                ),
                Decimal(str(parameter['scale'])),
            )
                
                                     

        
    def publish(self, user_settings: UserSettings, verbosity: int):

        #setup_logging(verbosity=verbosity)

        definitions = self.heat_pump.get_definitions(verbosity)

        client = get_modbus_client(self.heat_pump, definitions, verbosity)
        slave_id = self.heat_pump.slave_id

        logger.info(f'Publishing for {self.device_name}')

        if self.main_device is None:
            self.init_device(verbosity)

        while True:

            for address in self.sensors:
                sensor, scale = self.sensors[address]

                response = client.read_holding_registers(address=address, count=1, slave=slave_id)
                if isinstance(response, (ExceptionResponse, ModbusIOException)):
                    print('Error:', response)
                else:
                    assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
                    value = response.registers[0]

                    value = float(value * scale)

                sensor.set_state(value)
                sensor.publish(self.mqtt_client)
            
            print('\n', flush=True)
            print('Wait', end='...')
            for i in range(10, 0, -1):
                time.sleep(0.5)
                print(i, end='...', flush=True)



