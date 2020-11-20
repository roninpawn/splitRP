from file_handling import *
from ui2 import *
from videostream import *
from time import time, sleep


#   ~~~Define Public Functions~~~
def poi_test(vid_stream, rp_file):
    poi_list = []
    last_matched_tests = []
    prev_frame = []
    dismissed = 0   # Records how many Diff Tests were avoided using Sum Testing.
    total_tests = 0

    # Process ALL frames assigned to worker
    while True:
        eof, frame = vid_stream.read()
        if eof: break

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        if not len(prev_frame): prev_frame = frame  # On first frame only, set last_frame = current frame.
        nomatch_tests = {}
        matched_tests = {}
        last_proc = []

        # Test current frame against ALL possible matches in file.tests.
        for test_name in rp_file.tests:
            test = rp_file.tests[test_name]
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
                # Store no-match percentages exclusively for logging the nearest non-match percentage.
                if test_name not in nomatch_tests.keys() or nomatch_tests[test_name] < similarity:
                    nomatch_tests[test_name] = similarity

            last_proc = [test.color_proc, test.resize, test.crop_area]

        # Only record changes: Don't record same test(s) sequentially. Only if different, or if no match after match.
        if len(matched_tests):
            if matched_tests.keys() != last_matched_tests:
                poi_list.append((vid_stream.cur_frame, True, matched_tests, (prev_frame, frame)))
        elif len(last_matched_tests):   # If no matched tests in wake of matched tests.
            out_tests = {}
            for test_name in last_matched_tests:  # Return best match from no_matches.
                out_tests[test_name] = nomatch_tests[test_name]
            poi_list.append((vid_stream.cur_frame, False, out_tests, (prev_frame, frame)))

        last_matched_tests = matched_tests.keys()
        prev_frame = frame

    sleep(.1)  # Makes space for clean console logging.
    print(f"\nStored {len(poi_list)} frame events. Dismissed {dismissed} of {total_tests}"
          f"({round(100 * (dismissed / total_tests), 2)}%) by sum-testing.")
    return poi_list


class LogEvent:
    def __init__(self, match_cycle, matched, frame, event_name, match_percent, actions_taken, log_images):
        self.name = event_name
        self.actions = actions_taken
        self.cycle = match_cycle
        self.matched = matched
        self.percent = match_percent
        self.frame = frame
        self.log_images = log_images

    def as_string(self):
        if self.matched:
            prepend = "Frame" if self.cycle else "     "
            per = f"{'{0:.2f}'.format(self.percent)}%"
        else:
            prepend = "    -"
            per = f"({'{0:.2f}'.format(self.percent)}%)"
        return f"{prepend} {self.frame} with {per} in *{self.name}* did '{', '.join(self.actions)}'"


class Logger:
    def __init__(self):
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
    
    def add_log_event(self, log_event):
        self.run_log.append([self.event_num, log_event])
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
        for num, event in self.run_log:
            pre_frame, match_frame = event.log_images
            cv2.imwrite(f'runlog/{num}a.png', pre_frame)
            cv2.imwrite(f'runlog/{num}b.png', match_frame)
            
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
            first = self.run_log[start][1].frame   # Frame that event occurred.
            waste = 0
            waste_first = 0
            num = 1

            for x in range(start, end+1, 1):
                event = self.run_log[x][1]
                actions = event.actions
                now = event.frame

                for action in actions:
                    if action == "split":
                        rta = now - first
                        igt = rta - waste
                        splits.append([num, rta, igt, waste, now - rta])
                        # Reset for new split.
                        first = now
                        waste = 0
                        num += 1
                    elif action == "pause":
                        waste_first = now
                    elif action == "unpause":
                        waste += now - waste_first
        return splits
    
    def print_splits(self, splits, rate):
        if len(self.run_log) == 0:
            return
        sum_rta, sum_igt, sum_waste = 0, 0, 0

        print("--- SPLITS ---   Time|Frames (time by frames)]")
        for split in splits:
            num, rta, igt, waste, start = split

            sum_rta += rta
            sum_igt += igt
            sum_waste += waste

            out = [f"{num} - [{frames_to_hms(sum_rta, rate)} | {sum_rta}] ",
                   f"RTA: {frames_to_hms(rta, rate)} | {rta}",
                   f"IGT: {frames_to_hms(igt, rate)} | {igt}",
                   f"WASTE: {frames_to_hms(waste, rate)} | {waste}"]

            print("{:<30s} {:<28s} {:<28s} {:<28s}".format(*out))

        filler_line = "-------------------"
        print("{:<30s} {:<28s} {:<28s} {:<28s}".format("", filler_line, filler_line, filler_line))

        out = ["SPLIT TOTALS:  ", f"RTA: {frames_to_hms(sum_rta, rate)} | {sum_rta} ",
                                  f"IGT: {frames_to_hms(sum_igt, rate)} | {sum_igt} ",
                                  f"WASTE: {frames_to_hms(sum_waste, rate)} | {sum_waste}"]
        print("{:>30s} {:<28s} {:<28s} {:<28s}".format(*out))


