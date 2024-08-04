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
    print('Device just reset...')


class ExpanderMqttHandler:
    def __init__(self,  mqtt_client, user_settings: UserSettings, verbosity: int):
        self.mqtt_client = mqtt_client
        self.user_settings = user_settings
        self.mqtt_device: MqttDevice | None = None
        self.sensors = list()
        self.relays = list()
        self.etera = None


    def init_device(self, main_device: MqttDevice, verbosity: int):
        """Create sensors and add it as subdevice for later update in
        the publish process"""

        port = self.user_settings.custom_expander.port
        print(f"Custom expander is using port {port}")

        self.etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler)
        loop = asyncio.create_task(self.etera.run_forever())

        self.mqtt_device = MqttDevice(
                main_device=main_device,
                name="ETERA expander",
                uid="expander",
                manufacturer='DIY by Wigaun',
                sw_version=kronoterm2mqtt.__version__,
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
            self.relays.append((BinarySensor(
                    device=self.mqtt_device,
                    name=name,
                    uid=slugify(name, '_').lower(),
                    device_class='running',
            ) if len(name) else None, False)) # relay in use?

    async def update_sensors(self):
        await self.etera.ready()
        temperatures = await self.etera.get_temperatures()
        settings = self.user_settings.custom_expander
        ids = settings.loop_sensors + settings.solar_sensors
        for i, sensor in enumerate(self.sensors):
            value = temperatures[ids[i]]
            sensor.set_state(value)
            sensor.publish(self.mqtt_client)
        relay_names = self.user_settings.custom_expander.relay_names
        for relay, value in self.relays:
            if relay is not None:
                relay.set_state(relay.ON if value else relay.OFF)
                relay.publish(self.mqtt_client)

    
