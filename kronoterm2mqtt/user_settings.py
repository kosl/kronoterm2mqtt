import dataclasses
import logging
import sys

from bx_py_utils.path import assert_is_file
from cli_base.systemd.data_classes import BaseSystemdServiceInfo, BaseSystemdServiceTemplateContext
from cli_base.toml_settings.api import TomlSettings
from ha_services.mqtt4homeassistant.data_classes import MqttSettings
from rich import print  # noqa



from kronoterm2mqtt.constants import BASE_PATH

try:
    import tomllib  # New in Python 3.11
except ImportError:
    import tomli as tomllib  # noqa:F401
    

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class HeatPump:
    """
    The "definitions_name" is the prefix of "kronoterm2mqtt/definitions/*.toml" files!    
    """
    definitions_name: str = 'kronoterm_ksm'
    device_name: str = 'Heat Pump' # Appearing in MQTT as Device
    model: str = 'ETERA' # Just for MQTT device Model info

    port: str = '/dev/ttyUSB0'
    slave_id: int = 20  # Kronoterm System Module Modbus address

    timeout: float = 0.5

    def get_definitions(self, verbosity) -> dict:
        definition_file_path = BASE_PATH / 'definitions' / f'{self.definitions_name}.toml'
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

    module_enabled: int = 0
    uid: str = 'etera_expander_module'
    name: str = 'Custom ETERA Expander Module'
    model: str = 'DIY' # Just for MQTT sub-device model info
    mqtt_payload_prefix: str = 'expander'


    port: str = '/dev/ttyUSB1'
    port_speed: int = 115200  

    timeout: float = 0.5
    number_of_thermometers: int = 10 # To check initially if settings are OK

    loop_operation: list = dataclasses.field(default_factory=lambda:[1,1,1,0])

    loop_operation: list = dataclasses.field(default_factory=lambda:[1, 1, 1, 0]) # Same as MA_2042
    loop_sensors: list = dataclasses.field(default_factory=lambda:[0, 1, 5, 6]) # ID order in get_sensors() list
    loop_temperatue: list = dataclasses.field(default_factory=lambda:[24.0, 24.0, 24.0, 24.0]) # At 0°C
    heating_curve_coefficient: float = 0.2 #: loop/outside temp °C

    solar_pump_operation: int = 1 #: 0 = disabled, 1 = enabled
    solar_pump_difference_on: float = 8.0 #: °C On(solar collector - pre-tank bottom)
    solar_pump_difference_off: float = 3.0 #: °C Off(solar collector - pre-tank bottom) 
    intra_tank_circulation_operation: int = 1 # 0 = disabled, 1 = enabled
    intra_tank_circulation_difference_on: float = 8.0 #: °C On > (pre-tank top - Hydro B DHW)
    intra_tank_circulation_difference_off: float = 5.0 #: °C Off < (pre-tank top - Hydro B DHW)
    solar_sensors: list = dataclasses.field(default_factory=lambda:[4, 3, 2, 8, 7]) #: id of solar collector, pre-tank (top, bottom), Etera DHW, DHW Circulator return
    # Relays with id [0 to 3] are for loop circulation pumps
    solar_pump_relay_id: int = 4
    inter_tank_pump_relay_id: int = 5


    def get_definitions(self, verbosity) -> dict:
        definition_file_path = BASE_PATH / 'definitions' / f'{self.definitions_name}.toml'
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

    See README for more information.

    At least you should specify MQTT settingsi to connect to mosquito server.
    main_uid defaults to hostname
    """


    # Information about the MQTT server:
    mqtt: dataclasses = dataclasses.field(default_factory=MqttSettings)

    systemd: dataclasses = dataclasses.field(default_factory=SystemdServiceInfo)

    heat_pump: dataclasses = dataclasses.field(default_factory=HeatPump)

    custom_expander: dataclasses = dataclasses.field(default_factory=CustomEteraExpander)

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
