import sys
import rich_click as click
from pathlib import Path

import kronoterm2mqtt
from kronoterm2mqtt.cli_dev import PACKAGE_ROOT, cli
from kronoterm2mqtt.user_settings import UserSettings, get_user_settings
from cli_base.cli_tools.subprocess_utils import verbose_check_call
from cli_base.cli_tools.verbosity import OPTION_KWARGS_VERBOSE, setup_logging

@cli.command()
def compile_firmware():
    """
    Compiles firmware for Etera GPIO expander with PlatformIO compiler
    """
    bin_path = Path(sys.executable).parent

    verbose_check_call(bin_path / 'pio', 'run', cwd="etera-uart-bridge/pio-eub-firmware")
    

@cli.command()
@click.option('-v', '--verbosity', **OPTION_KWARGS_VERBOSE)
def flash_firmware(verbosity: int):
    """
    Flashes compiled firmware
    """

    user_settings: UserSettings = get_user_settings(verbosity=verbosity)
    port = user_settings.custom_expander.port

    verbose_check_call('avrdude', '-v', '-p', 'atmega328p', '-c', 'arduino',
                       '-P', port, '-b',  '57600', '-D',
                       '-U', 'flash:w:etera-uart-bridge/pio-eub-firmware/.pio/build/nanoatmega328/firmware.hex:i')
