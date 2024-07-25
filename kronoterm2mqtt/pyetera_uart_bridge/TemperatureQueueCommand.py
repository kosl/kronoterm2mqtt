import asyncio

class TemperatureQueueCommand:
    temperatures: list[float]
    finished: asyncio.Event
    successful: bool

    def __init__(self):
        self.temperatures = []
        self.finished = asyncio.Event()
        self.successful = False

    def to_bytes(self):
        return b't'