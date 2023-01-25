import os
from sysv_ipc import MessageQueue, IPC_CREAT, BusyError
from multiprocessing import Process
from time import sleep

START_CONSUMPTION_RATE = 1.6
START_PRODUCTION_RATE = 1
TRADE_POLICY = "GIVE_ONLY" # or "SELL_ONLY" or "SELL_IF_NONE" ()
MAX_ENERGY = 11
AWAIT_DONATION_TIME = 3
LOW_ENERGY_LEVEL = 2
START_ENERGY = 5

# TODO LIST
# - do a 'supply' and when it reaches the 'supply' the home will try to buy
# - replace the TRADE_POLICY strings with vars to avoid mistakes (?)
# - catch SIGINT to close msq queue

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
        self.await_donation_counter = AWAIT_DONATION_TIME

    def run(self) -> None:
        while True:
            self.energy -= self.consumption_rate
            self.energy += self.production_rate
            
            surplus = self.energy - MAX_ENERGY
            if surplus > 0:
                if TRADE_POLICY == "GIVE_ONLY":
                    # Check the Mq for transaction requests from needy homes
                    try:
                        needy_home_id = msg_queue.receive(type=1, block=False)[0].decode()
                        msg_queue.send(str(surplus).encode(), type=int(needy_home_id))
                        surplus = 0
                        self.energy = MAX_ENERGY
                        print(self.id, "gave energy to home", needy_home_id)
                    except BusyError:
                        print("No needy home found")
                elif TRADE_POLICY == "SELL_ONLY":
                    pass # wait for reaching the threshold of MIN_MARKET_SELL and then sell all surplus
                else: # SELL_IF_NONE
                    pass # check in mq for 'in need' request. If none, sell immediately
            
            elif self.energy < LOW_ENERGY_LEVEL:
                # Ask other homes for giveaway, wait for a reply, and if none, buy from market
                if not awaiting_donation: # Let every home know that this home needs energy
                    print(self.id, "sent energy request")
                    msg_queue.send(str(self.id).encode(), type=1)
                    awaiting_donation = True
                else:
                    try:
                        energy_received = msg_queue.receive(type=self.id, block=False)
                        awaiting_donation = False
                        self.energy += energy_received
                    except BusyError: # No home responded to the request
                        await_donation_counter -= 1
                        if await_donation_counter == 0: # Await time elapsed, buy on market
                            # BUY FROM MARKET
                            print("Buy from market")
                            await_donation_counter = AWAIT_DONATION_TIME
                        pass

            print(f"Energy remaining: {self.energy:.2f}")
            sleep(1)


if __name__ == "__main__":
    homes = [Home(id=2)]
    for h in homes:
        h.start()
    print("~~", timestamp, "~~")