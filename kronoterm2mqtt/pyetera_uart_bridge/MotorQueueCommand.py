from enum import Enum
import asyncio
import ctypes


class MotorQueueCommand:
    class Direction(Enum):
        COUNTER_CLOCKWISE = 0
        CLOCKWISE = 1
    
    direction: Direction
    length: int
    started: bool
    finished: asyncio.Event
    successful = bool

    def __init__(self, direction: Direction, length: int):
        self.direction = direction
        if length > 65535:
            raise ValueError("Length exceeds maximum value of uint16_t.")
        self.length = length
        self.started = False
        self.finished = asyncio.Event()
        self.successful = False

    def to_bytes(self, motor_id: int):
        if motor_id > 3 or motor_id < 0:
            raise ValueError("Motor ID must be between 0 and 3.")
        return bytes([0b11000000 | (motor_id << 1) | self.direction.value]) + ctypes.c_uint16(self.length).value.to_bytes(2, 'little')