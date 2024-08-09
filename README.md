# kronoterm2mqtt

[![tests](https://github.com/kosl/kronoterm2mqtt/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/kosl/kronoterm2mqtt/actions/workflows/tests.yml)
[![codecov](https://codecov.io/github/kosl/kronoterm2mqtt/branch/main/graph/badge.svg)](https://app.codecov.io/github/kosl/kronoterm2mqtt)
[![kronoterm2mqtt @ PyPi](https://img.shields.io/pypi/v/kronoterm2mqtt?label=kronoterm2mqtt%20%40%20PyPi)](https://pypi.org/project/kronoterm2mqtt/)
[![Python Versions](https://img.shields.io/pypi/pyversions/kronoterm2mqtt)](https://github.com/kosl/kronoterm2mqtt/blob/main/pyproject.toml)
[![License GPL-3.0-or-later](https://img.shields.io/pypi/l/kronoterm2mqtt)](https://github.com/kosl/kronoterm2mqtt/blob/main/LICENSE)

Get information from the Kronoterm heat pump connected to Modbus TEX interface.

While reading Modbus registers from the pump the kronoterm2mqtt sends
MQTT discovery events from KRONOTERM to MQTT broker (Mosquito) that
Home Assistant then reads and the sensor readings appear therein
automatically.

Optionally, the MQTT loop can also control custom (DIY) IO expander to
be added to heat pump controlling additional heating loops and pumps
for solar DHW pre-heat boiler. This expander board is using Arduino
nano MCU to provide serial (UART) interface for Raspberry Pi
control. See [Etera UART GPIO expander
project](https://github.com/Lenart12/etera-uart-bridge) for help on
the protocol and interface. By default, this module functionality is
disabled so that only Kronoterm Heat Pump MQTT can still be used
without having this hardware module.

## Bootstrap kronoterm2mqtt

Clone the sources and just call the CLI to create a Python Virtualenv, e.g.:

```bash
~$ git clone --recursive https://github.com/kosl/kronoterm2mqtt.git
~$ cd kronoterm2mqtt
~/kronoterm2mqtt$ ./cli.py --help
```
The output of `./cli.py --help` looks like:

```sh
kronoterm2mqtt v0.1.6 bed9746 (/home/leon/kronoterm2mqtt)
                                                                                            
 Usage: ./cli.py [OPTIONS] COMMAND [ARGS]...                                                
                                                                                            
╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --help      Show this message and exit.                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────╮
│ edit-settings         Edit the settings file. On first call: Create the default one.     │
│ print-registers       Print RAW modbus register data                                     │
│ print-settings        Display (anonymized) MQTT server username and password             │
│ print-values          Print all values from the definition                               │
│ probe-usb-ports       Probe through the USB ports and print the values from definition   │
│ publish-loop          Publish KRONOTERM registers to Home Assistant MQTT                 │
│ systemd-debug         Print Systemd service template + context + rendered file content.  │
│ systemd-remove        Remove Systemd service file. (May need sudo)                       │
│ systemd-setup         Write Systemd service file, enable it and (re-)start the service.  │
│                       (May need sudo)                                                    │
│ systemd-status        Display status of systemd service. (May need sudo)                 │
│ systemd-stop          Stops the systemd service. (May need sudo)                         │
│ test-mqtt-connection  Test connection to MQTT Server                                     │
│ version               Print version and exit                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
                                                                                            
 Project Homepage: https://github.com/kosl/kronoterm2mqtt
 ```

## Setup

Once having hardware (Modbus wiring) correctly installed the steps to get running are:

1. `./cli-app.py edit-setting` to configure MQTT host and credentials, heat pump model and RS485 port.
2. `./cli-app.py test-mqtt-connection` to check that Mosquitto broker accepts connections.
4. `./cli-app.py print-values` to see the actual registers from the heat pump converted to correct units.
3. Install and configure MQTT integration in Home assistant
4. `./cli-app.py publish-loop` to see the heat pump under Home Assistant -> Settings -> Devices & Services -> MQTT.
5. `sudo ./cli-app.py systemd-setup` to create permanent service, and
6. `sudo ./cli-app.py systemd-start` to start the `publish-loop` service

There are some other useful commands to debug (`-v` switch) and
develop it further. Unwanted registers can be commented out by
changing `kronoterm2mqtt/definitions/kronoterm_ksm.toml` individual
`[[sensor]]` entries to something like `[[sensor_disabled]]` so that
it will be skipped during definitions scan. There are quite some
number of disabled sensors that can be shown and the TOML file can get
more sensors if required.

### print-values
```sh
$ ./cli.py print-values

+ /home/leon/kronoterm2mqtt/.venv-app/bin/kronoterm2mqtt_app print-values

kronoterm2mqtt v0.1.6 42cf603 (/home/leon/kronoterm2mqtt)

Connect to /dev/ttyUSB0...
          HP inlet temperature 30.7 °C
               DHW temperature 48.1 °C
           Outside temperature 29.0 °C
         HP outlet temperature 30.9 °C
       Evaporating temperature 30.7 °C
        Compressor temperature 30.3 °C
     Current power consumption 0.0 W
            Loop 1 temperature 29.8 °C
            Loop 2 temperature 28.3 °C
 Loop 2 thermostat temperature 25.5 °C
       Heating system pressure 1.4 bar
               Source pressure 1.8 bar
                           COP 0.00 
                          SCOP 0.00 
```

## Using PyPi repository

*kronoterm2mqtt* is released under PyPi so that it is easier to
install it in a virtual environment such as:

```sh
python -m venv venv
venv/bin/pip install kronoterm2mqtt
venv/bin/kronoterm2mqtt_app edit-settings
venv/bin/kronoterm2mqtt_app print-values
```

## Images
### Modbus RTU connection within a Kronoterm ETERA heat pump from Raspberry Pi3B to TEX interface
![](images/etera.jpeg)

Raspberry Pi3B (running Home Assistant) and a small 5-port ethernet
switch below are powered by a buckle step down (12->5V) converters.

### Home Assistant

Home Assistant -> Settings -> Devices & Services -> MQTT screenshot
![Home Assistant](images/ha-sensors.png)

## Hardware wiring test

The connection to TEX port is done with RS485 dongle using 3 wires (A,
B, GND). Before running `kronoterm2mqtt` it is advisable to run simple
example provided to debug and test the communication as shown below.

~~~sh
$ python -m venv venv
$ venv/bin/pip install pymodbus pyserial
$ venv/bin/python kronoterm2mqtt/examples/print-temperatures.py
2024-08-09 10:11:35,553 DEBUG logging:103 Current transaction state - IDLE
2024-08-09 10:11:35,554 DEBUG logging:103 Running transaction 1
2024-08-09 10:11:35,554 DEBUG logging:103 SEND: 0x14 0x3 0x8 0x34 0x0 0xa 0x84 0xa6
2024-08-09 10:11:35,555 DEBUG logging:103 Resetting frame - Current Frame in buffer - 
2024-08-09 10:11:35,556 DEBUG logging:103 New Transaction state "SENDING"
2024-08-09 10:11:35,557 DEBUG logging:103 Changing transaction state from "SENDING" to "WAITING FOR REPLY"
2024-08-09 10:11:35,579 DEBUG logging:103 Changing transaction state from "WAITING FOR REPLY" to "PROCESSING REPLY"
2024-08-09 10:11:35,579 DEBUG logging:103 RECV: 0x14 0x3 0x14 0x1 0x20 0x1 0xe3 0x0 0xf7 0x1 0x25 0x1 0x2f 0x1 0x2a 0xfd 0xa8 0x0 0x0 0xfd 0xa8 0x1 0xc 0x8d 0x77
2024-08-09 10:11:35,580 DEBUG logging:103 Processing: 0x14 0x3 0x14 0x1 0x20 0x1 0xe3 0x0 0xf7 0x1 0x25 0x1 0x2f 0x1 0x2a 0xfd 0xa8 0x0 0x0 0xfd 0xa8 0x1 0xc 0x8d 0x77
2024-08-09 10:11:35,580 DEBUG logging:103 Getting Frame - 0x3 0x14 0x1 0x20 0x1 0xe3 0x0 0xf7 0x1 0x25 0x1 0x2f 0x1 0x2a 0xfd 0xa8 0x0 0x0 0xfd 0xa8 0x1 0xc
2024-08-09 10:11:35,580 DEBUG logging:103 Factory Response[ReadHoldingRegistersResponse': 3]
2024-08-09 10:11:35,581 DEBUG logging:103 Frame advanced, resetting header!!
2024-08-09 10:11:35,581 DEBUG logging:103 Adding transaction 0
2024-08-09 10:11:35,581 DEBUG logging:103 Getting transaction 0
2024-08-09 10:11:35,581 DEBUG logging:103 Changing transaction state from "PROCESSING REPLY" to "TRANSACTION_COMPLETE"
KRONOTERM Temperatures: ['28.8°C', '48.3°C', '24.7°C', '29.3°C', '30.3°C', '29.8°C', '6493.6°C', '0.0°C', '6493.6°C', '26.8°C']
~~~


## TODO

- [x] `enum_sensor` to convert status registers to more meaningfull text readings instead of float sensor
- [x] `switch` to turn on at least DHW circulation pump manually in Home Assistant and then programatically since 6 transitions provided by the heat pump is too limited
- [x] `binary_sensor` to show some two-state states
- [x] `binary_sensor` to decode binary statuses in `enum` like manner combined. For example error messages or "additional activations".
- [ ] Upgrade [ha-services](https://github.com/jedie/ha-services) with `number` component allowing change of some numeric parameters (set temperatures, etc.).

## References

- `Navodila za priklop in uporabo CNS sistema.pdf` Kronoterm Modbus RTU description (in Slovene) obtained from Kronoterm support
- `Installation and Operating Manual for BMS System.pdf` Kronoterm Modbus V3.13-1 RTU description obtained from Kronoterm support