class VideoAnalyzer:
    def __init__(self, video_path=None, rp_path=None, start=0, end=None):
        self.vid_path = video_path
        self.rp_path = rp_path
        self.start_frame = start
        self.end_frame = end
        self.log = Logger()

        if video_path is not None and rp_path is not None:
            self._analyze(video_path, rp_path, start, end)

    def analyze(self, vid_path=None, rp_path=None, start=None, end=None):
        # Public method to allow maximum calling options at instantiation, afterwards, or mixed.
        v = vid_path if vid_path is not None else self.vid_path
        rp = rp_path if rp_path is not None else self.rp_path
        s = start if start is not None else self.start_frame
        e = end if end is not None else self.end_frame

        if v is not None and rp is not None:
            self._analyze(v, rp, s, e)
        else:
            warn("VideoAnalyzer analyze() method requires both vid_path AND rp_path assigned.")

    def _analyze(self, vid_path, rp_path, start, end):
        self.log.reset()
        process_start = time()

        video = VideoStream(vid_path)
        rp_file = FileAccess(rp_path)

        if end is None or end > video.total_frames:
            end = video.total_frames
        total_frames = end - start

        res = video.shape() if rp_file.rescale_values is None else rp_file.rescale_values
        rp_file.convert(xywh2dict(0, 0, res[0], res[1]))
        rp_file.init_packs()
        rp_file.master_crop['left'] += rp_file.translation[0]
        rp_file.master_crop['top'] += rp_file.translation[1]

        video.config(start, end, dict2xywh(rp_file.master_crop))
        video.open_stream()

        rounded_frame_rate = round(video.frame_rate, 3)
        print(f"\r\nVideo analysis of {total_frames} frames in {vid_path} @ ~{rounded_frame_rate}fps now running.")
        poi_list = poi_test(video, rp_file)
        print(f"[Generated poi_list in: {secs_to_hms(time() - process_start)} seconds.]")

        self._map_splits(poi_list, rp_file.first_pack)
        self.log.generate(video.frame_rate)

        va_win.pop_splits(self.log.splits, video.frame_rate)
        print(f"\r\nVideo analysis of {total_frames} frames in {vid_path} @ ~{rounded_frame_rate}fps complete.")
        print(f"Full Analysis took: {secs_to_hms(time() - process_start)} of duration: "
              f"{secs_to_hms(total_frames / video.frame_rate)}")

    def _map_splits(self, poi_list, cur_pack):
        def log_it(matched, percent, actions):
            self.log.add_log_event(LogEvent(cycle, matched, frame, cur_pack.name, percent, actions, log_images))
            # (un/match cycle, match made, frame number, pack_name, best match %, actions taken, logging images)

        cycle = True
        cur_match = ""
        for frame, match, tests, log_images in poi_list:
            if cycle:
                if match:  # If match-cycle and match found.
                    for match_test in cur_pack.match_tests:
                        if match_test.name in tests.keys():
                            cur_match = match_test.name
                            log_it(True, tests[cur_match], cur_pack.match_actions)
                            cycle = False
            else:
                if match:  # If unmatch-cycle and match found.
                    if cur_pack.unmatch_packs is not None:
                        for pack in cur_pack.unmatch_packs:
                            for unmatch_test in pack.match_tests:
                                if unmatch_test in tests:
                                    log_it(True, tests[unmatch_test], cur_pack.unmatch_actions)
                                    cur_pack = pack

                else:  # If unmatch-cycle and no match found.
                    log_it(False, tests[cur_match], cur_pack.nomatch_actions)
                    cycle = True
                    cur_pack = cur_pack.nomatch_pack


#   ~~~Instantiate Objects~~~
settings = SettingsAccess("settings.cfg")
analyzer = VideoAnalyzer(rp_path='clustertruck.rp')

#   ~~~Let's Go!~~~
va_win = MainUI(analyzer)
va_win.mainloop()
