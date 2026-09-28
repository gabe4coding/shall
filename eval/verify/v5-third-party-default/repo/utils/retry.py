import random
import time


def retry(attempts=3, base=0.2):
    def wrap(fn):
        def inner(*args, **kwargs):
            for n in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    time.sleep(base * 2 ** n * (1 + random.random()))
            return fn(*args, **kwargs)
        return inner
    return wrap
