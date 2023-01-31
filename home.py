from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process, Event, Lock, current_process
import time
import signal
from random import randrange, random
import socket

HOMES_COUNT = 5
MIN_CONSUMPTION_RATE = 1
MIN_PRODUCTION_RATE = 1
MAX_CONSUMPTION_RATE = 3
MAX_PRODUCTION_RATE = 3

LOCALHOST = "localhost"
MARKET_PORT = 9000

# Enum-like class
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
# - Handle the SIGINT error if it is stuck on semaphore or event (check docs) when simulation is stopped
# - Sell on market the remaining energy that was not taken by needy homes in SELL_IF_NONE policy
# - Remove next_tick event if only used by parent process and replace in on_tick_start callback.
# well actually it's not that bad to put tick updates with other processes in parent process...
# - Clean file from debug print
# - Move all home-related only variables to Home class

KEY = 257
msg_queue = MessageQueue(KEY, flags=IPC_CREAT)

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
    tick_socket.close()
    
    print("\n-----------------END OF SIMULATION--------------------")
    exit(0)

# Allows for home to sync. Calling this each round ensures the ticks do not mix,
# i.e. tick N (present) is not mixed with ticks N-1 (past) or N+1 (future).
# The on_sync function will be called only once, just before releasing all processes.
def sync_all_homes(on_sync_callback = (lambda: None), *args):
    if atomic_counter.increment(1) == HOMES_COUNT:
        atomic_counter.setValue(0)
        on_sync_callback(*args)
        sync_event.set()
    else:
        sync_event.wait()
    sync_event.clear()

def on_tick_start():
    # We assume that there will be no takers or givers by default
    givers_advertisment.set()
    awaiting_takers.set()

    time.sleep(1)
    next_tick.set()

#---------------------------------------------------------------------

# Represents an atomic countdown stored in a message queue.
class MsgQueueCounter:

    # Msg queue must be opened prior to instanciation
    # Type of the message used to store the counter, must be unused by other interactions with the queue
    def __init__(self, start_value, queue, msg_type):
        self.value = start_value
        self.start_value = start_value
        self.msg_queue = queue
        self.msg_type = msg_type

        self.msg_queue.send(str(start_value).encode(), type=self.msg_type)

    # Increment counter by given amount and return its updated value.
    def increment(self, amount, do_print=False) -> int:
        current_value = int(msg_queue.receive(type=self.msg_type)[0].decode())

        if do_print:
            print("Counter value:", current_value)
        updated_value = current_value + amount
        self.value = updated_value
        self.msg_queue.send(str(updated_value).encode(), type=self.msg_type)
        if do_print:
            print("Updated counter val:", updated_value)
        return updated_value

    def setValue(self, value):
        self.increment(value - self.value)

# Sync objects
atomic_counter = MsgQueueCounter(0, msg_queue, 1000)
giver_counter = MsgQueueCounter(0, msg_queue, 1001)
taker_counter = MsgQueueCounter(0, msg_queue, 1002)

class Home(Process):
    

    def __init__(self, id: int, trade_policy: str, consumption, production, home_socket):
        super().__init__()
        self.id = id
        self.consumption_rate = consumption
        self.production_rate = production
        self.trade_policy = trade_policy
        self.socket = home_socket

    def market_transaction(self, type: str, energy_amount: int):
        with self.socket:
            self.socket.connect((LOCALHOST, MARKET_PORT))
            self.market_transaction.sendall((f"{type} {energy_amount}").encode())

    def run(self):
        while True:
            sync_all_homes(on_tick_start)

            energy_delta = self.production_rate - self.consumption_rate
            print(current_process().name + ":", f"D(E)= {energy_delta:.2f}", "[" + self.trade_policy + "]")

            if energy_delta > 0 and (self.trade_policy == Policy.GIVE_ONLY or \
                    self.trade_policy == Policy.SELL_IF_NONE):
                # GIVER
                giver_counter.increment(1)
                givers_advertisment.clear() # Takers, if any, will be waiting for givers
            elif energy_delta < 0: # TAKER
                awaiting_takers.clear() # Givers, if any, will be waiting for takers

            sync_all_homes()

            # TAKER
            if energy_delta < 0:
                # Ask other homes for giveaway, wait for a reply, and if none, buy from market
                taker_counter.increment(1)
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
                        print(current_process().name, "initiates buy from market")
                        # self.market_transaction("BUY", -energy_delta)
                        break
                    surplus = float(surplus_advertisment.decode())
                    energy_received = min(surplus, -energy_delta) # energy_delta is negative
                    remaining_energy = surplus - energy_received
                    # print(f"\n Giver-{giver_id} now has", remaining_energy)

                    # Put back in the msg queue only if the 'packet' still contains energy
                    if remaining_energy > 0:
                        # print("Putting back in queue: ", remaining_energy, f"from Giver-{giver_id}")
                        # Surplus from other home was enough to meed need of energy.
                        msg_queue.send(str(remaining_energy).encode(),type=giver_id)
                        break
                    else:
                        energy_delta += energy_received
                         # Surplus from other home was insufficient, check for another one
                        continue
                taker.release()
                if taker_counter.increment(-1) == 0:
                    awaiting_takers.set()


            if energy_delta > 0:

                if self.trade_policy == Policy.SELL_ONLY:
                    # TODO: market transaction
                    print(current_process().name, "initiate sell on market")
                    # self.market_transaction("SELL", -energy_delta)
                else:
                    surplus_advertisment = f"{energy_delta}"
                    msg_queue.send(surplus_advertisment.encode(), type=self.id)

                    if giver_counter.increment(-1) == 0:
                        givers_advertisment.set()

                    awaiting_takers.wait()
                    try:
                        remaining_energy = float(msg_queue.receive(type=self.id, block=False)[0].decode())

                        # TODO: Sell on market the remaining energy that was not taken by needy homes
                        if self.trade_policy == Policy.SELL_IF_NONE:
                            print(current_process().name, "sells on market")

                    except BusyError:
                        # All surplus was taken by needy homes, end of the day
                        print(current_process().name, ": all surplus given")
                        pass

            # print(current_process().name, "reached sync point.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_interrupt)

    # givers_advertisment.set()
    # awaiting_takers.set()

    tick_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tick_socket.connect((LOCALHOST, MARKET_PORT))
    print("Tick connection established")

    homes = []
    for i in range(HOMES_COUNT):
        production_rate = rand_range(MIN_PRODUCTION_RATE, MAX_PRODUCTION_RATE)
        consumption_rate = rand_range(MIN_CONSUMPTION_RATE, MAX_CONSUMPTION_RATE)
        home_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        home_process = Home((i+1), Policy.getRandom(), production_rate, consumption_rate, home_socket)
        homes.append(home_process)
        home_process.start()

    timestamp = 0
    tick_notif = "NEXT_TICK".encode()
    while True:
        next_tick.wait()
        next_tick.clear()

        tick_socket.sendall(tick_notif)

        timestamp += 1
        print("~~ homes:", timestamp, "~~")

    # for h in homes:
    #     h.join()
    # msg_queue.remove()