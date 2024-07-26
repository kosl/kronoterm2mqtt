# kronoterm2mqtt

[![codecov](https://codecov.io/github/kosl/kronoterm2mqtt/branch/main/graph/badge.svg)](https://app.codecov.io/github/kosl/kronoterm2mqtt)
[![kronoterm2mqtt @ PyPi](https://img.shields.io/pypi/v/kronoterm2mqtt?label=kronoterm2mqtt%20%40%20PyPi)](https://pypi.org/project/kronoterm2mqtt/)
[![Python Versions](https://img.shields.io/pypi/pyversions/kronoterm2mqtt)](https://github.com/kosl/kronoterm2mqtt/blob/main/pyproject.toml)
[![License GPL-3.0-or-later](https://img.shields.io/pypi/l/kronoterm2mqtt)](https://github.com/kosl/kronoterm2mqtt/blob/main/LICENSE)

Get information from the Kronoterm heat pump connected to Modbus TEX interface

Send MQTT discovery events from KRONOTERM heat_pump to Home Assistant.

Optionally, the MQTT loop can also control custom (DIY) IO expander to
be added to heat pump controlling additional heating loops and pumps
for solar DHW pre-heat boiler. More info on hardware and forfware under
[etera-uart-bridge/README.md](etera-uart-bridge/README.md)



## Bootstrap kronoterm2mqtt

Clone the sources and just call the CLI to create a Python Virtualenv, e.g.:

```bash
~$ git clone https://github.com/kosl/kronoterm2mqtt.git
~$ cd kronoterm2mqtt
~/kronoterm2mqtt$ ./cli.py --help
```
The output of `./cli.py --help` looks like:


## Screenshots

### Home Assistant



### print data

test print data in terminal looks like:

