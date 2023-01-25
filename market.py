from socket import socket
# from threading import Thread
from concurrent.futures import ThreadPoolExecutor

START_ENERGY_PRICE = 0.1
MAX_CLIENTS = 3

current_energy_price = START_ENERGY_PRICE  # in €/kWh

# hard-coded data
temperature = 25

# -----------------

on_going_transactions = 0

def handle_transaction(client_socket, address):
    global on_going_transactions
    on_going_transactions += 1
    with client_socket:
        print("Connected to client: ", address)
        data = client_socket.recv(1024)
        while len(data):
            client_socket.sendall(data)
            data = client_socket.recv(1024)
        print("Disconnecting from client: ", address)
    on_going_transactions -= 1

if __name__ == "__main__":

    HOST = "localhost"
    PORT = 9000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(3)
        # client_socket, address = server_socket.accept() # Wait for the first connection from a client
        with ThreadPoolExecutor(max_workers=MAX_CLIENTS) as executor:
            while True:
                client_socket, address = server_socket.accept()
                # handler = Thread(target=handle_transaction, args=(client_socket, address))
                # handler.start()
                future = executor.submit(handle_transaction)