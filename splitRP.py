import keyboard
import multiprocessing as multiproc
from file_handling import *
from ui2 import *
from functools import partial


#   ~~~Define Public Functions~~~
def mp_test(vid_path, rp_path, start, end):   # Initiates multiprocessing and returns Points of Interest list.
    poi_list = []
    if __name__ == "__main__":
        total_workers = multiproc.cpu_count()
        mp_pool = multiproc.Pool(total_workers)
        poi_func = partial(poi_test, vid_path, rp_path, start, end)   # Necessary for static + iterable args.
        poi_list = mp_pool.map(poi_func, range(total_workers))
        mp_pool.close()
        mp_pool.join()

        poi_list = [j for sub in poi_list for j in sub]     # Flattens 3d list to 2d list
    return poi_list


def poi_test(vid_path, file_path, start, end, worker_num):
    video = cv2.VideoCapture(vid_path)   # Each worker instantiates it's own hook to video and a new FileAccess object.
    file = FileAccess(file_path)

    total_frames = end - start           # Each worker calculates it's own job-scope based on it's worker-number.
    total_workers = multiproc.cpu_count()
    frames_per_worker = floor(total_frames / total_workers)
    start = start + (worker_num * frames_per_worker)
    end = start + frames_per_worker

    if file.rescale_values is None:      # Pattern file's values / tests / images are conformed to the video properties.
        res = int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    else:
        res = file.rescale_values
    file.convert(xywh2dict(0, 0, res[0], res[1]))
    file.init_packs()
    file.master_crop['left'] += file.translation[0]
    file.master_crop['top'] += file.translation[1]
    crop = dict2xywh(file.master_crop)

    video.set(cv2.CAP_PROP_POS_FRAMES, start)   # Move play-head to starting frame.

    poi_list = []
    last_matched_tests = []
    cur_frame = start
    dismissed = 0   # Records how many Diff Tests were avoided using Sum Testing.
    total_tests = 0

    # Process ALL frames assigned to worker
    while cur_frame < end:
        matched_tests = {}
        last_proc = []

        has_frames, frame = video.read()        # Read and prep frame for analysis.
        frame = frame[crop[1]:crop[1] + crop[3], crop[0]:crop[0] + crop[2]]
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)

        # Test current frame against ALL possible matches in file.tests.
        for test_name in file.tests:
            test = file.tests[test_name]
            if last_proc != [test.color_proc, test.resize, test.crop_area]:     # Don't reprocess frame if unnecessary.
                shot = processing(frame, test.color_proc, test.resize, test.crop_area)
                shot_sum = int(np.sum(shot))

            for img, img_sum, max in test.images:      # Test frame against each image in current test.
                total_tests += 1
                similarity = 100 * (1 - ((abs(shot_sum - img_sum)) / max))  # Sum Test ( >2x faster than Diff Test.)

                if similarity >= test.match_percent:   # Diff Test - Is the sum of a difference map similar?
                    diff_map = cv2.absdiff(img, shot)  # Composite images into difference map.
                    similarity = 100 * (1 - ((np.sum(diff_map)) / max))

                    if similarity >= test.match_percent:
                        matched_tests[test_name] = similarity     # Generate dict of matching tests for each frame.
                        break
                else:
                    dismissed += 1

            last_proc = [test.color_proc, test.resize, test.crop_area]

        if len(matched_tests) and matched_tests != last_matched_tests \
                or len(last_matched_tests) and not len(matched_tests):  # Only record changes. So, if the same test(s)
            poi_list.append((cur_frame, matched_tests))                 # match sequentially, don't record it. But if
                                                                        # different test(s) match, or no match found
        last_matched_tests = matched_tests                              # in wake of matches, make a new record.
        cur_frame += 1

    video.release()
    # print(f"Worker #{worker_num} stored {len(poi_list)} frame events. Dismissed {dismissed} of {total_tests}"
    #       f"({round(100 * (dismissed / total_tests), 2)}%) by sum-testing.")
    return poi_list


#   ~~~Define Classes~~~
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


class LogEvent:
    def __init__(self, match_cycle, frame, event_name, match_percent, actions_taken):
        self.time = time.time()
        self.name = event_name
        self.actions = actions_taken
        self.cycle = match_cycle
        self.percent = match_percent
        self.frame = frame

    def as_string(self):
        return f"Frame {self.frame} with {'{0:.2f}'.format(self.percent)}% in " \
               f"*{self.name}* did '{', '.join(self.actions)}'"


