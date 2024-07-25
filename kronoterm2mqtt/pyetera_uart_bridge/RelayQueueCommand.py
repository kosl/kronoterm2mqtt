import asyncio

class RelayQueueCommand:
    relay_id: int
    state: bool
    finished: asyncio.Event
    successful: bool

    def __init__(self, relay_id: int, state: bool):
        if relay_id < 0 or relay_id > 7:
            raise ValueError("Relay ID must be between 0 and 7.")
        self.relay_id = relay_id
        self.state = state
        self.finished = asyncio.Event()
        self.successful = False

    def to_bytes(self):
        return bytes([0b10100000 | (self.relay_id << 1) | self.state])