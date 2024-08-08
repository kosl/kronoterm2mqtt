from pathlib import Path

import kronoterm2mqtt


CLI_EPILOG = 'Project Homepage: https://github.com/kosl/kronoterm2mqtt'

BASE_PATH = Path(__file__).parent


DEFAULT_DEVICE_MANUFACTURER = 'KRONOTERM'

MODBUS_SLAVE_ID = 20 # Kronoterm System Module Modbus address
