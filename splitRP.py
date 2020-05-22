import socket
from select import select as select
import mss
import mss.tools
import keyboard
from file_handling import *
from ui2 import *


#   ~~~Define Public Functions~~~
def compare(img1, img2):
    composite = cv2.absdiff(img1, img2)         # Composite images into difference map.
    shape = np.shape(composite)                 # [Pixel height, width, (color channels)]
    color_channels = 1 if len(shape) == 2 else shape[2]
    depth = 255         # depth ought to be resolved based on data type? (uint8 = 255, float = 1?)
    similarity = 100 * (1 - ((np.sum(composite) / depth) / (shape[0] * shape[1] * color_channels)))

    return similarity


def time_to_hms(t):
    return f"{time.strftime('%H:%M:%S', time.localtime(t))}.{repr(t).split('.')[1][:3]}"


def secs_to_hms(dur):
    if dur <= 0:
        return "0.000"
    else:
        h = dur // 3600
        dur -= h * 3600
        m, s = divmod(int(dur), 60)
        ms = '{:.03f}'.format(dur)[-3:]
        out = f"{h}:" if h > 0 else ""
        out += f"{'{:02d}'.format(m)}:{'{:02d}'.format(s)}.{ms}" if m > 0 else f"{s}.{ms}"
        return out


def frames_to_hms(f, rate):
    return secs_to_hms(f / rate)


#   ~~~Define Classes~~~
class LivesplitClient(socket.socket):
    def __init__(self, host=None, port=16834, timeout=3):
        self.host, self.port = None, None
        self.connected = False
        self._lastattempt = time.time() - timeout
        self.attempt = 1

        if host is not None:
            self.connect(host, port, timeout)

    def connect(self, host, port=16834, timeout=3):
        if time.time() - self._lastattempt > timeout:
            if self.connected: self.close()
            super().__init__(socket.AF_INET, socket.SOCK_STREAM)
            self.setblocking(False)

            self.connect_ex((host, port))
            ready_to_read, ready_to_write, in_error = select([], [self], [], 0)
            if not ready_to_write:
                self.connected = False
                self._lastattempt = time.time()
                self.attempt += 1
            else:
                self.host, self.port = host, port
                self.connected = True
                self.attempt = 1
                self.setblocking(True)
        return self.connected

    def send(self, *args):
        try:
            super().send(*args)
        except:
            self.connected = False
            return False
        return True

    def recv(self, *args):
        try:
            out = super().recv(*args).decode()
        except:
            out = "Dead Jim"
            self.connected = False
        return out


class Timer:
    def __init__(self, max_stored=250):
        self.slowest = 0.0
        self.started = time.time()
        self._began = None

        self._durations = [0] * max_stored
        self._dur_pointer = 0
        self._dur_count = 0

    def clear(self):
        self._durations = [0] * len(self._durations)
        self._dur_pointer = 0
        self._dur_count = 0
        self.restart()

    def restart(self):
        self.started = time.time()
        self.slowest = 0.0
        self._began = None

    def start(self):
        self.started = time.time()
        self._began = self.started

    def stop(self):
        self.split()
        self._began = None

    def split(self):
        t = time.time()
        if self._began is None:
            self._began = t
            # self.started = t
            return 0.0
        else:
            dur = t - self._began
            if dur > self.slowest:
                self.slowest = dur
            self._durations[self._dur_pointer] = dur

            dur_len = len(self._durations) - 1
            self._dur_pointer = self._dur_pointer + 1 if self._dur_pointer < dur_len else 0
            if self._dur_count < dur_len:
                self._dur_count += 1

            self._began = t
            return dur

    def avg(self, of_last=None):
        if of_last is None or of_last > self._dur_count or of_last < 1:
            s = sum(self._durations)
            c = self._dur_count
        else:
            of_last = int(of_last)
            c = of_last
            if of_last > self._dur_pointer:
                s = sum(self._durations[0:self._dur_pointer]) + sum(self._durations[-(of_last - self._dur_pointer):])
            else:
                s = sum(self._durations[self._dur_pointer - of_last:self._dur_pointer])
        if c == 0:
            return 1.0
        return s / c

    def now(self):
        if self._began is not None:
            return time.time() - self._began
        else:
            return time.time() - self.started

    def all(self):
        return copy.copy(self._durations)

    def last(self):
        return self._durations[self._dur_pointer-1]

    def active(self):
        return True if self._began is not None else False


