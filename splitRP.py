import numpy as np
import cv2
import time
import socket
from select import select as select
import mss
import mss.tools
import copy
import keyboard


#   ~~~Define Objects~~~
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


class ImagePack:
    def __init__(self, name, directory=None, files="", match_percent=100, unmatch_percent=0):
        self.name = name
        self.files = self._parse_paths(files, directory)
        self.images = []
        self.match_percent = match_percent
        self.unmatch_percent = unmatch_percent
        for file in self.files:
            self.images.append(cv2.imread(file, 1))

    def _parse_paths(self, file_str, dir = None):
        file_arr = file_str.split("|")
        if dir is not None:
            for x in range(0,len(file_arr),1):
                file_arr[x] = dir + "/" + file_arr[x]
        return(file_arr)


class TestObject:
    def __init__(self, name, master_crop, img_packs, match_send='', unmatch_test=None, nomatch_test=None,
                 nomatch_send='', crop_area=None, scale_img=None, color_proc=None):
        self.name = name
        self.img_packs = [img_packs] if type(img_packs) != list else img_packs
        self.match_send = match_send
        self.nomatch_send = nomatch_send
        self.scale_img = scale_img
        self.color_proc = color_proc
        self.updateTests(unmatch_test, nomatch_test)
        self.image_tests = []

        if crop_area is None:
            crop_area = {"left":0,"top":0,"width":master_crop["width"],"height":master_crop["height"]}
        else:
            self.crop_area = copy.copy(crop_area)

        # Redefine crop_area to conform to master crop area.
        if master_crop["left"] + master_crop["width"] > crop_area["left"] >= master_crop["left"]:
            self.crop_area["left"] = crop_area["left"] - master_crop["left"]
        else:
            self.crop_area["left"] = 0
        if master_crop["top"] + master_crop["height"] > crop_area["top"] >= master_crop["top"]:
            self.crop_area["top"] = crop_area["top"] - master_crop["top"]
        else:
            self.crop_area["top"] = 0

        self.processImages(master_crop)

    def updateTests(self, unmatch_test=None, nomatch_test=None):
        self.unmatch_test = self if unmatch_test is None else unmatch_test
        self.nomatch_test = self if nomatch_test is None else nomatch_test

    def processImages(self, master_area):
        for pack in self.img_packs:
            for img in pack.images:
                out = np.copy(img)
                out = out[  master_area["top"]:master_area["top"] + master_area["height"],
                            master_area["left"]:master_area["left"] + master_area["width"]]
                out = processing(out, self.color_proc, self.scale_img, self.crop_area)
                self.image_tests.append([out, pack.match_percent, pack.unmatch_percent])


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
        depth = 255

        similarity = 100 * (1 - ((np.sum(composite) / depth) / (shape[0] * shape[1] * color_channels)))
        if similarity > best: best = similarity
        if similarity < worst: worst = similarity

        if (match and similarity >= img[1]) or (not match and similarity >= img[2]):
            found = True
            if not compare_all:
                break

    return [found, f"{'{0:.2f}%'.format(best)} - {'{0:.2f}%'.format(worst)}"]

def processing(img, color=None, resize=None, crop=None):
    if crop is not None:
        img = img[crop["top"]:crop["top"] + crop["height"], crop["left"]:crop["left"] + crop["width"]]
    if color is not None:
        img = cv2.cvtColor(img, color)
    if resize is not None:
        img = cv2.resize(img, (resize[0], resize[1]), interpolation=cv2.INTER_AREA)
    return img

def xywh2dict(x, y, w, h): return {'left':x,'top':y,'width':w,'height':h}

def testHotkey(event):
    global reset_key, keysdown, cur_test, cycle, file_num      # Temporary bodge. When objectified, 'self.' will do.
    if event.event_type == keyboard.KEY_DOWN:
        keysdown[event.name] = event.scan_code
    elif event.event_type == keyboard.KEY_UP:
        keysdown = {}
    if keysdown == reset_key:
        cur_test = first_test
        cycle = True
        file_num = 0.0
        print(f"RESET ({keysdown})")


