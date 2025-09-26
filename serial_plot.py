"""Live plotter that reads lines from a serial port and updates a matplotlib
plot whenever new "label:value" pairs arrive.
"""

import time
from collections import deque
import sys
import threading
import serial
from serial.tools import list_ports
import matplotlib.pyplot as plt
from timed_queue import TimedQueue

# Configuration
PORT = 'COM14'
BAUD = 115200
X_RANGE = 10  # size of plotting window in seconds

def main(port, baud, x_range):
    ser = open_serial_port(port, baud)
    
    series = {}

    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots()
    
    ax.set_ylim(0, 100)
    ax.set_xlim(-x_range, 0)
    ax.set_title("Live Serial Data by Label")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Value")

    # Configuration: how often to update the plot (seconds)
    UPDATE_INTERVAL = 0.1

    stop_event = threading.Event()

    # Background reader: reads serial lines and enqueues values into TimedQueue per label
    def reader_thread():
        while not stop_event.is_set():
            label, value = read_and_parse(ser)
            if label not in series:
                # Note: creating matplotlib Line2D objects must be done from the main thread
                # so we only create the TimedQueue here; the main thread will create lines when it sees a new label
                series[label] = {}
                series[label]['data'] = TimedQueue(timeout_seconds=x_range + .01)
            series[label]['data'].add(value)

    t = threading.Thread(target=reader_thread, daemon=True)
    t.start()

    try:
        while True:
            now = time.time()

            # Ensure any new labels have plot lines created on the main thread
            for label in list(series.keys()):
                if 'line' not in series[label]:
                    series[label]['line'] = ax.plot([], [], label=label)[0]
                    ax.legend(loc='upper right')

            for label in series:
                df = series[label]['data'].get_data()
                if df.empty:
                    series[label]['line'].set_data([], [])
                else:
                    series[label]['line'].set_data(df.time - now, df.value)

            fig.canvas.draw()
            fig.canvas.flush_events()
            time.sleep(UPDATE_INTERVAL)
    except KeyboardInterrupt:
        stop_event.set()
        t.join(timeout=1)

def open_serial_port(port, rate):
    while True:
        try:
            ser = serial.Serial(port, rate, timeout=None)
            print(f"Opened serial port {port} @ {rate}")
            return ser
        except Exception as e:
            print(f"Failed to open serial port {port}: {e}")
            list_com_ports()
            print(f"retrying in 5 seconds...")
            time.sleep(5)


def list_com_ports():
    ports = list_ports.comports()
    if not ports:
        print("No serial/com ports found.")
        return
    print("Available serial ports:")
    for p in ports:
        print(f"- {p.device}: {p.description}")

def read_and_parse(ser):
    while True:
        line = ser.readline().decode('utf-8').strip()
        s = line.split(':')
        if len(s) != 2:
            print(f"Skipping unparseable line: {line}")
            continue

        label = s[0]

        try:
            value = float(s[1])
            return label, value
        except ValueError:
            print(f"Skipping unparseable value: {s[1]}")
            continue






if __name__ == '__main__':
    # Allow overriding port/baud from command-line args
    if len(sys.argv) >= 2:
        PORT = sys.argv[1]
    if len(sys.argv) >= 3:
        BAUD = int(sys.argv[2])
    if len(sys.argv) >= 4:
        X_RANGE = int(sys.argv[3])
    main(PORT, BAUD, X_RANGE)