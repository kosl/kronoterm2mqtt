import serial
import asyncio
from enum import Enum
import ctypes

from .MotorQueue import MotorQueue
from .MotorQueueCommand import MotorQueueCommand
from .RelayQueue import RelayQueue
from .TemperatureQueue import TemperatureQueue
import inspect


class EteraUartBridge:
    _s: serial.Serial

    _motor_queue: list[MotorQueue]
    _motor_queue_lock: list[asyncio.Lock]

    _relay_queue: RelayQueue
    _relay_queue_lock: asyncio.Lock

    _temperature_queue: TemperatureQueue
    _temperature_queue_lock: asyncio.Lock

    Direction = MotorQueueCommand.Direction

    class DeviceException(Exception):
        pass

    class _ParseState(Enum):
        WAIT_READY = 0
        DEVICE_RESET = 1
        IDLE = 2
        READ_ASCII = 3

    _parse_state: _ParseState
    _before_read_state: _ParseState
    _current_read: bytes
    _command_read_buffer: bytes
    _running: bool
    _device_ready: asyncio.Event

    _temp_sensors: list[bytes]
    _temp_sensors_lock: asyncio.Lock

    _on_device_message_handler: callable
    _on_device_reset_handler: callable

    def __init__(self, serial_port: str, on_device_message_handler: callable = print,  on_device_reset_handler: callable = None):
        self._s = serial.Serial(port=serial_port, baudrate=115200, timeout=0.5)

        self._motor_queue = [MotorQueue() for _ in range(4)]
        self._motor_queue_lock = [asyncio.Lock() for _ in range(4)]

        self._relay_queue = RelayQueue()
        self._relay_queue_lock = asyncio.Lock()

        self._temperature_queue = TemperatureQueue()
        self._temperature_queue_lock = asyncio.Lock()

        self._parse_state = self._ParseState.WAIT_READY
        self._before_read_state = self._parse_state
        self._current_read = b''
        self._command_read_buffer = b''
        self._running = False
        self._device_ready = asyncio.Event()

        self._temp_sensors = []
        self._temp_sensors_lock = asyncio.Lock()

        self.set_device_message_handler(on_device_message_handler)
        self.set_device_reset_handler(on_device_reset_handler)

    async def ready(self):
        await self._device_ready.wait()

    async def move_motor(self, motor_id: int, direction: MotorQueueCommand.Direction, length_ms: int, override: bool = False):
        if motor_id > 3 or motor_id < 0:
            raise ValueError("Motor ID must be between 0 and 3.")
        
        if length_ms < 0:
            raise ValueError("Length must be non-negative.")

        if not self._device_ready.is_set():
            raise self.DeviceException("Device is not ready.")

        move_commands = []

        async with self._motor_queue_lock[motor_id]:
            if override:
                self._motor_queue[motor_id].clear_queue()

            while length_ms > 65535:
                move_commands.append(self._motor_queue[motor_id].add_command(direction, 65535))
                length_ms -= 65535
                    
            if length_ms > 0:
                move_commands.append(self._motor_queue[motor_id].add_command(direction, length_ms))

        for i, command in enumerate(move_commands):
            await command.finished.wait()
            if not command.successful:
                raise self.DeviceException(f"Failed to fully move motor (seq. {i}/{len(move_commands)}).")

    async def set_relay(self, relay_id: int, state: bool):
        if relay_id > 7 or relay_id < 0:
            raise ValueError("Relay ID must be between 0 and 7.")
        
        if not self._device_ready.is_set():
            raise self.DeviceException("Device is not ready.")

        async with self._relay_queue_lock:
            command = self._relay_queue.add_command(relay_id, state)
        
        await command.finished.wait()
        if not command.successful:
            raise self.DeviceException("Failed to switch relay.")

    async def get_sensors(self):
        if not self._device_ready.is_set():
            raise self.DeviceException("Device is not ready.")
        
        async with self._temp_sensors_lock:
            return [a[:] for a in self._temp_sensors]

    async def get_temperatures(self):
        if not self._device_ready.is_set():
            raise self.DeviceException("Device is not ready.")
        
        async with self._temperature_queue_lock:
            command = self._temperature_queue.add_command()

        await command.finished.wait()
        if not command.successful:
            raise self.DeviceException("Failed to get temperature.")
        return command.temperatures

    async def run_forever(self):
        if self._running:
            raise self.DeviceException(f"EteraUartBridge is already running on {self._s.port}")

        self._running = True

        while True:
            if self._s.in_waiting != 0 or len(self._command_read_buffer) != 0:
                c = None
                if len(self._command_read_buffer) > 0:
                    c = self._command_read_buffer[0:1]
                    self._command_read_buffer = self._command_read_buffer[1:]
                else:
                    c = self._s.read(1)
                                
                match c:
                    # Device ready!
                    case b'\xE0':
                        if self._parse_state not in [self._ParseState.WAIT_READY, self._ParseState.DEVICE_RESET] and \
                            self._on_device_reset_handler is not None:
                            asyncio.create_task(self._on_device_reset_handler())
                        await self._init()
                    case b'\xE1':
                        self._device_message(f'Device reset unexpectedly in state {self._parse_state}'.encode())
                        await self._reset_device()
                    # Start of ASCII message
                    case b'\xEA':
                        if self._current_read != b'':
                            self._device_message(self._current_read)
                        self._current_read = b''
                        self._before_read_state = self._parse_state
                        self._parse_state = self._ParseState.READ_ASCII
                    # End of ASCII message
                    case b'\xEB':
                        if self._parse_state != self._ParseState.READ_ASCII:
                            self._device_message(f'Device reached end of ASCII message in state {self._parse_state} and will try to reset'.encode())
                            await self._reset_device()
                        self._parse_state = self._before_read_state
                        self._device_message(self._current_read)
                        self._current_read = b''
                    # Other
                    case _:
                        if self._parse_state == self._ParseState.READ_ASCII:
                            self._current_read += c
                        else:
                            # Stop moving motor
                            if c[0] & 0b11111000 == 0b11010000:
                                motor_id = c[0] & 0b0000011
                                async with self._motor_queue_lock[motor_id]:
                                    command = self._motor_queue[motor_id].get_next_command()
                                    if command is not None:
                                        command.finished.set()
                            else:
                                self._device_message(f'Device reached unknown input `{c}` in state {self._parse_state} and will try to reset'.encode())
                                await self._reset_device()

            if self._parse_state == self._ParseState.IDLE:
                # Process motor queue
                for i in range(4):
                    async with self._motor_queue_lock[i]:
                        if not self._motor_queue[i].is_empty():
                            command = self._motor_queue[i].peek_next_command()
                            if not command.started:
                                command.started = True
                                cmd_bytes = command.to_bytes(i)
                                command.successful = self._send_command(cmd_bytes)
                                if not command.successful:
                                    command.finished.set()
                            
                # Process relay queue
                async with self._relay_queue_lock:
                    if not self._relay_queue.is_empty():
                        command = self._relay_queue.get_next_command()
                        cmd_bytes = command.to_bytes()
                        command.successful = self._send_command(cmd_bytes)
                        command.finished.set()

                # Process temperature queue
                async with self._temperature_queue_lock:
                    if not self._temperature_queue.is_empty():
                        command = self._temperature_queue.get_next_command()
                        cmd_bytes = command.to_bytes()
                        command.successful = self._send_command(cmd_bytes)
                        async with self._temp_sensors_lock:
                            for _ in range(len(self._temp_sensors)):
                                c = self._s.read(2)
                                if len(c) != 2:
                                    command.successful = False
                                    break
                                command.temperatures.append(ctypes.c_int16.from_buffer_copy(c).value / 16)

                        command.finished.set()

            await asyncio.sleep(0.05)

    def set_device_reset_handler(self, handler: callable):
        if inspect.iscoroutinefunction(handler) or handler is None:
            self._on_device_reset_handler = handler
        else:
            async def async_handler():
                handler()
            self._on_device_reset_handler = async_handler

    def set_device_message_handler(self, handler: callable):
        if inspect.iscoroutinefunction(handler) or handler is None:
            self._on_device_message_handler = handler
        else:
            async def async_handler(message):
                handler(message)
            self._on_device_message_handler = async_handler

    async def _init(self):
        self._device_ready.clear()

        if not self._send_command(b'c'):
            raise self.DeviceException('Failed to send get temperature count command')
        c = self._s.read(1)
        if len(c) != 1:
            raise self.DeviceException('Failed to get temperature count')

        temp_sensor_count = ctypes.c_uint8.from_buffer_copy(c).value

        if not self._send_command(b'a'):
            raise self.DeviceException('Failed to send get temperature sensors command')
        async with self._temp_sensors_lock:
            self._temp_sensors.clear()
            for _ in range(temp_sensor_count):
                c = self._s.read(8)
                if len(c) != 8:
                    raise self.DeviceException('Failed to get temperature sensors')
                self._temp_sensors.append(c)

        self._parse_state = self._ParseState.IDLE
        self._device_ready.set()

        
    async def _reset_device(self):
        self._device_ready.clear()
        if self._parse_state != self._ParseState.WAIT_READY and self._on_device_reset_handler is not None:
            asyncio.create_task(self._on_device_reset_handler())
        self._command_read_buffer = b''
        self._parse_state = self._ParseState.DEVICE_RESET
        self._s.close()
        for i in range(4):
            async with self._motor_queue_lock[i]:
                self._motor_queue[i].clear_queue()
        async with self._relay_queue_lock:
            self._relay_queue.clear_queue()
        async with self._temperature_queue_lock:
            self._temperature_queue.clear_queue()
        self._s = serial.Serial(port=self._s.port, baudrate=self._s.baudrate, timeout=self._s.timeout)


    def _send_command(self, command: bytes, expected_byte: bytes | None = None):
        if expected_byte is None:
            expected_byte = command[0:1]
        for retries in range(3):
            self._s.write(command)
            # print(f"Sending command {command}")
            if self._confirm_command(expected_byte):
                # print(f"Command {command} successful")
                return True
        # print(f"Command {command} failed")
        return False

    def _confirm_command(self, expected_byte: bytes):
        assert(len(expected_byte) == 1)
        while True:
            c = self._s.read(1)

            if len(c) == 0:
                return False

            if c == expected_byte:
                return True
            else:
                self._command_read_buffer += c

    def _device_message(self, message: bytes):
        if self._on_device_message_handler is not None:
            asyncio.create_task(self._on_device_message_handler(message))

