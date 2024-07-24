import dataclasses
import logging
from decimal import Decimal

from cli_base.systemd.data_classes import BaseSystemdServiceInfo, BaseSystemdServiceTemplateContext

import ha_services
from ha_services.mqtt4homeassistant.components.binary_sensor import BinarySensor
from ha_services.mqtt4homeassistant.components.select import Select
from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.components.switch import Switch
from ha_services.mqtt4homeassistant.data_classes import MqttSettings
from ha_services.mqtt4homeassistant.device import MainMqttDevice, MqttDevice
from ha_services.mqtt4homeassistant.mqtt import get_connected_client


from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer.rtu_framer import ModbusRtuFramer
from pymodbus.pdu import ExceptionResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from rich.pretty import pprint

from kronoterm2mqtt.user_settings import HeatPump


logger = logging.getLogger(__name__)


def get_modbus_client(heat_pump: HeatPump, definitions: dict, verbosity: int) -> ModbusSerialClient:
    conn_settings = definitions['connection']

    print(f'Connect to {heat_pump.port}...')
    conn_kwargs = dict(
        baudrate=conn_settings['baudrate'],
        bytesize=conn_settings['bytesize'],
        parity=conn_settings['parity'],
        stopbits=conn_settings['stopbits'],
        timeout=heat_pump.timeout,
        retry_on_empty=heat_pump.retry_on_empty,
    )
    if verbosity:
        print('Connection arguments:')
        pprint(conn_kwargs)

    client = ModbusSerialClient(heat_pump.port, framer=ModbusRtuFramer, broadcast_enable=False, **conn_kwargs)
    if verbosity > 1:
        print('connected:', client.connect())
        print(client)

    return client


@dataclasses.dataclass
class SystemdServiceTemplateContext(BaseSystemdServiceTemplateContext):
    """
    Context values for the systemd service file content.
    """

    verbose_service_name: str = 'Kronoterm Heat Pump'


@dataclasses.dataclass
class SystemdServiceInfo(BaseSystemdServiceInfo):
    """
    Information for systemd helper functions.
    """

    template_context: SystemdServiceTemplateContext = dataclasses.field(default_factory=SystemdServiceTemplateContext)


@dataclasses.dataclass
class MqttExampleValues:
    """
    Some values used to create MQTT messages.
    """

    mqtt_payload_prefix: str = 'kronoterm'
    device_name: str = 'etera'



def get_ha_values(*, client, parameters, slave_id) -> list[Sensor]:
    values = []
    for parameter in parameters:
        logger.debug('Parameters: %r', parameter)
        parameter_name = parameter['name']
        address = parameter['register']
        count = parameter.get('count', 1)
        logger.debug('Read register %i (dez, count: %i, slave id: %i)', address, count, slave_id)

        response = client.read_holding_registers(address=address, count=count, slave=slave_id)
        if isinstance(response, (ExceptionResponse, ModbusException)):
            logger.error(
                'Error read register %i (dez, count: %i, slave id: %i): %s', address, count, slave_id, response
            )
        else:
            assert isinstance(response, ReadHoldingRegistersResponse), f'{response=}'
            registers = response.registers
            logger.debug('Register values: %r', registers)
            value = registers[0]
            if count > 1:
                value += registers[1] * 65536

            if scale := parameter.get('scale'):
                logger.debug('Scale %s: %r * %r', parameter_name, value, scale)
                scale = Decimal(str(scale))
                value = float(value * scale)
                logger.debug('Scaled %s results in: %r', parameter_name, value)

            ha_value = Sensor(
                name=parameter_name,
                value=value,
                device_class=parameter['device_class'],
                state_class=parameter['state_class'],
                unit=parameter['unit_of_measure'],
                device=device,
                suggested_display_precision=1,
            )
            logger.debug('HA-Value: %s', ha_value)
            values.append(ha_value)
    return values
