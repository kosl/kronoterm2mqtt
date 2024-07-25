from .MotorQueueCommand import MotorQueueCommand

class MotorQueue:
    _queue: list[MotorQueueCommand]

    def __init__(self):
        self._queue = []

    def add_command(self, direction: MotorQueueCommand.Direction, length: int):
        command = MotorQueueCommand(direction, length)
        self._queue.append(command)
        return command

    def peek_next_command(self):
        if self._queue:
            return self._queue[0]
        else:
            return None

    def get_next_command(self):
        if self._queue:
            return self._queue.pop(0)
        else:
            return None

    def is_empty(self):
        return len(self._queue) == 0
    
    def clear_queue(self):
        for command in self._queue:
            command.finished.set()
        self._queue = []

