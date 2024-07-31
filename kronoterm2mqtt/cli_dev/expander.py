import asyncio

import rich_click as click
from cli_base.cli_tools.verbosity import OPTION_KWARGS_VERBOSE, setup_logging
from rich import print  as rprint # noqa

import kronoterm2mqtt
from kronoterm2mqtt.cli_dev import cli
from kronoterm2mqtt.user_settings import UserSettings, get_user_settings
from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge

#import logging
#logger = logging.getLogger(__name__)

async def etera_reset_handler():
    print('Device just reset...')


@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def expander_temperatures(verbosity: int):
    """Print temperatures read from Custom expander"""
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    port = user_settings.custom_expander.port

    etera = EteraUartBridge(port, on_device_reset_handler=etera_reset_handler)

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
        
