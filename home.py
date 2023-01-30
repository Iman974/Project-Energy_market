import os
from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process, Semaphore, Event, Lock
from time import sleep

HOMES_COUNT = 1
START_CONSUMPTION_RATE = 1.6
START_PRODUCTION_RATE = 1
TRADE_POLICY = "GIVE_ONLY" # or "SELL_ONLY" or "SELL_IF_NONE" ()
START_ENERGY = 5

# Synchronization primitives
awaiting_taker_response = Event()
home_counter = Semaphore(0)
givers_advertisment = Event()
taker = Lock()
gate1 = Event()
gate2 = Event()
gate3 = Event()

# TODO LIST
# - replace the TRADE_POLICY strings with vars to avoid mistakes (?)
# - catch SIGINT to close msq queue

KEY = 532
msg_queue = MessageQueue(KEY, flags=IPC_CREAT)

# weather hard-coded
temperature = 25 # °C
# ----------


class Home(Process):

    def __init__(self, id : int, trade_policy : str) -> None:
        super().__init__()
        self.id = id
        self.consumption_rate = START_CONSUMPTION_RATE
        self.production_rate = START_PRODUCTION_RATE
        self.trade_policy = trade_policy

    # Allows for home sync. Calling this each round ensures the ticks do not mix,
    # i.e. tick N (present) is not mixed with ticks N-1 (past) or N+1 (future)
    def sync_for_next_tick(inter_gate_operation = (lambda: None)):
        home_counter.release()
        gate1.wait()
        inter_gate_operation()
        home_counter.release()
        gate2.wait()    

    def on_sync():
        givers_advertisment.set()
        awaiting_taker_response.set()

    def run(self) -> None:
        while True:
            self.sync_for_next_tick(self.on_sync)
            energy_delta = self.production_rate - self.consumption_rate

            if energy_delta > 0 and self.trade_policy == "GIVE_ONLY" or self.trade_policy == "SELL_IF_NONE":
                # GIVER
                givers_advertisment.clear() # indicates to the takers the presence of givers
            elif energy_delta < 0:
                awaiting_taker_response.clear() # indicates to the givers the presence of takers
                # home_counter.release()
                # start_sync.wait() # wait for every home to get there

            gate3.clear()
            home_counter.release()
            gate3.wait()

            # TAKER
            if energy_delta < 0:
                # Ask other homes for giveaway, wait for a reply, and if none, buy from market
                while True:
                    givers_advertisment.wait()
                    taker.acquire()
                    if msg_queue.current_messages == 0: # if atomic, then takers lock is not needed
                        # All surplus advertisments were taken homes, buy on market
                        # No home with surplus remaining this round, need to buy from market
                        # TODO: Market transaction (always)
                        taker.release()
                        break

                    surplus_advertisment, giver_id = msg_queue.receive()
                    surplus = float(surplus_advertisment.decode())
                    energy_received = min(surplus, -energy_delta) # energy_delta is < 0
                    remaining_energy = surplus - energy_received

                    if remaining_energy > 0: # Don't put in the msg_queue empty packets of energy
                        msg_queue.send(str(remaining_energy).encode(),type=giver_id)
                    taker.release()
                    energy_delta += energy_received
                    print(self.id, "received energy from home", giver_id)
                    if energy_delta >= 0:
                        # Surplus from other home was more than enough for energy need.
                        break
                    else:
                        # Surplus from other home was insufficient, check for another one
                        pass
                # Doing this will prevent houses which resolved their DeltaE < 0 to reach the end of the while,
                # where other homes meet
                # continue

            if energy_delta > 0:

                if self.trade_policy == "GIVE_ONLY":
                    surplus_advertisment = f"{energy_delta}"
                    msg_queue.send(surplus_advertisment.encode(), type=self.id)

                    givers_advertisment.set()
                    awaiting_taker_response.wait()
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

                # Doing this will prevent houses which resolved their DeltaE > 0 to reach the end
                # of the while,where other homes meet (might want to do this with givers only),
                # thus prevent a giver to increase/release the home_counter
                continue

            if energy_delta == 0:
                # This home has either sold surplus energy to the market (SELL_ONLY or SELL_IF_NO_TAKERS when
                # no needy homes are remaining) or just had energy_delta == 0 from start, or was a needy
                # home but found all of what it needed with other homes or on the market
                pass

            print(f"Energy remaining: {self.energy:.2f}")



if __name__ == "__main__":
    timestamp = 0
    # Events to set by default
    # givers_advertisment.set()
    # awaiting_givers_advertisment.set()

    homes = [Home(id=(i+1)) for i in range(HOMES_COUNT)]
    for h in homes:
        h.start()
    print("~~", timestamp, "~~")

    counter = 0
    increment = 1

    # count advertisments every time a house sets the flag !atomically!, it increases a var by 1
    while True:
        # TODO: Handle the SIGINT error if it is stuck here when simulation is stopped
        home_counter.acquire()
        counter += increment
        if counter == HOMES_COUNT:
            givers_advertisment.set()
            # Release all givers which may be waiting for takers reponse
            # awaiting_taker_response.set()
            gate3.set()
            
            gate2.clear()
            gate1.set() # Release all homes at once (we made sure that they're all waiting on this event)
            # start_sync.clear()
            increment = -1
            # awaiting_taker_response.clear()
        elif counter == 0:
            gate1.clear()
            gate2.set()
            increment = 1