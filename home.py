import os
from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process
from time import sleep

START_CONSUMPTION_RATE = 1.6
START_PRODUCTION_RATE = 1
TRADE_POLICY = "GIVE_ONLY" # or "SELL_ONLY" or "SELL_IF_NONE" ()
START_ENERGY = 5

# TODO LIST
# - replace the TRADE_POLICY strings with vars to avoid mistakes (?)
# - catch SIGINT to close msq queue

### Message types:
# 1: surplus advertisment
# <home_id> : transfer request (from taker) or energy transfer (from giver)

key = 532
msg_queue = MessageQueue(key, flags=IPC_CREAT)

# weather hard-coded
temperature = 25 # °C
MIN_SELL_AMOUNT = 1 # kWh
# ----------

class Home(Process):
    def __init__(self, id) -> None:
        super().__init__()
        self.id = id # Home ID must be > 1 (1 is a type used for energy request)
        self.energy = START_ENERGY
        self.consumption_rate = START_CONSUMPTION_RATE
        self.production_rate = START_PRODUCTION_RATE
        self.START_CONSUMPTION_RATE = 8
        self.awaiting_donation = False

    def run(self) -> None:
        while True:
            energy_delta = self.production_rate - self.consumption_rate
            
            if energy_delta > 0:
                if TRADE_POLICY == "GIVE_ONLY":
                    while True:
                        surplus_advertisment = f"{self.id} {energy_delta}"
                        msg_queue.send(surplus_advertisment.encode(), type=1)
                        energy_sent = int(msg_queue.receive(type=self.id)[0].decode())
                        energy_delta -= energy_sent
                        if energy_delta > 0:
                            # Surplus is still there, even though it was decreased. Try to give again
                            pass
                        else:
                            # All surplus energy was given, end of the day.
                            break

                elif TRADE_POLICY == "SELL_ONLY":
                    pass # wait for reaching the threshold of MIN_MARKET_SELL and then sell all surplus
                else: # SELL_IF_NONE
                    pass # check in mq for 'in need' request. If none, sell immediately
            
            elif energy_delta < 0:
                # Ask other homes for giveaway, wait for a reply, and if none, buy from market
                while True:
                    surplus_advertisment = msg_queue.receive(type=1)[0].decode()
                    giver_id, surplus = tuple(surplus_advertisment.split(' '))
                    energy_received = min(surplus, -energy_delta) # energy_delta is < 0
                    # Always accept transaction
                    msg_queue.send(str(energy_received).encode(),type=giver_id)
                    energy_delta += energy_received
                    print(self.id, "received energy from home", giver_id)
                    if energy_delta >= 0:
                        # Surplus from other home was more than enough for energy need.
                        # End of the day
                        break
                    else:
                        # Surplus from other home was insufficient, check for another one
                        # TODO /!\ MUST FIND A WAY TO STOP WHEN NO HOME IS GIVING ANYMORE
                        pass

            print(f"Energy remaining: {self.energy:.2f}")
            sleep(1)


if __name__ == "__main__":
    timestamp = 0
    homes = [Home(id=2)]
    for h in homes:
        h.start()
    print("~~", timestamp, "~~")