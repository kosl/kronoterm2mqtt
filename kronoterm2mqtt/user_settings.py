import dataclasses
import logging
import sys

from bx_py_utils.path import assert_is_file
from cli_base.systemd.data_classes import BaseSystemdServiceInfo, BaseSystemdServiceTemplateContext
from cli_base.toml_settings.api import TomlSettings
from ha_services.mqtt4homeassistant.data_classes import MqttSettings
from rich import print  # noqa



from kronoterm2mqtt.constants import DEFAULT_DEVICE_NAME, BASE_PATH

try:
    import tomllib  # New in Python 3.11
except ImportError:
    import tomli as tomllib  # noqa:F401
    

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class HeatPump:
    """
    The "name" is the prefix of "kronoterm2mqtt/definitions/*.toml" files!
    """

    name: str = 'kronoterm_ksm'
    verbose_name: str = 'Kronoterm System Module'
    mqtt_payload_prefix: str = 'kronoterm'  # FIXME: Use serial number?!?

    port: str = '/dev/ttyUSB0'
    slave_id: int = 20  # Modbus address

    timeout: float = 0.5
    retry_on_empty: bool = True

    def get_definitions(self, verbosity) -> dict:
        definition_file_path = BASE_PATH / 'definitions' / f'{self.name}.toml'
        assert_is_file(definition_file_path)
        content = definition_file_path.read_text(encoding='UTF-8')
        definitions = tomllib.loads(content)

        if verbosity > 1:
            pprint(definitions)

        return definitions

@dataclasses.dataclass
class CustomEteraExpander:
    """
    Custom IO Expander with 1-wire thermometers
    for controlling additional loops and solar pumps 
    """

    name: str = 'etera_expander_module'
    verbose_name: str = 'Custom ETERA Expander Module'
    mqtt_payload_prefix: str = 'kronoterm'

    port: str = '/dev/ttyUSB1'
    port_speed: int = 115200  

    timeout: float = 0.5

    def get_definitions(self, verbosity) -> dict:
        definition_file_path = BASE_PATH / 'definitions' / f'{self.name}.toml'
        assert_is_file(definition_file_path)
        content = definition_file_path.read_text(encoding='UTF-8')
        definitions = tomllib.loads(content)

        if verbosity > 1:
            pprint(definitions)

        return definitions
    


@dataclasses.dataclass
class SystemdServiceTemplateContext(BaseSystemdServiceTemplateContext):
    """
    Context values for the systemd service file content.
    """

    verbose_service_name: str = 'kronoterm2mqtt'
    exec_start: str = f'{sys.argv[0]} publish-loop'


@dataclasses.dataclass
class SystemdServiceInfo(BaseSystemdServiceInfo):
    """
    Information for systemd helper functions.
    """

    template_context: SystemdServiceTemplateContext = dataclasses.field(default_factory=SystemdServiceTemplateContext)


@dataclasses.dataclass
class UserSettings:
    """
    KRONOTERM -> MQTT - settings

    device_name: will appear as a name in Home Assistant

    See README for more information.
    """

    device_name: str = DEFAULT_DEVICE_NAME
    

    # Information about the MQTT server:
    mqtt: dataclasses = dataclasses.field(default_factory=MqttSettings)

    systemd: dataclasses = dataclasses.field(default_factory=SystemdServiceInfo)

    heat_pump: dataclasses = dataclasses.field(default_factory=HeatPump)

    etera_expander: dataclasses = dataclasses.field(default_factory=CustomEteraExpander)

def get_toml_settings() -> TomlSettings:
    return TomlSettings(
        dir_name='kronoterm2mqtt',
        file_name='kronoterm2mqtt',
        settings_dataclass=UserSettings(),
    )


def get_user_settings(verbosity: int) -> UserSettings:
    toml_settings: TomlSettings = get_toml_settings()
    user_settings: UserSettings = toml_settings.get_user_settings(debug=verbosity > 0)
    return user_settings
