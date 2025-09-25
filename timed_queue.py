import time
from collections import deque
from typing import Any, Tuple
import pandas as pd

class TimedQueue:
    def __init__(self, timeout_seconds: float):
        """
        Initializes a queue that automatically removes items older than `timeout_seconds`.
        """
        self.timeout_seconds = timeout_seconds
        self.queue = deque()

    def add(self, value: Any):
        """
        Adds a new data point to the queue with the current timestamp.
        """
        self.queue.append((time.time(), value))

    def _drop_expired(self):
        """
        Removes all expired data points from the front of the queue.
        This is an O(k) operation where k is the number of expired items.
        """
        now = time.time()
        # Pop all items from the left that are older than the timeout
        while self.queue and self.queue[0][0] < now - self.timeout_seconds:
            self.queue.popleft()

    def get_data(self) :
        """
        Returns a list of all currently valid data points and their timestamp.
        Expired items are removed automatically before returning.
        """
        self._drop_expired()
        # times, values = map(tuple, zip(*self.queue))
        return pd.DataFrame(self.queue, columns=['time','value'])