#   ~~~Simulate Load from File~~~
# Bodge in some quick values for resize, cropping, and color
master_crop = xywh2dict(353, 136, 560, 825)
crop = xywh2dict(353, 136, 560, 825)
res = (112, 165)
color = cv2.COLOR_BGR2GRAY
# -Instantiate Image Objects
imgpack_lc1 = ImagePack("pack_lc1", "images", "lc1.png|lc2_91.5.png|lc3_91.5.png|lc4_93.png|lc5_93.png|lc6_94.png|"
                                              "lc7_94.3.png",93.5, 90)
imgpack_sel1 = ImagePack("img_sel1", "images", "select1.png|select2.png", 86, 85)
imgpack_menu1 = ImagePack("img_menu1", "images", "menu1.png", 100, 76)
# -Instantiate Test Objects
test_menu1 = TestObject("test_menu1", master_crop, imgpack_menu1, "", nomatch_send="", crop_area=crop, scale_img=res,
                        color_proc=color)
test_lc1 = TestObject("test_lc1", master_crop, [imgpack_lc1], "pausegametime\r\nsplit\r\n",
                      nomatch_send="unpausegametime\r\n", crop_area=crop, scale_img=res, color_proc=color)
test_sel1 = TestObject("test_sel1", master_crop, imgpack_sel1, "", test_menu1, test_lc1,
                             nomatch_send="setgametime 0.0\r\nstarttimer\r\n", crop_area=crop, scale_img=res,
                             color_proc=color)
# -Bodge in overlapping values
test_menu1.updateTests(test_sel1, test_sel1)

#   ~~~Instantiate Objects~~~
livesplit = LivesplitClient()
fpstimer = FPSTimer()
screen = ScreenShot(master_crop, 1)

#   ~~~Pre-run~~~
livesplit.connect("localhost", 16834)
start = time.time()
seek_time = time.time()
cycle = True
first_test = test_sel1
cur_test = first_test
file_num = 0.0
# Monitor keyboard input for reset event.
reset_key = {'3':81}
keysdown = {}
keyhook = keyboard.hook(testHotkey)
# Wait for first screenshot to be captured:
rawshot = screen.shot()
while rawshot is None:
    pass

#   ~~~Seek Loop~~~
print("Starting...")
while True:
    lastshot = rawshot
    rawshot = screen.shot()
    shot = processing(rawshot, cur_test.color_proc, cur_test.scale_img, cur_test.crop_area)
    match = compare(cur_test.image_tests, shot, cycle, True)
    if cycle:  # If Match Cycle(True)...
        if match[0]:  # If match
            livesplit.send(cur_test.match_send.encode())
            seek_end = time.time() - seek_time
            print(f"{int(file_num)}: [{'{0:.3f}'.format(seek_end)}] {match[1]} @ {int(fpstimer.fps)}fps -- "
                  f"{str.upper(cur_test.name)}: '{cur_test.match_send}'".replace("\r\n", "\\r\\n"))
            cycle = False
            cv2.imwrite(f'runlog/{file_num}.png', lastshot)
            file_num += 0.5
        #else:
        #    file_num += 0.5
        #    cv2.imwrite(f'runlog/{file_num}.png', rawshot)

    elif not match[0]:  # If Unmatch Cycle(False) and no match found...
        if cur_test.unmatch_test is not cur_test:
            temp_test = cur_test.unmatch_test
            temp_shot = processing(rawshot, temp_test.color_proc, temp_test.scale_img)
            temp_match = compare(temp_test.image_tests, temp_shot, True, True)
            if temp_match[0]:
                livesplit.send(temp_test.match_send.encode())
                print(f"*{temp_test.name}* ({match[1]}) - "
                      f"Sent '{temp_test.match_send}'".replace("\r\n", "\\r\\n"))
                cur_test = temp_test
                continue    # Goto while True:

        livesplit.send(cur_test.nomatch_send.encode())
        seek_time = time.time()
        print(f"          -{match[1]} - '{cur_test.nomatch_send}'".replace("\r\n", "\\r\\n"))
        cur_test = cur_test.nomatch_test
        cycle = True
        cv2.imwrite(f'runlog/{file_num}.png', lastshot)
        file_num += 0.5

    # Per-second Console Output
    fps = fpstimer.update()
    elapsed = time.time() - start
    if elapsed > 1:
        #print(f"{cur_test.name} ({match[1]}) - FPS: {int(fps)} ({'{0:.2f}'.format(elapsed)})")
        start = time.time()
        calcs = 0