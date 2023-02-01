import signal
import os
import time
from random import random

event_types = {"war", "fuel_shortage"}

def run_external():

    DELAY = 3
    ppid = os.getppid()
    
    while True:
        time.sleep(DELAY)
        for event in event_types:
            if event == "war":
                if random() < 0.05:
                    os.kill(ppid, signal.SIGUSR1)
                    print("!!! WAR IN THE COUNTRY !!!")
                
            elif event == "fuel_shortage":
                if random() < 0.2:
                    os.kill(ppid, signal.SIGUSR2)
                    print("!!! FUEL SHORTAGE !!!")