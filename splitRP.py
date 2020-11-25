from file_handling import *
from ui2 import *
from videostream import *
from time import time, sleep
import datetime
import base64
import webbrowser

splitrp_version = "VMT-0.11.25a"


#   ~~~Public Functions~~~
def poi_test(vid_stream, tests):
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
        for test_name in tests:
            test = tests[test_name]
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
                if test_name in last_matched_tests:
                    if test_name not in nomatch_tests.keys() or nomatch_tests[test_name] < similarity:
                        nomatch_tests[test_name] = similarity

            last_proc = [test.color_proc, test.resize, test.crop_area]

        # Only record changes: Don't record same test(s) sequentially. Only if different, or if no match after match.
        if len(matched_tests):
            if matched_tests.keys() != last_matched_tests:
                poi_list.append((vid_stream.cur_frame, True, matched_tests, [prev_frame, frame]))
        elif len(last_matched_tests):   # If no matched tests in wake of matched tests.
            out_tests = {}
            for test_name in last_matched_tests:  # Return best match from no_matches.
                out_tests[test_name] = nomatch_tests[test_name]
            poi_list.append((vid_stream.cur_frame, False, out_tests, [prev_frame, frame]))

        last_matched_tests = matched_tests.keys()
        prev_frame = frame

    return poi_list, total_tests, dismissed


def square_resize(img, max_dim):
    dim = img.shape
    larger_dim = dim[0] if dim[0] > dim[1] else dim[1]
    percent = max_dim / larger_dim
    dim = (int(dim[1] * percent), int(dim[0] * percent))
    return cv2.resize(img, dim, interpolation=cv2.INTER_AREA)


#   ~~~Classes~~~
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


class Split:
    def __init__(self, split_num, event_nums, start_frame, rta, igt, waste, sum_rta, sum_igt, sum_waste, images):
        self.num = split_num
        self.events = event_nums
        self.start = start_frame
        self.rta = rta
        self.igt = igt
        self.waste = waste
        self.sum_rta = sum_rta
        self.sum_igt = sum_igt
        self.sum_waste = sum_waste
        self.images = images


