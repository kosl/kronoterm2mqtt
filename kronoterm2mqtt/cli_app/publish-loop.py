import asyncio
from asyncio.exceptions import CancelledError
import logging
import time

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from ha_services.exceptions import InvalidStateValue
from ha_services.mqtt4homeassistant.data_classes import MqttSettings
from ha_services.mqtt4homeassistant.mqtt import get_connected_client
from rich import print  # noqa

from kronoterm2mqtt.cli_app import app
from kronoterm2mqtt.mqtt_handler import KronotermMqttHandler
from kronoterm2mqtt.user_settings import UserSettings, get_user_settings


logger = logging.getLogger(__name__)


@app.command
def test_mqtt_connection(verbosity: TyroVerbosityArgType):
    """
    Test connection to MQTT Server
    """
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    settings: MqttSettings = user_settings.mqtt
    mqttc = get_connected_client(settings=settings, verbosity=verbosity)
    mqttc.loop_start()
    mqttc.loop_stop()
    mqttc.disconnect()
    print('\n[green]Test succeed[/green], bye ;)')


@app.command
def publish_loop(verbosity: TyroVerbosityArgType):
    """
    Publish KRONOTERM registers to Home Assistant MQTT
    """
    setup_logging(verbosity=verbosity)
    user_settings: UserSettings = get_user_settings(verbosity=verbosity)

    while True:
        try:
            print('[green]Starting Kronoterm 2 MQTT[/green]')
            with KronotermMqttHandler(user_settings=user_settings, verbosity=verbosity) as mqtt_handler:
                asyncio.run(mqtt_handler.publish_loop())
        except KeyboardInterrupt:
            raise
        except (InvalidStateValue, CancelledError) as e:
            logging.error(f'Kronoterm2MQTT loop failed. USB problem? {e}. Restating in 5 seconds ...')
            time.sleep(5)
        except Exception as e:
            print(f'Error: {e}', type(e))
            logger.exception(f'Unhandled Exception: {e} {type(e)}')
            exit(1)

