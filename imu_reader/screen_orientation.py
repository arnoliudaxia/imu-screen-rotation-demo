"""Pure screen-orientation math. Axes: top +X, right +Y, front -Z."""
import math


def unit(v):
    try:
        v = tuple(float(x) for x in v)
        if len(v) != 3 or not all(math.isfinite(x) for x in v): return None
        n = math.hypot(*v)
        return tuple(x / n for x in v) if n > 1e-12 else None
    except (TypeError, ValueError, OverflowError):
        return None


def quaternion_up(q):
    """World +Z expressed in body coordinates, for wxyz body-to-world q."""
    try:
        q = tuple(float(x) for x in q)
        if len(q) != 4 or not all(math.isfinite(x) for x in q): return None
        n = math.hypot(*q)
        if n < 1e-12: return None
        w, x, y, z = (v / n for v in q)
        return unit((2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)))
    except (TypeError, ValueError, OverflowError):
        return None


def acceleration_up(a):
    v = unit(a)
    return tuple(-x for x in v) if v else None


def simulated_up(clockwise, upright=90):
    """upright=0 flat, 90 vertical; clockwise is physical phone rotation."""
    t, tilt = math.radians(clockwise), math.radians(upright)
    return (math.sin(tilt)*math.cos(t), -math.sin(tilt)*math.sin(t), math.cos(tilt))


def angle(up):
    v = unit(up)
    return (-math.degrees(math.atan2(v[1], v[0]))) % 360 if v else None


def angular_difference(a, b):
    return (a-b+180) % 360-180


class Orientation:
    def __init__(self, hysteresis=12, dwell=.25, flat_degrees=20, alpha=.18):
        self.hysteresis, self.dwell = hysteresis, dwell
        self.flat = math.sin(math.radians(flat_degrees))
        self.alpha = alpha
        self.current = self.pending = self.pending_since = self.filtered = None

    def update(self, up, now, smooth=False):
        v = unit(up)
        if v is None or not math.isfinite(now):
            self.pending = self.pending_since = None
            return self.current
        if smooth:
            if self.filtered is not None:
                v = unit(tuple((1-self.alpha)*a+self.alpha*b for a,b in zip(self.filtered, v)))
            self.filtered = v
            if v is None: return self.current
        else:
            self.filtered = None
        if math.hypot(v[0], v[1]) < self.flat:
            self.pending = self.pending_since = None
            return self.current
        a = angle(v)
        candidate = int((a+45)//90) % 4 * 90
        if self.current is None:
            self.current = candidate
        elif candidate == self.current or abs(angular_difference(a, self.current)) < 45+self.hysteresis:
            self.pending = self.pending_since = None
        elif candidate != self.pending:
            self.pending, self.pending_since = candidate, now
        elif now-self.pending_since >= self.dwell:
            self.current, self.pending, self.pending_since = candidate, None, None
        return self.current
