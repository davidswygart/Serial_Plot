"""Live plotter that reads lines from a serial port and plots "comma seperated" values.
"""

import time
import threading
import serial
from serial.tools import list_ports
import matplotlib.pyplot as plt
from timed_queue import TimedQueue
stop_event = threading.Event()

def main(opts):
    ser = open_serial_port(opts.port, opts.baud)
    
    series = {}

    # Start the background reader thread (module-level reader_loop)
    rl = threading.Thread(target=reader_loop, args=(ser, series, opts.x_range), daemon=True)
    rl.start()

    try:
        plot_loop(series , opts)
    except KeyboardInterrupt:
        stop_event.set()
        rl.join(timeout=10)


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
        s = line.split(',')
        if len(s) != 2:
            print(f"Skipping unparseable line: {line}")
            continue

        try:
            values = [float(v) for v in s ]
            labels = [str(num) for num in range(len(values))]
            return labels, values
        except ValueError:
            print(f"Skipping unparseable value: {s[1]}")
            continue

def reader_loop(ser, series, x_range):
    """Background reader: read lines from serial and add to per-label TimedQueue.
    """
    while not stop_event.is_set():
        labels, values = read_and_parse(ser)
        
        for ind, label in enumerate(labels):
            if label not in series:
                # create storage for label; plotting line will be created by main thread
                series[label] = {}
                series[label]['data'] = TimedQueue(timeout_seconds=x_range + .01)
            series[label]['data'].add(values[ind])
            # print(f"added {values[ind]}")

def plot_loop(series , opts):
    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots()
    
    ax.set_ylim(opts.y_min, opts.y_max)
    ax.set_xlim(-opts.x_range, 0)
    # ax.set_title("Live Serial Data by Label")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(opts.y_label)
    
    fig.show()  # Ensure the figure window is shown

    while not stop_event.is_set():
        now = time.time()

        # Ensure any new labels have plot lines created on the main thread
        for label in list(series.keys()):
            if 'line' not in series[label]:
                series[label]['line'] = ax.plot([], [], label=label)[0]
                ax.legend(loc='upper right')

        for label in list(series.keys()):
            df = series[label]['data'].get_data()
            if df.empty: 
                series[label]['line'].remove()
                del series[label]   # TODO: make thread safe
                ax.legend(loc='upper right')
            else:
                series[label]['line'].set_data(df.time - now, df.value)

        fig.canvas.draw_idle()
        plt.pause(opts.update_interval)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Live serial plotter')
    parser.add_argument('--port', default='COM23', help='Serial port (e.g. COM14)')
    parser.add_argument('--baud', type=int, default=250000, help='Serial baud rate')
    parser.add_argument('--x-range', type=int, default=30, help='X axis window in seconds')
    parser.add_argument('--update-interval', type=float, default=0.05, help='Plot update interval in seconds')
    parser.add_argument('--y_min', type=float, default=40000, help='min Y axis value')
    parser.add_argument('--y_max', type=float, default=600000, help='max Y axis value')
    parser.add_argument('--y_label', default='Value', help='Y-axis label')

    options = parser.parse_args()

    main(options)