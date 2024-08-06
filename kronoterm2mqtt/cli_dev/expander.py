import asyncio

import rich_click as click
from cli_base.cli_tools.verbosity import OPTION_KWARGS_VERBOSE, setup_logging
from rich import print  as rprint # noqa

import kronoterm2mqtt
from kronoterm2mqtt.cli_dev import cli
from kronoterm2mqtt.user_settings import UserSettings, CustomEteraExpander, get_user_settings
import kronoterm2mqtt.pyetera_uart_bridge
from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge


#import logging
#logger = logging.getLogger(__name__)

async def etera_reset_handler():
    print('Device just reset...')

async def etera_message_handler(message: bytes):
    print(message.decode())


@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def expander_temperatures(verbosity: int):
    """Print temperatures read from Custom expander"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler,
                            on_device_message_handler=etera_message_handler)

    print('Starting temperature read from custom expander')
    
    async def print_temperatures():
        await etera.ready()
        sensors = await etera.get_sensors()
        print(f'Sensors {[s.hex() for s in sensors]}')
        try:
            temps = await etera.get_temperatures()
            print(f'Temperatures {temps}')
        except EteraUartBridge.DeviceException as e:
            print('Get temp error', e)

    async def temp():
        loop = asyncio.create_task(etera.run_forever())
        await print_temperatures()
        loop.cancel()
        
    asyncio.run(temp())


OPTION_ARGS_DEFAULT_TRUE = dict(is_flag=True, show_default=True, default=True)
        
@cli.command()
@click.option('-o', '--opening/--closing', **OPTION_ARGS_DEFAULT_TRUE)
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def expander_motors(opening, verbosity: int):
    """Rotates all 4 motors by closing (counterclockwise) or opening (clockwise) for 120 seconds"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler,
                            on_device_message_handler=etera_message_handler)

    duration = 120

    print(f'Moving all motors for {duration} seconds at custom expander')


    async def move_motors(opening, duration: int):

        await etera.ready()
        #await etera.move_motor(1, EteraUartBridge.Direction.CLOCKWISE, 120 * 1000) # clockwise for 120 seconds

        try:
            moves = []
            for i in range(4):
                moves.append(etera.move_motor(i, EteraUartBridge.Direction.CLOCKWISE if opening
                                              else EteraUartBridge.Direction.COUNTER_CLOCKWISE, duration*1000))
            await asyncio.gather(*moves)
        except EteraUartBridge.DeviceException as e:
            print('Motor move error', e)
            await asyncio.sleep(1)

    async def go():
        loop = asyncio.create_task(etera.run_forever())
        await move_motors(opening, duration)
        loop.cancel()
    
    asyncio.run(go())

option_kwargs_relay = dict(
    required=True,
    type=click.IntRange(0, 7),
    help='Relay number',
    default=0,
    show_default=True,
)

@cli.command()
@click.option('-r', '--relay', **option_kwargs_relay)
@click.option('-o', '--on/--off', **OPTION_ARGS_DEFAULT_TRUE)
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def expander_relay(relay: int, on: bool, verbosity: int):
    """Switches on or off selected relay"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler,
                            on_device_message_handler=etera_message_handler)

    print(f'Switching relay {relay} to {on}')

    async def switch_relay(relay, on: bool):

        await etera.ready()

        try:
            await etera.set_relay(relay, on)
            await asyncio.sleep(3)
        except EteraUartBridge.DeviceException as e:
            print('Relay switch error', e)


    async def go():
        loop = asyncio.create_task(etera.run_forever())
        await switch_relay(relay, on)
        loop.cancel()
    
    asyncio.run(go())

@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def expander_loop(verbosity: int):
    """Runs Custom expander control of a solar pump"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)
    relay = user_settings.custom_expander.solar_pump_relay_id
    port = user_settings.custom_expander.port
    etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler,
                            on_device_message_handler=etera_message_handler)
    
    print('Starting manual control of a solar pump')
    
    async def temperature_loop():
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
            
    async def loop():
        await asyncio.gather(etera.run_forever(),
                             temperature_loop()
                             )
    asyncio.run(loop())