class Logger:
    def __init__(self):
        self.splits = []
        self.reset()
        
    def reset(self):       
        self.event_num = 0.0
        self.run_log = []
        self.full_log = ""

    def print(self, str):
        self.full_log += str + "\r\n"
        print(str)

    def generate(self, frame_rate):
        self.output_log(frame_rate)
        self.splits = self.gen_splits()
        self.print_splits(self.splits, frame_rate)
        self.write_images()
    
    def add_log_event(self, log_event):
        self.run_log.append([self.event_num, log_event])
        self.event_num += 0.5

    def output_log(self, frame_rate):
        out = ""
        if len(self.run_log) != 0:
            last, cnt, dur = 0, 0, 0.0
            out += "\r\n--- RUN LOG ---\r\n"
            for num, event in self.run_log:
                cnt = event.frame - last
                line = [f"{num}: ", f"{frames_to_hms(cnt, frame_rate)} ({cnt})", f"| {event.as_string()}"]
                out += "{:<6s} {:<16s} {:<100s}\r\n".format(*line)
                last = event.frame
            out += f"--- LOG END ---\r\n"
        self.print(out)

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
            last_images = self.run_log[start][1].log_images
            last_event = start
            waste, waste_first = 0, 0
            sum_rta, sum_igt, sum_waste = 0, 0, 0
            num = 1

            for x in range(start, end+1, 1):
                event = self.run_log[x][1]
                actions = event.actions
                now = event.frame

                for action in actions:
                    if action == "split":
                        rta = now - first
                        igt = rta - waste
                        sum_rta += rta
                        sum_igt += igt
                        sum_waste += waste
                        images = last_images + event.log_images
                        events = (self.run_log[last_event][0], self.run_log[x][0])
                        splits.append(Split(num, events, now - rta, rta, igt, waste, sum_rta, sum_igt, sum_waste, images))
                        last_images = event.log_images

                        # Reset for new split.
                        first = now
                        waste = 0
                        num += 1
                    elif action == "pause":
                        waste_first = now
                    elif action == "unpause":
                        waste += now - waste_first
                        last_images = event.log_images
                        last_event = x
        return splits
    
    def print_splits(self, splits, rate):
        if len(splits):
            out = "--- SPLITS ---   Time|Frames (time by frames)]\r\n"
            for split in splits:
                line = [f"{split.num} - [{frames_to_hms(split.sum_rta, rate)} | {split.sum_rta}] ",
                        f"RTA: {frames_to_hms(split.rta, rate)} | {split.rta}",
                        f"IGT: {frames_to_hms(split.igt, rate)} | {split.igt}",
                        f"WASTE: {frames_to_hms(split.waste, rate)} | {split.waste}"]

                out += "{:<30s} {:<28s} {:<28s} {:<28s}\r\n".format(*line)

            filler_line = "-------------------"
            out += "{:<30s} {:<28s} {:<28s} {:<28s}\r\n".format("", filler_line, filler_line, filler_line)

            split = splits[-1]
            line = ["SPLIT TOTALS:  ", f"RTA: {frames_to_hms(split.sum_rta, rate)} | {split.sum_rta} ",
                                       f"IGT: {frames_to_hms(split.sum_igt, rate)} | {split.sum_igt} ",
                                       f"WASTE: {frames_to_hms(split.sum_waste, rate)} | {split.sum_waste}"]
            out += "{:>30s} {:<28s} {:<28s} {:<28s}\r\n".format(*line)
            self.print(out)

    def to_html(self):
        html = open("log_template.html", 'r')

        rate = analyzer.videostream.frame_rate      # Get frame rate for frame-to-time conversions.
        with open(analyzer.rp_path, 'r') as f:      # Store raw text of rp_file for output.
            pattern_str = f.read()

        # Dictionary of all top-level replacement values to overwrite in the HTML template.
        html_dict = {
            "rp_version": splitrp_version,
            "rp_date": datetime.datetime.now().strftime("%B %d, %Y"),
            "rp_time": datetime.datetime.now().strftime("%I:%M:%S %p"),
            "rp_runner": "Not Named",
            "rp_moderator": "Not Named",
            "rp_category": "None Given",
            "rp_segment": "None Given",

            "rp_vidname": os.path.split(analyzer.vid_path)[1],
            "rp_vidpath": analyzer.vid_path,
            "rp_totalhms": frames_to_hms(analyzer.videostream.total_frames, rate),
            "rp_totalframes": analyzer.videostream.total_frames,
            "rp_resolution": f"{analyzer.videostream.resolution[0]} x {analyzer.videostream.resolution[1]}",
            "rp_framerate": rate,
            "rp_roundframerate": round(rate, 2),

            "rp_patternfile": os.path.split(analyzer.rp_path)[1],
            "rp_startframe": analyzer.videostream.start,
            "rp_endframe": analyzer.videostream.end,
            "rp_procframes": analyzer.videostream.frame_range,
            "rp_prochms": frames_to_hms(analyzer.videostream.frame_range, rate),
            "rp_screenshotarea": analyzer.videostream.shape(),
            "rp_translation": analyzer.rp_file.translation,
            "rp_nestedscale": analyzer.rp_file.rescale_values,

            "rp_totaltests": analyzer.test_count,
            "rp_testsdismissed": analyzer.dismissed_count,
            "rp_dismissedpercent": f"{round(100 * (analyzer.dismissed_count / analyzer.test_count), 2)}%",
            "rp_poicount": len(analyzer.poi_list),
            "rp_testshms": secs_to_hms(analyzer.time_tests),

            "rp_splitscount": len(self.splits),
            "rp_totalrtahms": frames_to_hms(self.splits[-1].sum_rta, rate, True),
            "rp_totalrtaframes": self.splits[-1].sum_rta,
            "rp_totaligthms": frames_to_hms(self.splits[-1].sum_igt, rate, True),
            "rp_totaligtframes": self.splits[-1].sum_igt,
            "rp_totalwastehms": frames_to_hms(self.splits[-1].sum_waste, rate, True),
            "rp_totalwasteframes": self.splits[-1].sum_waste,

            "rp_logpath": resource_path("runlog/"),
            "rp_consolelog": self.full_log,
            "rp_patterncontents": pattern_str
        }

        lines = []
        for line in html:   # Replace all html_dict matches.
            for key, value in html_dict.items():
                line = line.replace(f"%{key}%", str(value))
            lines.append(line)
        html.close()

        top, bottom = -1, -1    # str.find() returns -1 if not found.
        for i in range(len(lines)):     # Find top and bottom of splits are for duplication.
            if lines[i].find("%rp_splittop%") != -1:
                top = i
            if lines[i].find("%rp_splitbottom%") != -1:
                bottom = i

        if top != -1 and bottom != -1:
            split_out = []

            for split in self.splits:
                thumbnails = []
                for img in split.images:    # Scale and convert run_log images to base64 to embed as in-line HTML.
                    thumbnail = square_resize(img, 100)
                    is_success, im_buf_arr = cv2.imencode('.jpg', thumbnail)
                    byte_im = im_buf_arr.tobytes()
                    thumbnails.append(base64.b64encode(byte_im).decode())

                # Dictionary of split-level replacement values to overwrite in the splits duplication.
                split_dict = {
                    "rp_splittop": "",
                    "rp_splitbottom": "",
                    "rp_splitnum": split.num,
                    "rp_eventnums": split.events,
                    "rp_rtahms": frames_to_hms(split.rta, rate),
                    "rp_rtaframes": split.rta,
                    "rp_igthms": frames_to_hms(split.igt, rate),
                    "rp_igtframes": split.igt,
                    "rp_wastehms": frames_to_hms(split.waste, rate),
                    "rp_wasteframes": split.waste,
                    "rp_sumrtahms": frames_to_hms(split.sum_rta, rate),
                    "rp_sumrtaframes": split.sum_rta,
                    "rp_sumigthms": frames_to_hms(split.sum_igt, rate),
                    "rp_sumigtframes": split.sum_igt,
                    "rp_sumwastehms": frames_to_hms(split.sum_waste, rate),
                    "rp_sumwasteframes": split.sum_waste,
                    "rp_inprevthumb": f'<img src="data:image/png;base64, {thumbnails[0]}"/>',
                    "rp_inprevlink": f"runlog/{split.events[0]}a.png",
                    "rp_inthumb": f'<img src="data:image/png;base64, {thumbnails[1]}"/>',
                    "rp_inlink": f"runlog/{split.events[0]}b.png",
                    "rp_frameprevthumb": f'<img src="data:image/png;base64, {thumbnails[2]}"/>',
                    "rp_frameprevlink": f"runlog/{split.events[1]}a.png",
                    "rp_framethumb": f'<img src="data:image/png;base64, {thumbnails[3]}"/>',
                    "rp_framelink": f"runlog/{split.events[1]}b.png",
                }

                split_in = lines[top:bottom + 1]
                for line in split_in:       # Replace all split_dict matches.
                    for key, value in split_dict.items():
                        line = line.replace(f"%{key}%", str(value))
                    split_out.append(line)
            lines = lines[:top] + split_out + lines[bottom + 1:]    # Re-assemble HTML, inserting all splits.

        with open("log_out.html", 'w') as out:  # Write everything to a new HTML file.
            out.writelines(lines)

        webbrowser.open("log_out.html", 1)      # Open log file in default browser.


