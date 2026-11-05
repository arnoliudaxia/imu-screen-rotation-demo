import csv
import queue
import threading
import time
from datetime import datetime, timezone

import serial
from .protocols import StreamParser

COLUMNS = ['host_time', 'protocol', 'device_time_us', 'roll_deg', 'pitch_deg', 'yaw_deg',
           'q_w', 'q_x', 'q_y', 'q_z', 'acc_x', 'acc_y', 'acc_z',
           'gyro_x', 'gyro_y', 'gyro_z', 'mag_x', 'mag_y', 'mag_z',
           'mag_norm_x', 'mag_norm_y', 'mag_norm_z', 'temperature_c']


class Worker(threading.Thread):
    def __init__(self, port, baud, events):
        super().__init__(daemon=True)
        self.port, self.baud, self.events = port, baud, events
        self.commands = queue.Queue()
        self.stop_event = threading.Event()

    def run(self):
        parser = StreamParser()
        output = None
        writer = None
        latest = {}
        last_protocol = ''
        bytes_count = 0
        start = last = time.monotonic()
        try:
            # Explicitly disable software/hardware flow control; no writes.
            ser = serial.Serial(port=None, baudrate=self.baud, timeout=0.1, xonxoff=False,
                                rtscts=False, dsrdtr=False)
            ser.dtr = False
            ser.rts = False
            ser.port = self.port
            ser.open()
            with ser:
                self.events.put(('connected', self.port))
                while not self.stop_event.is_set():
                    try:
                        while True:
                            cmd, arg = self.commands.get_nowait()
                            if cmd == 'record':
                                if output:
                                    old = output
                                    output = writer = None
                                    old.close()
                                try:
                                    output = open(arg, 'w', newline='', encoding='utf-8-sig')
                                    writer = csv.DictWriter(output, fieldnames=COLUMNS)
                                    writer.writeheader()
                                    self.events.put(('recording', arg))
                                except OSError as exc:
                                    if output: output.close()
                                    output = writer = None
                                    self.events.put(('record_error', str(exc)))
                            elif cmd == 'stop_record':
                                if output:
                                    old = output
                                    output = writer = None
                                    old.close()
                                self.events.put(('recording', ''))
                    except queue.Empty:
                        pass
                    data = ser.read(min(max(ser.in_waiting, 1), 8192))
                    bytes_count += len(data)
                    for protocol, fields in parser.feed(data):
                        if protocol != last_protocol:
                            latest.clear()
                            last_protocol = protocol
                        latest.update(fields)
                        if writer:
                            row = dict(fields, protocol=protocol, host_time=datetime.now(timezone.utc).isoformat(timespec='milliseconds'))
                            try:
                                writer.writerow(row)
                            except (OSError, ValueError) as exc:
                                old = output
                                output = writer = None
                                try: old.close()
                                except OSError: pass
                                self.events.put(('record_error', str(exc)))
                    now = time.monotonic()
                    if now - last >= .1:
                        if output:
                            try: output.flush()
                            except OSError as exc:
                                old = output
                                output = writer = None
                                try: old.close()
                                except OSError: pass
                                self.events.put(('record_error', str(exc)))
                        # Drop display snapshots if the UI is busy; never drop recording rows or control events.
                        if self.events.qsize() < 5:
                            self.events.put(('snapshot', (parser.protocol, parser.good, parser.bad,
                                                         bytes_count / max(now-start, .001), latest.copy())))
                        last = now
        except (serial.SerialException, OSError, ValueError) as exc:
            self.events.put(('error', str(exc)))
        finally:
            if output:
                try: output.close()
                except OSError as exc: self.events.put(('record_error', str(exc)))
            self.events.put(('closed', ''))