class ScreenShot:
    def __init__(self, area=None, monitor=1, *kwargs):
        with mss.mss() as self.sct:
            self.monitor_list = self.sct.monitors
            self.monitor = self.monitor_list[monitor]
            if area is None:
                area = self.monitor
            self.set_crop(area)

    def shot(self):
        return np.array(self.sct.grab(self.cap_area))

    def set_crop(self, area, monitor=None):
        if monitor is not None:
            self.monitor = self.sct.monitors[monitor]
        self.cap_area = xywh2dict(
            self.monitor["left"] + area["left"], self.monitor["top"] + area["top"], area["width"], area["height"]
        )


class LogEvent:
    def __init__(self, event_name, actions_taken, match_cycle, match_results, frame, frame_rate):
        self.time = time.time()
        self.name = event_name
        self.actions = actions_taken
        self.cycle = match_cycle
        self.result = match_results[0]
        self.best = match_results[1]
        self.worst = match_results[2]
        self.image = match_results[3]
        self.frame = frame
        self.frame_rate = frame_rate

    def as_string(self):
        return f"Frame {self.frame} with {'{0:.2f}'.format(self.best)}%({'{0:.2f}'.format(self.worst)}%) " \
               f"@ {'{0:.1f}'.format(1 / self.frame_rate)}fps] | " \
               f"{self.name} did '{', '.join(self.actions)}' [{time_to_hms(self.time)}]"


class Logger:
    def __init__(self, img_limit=150):
        self.img_limit = img_limit
        self.event_num = 0.0
        self.run_log = []
        self.splits = []
        self.reset()
        
    def reset(self):       
        self.event_num = 0.0
        self.run_log = []
        
    def generate(self, frame_rate):
        self.output_log(frame_rate)
        self.splits = self.gen_splits()
        self.print_splits(self.splits, frame_rate)
        self.write_images()
    
    def log_event(self, name, actions, cycle, results, frame, frame_rate, last_img, cur_img):
        new_log = LogEvent(name, actions, cycle, results, frame, frame_rate)
        images = [last_img, cur_img] if self.event_num < self.img_limit else None
        self.run_log.append([self.event_num, new_log, images])
        prepend = f"{int(self.event_num)}:" if cycle else "  -"
        print(prepend, new_log.as_string())
        self.event_num += 0.5

    def output_log(self, frame_rate):
        if len(self.run_log) != 0:
            last, cnt, dur = 0, 0, 0.0
            out = "\r\n--- RUN LOG ---\r\n"
            # for num, name, cycle, best, actions, frame, fps, t, img_list in self.run_log:
            for num, event, images in self.run_log:
                cnt = event.frame - last
                out += f"{num}: {cnt} ({frames_to_hms(cnt, 1 / event.frame_rate)}) | {event.as_string()}\r\n"
                last = event.frame
            print(out + f"--- LOG END ---\r\n")

    def write_images(self):
        if file.runlog:
            for num, event, images in self.run_log:
                if images is not None:
                    cv2.imwrite(f'runlog/{num}a.png', images[0])
                    cv2.imwrite(f'runlog/{num}b.png', images[1])
                    if file.runlog == 2:
                        cv2.imwrite(f'runlog/{num}c.png', event.image)
            
    def gen_splits(self):
        splits = []

        def search(start, end, inc, match):
            for x in range(start, end, inc):
                for action in self.run_log[x][1].actions:
                    if action == match:
                        return x
            return None

        # Limit calculations to events that happen between the start and final split.
        start = search(0, len(self.run_log), 1, "start")
        end = search(len(self.run_log)-1, -1, -1, "split")

        # Tally the frame-counts of RTA, IGT, and WASTE timing, for all runs in the log.
        if start is not None and end is not None:
            first = (self.run_log[start][1].frame, self.run_log[start][1].time)   # (Frame, Time) that event occurred.
            waste = (0, 0.0)
            waste_first = (0, 0.0)
            num = 1

            for x in range(start, end+1, 1):
                event = self.run_log[x][1]
                actions = event.actions
                now = (event.frame, event.time)

                for action in actions:
                    if action == "split":
                        rta = (now[0] - first[0], now[1] - first[1])
                        igt = (rta[0] - waste[0], rta[1] - waste[1])
                        splits.append([num, rta, igt, waste])
                        # Reset for new split.
                        first = now
                        waste = (0, 0.0)
                        num += 1
                    elif action == "pause":
                        waste_first = (now[0], now[1])
                    elif action == "unpause":
                        waste = (waste[0] + (now[0] - waste_first[0]), waste[1] + (now[1] - waste_first[1]))
        return splits
    
    def print_splits(self, splits, rate):
        if len(self.run_log) == 0:
            return
        sum_rta, sum_igt, sum_waste = (0, 0.0), (0, 0.0), (0, 0.0)
        sum_drop = 0

        print("--- SPLITS ---   Time|Frames (time by frames)]")
        for split in splits:
            num, rta, igt, waste = split

            sum_rta = (sum_rta[0] + rta[0], sum_rta[1] + rta[1])
            sum_igt = (sum_igt[0] + igt[0], sum_igt[1] + igt[1])
            sum_waste = (sum_waste[0] + waste[0], sum_waste[1] + waste[1])

            out = [f"{num} - [{secs_to_hms(sum_rta[1])}] ",
                   f"RTA: {secs_to_hms(rta[1])}|{rta[0]} ({secs_to_hms(rta[0] / rate)})",
                   f"IGT: {secs_to_hms(igt[1])}|{igt[0]} ({secs_to_hms(igt[0] / rate)})",
                   f"WASTE: {secs_to_hms(waste[1])}|{waste[0]} ({secs_to_hms(waste[0] / rate)})"]

            frames_dropped = round(rta[1] * rate - rta[0], 1)
            if frames_dropped > 0:
                out.append(f"  -dropped {frames_dropped} frames)")
                sum_drop += frames_dropped
            print("{:<20s} {:<28s} {:<28s} {:<28s}".format(*out))

        out = f"--- SPLIT TOTALS ---\r\n" \
              f"RTA: {secs_to_hms(sum_rta[1])}|{sum_rta[0]} ({secs_to_hms(sum_rta[0] / rate)})   " \
              f"IGT: {secs_to_hms(sum_igt[1])}|{sum_igt[0]} ({secs_to_hms(sum_igt[0] / rate)})   " \
              f"WASTE: {secs_to_hms(sum_waste[1])}|{sum_waste[0]} ({secs_to_hms(sum_waste[0] / rate)})"

        if sum_drop > 0:
            out += f"  DROPPED: {'{0:.1f}'.format(sum_drop)} frames"
        print(out, "\r\n")


