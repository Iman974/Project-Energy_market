import socket
from threading import Lock, Semaphore
from concurrent.futures import ThreadPoolExecutor

START_ENERGY_PRICE = 0.1
MAX_TRANSACTIONS = 3

current_energy_price = START_ENERGY_PRICE  # in €/kWh

# hard-coded data
temperature = 25

# -----------------

on_going_transactions = Semaphore(MAX_TRANSACTIONS)
transaction_lock = Lock()

energy_cost = 0
GAMMA = 0.2
previous_energy_cost = (1/GAMMA) * START_ENERGY_PRICE

energy_bought = 0
energy_sold = 0

def handle_transaction(home_socket, address):
    with home_socket:
        print("Connected to home: ", address)

        data = home_socket.recv(1024).decode()
        transaction_type, amount = data.split(" ")
        amount = float(amount)
        print(transaction_type + " ends with", address)
        
        with transaction_lock:
            if transaction_type == "SELL":
                energy_bought += amount
            else: # BUY
                energy_sold += amount

    on_going_transactions.release()

def handle_tick(tick_socket):
    print("Tick update thread started.")

    global energy_cost
    timestamp = 0
    with tick_socket:
        print("wait for tick update")
        # Wait for tick update
        while True:
            timestamp += 1
            print("~~", timestamp, "~~")
            tick_notif = tick_socket.recv(1024)
            if not len(tick_notif):
                break
            energy_cost = GAMMA * previous_energy_cost # [...] TODO: continue equation

if __name__ == "__main__":
    
    HOST = "localhost"
    PORT = 9000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(MAX_TRANSACTIONS)

        # Establish connection for tick updates
        tick_socket = server_socket.accept()[0]

        with ThreadPoolExecutor(max_workers=MAX_TRANSACTIONS+1) as executor:
            # Start a thread for tick updates
            executor.submit(handle_tick, tick_socket)

            while True:
                # on_going_transactions.acquire()
                home_socket, address = server_socket.accept()
                # handler = Thread(target=handle_transaction, args=(client_socket, address))
                # handler.start()
                executor.submit(handle_transaction, home_socket, address)