from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process, Event, Lock, current_process
import time
import signal
from random import randrange, random

HOMES_COUNT = 5
MIN_CONSUMPTION_RATE = 1
MIN_PRODUCTION_RATE = 1
MAX_CONSUMPTION_RATE = 3
MAX_PRODUCTION_RATE = 3

class Policy:
    GIVE_ONLY = "GIVE_ONLY"
    SELL_ONLY = "SELL_ONLY"
    SELL_IF_NONE = "SELL_IF_NONE"

    names = [GIVE_ONLY, SELL_ONLY, SELL_IF_NONE]

    @classmethod
    def getRandom(cls) -> str:
        return cls.names[randrange(0, len(cls.names))]

    def __init__(self):
        raise Exception("Policy objects cannot be instanciated.")

# Synchronization primitives
awaiting_takers = Event()
givers_advertisment = Event()
taker = Lock()
sync_event = Event()
next_tick = Event()

# TODO LIST
# - replace the TRADE_POLICY strings with vars to avoid mistakes (?)
# - catch SIGINT to close msq queue
# - Handle the SIGINT error if it is stuck on semaphore or event (check docs) when simulation is stopped
# - Make sure that no lock acquire/release is missing in MsgQueueCounter
# - Sell on market the remaining energy that was not taken by needy homes in SELL_IF_NONE policy

KEY = 257
msg_queue = MessageQueue(KEY, flags=IPC_CREAT)

timestamp = 0

# weather hard-coded
temperature = 25 # °C
# ----------

############
# FUNCTIONS#------------------------------------------------------------
############

def rand_range(start: float, end: float) -> float:
    return start + random() * (end-start)

def handle_interrupt(*args):
    for h in homes:
        h.terminate()
    msg_queue.remove()
    print("-----------------END OF SIMULATION--------------------")
    exit(0)

# Allows for home to sync. Calling this each round ensures the ticks do not mix,
# i.e. tick N (present) is not mixed with ticks N-1 (past) or N+1 (future).
# The on_sync function will be called only once, just before releasing all processes.
def sync_all_homes(on_sync = (lambda: None)):
    if atomic_counter.increment(1) == HOMES_COUNT:
        atomic_counter.setValue(0)
        on_sync()
        sync_event.set()
    else:
        sync_event.wait()
    sync_event.clear()

def on_tick_end():
    next_tick.set()
    # We assume that there will be no takers or givers by default
    givers_advertisment.set()
    awaiting_takers.set()

    time.sleep(1)

#---------------------------------------------------------------------

# Represents an atomic countdown stored in a message queue.
class MsgQueueCounter:

    # Type of the message used to store the counter, must be unused by other interactions with the queue
    MSG_TYPE = 999

    # Msg queue must be opened prior to instanciation
    def __init__(self, start_value, queue):
        self.value = start_value
        self.start_value = start_value
        self.msg_queue = queue

        self.msg_queue.send(str(start_value).encode(), type=self.MSG_TYPE)

    # Increment counter by given amount and return its updated value.
    def increment(self, amount, do_print=False) -> int:
        current_value = int(msg_queue.receive(type=self.MSG_TYPE)[0].decode())

        if do_print:
            print("Counter value:", current_value)
        updated_value = current_value + amount
        self.value = updated_value
        self.msg_queue.send(str(updated_value).encode(), type=self.MSG_TYPE)
        if do_print:
            print("Updated counter val:", updated_value)
        return updated_value

    def setValue(self, value):
        self.increment(value - self.value)

# Sync objects
atomic_counter = MsgQueueCounter(0, msg_queue)

