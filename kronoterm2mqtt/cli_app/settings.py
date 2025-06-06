import logging

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.toml_settings.api import TomlSettings
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from kronoterm2mqtt.cli_app import app
from kronoterm2mqtt.user_settings import get_toml_settings


logger = logging.getLogger(__name__)


@app.command
def edit_settings(verbosity: TyroVerbosityArgType):
    """
    Edit the settings file. On first call: Create the default one.
    """
    setup_logging(verbosity=verbosity)
    toml_settings: TomlSettings = get_toml_settings()
    toml_settings.open_in_editor()


@app.command
def print_settings(verbosity: TyroVerbosityArgType):
    """
    Display (anonymized) MQTT server username and password
    """
    setup_logging(verbosity=verbosity)
    toml_settings: TomlSettings = get_toml_settings()
    toml_settings.print_settings()
