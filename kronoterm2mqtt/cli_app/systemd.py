import logging

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.systemd.api import ServiceControl
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from kronoterm2mqtt.cli_app import app
from kronoterm2mqtt.user_settings import SystemdServiceInfo, UserSettings, get_user_settings


logger = logging.getLogger(__name__)


def get_systemd_settings(verbosity: int) -> SystemdServiceInfo:
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)
    systemd_settings: SystemdServiceInfo = user_settings.systemd
    return systemd_settings


@app.command
def systemd_debug(verbosity: TyroVerbosityArgType):
    """
    Print Systemd service template + context + rendered file content.
    """
    setup_logging(verbosity=verbosity)
    systemd_settings: SystemdServiceInfo = get_systemd_settings(verbosity)

    ServiceControl(info=systemd_settings).debug_systemd_config()


@app.command
def systemd_setup(verbosity: TyroVerbosityArgType):
    """
    Write Systemd service file, enable it and (re-)start the service. (May need sudo)
    """
    setup_logging(verbosity=verbosity)
    systemd_settings: SystemdServiceInfo = get_systemd_settings(verbosity)

    ServiceControl(info=systemd_settings).setup_and_restart_systemd_service()


@app.command
def systemd_remove(verbosity: TyroVerbosityArgType):
    """
    Remove Systemd service file. (May need sudo)
    """
    setup_logging(verbosity=verbosity)
    systemd_settings: SystemdServiceInfo = get_systemd_settings(verbosity)

    ServiceControl(info=systemd_settings).remove_systemd_service()


@app.command
def systemd_status(verbosity: TyroVerbosityArgType):
    """
    Display status of systemd service. (May need sudo)
    """
    setup_logging(verbosity=verbosity)
    systemd_settings: SystemdServiceInfo = get_systemd_settings(verbosity)

    ServiceControl(info=systemd_settings).status()


@app.command()
def systemd_stop(verbosity: TyroVerbosityArgType):
    """
    Stops the systemd service. (May need sudo)
    """
    setup_logging(verbosity=verbosity)
    systemd_settings: SystemdServiceInfo = get_systemd_settings(verbosity)

    ServiceControl(info=systemd_settings).stop()
