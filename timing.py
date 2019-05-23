import time


# ---Functions---
def secsToHMS(secs):    # Convert float of seconds to text as [Hours:Minutes:Seconds.milliseconds].
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    out = f"{m:02.0f}:{s:06.3f}"
    if h:
        out = f"{h:01.0f}:" + out
    return out


def HMStoSecs(hms):     # Convert text [Hours:Minutes:Seconds.milliseconds] to float of seconds.
    secs = 0.0
    mults = [1, 60, 3600]
    hms = hms.split(":")[::-1]
    for i in range(len(hms)):
        secs += float(hms[i]) * mults[i]
    return secs


# ---Classes---
class FPSTimer:
    def __init__(self, interval=1.0):
        self.fps = 1.0
        self.interval = interval
        self.reset()

    def reset(self):
        self._began = time.time()
        self._frame_count = 0

    def update(self):
        self._frame_count += 1
        if time.time() > self._began + self.interval:
            self.fps = self._frame_count / (time.time() - self._began)
            self.reset()
        return self.fps


class Stopwatch:
    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.last_split = 0.0
        self._began = 0.0
        self._total = 0.0

    def start(self):
        self._began = time.time()
        self.active = True

    def stop(self):
        self.last_split = time.time() - self._began
        if self.active:
            self._total += self.last_split
            self.active = False
        return self.last_split

    def current(self):
        if self.active:
            return self._total + time.time() - self._began
        else:
            return self._total

    def add(self, seconds):
        self._began -= seconds