class VideoAnalyzer:
    def __init__(self, video_path=None, rp_path=None, start=0, end=None):
        self.vid_path = video_path
        self.rp_path = rp_path
        self.start_frame = start
        self.end_frame = end
        self.log = Logger()

        self.videostream, self.rp_file = None, None
        self.test_count, self.dismissed_count = 0, 0
        self.poi_list = []
        self.time_configure, self.time_tests, self.time_complete = 0.0, 0.0, 0.0

        if video_path is not None and rp_path is not None:
            self._analyze(video_path, rp_path, start, end)

    def analyze(self, vid_path=None, rp_path=None, start=None, end=None):
        # Public method to allow maximum calling options at instantiation, afterwards, or mixed.
        if vid_path is not None: self.vid_path = vid_path
        if rp_path is not None: self.rp_path = rp_path
        if start is not None: self.start_frame = start
        if end is not None: self.end_frame = end

        if self.vid_path is not None and self.rp_path is not None:
            self._analyze(self.vid_path, self.rp_path, self.start_frame, self.end_frame)
        else:
            warn("VideoAnalyzer analyze() method requires both vid_path AND rp_path assigned.")

    def _analyze(self, vid_path, rp_path, start, end):
        self.log.reset()
        process_start = time()

        self.videostream = VideoStream(vid_path)
        self.rp_file = FileRP(rp_path)

        if end is None or end > self.videostream.total_frames: end = self.videostream.total_frames
        frame_range = end - start

        # Scales stored images to conform either if different resolutions or nested video indicated in .rp file.
        res = self.videostream.shape() if self.rp_file.rescale_values is None else self.rp_file.rescale_values
        self.rp_file.convert(*res)
        if self.rp_file.odd_warning:
            self.log.print(f"WARNING:\n"
                           f"'ScreenshotArea' in {os.path.split(self.rp_path)[1]} contains ODD 'width' and/or 'height.'"
                           f"\n Adjusting value(s) to next lower EVEN integer. {self.rp_file.master_crop[2:]}")
        self.rp_file.init_packs()

        # Translates FFmpeg video if nested video indicated in .rp file.
        live_crop = self.rp_file.master_crop
        live_crop[0] += self.rp_file.translation[0]
        live_crop[1] += self.rp_file.translation[1]

        self.videostream.config(start, end, live_crop)
        self.videostream.open_stream()

        rounded_frame_rate = round(self.videostream.frame_rate, 3)
        self.log.print(f"\r\nVideo analysis of {frame_range} frames in {vid_path} @ ~{rounded_frame_rate}fps now running.")
        self.time_configure = time() - process_start
        self.poi_list, self.test_count, self.dismissed_count = poi_test(self.videostream, self.rp_file.tests)
        self.time_tests = time() - process_start - self.time_configure
        sleep(.1)  # Makes space for clean console logging.

        self.log.print(f"\r\nStored {len(self.poi_list)} frame events. Dismissed {self.dismissed_count} of "
                       f"{self.test_count} ({round(100 * (self.dismissed_count / self.test_count), 2)}%) by sum-test.")
        self.log.print(f"[Generated poi_list in: {secs_to_hms(self.time_tests)} seconds.]")

        self._map_splits(self.poi_list, self.rp_file.first_pack)
        self.log.generate(self.videostream.frame_rate)

        va_win.pop_splits(self.log.splits, self.videostream.frame_rate)
        self.time_complete = time() - process_start
        self.log.print(f"Video analysis of {frame_range} frames in {vid_path} @ ~{rounded_frame_rate}fps complete.")
        self.log.print(f"Full Analysis took: {secs_to_hms(self.time_complete)} of duration: "
                       f"{secs_to_hms(frame_range / self.videostream.frame_rate)}")
        self.log.to_html()

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
settings = FileSettings("settings.cfg")
analyzer = VideoAnalyzer(rp_path='clustertruck.rp')

#   ~~~Bring up the UI~~~
va_win = MainUI(analyzer, settings)
va_win.mainloop()