class KeyInput:
    def __init__(self):
        self.keys_down = {}
        self.key_hook = keyboard.hook(self.test_hotkey)

    def test_hotkey(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            self.keys_down[event.name] = event.scan_code
        elif event.event_type == keyboard.KEY_UP:
            self.keys_down = {}

        if engine.live_run:
            if self.keys_down == settings.reset_key:
                engine.reset()
                print(f"RESET ({self.keys_down})")
            if self.keys_down == settings.video_key:
                engine.live_run = False


class Engine:
    def __init__(self):
        self.frame_limit = 60
        self.send_queue = ""
        self.drop_frame = False
        self.log_enabled = settings.verbose
        self.live_run = True

        self.log = Logger()
        self.run_timer = Timer()
        self.process_timer = Timer()
        self.shot_timer = Timer()
        self.fps_timer = Timer()
        self.key_input = KeyInput()

        self.reset()

        # Wait for first screenshot to be captured:
        self.rawshot = screen.shot()
        while self.rawshot is None:
            pass
        self.lastshot = self.rawshot

        print("Started and ready...")

    def reset(self):
        self.log.generate(self.frame_limit)
        self.log.reset()

        self.cur_pack = file.first_pack
        self.cycle = True
        self.frame_count = 0

        self.run_timer.clear()
        self.process_timer.clear()
        self.shot_timer.clear()
        self.fps_timer.restart()

    def send(self):
        if self.send_queue != "":
            livesplit.send(self.send_queue.encode())
            self.send_queue = ""

    def multi_test(self, tests, match=True, compare_all=False):
        best, worst = 0.0, 100.0
        result = False
        out_shot, shot = None, None
        last_proc = []

        for test in tests:
            if last_proc != [test.color_proc, test.resize, test.crop_area]:     # Don't reprocess if unnecessary.
                shot = processing(self.rawshot, test.color_proc, test.resize, test.crop_area)
                if out_shot is None: out_shot = shot

            percent = test.match_percent if match else test.unmatch_percent

            for img in test.images:
                similarity = compare(img, shot)
                if similarity > best: best = similarity
                if similarity < worst: worst = similarity

                if similarity >= percent:
                    if not compare_all:
                        return [True, best, worst, shot]
                    else:
                        out_shot = shot
                        result = True
            last_proc = [test.color_proc, test.resize, test.crop_area]

        return [result, best, worst, out_shot]

    def analyze(self, cur_match):
        if self.cycle:  # If Matching Cycle...
            if cur_match[0]:  # If match found...
                if self.live_run:
                    self.send_queue = self.cur_pack.match_send
                    self.run_timer.stop()
                else:
                    self.va_win.timeline.add_cursor(self.frame_count, self.frame_count)
                    self.va_win.timeline.cursors[self.frame_count].configure(bg='green', width=1)
                    self.va_win.timeline.cursors[self.frame_count].disable()
                self.cycle = False
                # name, actions, cycle, results, frame, frame_rate, last_img, cur_img
                self.log.log_event(self.cur_pack.name, self.cur_pack.match_actions, self.cycle, cur_match,
                                   self.frame_count, self.fps_timer.avg(self.frame_limit), self.lastshot, self.rawshot)

        elif not cur_match[0]:  # If UnMatch Cycle and no match found
            if self.cur_pack.unmatch_packs is not None:
                for pack in self.cur_pack.unmatch_packs:
                    match = self.multi_test(pack.match_tests)
                    if match[0]:
                        if self.live_run:
                            self.send_queue = pack.match_send
                        else:
                            self.fps_timer.split()
                            self.va_win.timeline.add_cursor(self.frame_count, self.frame_count)
                            self.va_win.timeline.cursors[self.frame_count].configure(bg='yellow', width=1)
                            self.va_win.timeline.cursors[self.frame_count].disable()
                        self.cur_pack = pack
                        self.log.log_event(self.cur_pack.name, self.cur_pack.match_actions, self.cycle, cur_match,
                                           self.frame_count, self.fps_timer.avg(self.frame_limit), self.lastshot,
                                           self.rawshot)
                        return

            if self.live_run:
                self.send_queue = self.cur_pack.nomatch_send
                self.run_timer.start()
            else:
                self.va_win.timeline.add_cursor(self.frame_count, self.frame_count)
                self.va_win.timeline.cursors[self.frame_count].configure(bg='purple', width=1)
                self.va_win.timeline.cursors[self.frame_count].disable()
            self.cycle = True
            nm_actions = self.cur_pack.nomatch_actions
            self.cur_pack = self.cur_pack.nomatch_pack
            self.log.log_event(self.cur_pack.name, nm_actions, self.cycle, cur_match,
                               self.frame_count, self.fps_timer.avg(self.frame_limit), self.lastshot, self.rawshot)

    def console_logging(self, cur_match, output=False):
        self.fps_timer.split()
        elapsed = time.time() - self.fps_timer.started
        # Per-second output, if enabled.
        if elapsed >= 1.0:
            fps = int(1 / self.fps_timer.avg())
            if output:
                print(f"{self.cur_pack.name}  ({'{0:.2f}'.format(cur_match[1])}%) "
                      f"- FPS: {'{0:.1f}'.format(1 / self.fps_timer.avg(fps))} "
                      f"({'{0:.2f}'.format(elapsed)})   * Shot: "
                      f"{'{0:.4f}'.format(self.shot_timer.avg())} ({'{0:.5f}'.format(self.shot_timer.slowest)})"
                      f"   * Proc: {'{0:.4f}'.format(self.process_timer.avg())} "
                      f"({'{0:.5f}'.format(self.process_timer.slowest)})")
            # Reset timers per second.
            self.process_timer.clear()
            self.shot_timer.clear()
            self.fps_timer.restart()

    def run(self):
        file.convert(screen.monitor)
        file.init_packs()
        screen.set_crop(file.master_crop)

        while self.live_run:
            self.lastshot = self.rawshot        # Hold previous shot for logging.

            self.shot_timer.start()
            self.rawshot = screen.shot()        # Capture current screenshot. (blocking process)
            self.shot_timer.stop()

            self.send()                         # Send signal to livesplit after screen.shot for timing consistency.

            # Test current screenshot against current test pack.
            self.process_timer.start()
            cur_match = self.multi_test(self.cur_pack.match_tests, self.cycle, True)
            self.analyze(cur_match)        # Take action based on cycle and results.
            self.process_timer.stop()

            self.console_logging(cur_match, self.log_enabled)             # Per second logging operations.
            self.frame_count += 1

        # Video processing.
        self.va_win = VideoAnalyzer(self)
        self.va_win.mainloop()

    def video(self, path, start=0, end=None):
        self.reset()
        video = cv2.VideoCapture(path)
        rate = video.get(cv2.CAP_PROP_FPS)
        total_frames = video.get(cv2.CAP_PROP_FRAME_COUNT)

        if end is None or end > total_frames:
            end = total_frames

        total_frames = end - start
        tenth_frames = int(total_frames / 10)
        iter_frames = 1
        self.frame_count = start

        has_frames, frame = video.read()
        video.set(cv2.CAP_PROP_POS_FRAMES, start)
        res = np.shape(frame)

        vid_file = FileAccess('clustertruck.rp')
        vid_file.convert(xywh2dict(0, 0, res[1], res[0]))
        vid_file.init_packs()
        crop = dict2xywh(vid_file.master_crop)
        self.cur_pack = vid_file.first_pack
        self.frame_limit = rate

        vid_timer = Timer()
        vid_timer.start()
        print(f"Video analysis of {path} containing {total_frames} frames @ {rate}fps now running.\r\n")

        while has_frames and video.get(cv2.CAP_PROP_POS_FRAMES) < end:
            if self.frame_count == tenth_frames * iter_frames:
                print(f"\r\n--- {iter_frames * 10}% Complete - {self.frame_count} of {total_frames}")
                iter_frames += 1
            self.frame_count += 1

            frame = frame[crop[1]:crop[1] + crop[3], crop[0]:crop[0] + crop[2]]
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)

            self.rawshot = frame
            cur_match = self.multi_test(self.cur_pack.match_tests, self.cycle, True)
            self.analyze(cur_match)  # Take action based on cycle and results.

            self.lastshot = frame
            has_frames, frame = video.read()
            self.fps_timer.split()

            self.va_win.screen.draw_frame(self.frame_count, 1/5)
            self.va_win.timeline.move_to(self.va_win.timeline.cursors["scrubber"], self.frame_count)
            self.va_win.update()

        vid_timer.stop()
        self.log.generate(rate)
        print(f"\r\nVideo Analysis took: {secs_to_hms(vid_timer.last())} of duration: "
              f"{secs_to_hms(total_frames / rate)}")

        sum_rta, sum_igt, sum_waste = 0, 0, 0
        for split in self.log.splits:
            num, rta, igt, waste = split

            sum_rta = sum_rta + rta[0]
            sum_igt = sum_igt + igt[0]
            sum_waste = sum_waste + waste[0]

            rta_time = frames_to_hms(rta[0], rate)
            igt_time = frames_to_hms(igt[0], rate)
            waste_time = frames_to_hms(waste[0], rate)

            out = f"- {num} -  ({frames_to_hms(sum_rta, rate)} | {frames_to_hms(sum_igt, rate)})\n" \
                  f"          RTA: {rta_time} ({rta[0]})\n" \
                  f"          IGT: {igt_time} ({igt[0]})\n" \
                  f"          WASTE: {waste_time} ({waste[0]})"

            self.va_win.add_data_entry(out)

        out = f"-TOTAL -\n" \
              f"          RTA: {frames_to_hms(sum_rta, rate)} ({sum_rta})\n" \
              f"          IGT: {frames_to_hms(sum_igt, rate)} ({sum_igt})\n" \
              f"          WASTE: {frames_to_hms(sum_waste, rate)} ({sum_waste})"

        self.va_win.add_data_entry(out)

        self.log.reset()


#   ~~~Instantiate Objects~~~
screen = ScreenShot(monitor=1)

settings = SettingsAccess("settings.cfg")
file = FileAccess('clustertruck.rp')

livesplit = LivesplitClient()
engine = Engine()
livesplit.connect("localhost", 16834)

#   ~~~Let's Go!~~~
engine.run()
