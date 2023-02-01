from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process, Event, Lock, current_process, Semaphore
from random import randrange, random
import socket
from utility import MsgQueueCounter
from market import MARKET_HOST, MARKET_PORT
from weather import temperature

HOMES_COUNT = 5
MIN_CONSUMPTION_RATE = 1
MIN_PRODUCTION_RATE = 1
MAX_CONSUMPTION_RATE = 3
MAX_PRODUCTION_RATE = 3

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

KEY = 257
msg_queue = MessageQueue(KEY, flags=IPC_CREAT)


class Home(Process):

    # Synchronization primitives
    awaiting_takers = Event()
    givers_advertisment = Event()
    taker = Lock()
    tick_start = Semaphore(0)
    tick_end = Semaphore(0)
    entry_gate = Event()
    exit_gate = Event()
    
    # Sync objects
    sync_counter = MsgQueueCounter(0, msg_queue, 1000)
    giver_counter = MsgQueueCounter(0, msg_queue, 1001)
    taker_counter = MsgQueueCounter(0, msg_queue, 1002)

    def __init__(self, id: int, trade_policy: str, consumption: float, production: float):
        super().__init__()
        self.id = id
        self.avg_consumption = consumption
        self.production_rate = production
        self.trade_policy = trade_policy
    
    def market_transaction(self, type: str, energy_amount: int):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as home_socket:
            home_socket.connect((MARKET_HOST, MARKET_PORT))
            home_socket.sendall((f"{type} {energy_amount}").encode())

    # Allows for homes to sync. Calling this each round ensures the ticks do not mix,
    # i.e. tick N (present) is not mixed with ticks N-1 (past) or N+1 (future).
    # The callback will be called only once, just before releasing all home processes.
    @classmethod
    def sync_all_homes(cls, on_sync_callback = (lambda: None), *args):
        Home.entry_gate.wait()
        if Home.sync_counter.increment(1) == HOMES_COUNT:
            Home.entry_gate.clear()
            on_sync_callback(*args)
            Home.exit_gate.set()

        Home.exit_gate.wait()

        if Home.sync_counter.increment(-1) == 0:
            Home.exit_gate.clear()
            Home.entry_gate.set()

    @classmethod
    def on_tick_sync(cls):
        Home.tick_end.release()
        Home.tick_start.acquire()

        # We assume that there will be no takers or givers by default
        Home.givers_advertisment.set()
        Home.awaiting_takers.set()

    def run(self):
        while True:
            Home.sync_all_homes(Home.on_tick_sync)

            self.consumption_rate = self.avg_consumption + (1/temperature.value)
            energy_delta = self.production_rate - self.consumption_rate
            print(f"{self.id}: Delta(E)= {energy_delta:.2f} [{self.trade_policy}]")

            if energy_delta > 0 and self.trade_policy != Policy.SELL_ONLY:
                # GIVER
                Home.giver_counter.increment(1)
                Home.givers_advertisment.clear() # Takers, if any, will be waiting for givers
            elif energy_delta < 0: # TAKER
                Home.awaiting_takers.clear() # Givers, if any, will be waiting for takers

            Home.sync_all_homes()

            # TAKER
            if energy_delta < 0:
                Home.taker_counter.increment(1)
                Home.taker.acquire()
                while True:
                    Home.givers_advertisment.wait()

                    try:
                        # Using -HOMES_COUNT as msg type, and the convention of giving each home an id in the
                        # range [1,HOMES_COUNT], we can use the remaining types for other purposes
                        # (e.g. countdown), because we only retrieve messages which types are <= HOMES_COUNT.
                        surplus_advertisment, giver_id = msg_queue.receive(type=-HOMES_COUNT, block=False)
                    except BusyError:
                        # All surplus advertisments were taken homes
                        self.market_transaction("BUY", -energy_delta)
                        break
                    surplus = float(surplus_advertisment.decode())
                    energy_received = min(surplus, -energy_delta)
                    remaining_energy = surplus - energy_received

                    # Put back in the msg queue only if the 'packet' still contains energy
                    if remaining_energy > 0:
                        # Surplus from giver home was enough to meed energy needs.
                        msg_queue.send(str(remaining_energy).encode(),type=giver_id)
                        break
                    else:
                        energy_delta += energy_received
                         # Surplus from other home was insufficient, check for another one
                        continue
                Home.taker.release()
                if Home.taker_counter.increment(-1) == 0:
                    Home.awaiting_takers.set()

            elif energy_delta > 0:
                if self.trade_policy == Policy.SELL_ONLY:
                    self.market_transaction("SELL", energy_delta)
                else:
                    # GIVER
                    surplus_advertisment = f"{energy_delta}"
                    msg_queue.send(surplus_advertisment.encode(), type=self.id)

                    if Home.giver_counter.increment(-1) == 0:
                        Home.givers_advertisment.set()

                    Home.awaiting_takers.wait()
                    try:
                        remaining_energy = float(msg_queue.receive(type=self.id, block=False)[0].decode())

                        if self.trade_policy == Policy.SELL_IF_NONE:
                            self.market_transaction("SELL", remaining_energy)

                    except BusyError:
                        # All surplus was taken by needy homes, end of the tick
                        pass