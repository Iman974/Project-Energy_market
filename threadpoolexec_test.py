from concurrent.futures import ThreadPoolExecutor
from threading import current_thread
import time

def test(n):
    print("Exec", current_thread().name, n)
    time.sleep(1)
    print("Finished", current_thread().name, n)

with ThreadPoolExecutor(max_workers=2) as executor:
    f1 = executor.submit(test, 1)
    f2 = executor.submit(test, 2)
    f3 = executor.submit(test, 3)
    print("-------------")
    print("1:", f1.running())
    print("2:", f2.running())
    print("3:", f3.running())
    # future.result()
    # future2.result()