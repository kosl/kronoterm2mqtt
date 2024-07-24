from pathlib import Path

import kronoterm2mqtt


CLI_EPILOG = 'Project Homepage: https://github.com/kosl/kronoterm2mqtt'

BASE_PATH = Path(__file__).parent


BLEAK_CLIENT_TIMEOUT = 3


ASK_FOR_VALUES_COMMAND = bytearray(b'bgetva\r\n')

# Firmware >= 1.15
RX_CHARACTERISTIC_UUID = '0000ffe1-0000-1000-8000-00805f9b34fb'
TX_CHARACTERISTIC_UUID = '0000ffe2-0000-1000-8000-00805f9b34fb'

DEFAULT_DEVICE_NAME = 'kronoterm'


