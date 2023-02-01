from multiprocessing import Value
from random import random

temperature = Value("f", 20.0)

def run_weather(tick_start, tick_end):
    AVG_TEMPERATURE = 20
    AMPLITUDE = 15

    while True:
        tick_start.acquire()

        temperature.value = AVG_TEMPERATURE + (2*random()-1) * AMPLITUDE
        print(f"Temperature: {temperature.value:.1f}°C")
        tick_end.release()