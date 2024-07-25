# pyetera_uart_bridge

# EteraUartBridge

The `EteraUartBridge` class is a Python class that provides an interface for communicating with an Etera UART bridge device. It allows you to control motors, relays, and retrieve sensor data and temperatures from the device.

```py
class EteraUartBridge:
    """
    Class representing an Etera UART bridge device.
    """

    class DeviceException(Exception):
        """
        Exception class for device-related errors.
        """
        pass

    def __init__(self, serial_port: str, on_device_message_handler: callable = print,  on_device_reset_handler: callable = None):
        """
        Initializes an instance of the EteraUartBridge class.

        Args:
            serial_port (str): The serial port to communicate with the device.
            on_device_message_handler (callable, optional): The handler for device messages. Defaults to print.
            on_device_reset_handler (callable, optional): The handler for device reset events. Defaults to None.
        """

    async def move_motor(self, motor_id: int, direction: EteraUartBridge.Direction, length_ms: int, override: bool = False) -> None:
        """
        Moves a motor connected to the expander board.

        Args:
            motor_id (int): The ID of the motor to move [0-3].
            direction (EteraUartBridge.Direction): The direction to move the motor.
            length_ms (int): The duration of the motor movement in milliseconds (duration is not limited).
            override (bool, optional): Whether to override any ongoing motor movement. Defaults to False.
        """

    async def set_relay(self, relay_id: int, state: bool) -> None:
        """
        Sets the state of a relay connected to the expander board. The state does not persist
        between resets and must be handled with `on_device_reset_handler`

        Args:
            relay_id (int): The ID of the relay to set [0-7].
            state (bool): The state to set the relay to (True for on, False for off).
        """

    async def get_sensors(self) -> list[bytes]:
        """
        Retrieves the sensor addresses connected to the expander board.

        Returns:
            list[bytes]: The sensor address as a list of bytes.
        """

    async def get_temperatures(self) -> list[float]:
        """
        Retrieves the temperatures from all connected sensors.

        Returns:
            list[float]: The temperatures as a list of floats, from sensors in the same order as addresses.
        """

    async def run_forever(self) -> None:
        """
        Runs the device communication indefinitely. Must be run in an asyncio task for the class to work properly.
        """

    def set_device_reset_handler(self, handler: callable) -> None:
        """
        Sets the handler for device reset events. It it called as soon as a device is reset, before it is ready again.

        Args:
            handler (callable): The handler function for device reset events. Can be async or non-async.
        """

    def set_device_message_handler(self, handler: callable) -> None:
        """
        Sets the handler for device messages incoming from the expander board.

        Args:
            handler (callable): The handler function for device messages. Can be async or non-async.
        """
```

## Device Communication

The `EteraUartBridge` class uses asynchronous communication to interact with the Etera UART bridge expander board. This allows for concurrent execution of multiple tasks, such as controlling motors, switching relays, and retrieving sensor data. The communication is handled internaly by the class by running the `run_forever` corutine.

To ensure proper communication with the device, it is important to call the `await etera.ready()` method before performing any operations. This method waits for the device to be ready and ensures that subsequent commands are executed successfully. Requesting any operation before the device is ready will raise an `DeviceException` exception. 

If the device cannot be reached, the `run_forever` method of the `EteraUartBridge` class will raise a `DeviceException`. This exception indicates that there was an error in the device communication and the device is not responding.

To handle this exception, you can wrap the `run_forever` method call in a try-except block and handle the exception accordingly. For example:

```py
try:
    await etera.run_forever()
except EteraUartBridge.DeviceException as e:
    print('Device communication error:', e)
```

By catching the `DeviceException`, you can handle the error gracefully and take appropriate actions, such as logging the error, retrying the communication, or terminating the program.

Remember to import the `EteraUartBridge` class from the appropriate module and replace `etera` with the instance of the `EteraUartBridge` class in your code.


## Motor Control

The `move_motor` method is used to control the motors connected to the expander board. It takes the motor ID, direction, duration, and an optional override parameter. The motor ID should be in the range of 0 to 3, representing the four available motors. The direction can be either `EteraUartBridge.Direction.CLOCKWISE` or `EteraUartBridge.Direction.COUNTER_CLOCKWISE`. The duration is specified in milliseconds.

## Relay Control

The `set_relay` method allows you to set the state of a relay connected to the expander board. The relay ID should be in the range of 0 to 7, representing the eight available relays. The state parameter can be either `True` for on or `False` for off.

Please note that the state of the relays does not persist between device resets. If you need to maintain the state across resets, you can use the `on_device_reset_handler` to handle device reset events and restore the desired relay states.

## Sensor Data and Temperatures

The `get_sensors` method retrieves the sensor addresses connected to the expander board. It returns a list of bytes representing the sensor addresses.

The `get_temperatures` method retrieves the temperatures from all connected sensors. It returns a list of floats representing the temperatures in the same order as the sensor addresses.

## Example Usage

The provided example code demonstrates how to use the `EteraUartBridge` class to control motors, switch relays, and retrieve temperature data. You can modify the example functions or create your own functions to suit your specific requirements.


Here is an example usage of the `EteraUartBridge` class:

Remember to replace `'/dev/ttyUSB1'` with the appropriate serial port for your device before running the code.
```py
from pyetera_uart_bridge import EteraUartBridge
import asyncio

async def main():
    etera = EteraUartBridge('/dev/ttyUSB1')

    async def etera_reset():
        print('Device just reset...')
        await etera.ready()
        print('Device is ready')

    etera.set_device_reset_handler(etera_reset)

    async def example_motors():
        direction = True
        await etera.ready()

        await etera.move_motor(0, EteraUartBridge.Direction.CLOCKWISE, 120 * 1000) # clockwise for 120 seconds

        while True:
            moves = []
            try:
                for i in range(4):
                    moves.append(etera.move_motor(i, EteraUartBridge.Direction.CLOCKWISE if direction else EteraUartBridge.Direction.COUNTER_CLOCKWISE, 1000))
                await asyncio.gather(*moves)
            except EteraUartBridge.DeviceException as e:
                print('Motor move error', e)
                await asyncio.sleep(1)
            finally:
                direction = not direction


    async def example_relays():
        state = True
        await etera.ready()

        while True:
            relays = []
            try:
                for i in range(8):
                    relays.append(etera.set_relay(i, state))
                await asyncio.gather(*relays)
            except EteraUartBridge.DeviceException as e:
                print('Relay switch error', e)
                await asyncio.sleep(1)
            finally:
                state = not state
                await asyncio.sleep(1)

    async def example_temp():
        await etera.ready()
        print(f'Sensors {await etera.get_sensors()}')
        while True:
            try:
                temps = await etera.get_temperatures()
                print(temps)
            except EteraUartBridge.DeviceException as e:
                print('Get temp error', e)
            finally:
                await asyncio.sleep(1)
            
    await asyncio.gather(
        example_motors(),
        example_relays(),
        example_temp(),
        etera.run_forever()
    )

asyncio.run(main())
```

In this example, we create an instance of the `EteraUartBridge` class, passing the serial port as a parameter. We also define some helper functions for handling device reset, controlling motors, relays, and retrieving temperature data.

The `example_motors` function demonstrates how to move motors in different directions. It uses the `move_motor` method of the `EteraUartBridge` class to control the motors. The `example_relays` function shows how to switch relays on and off using the `set_relay` method. The `example_temp` function retrieves sensor data and temperatures using the `get_sensors` and `get_temperatures` methods.

Finally, we use the `asyncio.gather` function to run all the example functions concurrently, along with the `run_forever` method of the `EteraUartBridge` class, which keeps the device communication running indefinitely.
