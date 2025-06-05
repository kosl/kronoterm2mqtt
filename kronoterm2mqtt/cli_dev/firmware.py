import sys
from pathlib import Path

from cli_base.cli_tools.subprocess_utils import verbose_check_call
from cli_base.tyro_commands import TyroVerbosityArgType

from kronoterm2mqtt.cli_dev import app
from kronoterm2mqtt.user_settings import UserSettings, get_user_settings


@app.command
def firmware_compile():
    """
    Compiles firmware for Etera GPIO expander with PlatformIO compiler
    """
    bin_path = Path(sys.executable).parent

    verbose_check_call(bin_path / 'pio', 'run', cwd="etera-uart-bridge/pio-eub-firmware")


@app.command
def firmware_flash(verbosity: TyroVerbosityArgType):
    """
    Flashes compiled firmware to Etera GPIO expander
    """

    user_settings: UserSettings = get_user_settings(verbosity=verbosity)
    port = user_settings.custom_expander.port

    verbose_check_call(
        'avrdude',
        '-v',
        '-p',
        'atmega328p',
        '-c',
        'arduino',
        '-P',
        port,
        '-b',
        '57600',
        '-D',
        '-U',
        'flash:w:etera-uart-bridge/pio-eub-firmware/.pio/build/nanoatmega328/firmware.hex:i',
    )
