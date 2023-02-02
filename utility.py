# Represents a process and thread safe counter stored in a message queue.
class MsgQueueCounter:
    # Msg queue must be opened prior to instanciation.
    # msg_type is the type of the message used to store the counter,
    # must be unused by other interactions with the queue
    def __init__(self, start_value, queue, msg_type):
        self.start_value = start_value
        self.msg_queue = queue
        self.msg_type = msg_type

        self.msg_queue.send(str(start_value).encode(), type=self.msg_type)

    # Increment counter by given amount and return its updated value.
    def increment(self, amount: int) -> int:
        current_value = int(self.msg_queue.receive(type=self.msg_type)[0].decode())
        updated_value = current_value + amount
        self.msg_queue.send(str(updated_value).encode(), type=self.msg_type)

        return updated_value

    def setValue(self, value: int):
        self.msg_queue.receive(type=self.msg_type)[0]
        self.msg_queue.send(str(value).encode(), type=self.msg_type)