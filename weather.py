from multiprocessing import Process, Value, Event
from random import random

temperature = Value("f", 25.0)

def weather_process(tick_update: Event):
    timestamp = 0
    while True:
        tick_update.wait()
        tick_update.clear()

        timestamp += 1
        print("~~ weather:", timestamp, "~~")

        with temperature.get_lock():
            temperature.value += random()

# class Weather(Process):

#     temperature = Value("f", 25.0)

#     def __init__(self, ):
#         super().__init__()

#     def update():
#         pass