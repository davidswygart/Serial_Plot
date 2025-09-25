"""Live plotter that reads lines from a serial port and updates a matplotlib
plot whenever new "label:value" pairs arrive.
"""

import time
from collections import deque
import sys
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

    while True:
        (label, value) = read_and_parse(ser)

        if label not in series:
            series[label] = {}
            series[label]['data'] = TimedQueue(timeout_seconds=x_range+.01)
            series[label]['line'] = ax.plot([], [], label=label)[0]
            ax.legend(loc='upper right')
        series[label]['data'].add(value)

        now = time.time()
        for label in series:
            df = series[label]['data'].get_data()
            series[label]['line'].set_data(df.time-now, df.value)
        
        # ax.relim()
        # ax.autoscale_view()
        fig.canvas.draw()
        fig.canvas.flush_events()

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