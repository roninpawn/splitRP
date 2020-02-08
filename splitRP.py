import time
import socket
from select import select as select
import mss
import mss.tools
import keyboard
from file_handling import *


#   ~~~Define Public Functions~~~
def compare(img1, img2):
    composite = cv2.absdiff(img1, img2)         # Composite images into difference map.
    shape = np.shape(composite)                 # [Pixel height, width, (color channels)]
    color_channels = 1 if len(shape) == 2 else shape[2]
    depth = 255         # depth needs to be resolved based on data type? (uint8 = 255, float = 1?)
    similarity = 100 * (1 - ((np.sum(composite) / depth) / (shape[0] * shape[1] * color_channels)))

    return similarity


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


class FPSTimer:
    def __init__(self, interval=1.0):
        self.fps = 1.0
        self._all_frames = 1.0
        self.interval = interval
        self._began = time.time()
        self.reset()

    def average(self):
        return self._all_frames / (time.time() - self._began)

    def reset(self):
        self._since = time.time()
        self._frame_count = 0

    def update(self):
        self._frame_count += 1
        if time.time() > self._since + self.interval:
            self.fps = self._frame_count / (time.time() - self._since)
            self._all_frames += self._frame_count
            self.reset()
        return self.fps


class ScreenShot():
    def __init__(self, area=None, monitor=1, *kwargs):
        with mss.mss() as self.sct:
            self.monitor_list = self.sct.monitors
            self.monitor = self.monitor_list[monitor]
            if area is None: area = self.monitor
            self.set_crop(area)

    def shot(self):
        self.last_shot = np.array(self.sct.grab(self.cap_area))
        return self.last_shot

    def set_crop(self, area, monitor=None):
        if monitor is not None:
            self.monitor = self.sct.monitors[monitor]
        self.cap_area = xywh2dict(
            self.monitor["left"] + area["left"], self.monitor["top"] + area["top"],area["width"], area["height"]
        )


class Engine:
    def __init__(self):
        self.start = time.time()
        self.seek_time = time.time()
        self.cycle = True
        self.cur_match = [True, 0.0, 100.0]
        self.cur_pack = file.first_pack
        self.split_num = 0.0
        self.image_log = []
        self.log_limit = 120
        self.send_queue = ""

        # Instantiate keyboard input.
        self.reset_key = {'3': 81}
        self.keys_down = {}
        self.key_hook = keyboard.hook(self.test_hotkey)

        # Wait for first screenshot to be captured:
        self.rawshot = screen.shot()
        while self.rawshot is None:
            pass

        print("Starting...")
        self.run()

    def test_hotkey(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            self.keys_down[event.name] = event.scan_code
        elif event.event_type == keyboard.KEY_UP:
            self.keys_down = {}
        if self.keys_down == self.reset_key:
            self.reset()
            print(f"RESET ({self.keys_down})")

    def reset(self):
        self.cur_pack = file.first_pack
        self.cycle = True
        self.split_num = 0.0
        self.write_images()
        self.image_log = []

    def write_images(self):
        for split, img in self.image_log:
            cv2.imwrite(f'runlog/{split}.png', img)

    def log_images(self, last, cur):
        if self.split_num < self.log_limit:
            if file.runlog == 2:
                self.image_log.append([self.split_num, last])
                self.split_num += 0.25
                self.image_log.append([self.split_num, cur])
                self.split_num += 0.25
            elif file.runlog == 1:
                self.image_log.append([self.split_num, cur])
                self.split_num += 0.5
            else:
                self.split_num += 1

    def multi_test(self, tests, match=True, compare_all=False):
        best, worst = 0.0, 100.0
        result = False
        out_shot = None

        for test in tests:
            shot = processing(self.rawshot, test.color_proc, test.resize, test.crop_area)
            if out_shot is None:
                out_shot = shot
            percent = test.match_percent if match else test.unmatch_percent

            for img in test.images:
                if np.shape(img) != np.shape(shot):
                    print("THIS AIN'T GON' WERK!")
                    print(test.name, np.shape(img), np.shape(shot))
                    showImage(img)
                    showImage(shot)
                similarity = compare(img, shot)
                if similarity > best: best = similarity
                if similarity < worst: worst = similarity

                if similarity >= percent:
                    if not compare_all:
                        return [True, best, worst, shot]
                    else:
                        out_shot = shot
                        result = True

        return [result, best, worst, shot]

    def run(self):
        lastshot = self.rawshot
        self.rawshot = screen.shot()
        # screen.shot is blocking, so send signal to livesplit ON the next frame collection event for consistency.
        if self.send_queue != "":
            livesplit.send(self.send_queue.encode())
            self.send_queue = ""

        self.cur_match = self.multi_test(self.cur_pack.match_tests, self.cycle, True)
        if self.cycle:  # If Matching Cycle...
            if self.cur_match[0]:    # If match found...
                self.send_queue = self.cur_pack.match_send
                seek_end = time.time() - self.seek_time
                self.cycle = False
                print(f"{int(self.split_num)}: [{'{0:.3f}'.format(seek_end)}] {'{0:.2f}'.format(self.cur_match[1])} @ "
                      f"{int(fpstimer.fps)}fps -- {str.upper(self.cur_pack.name)}: '{self.cur_pack.match_send}'".
                      replace("\r\n", "\\r\\n"))
                self.log_images(lastshot, self.cur_match[3])

        else:   # If Unmatch Cycle...
            if not self.cur_match[0]:   # If Nomatch found.
                if self.cur_pack.unmatch_packs is not None:
                    for pack in self.cur_pack.unmatch_packs:
                        match = self.multi_test(pack.match_tests)
                        if match[0]:
                            self.send_queue = pack.match_send
                            self.cur_pack = pack
                            print(f"*{pack.name}* ({'{0:.2f}'.format(self.cur_match[1])}) - Sent '{pack.match_send}'".
                                  replace("\r\n", "\\r\\n"))
                            fpstimer.update()
                            return

                self.send_queue = self.cur_pack.nomatch_send
                self.seek_time = time.time()
                self.cycle = True
                print(f"          -{'{0:.2f}'.format(self.cur_match[1])} - '{self.cur_pack.nomatch_send}'".
                      replace("\r\n", "\\r\\n"))
                self.cur_pack = self.cur_pack.nomatch_pack
                self.log_images(lastshot, self.cur_match[3])

        # Per-second Console Output
        fps = fpstimer.update()
        elapsed = time.time() - self.start
        if elapsed > 1:
            #print(f"{self.cur_pack.name} ({'{0:.2f}'.format(self.cur_match[1])}) - FPS: {int(fps)} "
            #      f"({'{0:.2f}'.format(elapsed)})")
            self.start = time.time()


#   ~~~Instantiate Objects~~~
screen = ScreenShot(monitor=1)

file = FileAccess('clustertruck.rp')
file.convert(screen.monitor)
file.init_packs()
screen.set_crop(file.master_crop)

livesplit = LivesplitClient()
fpstimer = FPSTimer()
mainloop = Engine()
livesplit.connect("localhost", 16834)

#   ~~~Seek Loop~~~
while True:
    mainloop.run()
