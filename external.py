import signal
import os
import time
from random import random

event_types = {"war", "fuel_shortage"}

def run_external():
    DELAY = 2
    ppid = os.getppid()
    
    while True:
        time.sleep(DELAY)
        for event in event_types:
            if event == "war":
                if random() < 0.13:
                    print("!!! WAR IN THE COUNTRY !!!")
                    os.kill(ppid, signal.SIGUSR1)
                
            elif event == "fuel_shortage":
                if random() < 0.25:
                    print("!!! FUEL SHORTAGE !!!")
                    os.kill(ppid, signal.SIGUSR2)