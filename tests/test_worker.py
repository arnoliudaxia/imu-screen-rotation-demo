import csv
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from imu_reader.worker import Worker
from test_protocols import yes, tlv


class FakeSerial:
    instance = None
    def __init__(self, *args, **kwargs):
        FakeSerial.instance = self
        self.data = queue.Queue()
        self.closed = False
    def open(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    @property
    def in_waiting(self): return 1
    def read(self, size):
        try: return self.data.get(timeout=.02)
        except queue.Empty: return b''


def wait_for(events, kind):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            event, value = events.get(timeout=.1)
            if event == kind: return value
            if event in ('error', 'record_error'): raise AssertionError(value)
        except queue.Empty: pass
    raise AssertionError('timeout waiting for ' + kind)


class WorkerTests(unittest.TestCase):
    def test_record_sparse_rows_and_close(self):
        with tempfile.TemporaryDirectory() as tmp, patch('imu_reader.worker.serial.Serial', FakeSerial):
            events = queue.Queue()
            worker = Worker('fake', 921600, events)
            worker.start()
            try:
                wait_for(events, 'connected')
                path = str(Path(tmp) / 'out.csv')
                worker.commands.put(('record', path))
                self.assertEqual(wait_for(events, 'recording'), path)
                FakeSerial.instance.data.put(yes(tlv(0x10, '<3i', 1000000,0,0)))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    snap = wait_for(events, 'snapshot')
                    if snap[1]: break
                self.assertEqual(snap[1], 1)
                worker.commands.put(('stop_record', None))
                self.assertEqual(wait_for(events, 'recording'), '')
                with open(path, encoding='utf-8-sig', newline='') as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['protocol'], 'YESENSE')
                self.assertEqual(float(rows[0]['acc_x']), 1)
                self.assertEqual(rows[0]['roll_deg'], '')
                self.assertTrue(rows[0]['host_time'].endswith('+00:00'))
            finally:
                worker.stop_event.set()
                worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertTrue(FakeSerial.instance.closed)
