import logging
import time
import asyncio

from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.switch import Switch
from ha_services.mqtt4homeassistant.device import  MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify
from paho.mqtt.client import Client

import kronoterm2mqtt
from kronoterm2mqtt.constants import BASE_PATH, DEFAULT_DEVICE_MANUFACTURER, MIXING_VALVE_HOLD_TIME
from kronoterm2mqtt.user_settings import UserSettings, CustomEteraExpander
import kronoterm2mqtt.pyetera_uart_bridge
from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge


logger = logging.getLogger(__name__)


async def etera_reset_handler():
    print('Custom ETERA expander just reset...')

async def etera_message_handler(message: bytes):
    print(message.decode())


class ExpanderMqttHandler:
    def __init__(self, mqtt_client, user_settings: UserSettings, verbosity: int):
        self.event_loop = None
        self.mqtt_client = mqtt_client
        self.user_settings = user_settings
        self.verbosity = verbosity
        self.mqtt_device: MqttDevice | None = None
        self.sensors: list(Sensor) = list()
        self.relays: list(Sensor|None) = list()
        self.switches: list(Switch) = list()
        self.etera = None


    async def init_device(self, event_loop, main_device: MqttDevice, verbosity: int):
        """Create sensors and add it as subdevice for later update in
        the publish process"""

        port = self.user_settings.custom_expander.port
        print(f"Custom expander is using port {port}")

        self.etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler,
                                     on_device_message_handler=etera_message_handler)
        self.event_loop = event_loop
        self.event_loop.create_task(self.etera.run_forever())
        await self.etera.ready()
        for i in range(4):
            event_loop.create_task(self.etera.move_motor(i, EteraUartBridge.Direction.COUNTER_CLOCKWISE, 120*1000))

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

        for i, state in enumerate(self.user_settings.custom_expander.loop_operation):
            name = self.user_settings.custom_expander.sensor_names[i]
            if len(self.user_settings.custom_expander.relay_names[i]):
                switch = Switch(
                    device=self.mqtt_device,
                    name=name,
                    uid=slugify(name),
                    callback=self.loop_switch_callback,
                )
                switch.set_state(switch.ON if state else switch.OFF)
                self.switches.append(switch)

    def loop_switch_callback(self, *, client: Client, component: Switch, old_state: str, new_state: str):
        """Switches on/off (manually) loop.
        """

        for loop_number, switch in enumerate(self.switches):
            if component == switch:
                break

        component.set_state(new_state)
        component.publish_state(client)
                                             
        logger.info(f'Loop number {loop_number} ({component.name}) state changed: {old_state!r} -> {new_state!r}')
        if new_state == 'OFF': # close the valve immediately TODO , override=True
            self.event_loop.create_task(self.etera.move_motor(loop_number, EteraUartBridge.Direction.COUNTER_CLOCKWISE, 120*1000, override=True))
            self.event_loop.create_task(self.etera.set_relay(loop_number, False))


    async def update_sensors_and_control(self, outside_temperature: float,
                                         current_desired_dhw_temperature: float,
                                         intra_tank_circulation_enabled: bool,
                                         loop_circulation_status: bool,
                                         loop_temperature_offset_in_eco_mode: float,
                                         loop_operation_status_on_schedule: int):
        """Updates ETERA expander sub-device in Home Assistant and
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
        afterwards. All loops are adjusted by negative temperature
        offset in ECO mode when loop_operation_status_on_schedule is 2
        (ECO).  Loops are turned off if
        loop_operation_status_on_schedule in 0 and run normally if
        oop_operation_status_on_schedule 1.

        """
        try:
            temperatures = await self.etera.get_temperatures()
            settings = self.user_settings.custom_expander
            ids = settings.loop_sensors + settings.solar_sensors
            solar_pump_relay_id = settings.solar_pump_relay_id

            for i, sensor in enumerate(self.sensors):
                value = temperatures[ids[i]]
                sensor.set_state(value)
                sensor.publish(self.mqtt_client)    
            for switch in self.switches:
                switch.publish(self.mqtt_client)
            #### Expander control start
            collector_temperature = temperatures[settings.solar_sensors[0]]
            tank_temperature = temperatures[settings.solar_sensors[2]]
            difference = collector_temperature - tank_temperature
            if difference > settings.solar_pump_difference_on:
                await self.etera.set_relay(solar_pump_relay_id, True)
                relay = self.relays[solar_pump_relay_id]
                relay.set_state(relay.ON)
                state_message = 'switch ON'
            elif difference < settings.solar_pump_difference_off:
                await self.etera.set_relay(solar_pump_relay_id, False)
                relay = self.relays[solar_pump_relay_id]
                relay.set_state(relay.OFF)
                state_message = 'switch OFF'
            else:
                state_message = 'switch unchanged'
            if self.verbosity:
                print(f'Temperatures {temperatures} Collector-heat exchanger difference {difference} -> {state_message}')
                
            #loop_circulation_status=True
            if loop_circulation_status: # if loop 2 pump is running so do other loops
                for heat_loop in range(4):
                    relay = self.relays[heat_loop]
                    if relay is not None:
                        if self.switches[heat_loop].state == 'ON':
                            if not relay.is_on:
                                relay.set_state('ON')
                                await self.etera.set_relay(heat_loop, True)
                                # TODO Move motors accordint to the last reading 
                        else: # OFF
                            if relay.is_on:
                                relay.set_state('OFF')
                                await self.etera.set_relay(heat_loop, False)                                
            else:
                for heat_loop in range(4):
                    relay = self.relays[heat_loop]
                    if relay is not None and relay.is_on:
                        relay.set_state('OFF')
                        await self.etera.set_relay(heat_loop, False)
                                
                
            #### Expander control end
        except EteraUartBridge.DeviceException as e:
                print('Get temperatures error', e)
        relay_names = settings.relay_names
        for relay in self.relays:
            if relay is not None:
                relay.publish(self.mqtt_client)

    
