from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process, Semaphore, Event, Lock
from math import intm

HOMES_COUNT = 1
START_CONSUMPTION_RATE = 1.6
START_PRODUCTION_RATE = 1
TRADE_POLICY = "GIVE_ONLY" # or "SELL_ONLY" or "SELL_IF_NONE" ()

# Synchronization primitives
awaiting_takers = Event()
givers_advertisment = Event()
taker = Lock()
sync_event = Event()
lock = Lock()

# TODO LIST
# - replace the TRADE_POLICY strings with vars to avoid mistakes (?)
# - catch SIGINT to close msq queue
# - Handle the SIGINT error if it is stuck on semaphore or event (check docs) when simulation is stopped
# - If lock works inside MsgQueueCountdown, then put it inside
# - Make sure that no lock acquire/release is missing in MsgQueueCounter

KEY = 257
msg_queue = MessageQueue(KEY, flags=IPC_CREAT)

# weather hard-coded
temperature = 25 # °C
# ----------

# Represents an atomic countdown stored in a message queue.
class MsgQueueCounter:

    # lock = Lock()

    # Type of the message used to store the counter, must be unused by other interactions with the queue
    MSG_TYPE = 999999

    def __init__(self, start_value, queue):
        self.countdown = start_value
        self.start_value = start_value
        self.msg_queue = queue

        self.setValue(start_value)

    # Increment by given amount and returns its updated value.
    def increment(self, amount) -> int:
        #with self.lock:
        with lock:
            current_value = int(msg_queue.receive()[0].decode(), type=self.MSG_TYPE)
            updated_value = current_value + amount
            self.countdown = updated_value

        self.msg_queue.send(str(updated_value).encode(), type=self.MSG_TYPE)
        return updated_value

    def setValue(self, value):
        self.increment(value - self.countdown)

# Sync object
atomic_counter = MsgQueueCounter(HOMES_COUNT, msg_queue)

class Home(Process):

    def __init__(self, id : int, trade_policy : str):
        super().__init__()
        self.id = id
        self.consumption_rate = START_CONSUMPTION_RATE
        self.production_rate = START_PRODUCTION_RATE
        self.trade_policy = trade_policy

    # Allows for home to sync. Calling this each round ensures the ticks do not mix,
    # i.e. tick N (present) is not mixed with ticks N-1 (past) or N+1 (future).
    # The on_sync function will be called only once, just before releasing all processes.
    def sync_all_homes(on_sync = (lambda: None)):
        if atomic_counter.increment(1) == HOMES_COUNT:
            atomic_counter.setValue(0)
            on_sync()
            sync_event.set()

        sync_event.wait()

    def on_sync():
        # We assume that there will be no takers or givers by default
        givers_advertisment.set()
        awaiting_takers.set()

    def run(self):
        while True:
            self.sync_all_homes(self.on_sync)
            energy_delta = self.production_rate - self.consumption_rate

            if energy_delta > 0 and self.trade_policy == "GIVE_ONLY" or self.trade_policy == "SELL_IF_NONE":
                # GIVER
                givers_advertisment.clear() # Takers, if any, will be waiting for givers
            elif energy_delta < 0: # TAKER
                awaiting_takers.clear() # Givers, if any, will be waiting for takers

            self.sync_all_homes()

            # TAKER
            if energy_delta < 0:
                # Ask other homes for giveaway, wait for a reply, and if none, buy from market
                atomic_counter.increment(1)
                while True:
                    givers_advertisment.wait()
                    taker.acquire()

                    try:
                        # Using -HOMES_COUNT as msg type, and the convention of giving each home an id in the
                        # range [1,HOMES_COUNT], we can use the remaining types for other purposes
                        # (e.g. countdown), because we only retrieve messages which types are <= HOMES_COUNT.
                        surplus_advertisment, giver_id = msg_queue.receive(type=-HOMES_COUNT, block=False)
                        print(self.id, "received energy from home", giver_id)
                    except BusyError:
                        # All surplus advertisments were taken homes, buy on market
                        # TODO: Market transaction (always)
                        break
                    surplus = float(surplus_advertisment.decode())
                    energy_received = min(surplus, -energy_delta) # energy_delta is < 0
                    remaining_energy = surplus - energy_received

                    # Put back in the msg queue only if the 'packet' still contains energy
                    if remaining_energy > 0:
                        # Surplus from other home was enough to meed need of energy.
                        msg_queue.send(str(remaining_energy).encode(),type=giver_id)
                        break
                    else:
                        energy_delta += energy_received
                         # Surplus from other home was insufficient, check for another one
                        continue
                if atomic_counter.increment(-1) == 0:
                    awaiting_takers.set()

                taker.release()

            if energy_delta > 0:

                if self.trade_policy == "GIVE_ONLY":
                    surplus_advertisment = f"{energy_delta}"
                    msg_queue.send(surplus_advertisment.encode(), type=self.id)

                    givers_advertisment.set()
                    awaiting_takers.wait()
                    try:
                        remaining_energy = float(msg_queue.receive(type=self.id, block=False)[0].decode())
                    except BusyError:
                        # All surplus was taken by needy homes, end of the day
                        break
                    # TODO: If SELL_IF_NONE, sell on market the remaining energy that was not taken by needy homes
                elif self.trade_policy == "SELL_ONLY":
                    pass
                else: # SELL_IF_NONE
                    pass # check in mq for 'in need' request. If none, sell immediately

            print(f"Energy remaining: {self.energy:.2f}")

if __name__ == "__main__":
    timestamp = 0

    homes = [Home(id=(i+1)) for i in range(HOMES_COUNT)]
    for h in homes:
        h.start()
    print("~~", timestamp, "~~")