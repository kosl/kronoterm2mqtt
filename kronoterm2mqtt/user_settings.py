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
    model: str = 'ETERA' # Just for MQTT device model info
    mqtt_payload_prefix: str = 'kronoterm'

    port: str = '/dev/ttyUSB0'
    slave_id: int = 20  # Kronoterm System Module Modbus address

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
    Custom IO Expander with DS18S20 1-wire thermometers
    for controlling additional loops and solar pumps
    See CustomEteraExpander class for more info.
    """

    module_enabled: bool = False
    uid: str = 'etera_expander_module'
    name: str = 'Custom ETERA Expander Module'
    model: str = 'DIY' # Just for MQTT sub-device model info
    mqtt_payload_prefix: str = 'expander'


    port: str = '/dev/ttyUSB1'
    port_speed: int = 115200  

    timeout: float = 0.5

    loop_operation: list = dataclasses.field(default_factory=lambda:[1,1,1,0])

    loop_operation: list = dataclasses.field(default_factory=lambda:[1, 1, 1, 0]) # Same as MA_2042
    loop_sensors: list = dataclasses.field(default_factory=lambda:[0, 1, 2, 3]) # ID order in get_sensors() list
    loop_temperatue: list = dataclasses.field(default_factory=lambda:[24.0, 24.0, 24.0, 24.0]) # At 0°C
    heating_curve_coefficient: float = 0.2 #: loop/outside temp °C

    solar_pump_operation: int = 1 #: 0 = disabled, 1 = enabled
    solar_pump_difference_on: float = 8.0 #: °C On(solar collector - pre-tank bottom)
    solar_pump_difference_off: float = 3.0 #: °C Off(solar collector - pre-tank bottom) 
    intra_tank_circulation_operation: int = 1 # 0 = disabled, 1 = enabled
    intra_tank_circulation_difference_on: float = 8.0 #: °C On > (pre-tank top - Hydro B DHW)
    intra_tank_circulation_difference_off: float = 5.0 #: °C Off < (pre-tank top - Hydro B DHW)
    solar_sensors: list = dataclasses.field(default_factory=lambda:[5, 6, 7, 8]) #: id od pre-tank (top, bottom), Etera DHW, solar collector


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
