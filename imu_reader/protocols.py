"""Incremental output-only protocol parsing; values in SI units except mGauss."""
import math
import struct


def crc8(data):
    # CRC-8/MAXIM-DOW, poly 0x31 reflected (0x8c), init/xorout 0.
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ (0x8c if c & 1 else 0)
    return c


def crc16(data):
    # CRC-16/XMODEM, poly 0x1021, init/xorout 0.
    c = 0
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ (0x1021 if c & 0x8000 else 0)) & 0xffff
    return c


def checksum(data):
    a = b = 0
    for value in data:
        a = (a + value) & 255
        b = (b + a) & 255
    return bytes((a, b))


def decode_fdi(kind, payload):
    result = {}
    if kind == 0x40 and len(payload) == 56:
        v = struct.unpack('<12fq', payload)
        keys = ('gyro_x', 'gyro_y', 'gyro_z', 'acc_x', 'acc_y', 'acc_z',
                'mag_x', 'mag_y', 'mag_z', 'temperature_c')
        result.update(zip(keys, v[:10]))
        result['device_time_us'] = v[12]
    elif kind == 0x41 and len(payload) == 48:
        v = struct.unpack('<10fq', payload)
        result.update(zip(('roll_deg', 'pitch_deg', 'yaw_deg'), map(math.degrees, v[3:6])))
        result.update(zip(('q_w', 'q_x', 'q_y', 'q_z'), v[6:10]))
        result['device_time_us'] = v[10]
    return result


def decode_yes(payload):
    out = {}
    pos = 0
    while pos < len(payload):
        if pos + 2 > len(payload):
            raise ValueError('truncated TLV header')
        kind, n = payload[pos:pos+2]
        pos += 2
        if pos + n > len(payload):
            raise ValueError('truncated TLV value')
        data = payload[pos:pos+n]
        pos += n
        if kind == 1 and n == 2:
            out['temperature_c'] = struct.unpack('<h', data)[0] * .01
        elif kind in (0x10, 0x20, 0x30, 0x31, 0x40) and n == 12:
            values = [x * (0.001 if kind == 0x31 else 0.000001) for x in struct.unpack('<3i', data)]
            if kind == 0x20:
                values = list(map(math.radians, values))
            keys = {0x10: ('acc_x','acc_y','acc_z'), 0x20: ('gyro_x','gyro_y','gyro_z'),
                    0x30: ('mag_norm_x','mag_norm_y','mag_norm_z'), 0x31: ('mag_x','mag_y','mag_z'),
                    0x40: ('pitch_deg','roll_deg','yaw_deg')}[kind]
            out.update(zip(keys, values))
        elif kind == 0x41 and n == 16:
            out.update(zip(('q_w','q_x','q_y','q_z'), (x * .000001 for x in struct.unpack('<4i', data))))
        elif kind == 0x51 and n == 4:
            out['device_time_us'] = struct.unpack('<I', data)[0]
    return out


class StreamParser:
    def __init__(self):
        self.buffer = bytearray()
        self.good = 0
        self.bad = 0
        self.protocol = ''

    def feed(self, data):
        self.buffer.extend(data)
        result = []
        while self.buffer:
            b = self.buffer
            if b[0] not in (0xfc, 0x59):
                del b[0]
                continue
            if b[0] == 0x59:
                if len(b) < 2: break
                if b[1] != 0x53:
                    del b[0]; continue
                if len(b) < 5: break
                size = b[4] + 7
                if len(b) < size: break
                frame = bytes(b[:size])
                if checksum(frame[2:-2]) != frame[-2:]:
                    self.bad += 1; del b[0]; continue
                try:
                    fields = decode_yes(frame[5:-2])
                except ValueError:
                    self.bad += 1; del b[0]; continue
                protocol = 'YESENSE'
            else:
                if len(b) < 5: break
                if crc8(b[:4]) != b[4]:
                    self.bad += 1; del b[0]; continue
                size = b[2] + 8
                if len(b) < size: break
                frame = bytes(b[:size])
                if frame[-1] != 0xfd or crc16(frame[7:-1]) != int.from_bytes(frame[5:7], 'big'):
                    self.bad += 1; del b[0]; continue
                fields = decode_fdi(frame[1], frame[7:-1])
                protocol = 'FDILink'
            del b[:size]
            # Reject NaN/Inf from otherwise valid frames before drawing/writing.
            fields = {k: v for k, v in fields.items() if not isinstance(v, float) or math.isfinite(v)}
            self.good += 1
            self.protocol = protocol
            result.append((protocol, fields))
        return result
