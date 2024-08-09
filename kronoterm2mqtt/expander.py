import logging
import time
import asyncio

from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.switch import Switch
from ha_services.mqtt4homeassistant.device import  MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify

import kronoterm2mqtt
from kronoterm2mqtt.constants import BASE_PATH, DEFAULT_DEVICE_MANUFACTURER
from kronoterm2mqtt.user_settings import UserSettings, CustomEteraExpander
import kronoterm2mqtt.pyetera_uart_bridge
from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge


async def etera_reset_handler():
    print('Custom ETERA expander just reset...')

async def etera_message_handler(message: bytes):
    print(message.decode())


class ExpanderMqttHandler:
    def __init__(self,  mqtt_client, user_settings: UserSettings, verbosity: int):
        self.mqtt_client = mqtt_client
        self.user_settings = user_settings
        self.verbosity = verbosity
        self.mqtt_device: MqttDevice | None = None
        self.sensors = list()
        self.relays = list()
        self.relay_state = list()
        self.etera = None


    def init_device(self, main_device: MqttDevice, verbosity: int):
        """Create sensors and add it as subdevice for later update in
        the publish process"""

        port = self.user_settings.custom_expander.port
        print(f"Custom expander is using port {port}")

        self.etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler,
                                     on_device_message_handler=etera_message_handler)
        loop = asyncio.create_task(self.etera.run_forever())

        self.mqtt_device = MqttDevice(
                main_device=main_device,
                name="ETERA expander",
                uid="expander",
                manufacturer='Wigaun DIY',
                model='Arduino nano',
                sw_version='1.0.8',
                config_throttle_sec=self.user_settings.mqtt.publish_config_throttle_seconds,
            )
        for name in self.user_settings.custom_expander.sensor_names:
            self.sensors.append(Sensor(
                device=self.mqtt_device,
                name=name,
                uid=slugify(name, '_').lower(),
                device_class='temperature',
                state_class='measurement',
                unit_of_measurement="°C",
                suggested_display_precision= 1,
            ))
        for name in self.user_settings.custom_expander.relay_names:
            self.relays.append(BinarySensor(
                    device=self.mqtt_device,
                    name=name,
                    uid=slugify(name, '_').lower(),
                    device_class='running',
            ) if len(name) else None) # relay in use?
            self.relay_state.append(False)

    async def update_sensors_and_control(self, outside_temperature: float,
                                         current_desired_dhw_temperature: float,
                                         loop_circulation_enabled: bool,
                                         intra_tank_circulation_enabled: bool):
        """Updates ETERA expander subdevice in Home Assistant and
        performs control of the pumps and mixing valve motors with
        target temperatures computed from outside temperature. If loop
        circulation is not enabled then the loop pumps and mixing
        valves are stopped. Intra tank circulation is required if the
        temperature in solar tank is higher that DHW tank and when the
        temperature of DHW tank is lower than "current desired
        domestic hot water temperature" increased for 1°C to prevent
        starting of heat pump when we have enough hot water from solar
        tank.  In winter when the solar tank temperature is well below
        current desired DHW temperature and if intra_tank_circulation
        is enabled then the intra-tank circulation starts to prepare
        water in both tanks for large bath tube consumption
        afterwards.
        """
        try:
            await self.etera.ready()
            temperatures = await self.etera.get_temperatures()
            settings = self.user_settings.custom_expander
            ids = settings.loop_sensors + settings.solar_sensors
            solar_pump_relay_id = settings.solar_pump_relay_id

            for i, sensor in enumerate(self.sensors):
                value = temperatures[ids[i]]
                sensor.set_state(value)
                sensor.publish(self.mqtt_client)    
            #### Expander control start
            collector_temperature = temperatures[settings.solar_sensors[0]]
            tank_temperature = temperatures[settings.solar_sensors[2]]
            difference = collector_temperature - tank_temperature
            if difference > settings.solar_pump_difference_on:
                await self.etera.set_relay(solar_pump_relay_id, True)
                self.relay_state[solar_pump_relay_id] = True
                state = 'switch ON'
            elif difference < settings.solar_pump_difference_off:
                await self.etera.set_relay(solar_pump_relay_id, False)
                state = 'switch OFF'
                self.relay_state[solar_pump_relay_id] = False
            else:
                state = 'switch unchanged'
            if self.verbosity:
                print(f'Temperatures {temperatures} Collector-heat exchanger difference {difference} -> {state}')
            #### Expander control end
        except EteraUartBridge.DeviceException as e:
                print('Get temperatures error', e)
        relay_names = settings.relay_names
        for i, relay in enumerate(self.relays):
            if relay is not None:
                relay.set_state(relay.ON if self.relay_state[i] else relay.OFF)
                relay.publish(self.mqtt_client)

    
