import time
from collections import deque
import pandas as pd
import threading

class TimedQueue:
    def __init__(self, timeout_seconds: float):
        """
        Initializes a queue that automatically removes items older than `timeout_seconds`.
        """
        self.timeout_seconds = timeout_seconds
        self.queue = deque()
        self._lock = threading.RLock()

    def add(self, value: float):
        """
        Adds a new data point to the queue with the current timestamp.
        """
        now = time.time()
        with self._lock:
            self.queue.append((now, value))

    def _drop_expired(self):
        """
        Removes all expired data points from the front of the queue.
        This is an O(k) operation where k is the number of expired items.
        """
        now = time.time()
        # Pop all items from the left that are older than the timeout
        with self._lock:
            while self.queue and self.queue[0][0] < now - self.timeout_seconds:
                self.queue.popleft()

    def get_data(self) :
        """
        Returns a list of all currently valid data points and their timestamp.
        Expired items are removed automatically before returning.
        """
        with self._lock:
            self._drop_expired()
            data = list(self.queue)
        return pd.DataFrame(data, columns=['time', 'value'])