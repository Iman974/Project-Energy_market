import signal
from home import *
import market
import weather
from multiprocessing import Process, Semaphore
from random import random
import time

def rand_range(start: float, end: float) -> float:
    return start + random() * (end-start)

if __name__ == "__main__":
    weather_start = Semaphore(0)
    weather_end = Semaphore(0)
    market_start = Semaphore(0)
    market_end = Semaphore(0)
    homes_start = Home.tick_start
    homes_end = Home.tick_end

    # These gates are 'opened' by default
    Home.enter_gate.set()
    Home.enter_gate.set()

    global weather_process
    weather_process = Process(target=weather.run_weather, args=(weather_start, weather_end))
    market_process = Process(target=market.run_market, args=(market_start, market_end))
    weather_process.start()
    market_process.start()

    homes = []

    for i in range(HOMES_COUNT):
        production_rate = rand_range(MIN_PRODUCTION_RATE, MAX_PRODUCTION_RATE)
        consumption_rate = rand_range(MIN_CONSUMPTION_RATE, MAX_CONSUMPTION_RATE)

        home_process = Home((i+1), Policy.getRandom(), consumption_rate, production_rate)
        homes.append(home_process)
        home_process.start()
    
    homes_end.acquire() # Reset semaphore to 0 because of Home.on_tick_start's first call to release on it

    def handle_interrupt(*args):
        for h in homes:
            h.terminate()
        market_process.terminate()
        weather_process.terminate()
        msg_queue.remove()
        
        print("\n-----------------END OF SIMULATION--------------------")
        exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)

    timestamp = 0
    TICK_DURATION = 1
    while True:
        timestamp += 1
        print("~~ {", timestamp, "} ~~")

        weather_start.release()
        weather_end.acquire()

        homes_start.release()
        homes_end.acquire()

        market_start.release()
        market_end.acquire()

        time.sleep(TICK_DURATION)