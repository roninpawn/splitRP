import time
import socket
from select import select as select
import mss
import mss.tools
import keyboard
from file_handling import *


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
            self._mon = self.sct.monitors[monitor]
            if area is None: area = self._mon
            self.setCrop(area)

    def shot(self):
        self.last_shot = np.array(self.sct.grab(self.cap_area))
        return self.last_shot

    def setCrop(self, area, monitor=None):
        if monitor is not None:
            self._mon = self.sct.monitors[monitor]
        self.cap_area = {
            "left": self._mon["left"] + area["left"], "top": self._mon["top"] + area["top"],
            "width": area["width"], "height": area["height"]}


class Engine:
    def __init__(self):
        self.start = time.time()
        self.seek_time = time.time()
        self.cycle = True
        self.cur_test = file.first_test
        self.split_num = 0.0
        self.image_log = []

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
            self.cur_test = file.first_test
            self.cycle = True
            self.split_num = 0.0
            self.write_images()
            print(f"RESET ({self.keys_down})")

    def write_images(self):
        for split, img in self.image_log:
            cv2.imwrite(f'runlog/{split}.png', img)

    def run(self):
        self.lastshot = self.rawshot
        self.rawshot = screen.shot()
        shot = processing(self.rawshot, self.cur_test.color_proc, self.cur_test.scale_img, self.cur_test.crop_area)
        match = compare(self.cur_test.image_tests, shot, self.cycle, True)
        if self.cycle:  # If Match Cycle(True)...
            if match[0]:  # If match
                livesplit.send(self.cur_test.match_send.encode())
                seek_end = time.time() - self.seek_time
                self.cycle = False
                self.image_log.append([self.split_num, self.lastshot])
                print(f"{int(self.split_num)}: [{'{0:.3f}'.format(seek_end)}] {match[1]} @ {int(fpstimer.fps)}fps -- "
                      f"{str.upper(self.cur_test.name)}: '{self.cur_test.match_send}'".replace("\r\n", "\\r\\n"))
                self.split_num += 0.5
            # else:
            #    file_num += 0.5
            #    cv2.imwrite(f'runlog/{file_num}.png', rawshot)

        elif not match[0]:  # If Unmatch Cycle(False) and no match found...
            if self.cur_test.unmatch_test is not self.cur_test:
                temp_test = self.cur_test.unmatch_test
                temp_shot = processing(self.rawshot, temp_test.color_proc, temp_test.scale_img)
                temp_match = compare(temp_test.image_tests, temp_shot, True, True)
                if temp_match[0]:
                    livesplit.send(temp_test.match_send.encode())
                    self.cur_test = temp_test
                    print(f"*{temp_test.name}* ({match[1]}) - Sent '{temp_test.match_send}'".replace("\r\n", "\\r\\n"))
                    return

            livesplit.send(self.cur_test.nomatch_send.encode())
            self.seek_time = time.time()
            self.cur_test = self.cur_test.nomatch_test
            self.cycle = True
            self.image_log.append([self.split_num, self.lastshot])
            print(f"          -{match[1]} - '{self.cur_test.nomatch_send}'".replace("\r\n", "\\r\\n"))
            self.split_num += 0.5

        # Per-second Console Output
        fps = fpstimer.update()
        elapsed = time.time() - self.start
        if elapsed > 1:
            # print(f"{cur_test.name} ({match[1]}) - FPS: {int(fps)} ({'{0:.2f}'.format(elapsed)})")
            self.start = time.time()


#   ~~~Define Public Functions~~~
def showImage(img, wait=0):
    cv2.imshow("imgWin", img)
    cv2.moveWindow("imgWin", 0, 0)  # Move it to (40,30)
    cv2.waitKey(wait)
    cv2.destroyAllWindows()


def compare(image_list, screenshot, match=True, compare_all=False):
    best, worst = 0, 100
    found = False

    for img in image_list:
        composite = cv2.absdiff(img[0], screenshot)  # Composite images into difference map.
        shape = np.shape(composite)  # [Pixel height, width, (color channels)]
        color_channels = 1 if len(shape) == 2 else shape[2]
        # depth needs to be resolved based on data type? (uint8 = 255, float = 1?)
        depth = 255

        similarity = 100 * (1 - ((np.sum(composite) / depth) / (shape[0] * shape[1] * color_channels)))
        if similarity > best: best = similarity
        if similarity < worst: worst = similarity

        if (match and similarity >= img[1]) or (not match and similarity >= img[2]):
            found = True
            if not compare_all:
                break

    return [found, f"{'{0:.2f}%'.format(best)} - {'{0:.2f}%'.format(worst)}"]


#   ~~~Instantiate Objects~~~
file = FileAccess('clustertruck.rp')
livesplit = LivesplitClient()
fpstimer = FPSTimer()
screen = ScreenShot(file.master_crop, 1)
livesplit.connect("localhost", 16834)
mainloop = Engine()
#   ~~~Seek Loop~~~
while True:
    mainloop.run()
