import asyncio

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print as rprint  # noqa

from kronoterm2mqtt.cli_dev import app
from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge
from kronoterm2mqtt.user_settings import UserSettings, get_user_settings


# import logging
# logger = logging.getLogger(__name__)


async def etera_reset_handler():
    print('Device just reset...')


async def etera_message_handler(message: bytes):
    print(message.decode())


@app.command
def expander_temperatures(verbosity: TyroVerbosityArgType):
    """Print temperatures read from Custom expander"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    async def print_temperatures():
        etera = EteraUartBridge(port,
                                on_device_reset_handler=etera_reset_handler,
                                on_device_message_handler=etera_message_handler)
        loop = asyncio.create_task(etera.run_forever())
        await etera.ready()
        print('Starting temperature read from custom expander')
        sensors = await etera.get_sensors()
        print(f'Sensors {[s.hex() for s in sensors]}')
        try:
            temps = await etera.get_temperatures()
            print(f'Temperatures {temps}')
        except EteraUartBridge.DeviceException as e:
            print('Get temp error', e)
        loop.cancel()

    asyncio.run(print_temperatures())


@app.command
def expander_motors(verbosity: TyroVerbosityArgType, opening: bool = True):
    """Rotates all 4 motors by closing (counterclockwise) or opening (clockwise) for 120 seconds"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    duration = 120

    print(f'Moving all motors for {duration} seconds at custom expander')

    async def move_motors():
        etera = EteraUartBridge(port,
                                on_device_reset_handler=etera_reset_handler,
                                on_device_message_handler=etera_message_handler)
        loop = asyncio.create_task(etera.run_forever())
        await etera.ready()

        # await etera.move_motor(1, EteraUartBridge.Direction.CLOCKWISE, 120 * 1000) # clockwise for 120 seconds
        try:
            moves = []
            for i in range(4):
                moves.append(
                    etera.move_motor(
                        i,
                        (
                            EteraUartBridge.Direction.CLOCKWISE
                            if opening
                            else EteraUartBridge.Direction.COUNTER_CLOCKWISE
                        ),
                        duration * 1000,
                    )
                )
            await asyncio.gather(*moves)
        except EteraUartBridge.DeviceException as e:
            print('Motor move error', e)
            await asyncio.sleep(1)
        loop.cancel()
        
    asyncio.run(move_motors())

@app.command
def expander_relay(verbosity: TyroVerbosityArgType, relay: int = 0, on: bool = True):
    """Switches on or off selected relay"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    print(f'Switching relay {relay} to {on}')

    async def switch_relay():
        etera = EteraUartBridge(port,
                                on_device_reset_handler=etera_reset_handler,
                                on_device_message_handler=etera_message_handler)
        loop = asyncio.create_task(etera.run_forever())
        await etera.ready()

        try:
            await etera.set_relay(relay, on)
            await asyncio.sleep(3)
        except EteraUartBridge.DeviceException as e:
            print('Relay switch error', e)
        loop.cancel()

    asyncio.run(switch_relay())


@app.command
def expander_loop(verbosity: TyroVerbosityArgType):
    """Runs Custom expander control of a solar pump"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)
    relay = user_settings.custom_expander.solar_pump_relay_id
    port = user_settings.custom_expander.port

    print('Starting manual control of a solar pump')

    async def temperature_loop():
        etera = EteraUartBridge(port,
                                on_device_reset_handler=etera_reset_handler,
                                on_device_message_handler=etera_message_handler)
        loop = asyncio.create_task(etera.run_forever())
        await etera.ready()
        while True:
            try:
                temps = await etera.get_temperatures()

                collector_temperature = temps[user_settings.custom_expander.solar_sensors[0]]
                tank_temperature = temps[user_settings.custom_expander.solar_sensors[2]]
                difference = collector_temperature - tank_temperature
                if difference > user_settings.custom_expander.solar_pump_difference_on:
                    await etera.set_relay(relay, True)
                    state = 'switch ON'
                elif difference < user_settings.custom_expander.solar_pump_difference_off:
                    await etera.set_relay(relay, False)
                    state = 'switch OFF'
                else:
                    state = 'switch unchanged'
                print(f'Temperatures {temps} Difference {difference} -> {state}')

            except EteraUartBridge.DeviceException as e:
                print('Get temp error', e)
            finally:
                await asyncio.sleep(60)
        loop.cancel()

    asyncio.run(temperature_loop())