class Home(Process):
    
    # timestamp = 0 # Move it in parent process

    def __init__(self, id: int, trade_policy: str, consumption_rate, production_rate):
        super().__init__()
        self.id = id
        self.consumption_rate = consumption_rate
        self.production_rate = production_rate
        self.trade_policy = trade_policy

    def run(self):
        while True:
            energy_delta = self.production_rate - self.consumption_rate
            print(current_process().name + ":", f"D(E)= {energy_delta:.2f}", "[" + self.trade_policy + "]")

            if energy_delta > 0 and (self.trade_policy == Policy.GIVE_ONLY or \
                    self.trade_policy == Policy.SELL_IF_NONE):
                # GIVER
                givers_advertisment.clear() # Takers, if any, will be waiting for givers
            elif energy_delta < 0: # TAKER
                awaiting_takers.clear() # Givers, if any, will be waiting for takers

            sync_all_homes()

            # TAKER
            if energy_delta < 0:
                # Ask other homes for giveaway, wait for a reply, and if none, buy from market
                c_b = atomic_counter.increment(1,True)
                print(current_process().name, "enters loop, counter to", c_b)
                taker.acquire()
                while True:
                    givers_advertisment.wait()

                    try:
                        # Using -HOMES_COUNT as msg type, and the convention of giving each home an id in the
                        # range [1,HOMES_COUNT], we can use the remaining types for other purposes
                        # (e.g. countdown), because we only retrieve messages which types are <= HOMES_COUNT.
                        surplus_advertisment, giver_id = msg_queue.receive(type=-HOMES_COUNT, block=False)
                        print(self.id, "received energy from home", giver_id)
                    except BusyError:
                        # All surplus advertisments were taken homes, buy on market
                        # TODO: Market transaction (always)
                        print(current_process().name, "buys from market")
                        break
                    surplus = float(surplus_advertisment.decode())
                    energy_received = min(surplus, -energy_delta) # energy_delta is negative
                    remaining_energy = surplus - energy_received
                    print(f"\n Giver-{giver_id} now has", remaining_energy)

                    # Put back in the msg queue only if the 'packet' still contains energy
                    if remaining_energy > 0:
                        print("Putting back in queue: ", remaining_energy, f"from Giver-{giver_id}")
                        # Surplus from other home was enough to meed need of energy.
                        msg_queue.send(str(remaining_energy).encode(),type=giver_id)
                        break
                    else:
                        energy_delta += energy_received
                         # Surplus from other home was insufficient, check for another one
                        continue
                
                c = atomic_counter.increment(-1,True)
                print(current_process().name, "leaves loop, updated counter to", c)
                if c == 0:
                    awaiting_takers.set()

                taker.release()

            if energy_delta > 0:

                if self.trade_policy == Policy.SELL_ONLY:
                    # TODO: market transaction
                    print(current_process().name, "sells on market")
                else:
                    surplus_advertisment = f"{energy_delta}"
                    msg_queue.send(surplus_advertisment.encode(), type=self.id)

                    givers_advertisment.set()
                    print(current_process().name, "awaiting takers")
                    awaiting_takers.wait()
                    print(current_process().name, "passed barrier")
                    try:
                        remaining_energy = float(msg_queue.receive(type=self.id, block=False)[0].decode())

                        # TODO: Sell on market the remaining energy that was not taken by needy homes
                        if self.trade_policy == Policy.SELL_IF_NONE:
                            print(current_process().name, "sells on market")

                    except BusyError:
                        # All surplus was taken by needy homes, end of the day
                        print(current_process().name, ": all surplus given")
                        pass

            print(current_process().name, "reached sync point.")
            sync_all_homes(on_tick_end)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_interrupt)

    givers_advertisment.set()
    awaiting_takers.set()


    homes = []
    for i in range(HOMES_COUNT):
        production_rate = rand_range(MIN_PRODUCTION_RATE, MAX_PRODUCTION_RATE)
        consumption_rate = rand_range(MIN_CONSUMPTION_RATE, MAX_CONSUMPTION_RATE)

        home_process = Home((i+1), Policy.getRandom(), production_rate, consumption_rate)
        homes.append(home_process)
        home_process.start()

    while True:
        next_tick.wait()
        next_tick.clear()

        print("~~", timestamp, "~~")
        timestamp += 1

    # for h in homes:
    #     h.join()
    # msg_queue.remove()