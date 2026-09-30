"""Live plotter that reads values from serial port and plots data.
Each newline is parsed, timestamped, and plotted. 
Multiple trendlines can be plotted by using label:value pairs, comma seperated values, or both.
If no label is provided (comma seperated values), then automatic labels are generated (e.g. A, B, C, ...)
Example of acceptable formats:
1. labelA: valueA, labelB: valueB \n
2. valueA, valueB \n
3 labelA: valueA \n labelB: valueB \n  **
**This format will result in a slightly later timestamp for valueB vs valueA.
"""

import time
import threading
import serial
from serial.tools import list_ports
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
import numpy as np
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


def downsample_for_display(timestamps, values, now, x_range, pixel_width):
    visible = timestamps >= now - x_range
    timestamps = timestamps[visible]
    values = values[visible]
    x_values = timestamps - now

    pixel_width = max(1, int(pixel_width))
    if x_range <= 0 or values.size <= pixel_width * 2 or not np.isfinite(values).all():
        return x_values, values

    buckets = np.floor((x_values + x_range) * (pixel_width / x_range)).astype(np.intp)
    buckets = np.clip(buckets, 0, pixel_width - 1)
    minima = np.full(pixel_width, np.inf)
    maxima = np.full(pixel_width, -np.inf)
    np.minimum.at(minima, buckets, values)
    np.maximum.at(maxima, buckets, values)

    occupied = np.flatnonzero(np.isfinite(minima))
    bucket_x = (occupied + 0.5) * (x_range / pixel_width) - x_range
    bucket_y = np.column_stack((minima[occupied], maxima[occupied])).ravel()
    return np.repeat(bucket_x, 2), bucket_y


def parse_line(line):
    samples = []
    for index, item in enumerate(line.split(',')):
        parts = item.split(':', maxsplit=1)
        if len(parts) == 2:
            label, raw_value = parts[0].strip(), parts[1].strip()
            if not label:
                print(f"Skipping unparseable field: {item}")
                continue
        else:
            label = chr(ord('A') + index)
            raw_value = item.strip()

        try:
            samples.append((label, float(raw_value)))
        except ValueError:
            print(f"Skipping unparseable value: {raw_value}")
    return samples


def read_and_parse(ser):
    while True:
        line = ser.readline().decode('utf-8').strip()
        samples = parse_line(line)
        if samples:
            return samples
        print(f"Skipping unparseable line: {line}")

def reader_loop(ser, series, x_range):
    """Background reader: read lines from serial and add to per-label TimedQueue.
    """
    while not stop_event.is_set():
        for label, value in read_and_parse(ser):
            if label not in series:
                # create storage for label; plotting line will be created by main thread
                series[label] = {}
                series[label]['data'] = TimedQueue(timeout_seconds=x_range + .01)
            series[label]['data'].add(value)

def plot_loop(series , opts):
    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots()
    copy_from_bbox = getattr(fig.canvas, 'copy_from_bbox', None)
    restore_region = getattr(fig.canvas, 'restore_region', None)
    use_blit = (
        fig.canvas.supports_blit
        and callable(copy_from_bbox)
        and callable(restore_region)
    )
    background = None

    if use_blit:
        assert callable(copy_from_bbox)
        assert callable(restore_region)

        def capture_background(_event):
            nonlocal background
            background = copy_from_bbox(ax.bbox)

        fig.canvas.mpl_connect('draw_event', capture_background)
    
    ax.set_ylim(opts.y_min, opts.y_max)
    ax.set_xlim(-opts.x_range, 0)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=12))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=20))
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    if opts.title:
        ax.set_title(opts.title)
    ax.set_xlabel("Time (s)")
    if opts.y_label:
        ax.set_ylabel(opts.y_label)

    while not stop_event.is_set():
        now = time.time()
        data_bounds = []

        # Ensure any new labels have plot lines created on the main thread
        for label in list(series.keys()):
            if 'line' not in series[label]:
                line = ax.plot([], [], label=label)[0]
                if use_blit:
                    line.set_animated(True)
                series[label]['line'] = line
                ax.legend(loc='upper right')
                background = None

        for label in list(series.keys()):
            if 'line' not in series[label]:
                continue
            timestamps, values = series[label]['data'].get_data()
            if values.size == 0:
                series[label]['line'].remove()
                del series[label]   # TODO: make thread safe
                ax.legend(loc='upper right')
                background = None
            else:
                x_values, display_values = downsample_for_display(
                    timestamps, values, now, opts.x_range, ax.bbox.width
                )
                series[label]['line'].set_data(x_values, display_values)
                finite_values = display_values[np.isfinite(display_values)]
                if finite_values.size:
                    data_bounds.append((finite_values.min(), finite_values.max()))
        
        # Auto-scale Y axis if not fixed
        if data_bounds and (not opts.y_max or not opts.y_min):
            min_span = 0.3
            margin = 0.3
        
            data_min = min(bounds[0] for bounds in data_bounds)
            data_max = max(bounds[1] for bounds in data_bounds)
            (ymin, ymax) = ax.get_ylim()
            yspan = ymax-ymin
            data_span = data_max-data_min

            #only recalculate if data is beyond range or taking up a small portion of the graph
            if data_min<ymin or data_max>ymax or (data_span/yspan)<min_span: 
                ymin = opts.y_min if opts.y_min else data_min-data_span*margin
                ymax = opts.y_max if opts.y_max else data_max+data_span*margin
                ax.set_ylim(ymin, ymax)
                background = None

        if use_blit:
            if background is None:
                fig.canvas.draw()
            if background is not None:
                assert callable(restore_region)
                restore_region(background)
                for label in list(series.keys()):
                    if 'line' in series[label]:
                        ax.draw_artist(series[label]['line'])
                fig.canvas.blit(ax.bbox)
            else:
                fig.canvas.draw_idle()
        else:
            fig.canvas.draw_idle()
        fig.canvas.flush_events()
        time.sleep(opts.update_interval)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Live serial plotter')
    parser.add_argument('--port', default='COM7', help='Serial port (e.g. COM14)')
    parser.add_argument('--baud', type=int, default=115200, help='Serial baud rate')
    parser.add_argument('--x-range', type=int, default=10, help='X axis window in seconds')
    parser.add_argument('--update-interval', type=float, default=0.1, help='Plot update interval in seconds')
    parser.add_argument('--y_min', type=float, help='min Y axis value')
    parser.add_argument('--y_max', type=float, help='min Y axis value')
    parser.add_argument('--y_label', type=str, help='Y-axis label')
    parser.add_argument('--title', type=str, help='Graph title')

    options = parser.parse_args()

    main(options)