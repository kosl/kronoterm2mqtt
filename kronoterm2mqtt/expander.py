import logging
import time
import sys
from typing import List
from enum import Enum

from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.select import Select
from ha_services.mqtt4homeassistant.device import MqttDevice
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify
from paho.mqtt.client import Client

from kronoterm2mqtt.constants import MIXING_VALVE_HOLD_TIME
from kronoterm2mqtt.user_settings import UserSettings
from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge

logger = logging.getLogger(__name__)


async def etera_reset_handler():
    print('Custom ETERA expander just reset...', flush=True, file=sys.stderr)
    logging.error('Custom ETERA expander just reset...')


async def etera_message_handler(message: bytes):
    try:
        print(message.decode(), flush=True)
    except UnicodeDecodeError:
        print(message, flush=True)
    # logging.info(message.decode())


class ExpanderMqttHandler:
    def __init__(self, mqtt_client, user_settings: UserSettings, verbosity: int):
        self.etera = None
        self.event_loop = None
        self.mqtt_client = mqtt_client
        self.user_settings = user_settings
        self.verbosity = verbosity
        self.mqtt_device: MqttDevice | None = None
        self.sensors: List[Sensor] = list()  # loop[0:4], collector, solar tank up/down, DHW, DHW circulation
        self.relays: List[BinarySensor] = list()
        self.loop_states: List[Select] = list()  # Loop names from sensors
        self.mixing_valve_sensors: List[Sensor] = list()  # Position sensors in percentage
        self.mixing_valve_timer: List[float] = list()  # Measuring time from last move
        self.expedited_heating_timer: List[float] = list()  # Measuring time from start of expedited heating
        self.last_working_function: int = 5  # Heat pump in 5=Standby

    class WorkingMode(Enum):
        OFF = 'Izklop'
        ON = 'Vklop'
        EXPEDITED = 'Pospešeno 5h'
        STANDBY = 'Standby'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            return False

        if self.config.verbosity:
            print('\nClosing Etera Expander"', end='...')
        if self.etera:
            self.etera._s.close()  # TODO add context manager or close to etera library

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

        self.mqtt_device = MqttDevice(
            main_device=main_device,
            name="ETERA expander",
            uid="expander",
            manufacturer='Wigaun DIY',
            model='Arduino nano',
            sw_version='1.1.3',
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
                suggested_display_precision=2,
            ))
        for name in self.user_settings.custom_expander.relay_names:
            if len(name):  # relay in use? We run only 3 out of 4 mixing valve motors for now
                relay = BinarySensor(
                    device=self.mqtt_device,
                    name=name,
                    uid=slugify(name, '_').lower(),
                    device_class='running',
                )
                relay.set_state(relay.OFF)
                self.relays.append(relay)
            else:
                self.relays.append(None)

        for i, state in enumerate(self.user_settings.custom_expander.loop_operation):
            name = self.user_settings.custom_expander.sensor_names[i]
            if len(self.user_settings.custom_expander.relay_names[i]):
                select = Select(
                    device=self.mqtt_device,
                    name=name,
                    uid=slugify(name),
                    callback=self.loop_switch_callback,
                    options=[v.value for v in self.WorkingMode],
                    default_option=(self.WorkingMode.ON if state else self.WorkingMode.OFF).value,
                )
                self.loop_states.append(select)
                mixing_valve_sensor = Sensor(
                    device=self.mqtt_device,
                    name='Mešalni ventil ' + name,
                    uid=slugify('mesalni ventil ' + name, '_').lower(),
                    device_class='power_factor',
                    state_class='measurement',
                    unit_of_measurement='%',
                    suggested_display_precision=1
                )
                self.mixing_valve_sensors.append(mixing_valve_sensor)
                mixing_valve_sensor.set_state(0)
                mixing_valve_sensor.publish(self.mqtt_client)
                event_loop.create_task(self.mixing_valve_motor_close(i, 120))
                self.mixing_valve_timer.append(time.monotonic())
                self.expedited_heating_timer.append(None)

    async def mixing_valve_motor_close(self, heating_loop_number: int, duration: float, override: bool = True):
        try:
            await self.etera.move_motor(
                heating_loop_number, EteraUartBridge.Direction.COUNTER_CLOCKWISE, int(duration * 1000), override=override)
            position = self.mixing_valve_sensors[heating_loop_number].value
            position -= duration / 120.0 * 100
            if position < 0:
                position = 0
            self.mixing_valve_sensors[heating_loop_number].set_state(position)
            self.mixing_valve_sensors[heating_loop_number].publish(self.mqtt_client)
        except IndexError as e:
            print(f'Motor #{heating_loop_number} close invalid', e)
        except EteraUartBridge.DeviceException as e:
            print(f'Motor #{heating_loop_number} move error', e)

    async def mixing_valve_motor_open(self, heating_loop_number: int, duration: float, override: bool = True):
        try:
            await self.etera.move_motor(
                heating_loop_number, EteraUartBridge.Direction.CLOCKWISE, int(duration * 1000), override=override)
            position = self.mixing_valve_sensors[heating_loop_number].value
            position += duration / 120.0 * 100
            if position > 100:
                position = 100
            self.mixing_valve_sensors[heating_loop_number].set_state(position)
            self.mixing_valve_sensors[heating_loop_number].publish(self.mqtt_client)
        except EteraUartBridge.DeviceException as e:
            print(f'Motor #{heating_loop_number} move error', e)

    def loop_switch_callback(self, *, client: Client, component: Select, old_state: str, new_state: str):
        """Switches on/off (manually) loop.
        """
        loop_number = self.loop_states.index(component)
        component.set_state(new_state)
        component.publish_state(client)

        logger.info(f'Loop number {loop_number} ({component.name}) state changed: {old_state!r} -> {new_state!r}')
        # if new_state == 'OFF': # close the valve immediately
        #     self.event_loop.create_task(self.etera.set_relay(loop_number, False))
        #     self.event_loop.create_task(self.mixing_valve_motor_close(loop_number, 120*1000, override=True))
        # else: # ON
        #     self.event_loop.create_task(self.etera.set_relay(loop_number, True))

        try:
            new_state_e = self.WorkingMode(new_state)

            # Reset expedited heating timer
            self.expedited_heating_timer[loop_number] = None

            if new_state_e == self.WorkingMode.OFF.value:
                pass
            elif new_state_e == self.WorkingMode.ON.value:
                pass
            elif new_state_e == self.WorkingMode.EXPEDITED.value:
                self.expedited_heating_timer[loop_number] = time.monotonic()
                print(f"Expedited heating for {component.name} is started!")
            elif new_state_e == self.WorkingMode.STANDBY.value:
                print(f"Standby mode for {component.name} is started!")
        except ValueError:
            logger.error(f'Invalid state: {new_state!r}')
            return

    def get_loop_target_temperature(self,
                                    loop_number: int,
                                    temp_at_zero: float,
                                    outside_temperature: float,
                                    heating_curve_coefficient: float,
                                    loop_temperature_offset_in_eco_mode: float,
                                    loop_operation_status_on_schedule: int
                                    ):
        """Returns target temperature for the loop based on the
        outside temperature and heating curve coefficient.
        """

        # Expedited heating for 5 hours is set to 30°C
        if self.loop_states[loop_number].state == self.WorkingMode.EXPEDITED.value:
            return 30.0
        elif self.loop_states[loop_number].state == self.WorkingMode.STANDBY.value:
            return 10.0

        underfloor_temp_correction = -outside_temperature * heating_curve_coefficient
        if loop_operation_status_on_schedule == 2:
            underfloor_temp_correction += loop_temperature_offset_in_eco_mode

        return temp_at_zero + underfloor_temp_correction

    async def update_sensors_and_control(self, *, outside_temperature: float,
                                         current_desired_dhw_temperature: float,
                                         additional_source_enabled: bool,
                                         loop_circulation_status: bool,
                                         loop_temperature_offset_in_eco_mode: float,
                                         loop_operation_status_on_schedule: int,
                                         working_function: int
                                         ):
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
        loop_operation_status_on_schedule 1.  To synchronise the
        mixing valves motion with start of the heating from
        `working_function` and to add differential response to ramp up
        10K/10minutes for Loop 1 and initial closing of all mixing
        valves is started.

        """
        settings = self.user_settings.custom_expander
        try:
            # Heating loop state
            for i, select in enumerate(self.loop_states):
                if self.expedited_heating_timer[i] is not None:
                    if time.monotonic() - self.expedited_heating_timer[i] > 5 * 3600:
                        select.set_state(self.WorkingMode.OFF.value)
                        self.expedited_heating_timer[i] = None
                        print(f"Expedited heating for {select.name} is over!")

            temperatures = await self.etera.get_temperatures()
            ids = settings.loop_sensors + settings.solar_sensors
            solar_pump_relay_id = settings.solar_pump_relay_id

            for i, sensor in enumerate(self.sensors):
                value = temperatures[ids[i]]
                sensor.set_state(value)
                sensor.publish(self.mqtt_client)
            for select in self.loop_states:
                select.publish(self.mqtt_client)

            # Expander control start
            collector_temperature = temperatures[settings.solar_sensors[0]]
            tank_temperature = temperatures[settings.solar_sensors[2]]
            difference = collector_temperature - tank_temperature
            relay = self.relays[solar_pump_relay_id]
            if settings.solar_pump_operation:
                if difference > settings.solar_pump_difference_on or collector_temperature < -13.45:
                    await self.etera.set_relay(solar_pump_relay_id, True)
                    relay.set_state(relay.ON)
                    state_message = 'switch ON'
                elif difference < settings.solar_pump_difference_off:
                    await self.etera.set_relay(solar_pump_relay_id, False)
                    relay.set_state(relay.OFF)
                    state_message = 'switch OFF'
                else:
                    state_message = 'switch unchanged'
                    if self.verbosity:
                        print(
                            f'Temperatures {temperatures} Collector-heat exchanger difference {difference} -> {state_message}')

            relay = self.relays[settings.inter_tank_pump_relay_id]
            if additional_source_enabled and settings.intra_tank_circulation_operation:
                dhw_temperature = self.sensors[7].value  # noqa
                solar_tank_temperature = self.sensors[5].value  # noqa
                # if dhw_temperature < current_desired_dhw_temperature:
                #    dt = solar_tank_temperature - dhw_temperature
                #    if abs(dt) > settings.solar_pump_difference_on:
                #        if not relay.is_on:
                #            relay.set_state(relay.ON)
                #            await self.etera.set_relay(settings.inter_tank_pump_relay_id, True)
                #    elif abs(dt) < settings.solar_pump_difference_off:
                #        if relay.is_on:
                #            relay.set_state(relay.OFF)
                #            await self.etera.set_relay(settings.inter_tank_pump_relay_id, False)
                # else:
                #    if relay.is_on:
                #       relay.set_state(relay.OFF)
                #       await self.etera.set_relay(settings.inter_tank_pump_relay_id, False)
                if not relay.is_on:
                    relay.set_state(relay.ON)
                    await self.etera.set_relay(settings.inter_tank_pump_relay_id, True)
            elif relay.is_on:
                relay.set_state(relay.OFF)
                await self.etera.set_relay(settings.inter_tank_pump_relay_id, False)

            # loop_circulation_status=True
            if loop_circulation_status:  # if primary loop pump is running so should other heating loops
                for heat_loop in range(4):
                    relay = self.relays[heat_loop]
                    if relay is not None:
                        if self.loop_states[heat_loop].state != self.WorkingMode.OFF.value:
                            if not relay.is_on:
                                relay.set_state(relay.ON)
                                await self.etera.set_relay(heat_loop, True)
                            # Move motors according to the last reading
                            loop_temperature = self.sensors[heat_loop].value
                            if loop_temperature > 40.0:  # rapid loop shutdown
                                self.loop_states[heat_loop].set_state('Izklop')
                                await self.etera.set_relay(heat_loop, False)
                                self.event_loop.create_task(
                                    self.mixing_valve_motor_close(
                                        heat_loop, 120, override=True))
                                print(f"Undefloor temperature #{heat_loop} too high ({loop_temperature}) for {self.loop_states[heat_loop].name}!"
                                      " Switched off now!")
                                continue
                            if self.last_working_function > 0 and working_function == 0:  # Start of heating detected, close the valve
                                self.mixing_valve_timer[heat_loop] = time.monotonic()  # reset timer
                                self.event_loop.create_task(self.mixing_valve_motor_close(heat_loop, 12))
                                continue  # to next loop
                            if time.monotonic() - \
                                    self.mixing_valve_timer[heat_loop] > MIXING_VALVE_HOLD_TIME:  # can move motor?
                                self.mixing_valve_timer[heat_loop] = time.monotonic()  # reset timer
                                temp_at_zero = settings.loop_temperature[heat_loop]
                                target_loop_temperature = self.get_loop_target_temperature(
                                    heat_loop, temp_at_zero,
                                    outside_temperature, settings.heating_curve_coefficient,
                                    loop_temperature_offset_in_eco_mode, loop_operation_status_on_schedule)
                                # print(f"DBG: Loop {heat_loop}: target -> {target_loop_temperature} ({self.loop_states[heat_loop].state})")
                                if loop_temperature >= target_loop_temperature:  # close the mixing valve
                                    move_duration = (
                                        loop_temperature - target_loop_temperature) * 3.0  # 3 seconds for 1K
                                    if move_duration > 12:
                                        move_duration = 12  # limit move
                                    self.event_loop.create_task(
                                        self.mixing_valve_motor_close(
                                            heat_loop, move_duration))

                                else:  # open the mixing valve since target_loop_temperature > loop_temperature
                                    move_duration = (
                                        target_loop_temperature - loop_temperature) * 3.0  # 3 seconds for 1K
                                    if move_duration > 10:
                                        move_duration = 10  # limit move
                                    self.event_loop.create_task(self.mixing_valve_motor_open(heat_loop, move_duration))
                                if self.verbosity > 1:
                                    underfloor_temp_correction = target_loop_temperature - temp_at_zero
                                    print(f"Circuit #{heat_loop} {self.loop_states[heat_loop].name}[{self.loop_states[heat_loop].state}]: {loop_temperature=} {target_loop_temperature=}"
                                          f" {temp_at_zero=} {outside_temperature=} {underfloor_temp_correction=} {move_duration=}")

                        else:  # Loop is switched OFF (disabled) and we close the valve and the pump if needed
                            if relay.is_on:
                                relay.set_state(relay.OFF)
                                self.event_loop.create_task(self.mixing_valve_motor_close(
                                    heat_loop, 120, override=True))
                                await self.etera.set_relay(heat_loop, False)

            else:  # The loop circulation in the Kronoterm heat pump is stopped momentarily due to DHW heating?
                for heat_loop in range(4):
                    relay = self.relays[heat_loop]
                    if relay is not None:
                        if self.loop_states[heat_loop].state == self.WorkingMode.OFF.value and relay.is_on:
                            self.event_loop.create_task(self.mixing_valve_motor_close(
                                heat_loop, 120, override=True))
                        if relay.is_on:  # We stop the pumps for now
                            relay.set_state(relay.OFF)
                            await self.etera.set_relay(heat_loop, False)
                            if self.verbosity:
                                print(f"{relay.name} switched OFF")

            self.last_working_function = working_function
            # Expander control end
        except EteraUartBridge.DeviceException as e:
            print('Get temperatures error', e)
        for relay in self.relays:
            if relay is not None:
                relay.publish(self.mqtt_client)
