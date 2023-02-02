import socket
from threading import Lock, Semaphore
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
from weather import temperature
from external import *
import signal
from random import randrange

START_ENERGY_PRICE = 0.17
MIN_ENERGY_PRICE = 0.05
MAX_TRANSACTIONS = 3

MARKET_HOST = "localhost"
MARKET_PORT = randrange(2000, 40000) # Using random to avoid "Address already in use" error

# Sync primitives
on_going_connections = Semaphore(MAX_TRANSACTIONS)
transaction_lock = Lock()

energy_cost = START_ENERGY_PRICE # in €/kWh
GAMMA = 0.75
past_energy_cost = 0

ALPHA_TEMPERATURE = 0.5
# Energy transactions modulators, from the point of view of the market
ALPHA_SOLD = 0.05
ALPHA_BOUGHT = -0.02

external_events = [0 for i in range(len(event_types))]

energy_bought = 0
energy_sold = 0

def handle_transaction(home_socket):
    global energy_sold, energy_bought
    
    with home_socket:
        data = home_socket.recv(1024).decode()
        transaction_type, amount = data.split(" ")
        amount = float(amount)
        
        with transaction_lock:
            if transaction_type == "SELL":
                energy_bought += amount
            else: # BUY
                energy_sold += amount

    on_going_connections.release()

def handle_tick(tick_start, tick_end):
    while True:
        tick_start.acquire()

        # Wait for all transactions to end
        for f in transactions_futures:
            f.result()
        transactions_futures.clear()

        update_energy()
        reset_factors()
        print("##################")
        print(f"Energy cost: {energy_cost:.3f}€")
        print("##################\n")

        tick_end.release()

def update_energy():
    global energy_cost, past_energy_cost

    temperatureVal = temperature.value
    internals = ALPHA_TEMPERATURE * (1/temperatureVal) + energy_bought * ALPHA_BOUGHT + energy_sold * ALPHA_SOLD
    print(f"Sold on market: {energy_bought:.2f}, | Bought from market: {energy_sold:.2f}")
    externals = external_modulators[0] * external_events[0] + external_modulators[1] * external_events[1]
    past_energy_cost = energy_cost
    energy_cost = GAMMA * past_energy_cost + internals + externals

    if energy_cost < MIN_ENERGY_PRICE:
        energy_cost = MIN_ENERGY_PRICE

def reset_factors():
    global energy_bought, energy_sold

    for i in range(len(external_events)):
        external_events[i] = 0

    energy_bought = 0
    energy_sold = 0

def on_external_event(event_signal, *args):
    if event_signal == signal.SIGUSR1:
        external_events[0] = 1
    elif event_signal == signal.SIGUSR2:
        external_events[1] = 1

transactions_futures = []

def run_market(tick_start, tick_end):
    signal.signal(signal.SIGUSR1, on_external_event)
    signal.signal(signal.SIGUSR2, on_external_event)

    external = Process(target=run_external)
    external.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((MARKET_HOST, MARKET_PORT))
        server_socket.listen(MAX_TRANSACTIONS)

        with ThreadPoolExecutor(max_workers=MAX_TRANSACTIONS+1) as executor:
            # Start a thread for tick updates
            executor.submit(handle_tick, tick_start, tick_end)

            while True:
                on_going_connections.acquire()
                home_socket = server_socket.accept()[0]
                future = executor.submit(handle_transaction, home_socket)
                if len(transactions_futures) >= MAX_TRANSACTIONS:
                    transactions_futures.pop(0)
                transactions_futures.append(future)