import logging
import ssl

import paho.mqtt.client as mqtt
from ha_services.mqtt4homeassistant.mqtt import get_connected_client as _upstream_get_connected_client

from kronoterm2mqtt.user_settings import MqttTlsSettings, UserSettings


logger = logging.getLogger(__name__)


def get_connected_client(user_settings: UserSettings, verbosity: int, timeout: int = 10) -> mqtt.Client:
    """
    Create and return a connected MQTT client with optional TLS support.

    If TLS is not enabled, delegates to the upstream ha_services implementation.
    If TLS is enabled, configures TLS before connecting.
    """
    tls_settings: MqttTlsSettings = user_settings.mqtt_tls
    mqtt_settings = user_settings.mqtt

    if not tls_settings.enabled:
        return _upstream_get_connected_client(settings=mqtt_settings, verbosity=verbosity, timeout=timeout)

    # TLS is enabled - we need to set up TLS before connect(),
    # so we replicate the connection logic with TLS inserted.
    from ha_services.mqtt4homeassistant.mqtt import OnConnectCallback, get_client_id

    import socket

    from bx_py_utils.anonymize import anonymize
    from cli_base.cli_tools.rich_utils import human_error
    from rich import print

    client_id = get_client_id()
    port = int(mqtt_settings.port)

    if verbosity:
        print(f'\nConnect [cyan]{mqtt_settings.host}:{port}[/cyan] as "[magenta]{client_id}[/magenta]"', end='...')

    socket.setdefaulttimeout(timeout)
    try:
        info = socket.getaddrinfo(mqtt_settings.host, port)
    except socket.gaierror as err:
        human_error(
            message=f'{err}\n(Hint: Check you host/port settings)',
            title=f'[red]Error get address info from: [cyan]{mqtt_settings.host}:{port}[/cyan]',
            exception=err,
            exit_code=1,
        )
    else:
        if not info:
            print('[red]Resolve error: No info!')
        elif verbosity:
            print('Host/port test [green]OK')

    mqttc = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
    )
    mqttc.on_connect = OnConnectCallback(verbosity=verbosity)
    mqttc.enable_logger(logger=logger)

    if mqtt_settings.user_name and mqtt_settings.password:
        if verbosity:
            print(
                f'login with user: {anonymize(mqtt_settings.user_name)} password:{anonymize(mqtt_settings.password)}',
                end='...',
            )
        mqttc.username_pw_set(mqtt_settings.user_name, mqtt_settings.password)

    # Configure TLS
    ca_certs = tls_settings.ca_certs or None
    certfile = tls_settings.certfile or None
    keyfile = tls_settings.keyfile or None

    if verbosity:
        print(f'TLS enabled (ca_certs={ca_certs}, certfile={certfile})', end='...')

    mqttc.tls_set(
        ca_certs=ca_certs,
        certfile=certfile,
        keyfile=keyfile,
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )

    if tls_settings.insecure:
        mqttc.tls_insecure_set(True)

    mqttc.connect(mqtt_settings.host, port=port)

    if verbosity:
        print('[green]OK')
    return mqttc
