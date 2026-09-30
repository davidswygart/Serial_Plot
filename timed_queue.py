import time
from collections import deque
import numpy as np
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

    def _drop_expired(self, now):
        """
        Removes all expired data points from the front of the queue.
        This is an O(k) operation where k is the number of expired items.
        """
        # Pop all items from the left that are older than the timeout
        while self.queue and self.queue[0][0] < now - self.timeout_seconds:
            self.queue.popleft()

    def get_data(self) :
        """
        Returns timestamp and value arrays for all valid points.
        Expired items are removed automatically before returning.
        """
        with self._lock:
            self._drop_expired(time.time())
            data = np.fromiter(
                (value for point in self.queue for value in point),
                dtype=np.float64,
                count=len(self.queue) * 2,
            ).reshape(-1, 2)
        return data[:, 0], data[:, 1]