class Logger:
    def __init__(self, log_mode=2):
        self.log_mode = log_mode
        self.splits = []
        self.reset()
        
    def reset(self):       
        self.event_num = 0.0
        self.run_log = []
        
    def generate(self, frame_rate):
        self.output_log(frame_rate)
        self.splits = self.gen_splits()
        self.print_splits(self.splits, frame_rate)
        #self.write_images()
    
    def log_event(self, cycle, frame, name, percent, actions):
        new_log = LogEvent(cycle, frame, name, percent, actions)
        self.run_log.append([self.event_num, new_log])
        self.event_num += 0.5

    def output_log(self, frame_rate):
        if len(self.run_log) != 0:
            last, cnt, dur = 0, 0, 0.0
            print("\r\n--- RUN LOG ---")
            for num, event in self.run_log:
                cnt = event.frame - last
                out = [f"{num}: ", f"{frames_to_hms(cnt, frame_rate)} ({cnt})", f"| {event.as_string()}"]
                print("{:<6s} {:<16s} {:<100s}".format(*out))
                last = event.frame
            print(f"--- LOG END ---\r\n")

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
                        splits.append([num, rta, igt, waste, now[0] - rta[0]])
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

        print("--- SPLITS ---   Time|Frames (time by frames)]")
        for split in splits:
            num, rta, igt, waste, start = split

            sum_rta = (sum_rta[0] + rta[0], sum_rta[1] + rta[1])
            sum_igt = (sum_igt[0] + igt[0], sum_igt[1] + igt[1])
            sum_waste = (sum_waste[0] + waste[0], sum_waste[1] + waste[1])

            out = [f"{num} - [{frames_to_hms(sum_rta[0], rate)} | {sum_rta[0]}] ",
                   f"RTA: {frames_to_hms(rta[0], rate)} | {rta[0]}",
                   f"IGT: {frames_to_hms(igt[0], rate)} | {igt[0]}",
                   f"WASTE: {frames_to_hms(waste[0], rate)} | {waste[0]}"]

            print("{:<30s} {:<28s} {:<28s} {:<28s}".format(*out))

        filler_line = "-------------------"
        print("{:<30s} {:<28s} {:<28s} {:<28s}".format("", filler_line, filler_line, filler_line))

        out = ["SPLIT TOTALS:  ", f"RTA: {frames_to_hms(sum_rta[0], rate)} | {sum_rta[0]} ",
                                  f"IGT: {frames_to_hms(sum_igt[0], rate)} | {sum_igt[0]} ",
                                  f"WASTE: {frames_to_hms(sum_waste[0], rate)} | {sum_waste[0]}"]
        print("{:>30s} {:<28s} {:<28s} {:<28s}".format(*out))


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
        if __name__ == "__main__":
            self.frame_rate = 1
            self.log = Logger()
            # self.key_input = KeyInput()

            self.reset()

            # Wait for first screenshot to be captured:

            self.va_win = VideoAnalyzer(self)
            self.va_win.mainloop()
            print("Started and ready...")

    def reset(self):
        self.log.generate(self.frame_rate)
        self.log.reset()

        self.cur_pack = file.first_pack
        self.cycle = True

    def analyze(self, poi_list):
        def draw_it(frame, color):
            self.va_win.timeline.add_cursor(frame, frame)
            self.va_win.timeline.cursors[frame].configure(bg=color, width=1)
            self.va_win.timeline.cursors[frame].disable()

        for frame, tests in poi_list:
            match = bool(len(tests))
            if self.cycle:
                if match:
                    for match_test in self.cur_pack.match_tests:
                        if match_test.name in tests.keys():
                            # cycle, frame, pack_name, match percent, actions
                            draw_it(frame, 'green')
                            self.log.log_event(self.cycle, frame, self.cur_pack.name, tests[match_test.name],
                                               self.cur_pack.match_actions)
                            self.cycle = False
            else:
                if match:
                    if self.cur_pack.unmatch_packs is not None:
                        for pack in self.cur_pack.unmatch_packs:
                            for unmatch_test in pack.match_tests:
                                if unmatch_test in tests:
                                    draw_it(frame, 'pink')
                                    self.log.log_event(self.cycle, frame, self.cur_pack.name, tests[unmatch_test],
                                                       self.cur_pack.unmatch_actions)
                                    self.cur_pack = pack
                else:
                    draw_it(frame, 'purple')
                    self.log.log_event(self.cycle, frame, self.cur_pack.name, 0, self.cur_pack.nomatch_actions)
                    self.cycle = True
                    self.cur_pack = self.cur_pack.nomatch_pack

    def video(self, vid_path, start=0, end=None):
        self.reset()
        process_timer = Timer()
        process_timer.start()

        video = cv2.VideoCapture(vid_path)
        self.frame_rate = round(video.get(cv2.CAP_PROP_FPS), 2)
        total_frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
        video.release()

        if end is None or end > total_frames:
            end = total_frames
        total_frames = end - start

        print(f"\r\nVideo analysis of {total_frames} frames in {vid_path} @ {self.frame_rate}fps now running.")
        poi_list = mp_test(vid_path, file.path, start, end)
        print(f"POI list contains {len(poi_list)} frame events. [Generated in: {secs_to_hms(process_timer.now())}]")

        file.init_packs()
        self.cur_pack = file.first_pack
        self.analyze(poi_list)
        self.log.generate(self.frame_rate)

        self.va_win.pop_splits(self.log.splits, self.frame_rate)
        print(f"\r\nVideo analysis of {total_frames} frames in {vid_path} @ {self.frame_rate}fps complete.")
        print(f"Analysis took: {secs_to_hms(process_timer.now())} of duration: "
              f"{secs_to_hms(total_frames / self.frame_rate)}")
        process_timer.stop()


#   ~~~Instantiate Objects~~~
settings = SettingsAccess("settings.cfg")
file = FileAccess('clustertruck.rp')        # NEEDS INSTANTIATED IN OBJECT W/ RESET ACROSS MULTIPLE TESTS.

#   ~~~Let's Go!~~~
engine = Engine()
