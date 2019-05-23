from GUI_v2 import *
from screenMonitoring import *
from timing import FPSTimer
from confighandler import *
from sys import exit
import win32api, win32con
import win32gui
import socket
from select import select as select
import keyboard
import ctypes

# ---Functions---

def click(x, y, multi=1):
    for n in range(multi):
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)


def change_mouse_speed(speed):
    set_mouse_speed = 113   # 0x0071 for SPI_SETMOUSESPEED
    ctypes.windll.user32.SystemParametersInfoA(set_mouse_speed, 0, speed, 0)


def get_mouse_speed():
    get_mouse_speed = 112   # 0x0070 for SPI_GETMOUSESPEED
    speed = ctypes.c_int()
    ctypes.windll.user32.SystemParametersInfoA(get_mouse_speed, 0, ctypes.byref(speed), 0)
    return speed.value


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
            window.updateStatus(f"Livesplit Connect [{self.attempt}]")

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
                window.updateStatus("Livesplit Connected")
        return self.connected

    def send(self, *args):
        if speedrun.leds[1][1] == 6: speedrun.leds[1][1] = 0
        try:
            super().send(*args)
        except:
            window.updateStatus("Livesplit Disconnected")
            self.connected = False
            return False
        return True

    def recv(self, *args):
        try:
            out = super().recv(*args).decode()
        except:
            out = "Dead Jim"
            window.updateStatus("Livesplit Disconnected")
            self.connected = False
        return out


class autoSplitter:
    def __init__(self):
        self.active = True
        self._state = "reconnect"
        self._last_state = "wait"
        self._last_detected = ""
        self._last_reset = time.time()
        self._active_buffer = 3
        self._keysdown = {}

    def loadFile(self):
        if livesplit.connected:
            window.load_patterns(file.all_patterns)
        self.standby_monitor = screenTest(file.start_screen, file.standby_patterns)
        self.prerun_monitor = screenTest(file.start_screen, file.prerun_patterns)
        self.run_monitor = screenTest(file.run_screen, file.run_patterns)
        self.prerun_monitor.last_test["name"] = None
        window.highlight_pattern()

    def reset(self):
        #if not livesplit.send("reset\r\n".encode()): self._state = "reconnect"
        window.highlight_pattern()
        if file.pattern_file != "":
            self._state = "armed"
            window.updateStatus("- RESET -")
        else:
            self._state = "wait"
            window.updateStatus("Select file to load")
        self._last_found_time = time.time()
        self._last_dropped_time = time.time()
        self._last_reset = time.time() + .5
        if file.roulette:
            self.roulette_current = 0
            self.roulette_order = randomList(file.roulette_total, file.roulette_final)

    def testHotkey(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            self._keysdown[event.name] = event.scan_code
        elif event.event_type == keyboard.KEY_UP:
            self._keysdown = {}
        for key in file.reset_key:
            if key not in self._keysdown:
                return
            if file.reset_key[key] != self._keysdown[key]:
                return
        if self._last_reset < time.time(): self._state = "reset"

    def _testLivesplit(self):
        if not livesplit.connected:
            if self._state != "wait":
                window.led_1.changeImage(3)
                window.led_2.changeImage(3)
                self._colorPower(2)
                window.power_skin.directSetImages(normal_img=window.power_images.images()[2])
                window.power_skin2.directSetImages(active_img=window.power_images.images()[2])
                updateHover(window.power_btn)
                window.load_btn.disable()
                window.load_patterns()
                window.updateStatus("Seeking Livesplit Host")
                window.update()
                try:
                    socket.gethostbyname(file.livesplit_host)
                except socket.gaierror:
                    window.updateStatus("ERROR: Invalid Server Host")
                    livesplit.connected = True
            if not livesplit.connected and livesplit.connect(file.livesplit_host, file.livesplit_port):
                window.led_2.changeImage(0)
                self._colorPower(1)
                window.load_btn.enable()
                if file.pattern_file != "": window.load_patterns(file.all_patterns)
                self._state = "reset"
            else:
                self._state = "wait"

    def mainloop(self):
        if file.pattern_file != "": self.loadFile()
        self.leds = [[window.led_1, 6, time.time(), 0],
                     [window.led_2, 6, time.time()], 0]
        self._keyhook = keyboard.hook(self.testHotkey)

        while True:
            self._testClosing()
            self._blinkLEDS()
            self._testLivesplit()
            if self._state == "wait": time.sleep(1 / 140)
            if self._state == "reconnect": livesplit.connected = False
            elif self._state == "reset": self.reset()
            elif self.active and file.pattern_file != "":
                if livesplit.connected: self._testActive()
                if self._state == "standby": self._standby()
                elif self._state == "armed": self._ready(True)
                elif self._state == "ready": self._ready()
                elif self._state == "running": self._running()
                elif self._state == "pause": self._pause()
                elif self._state == "roulette": self._ready()
            window.updateFPS(fps.update(), fpms.update())

    def updateDetected(self, detection_name):
        if self._last_detected != detection_name or self._state != self._last_state:
            window.highlight_pattern(detection_name)
            if self._state != self._last_state:
                self.leds[0][0].disable()
                self.leds[0][1] = -1
            elif self.leds[0][1] == 6: self.leds[0][1] = 0
        self._last_detected = detection_name

    def _colorPower(self, color):
        window.power_skin.directSetImages(normal_img=window.power_images.images()[color])
        window.power_skin2.directSetImages(active_img=window.power_images.images()[color])
        updateHover(window.power_btn)

    def _colorLED(self, color):
        self.leds[0][0].changeImage(color)
        self._colorPower(int(color/2))
        self.leds[0][3] = color

    def _blinkLEDS(self):
        now = time.time()
        for led in range(2):
            if self.leds[led][1] < 6 and now > self.leds[led][2]:
                self.leds[led][1] += 1
                self.leds[led][0].disable() if self.leds[led][0].enabled else self.leds[led][0].enable()
                self.leds[led][2] = now + .115
                self.leds[led][0].update_idletasks()

    def _testClosing(self):
        if window.closing:
            file.window_position = f"+{window.winfo_x()}+{window.winfo_y()}"
            file.saveSettings()
            file.savePattern()
            exit()

    def _testActive(self):
        if file.lock_to_window:
            if file.game_title != win32gui.GetWindowText(win32gui.GetForegroundWindow()):
                if self._state != "wait":
                    if self._state != "running" and self._state != "armed":
                        self._active_buffer = 0
                    self._last_state = self._state
                    self._state = "wait"
                    if file.pause_when_inactive:
                        if not livesplit.send("pausegametime\r\n".encode()): self._state = "reconnect"
                    window.updateStatus("Game window not active")
                    window.led_1.changeImage(3)
            else:
                if self._state == "wait":
                    if self._active_buffer < 3:
                        if self._last_state == "pause":
                            detected = self.run_monitor.test()
                        else:
                            detected = self.prerun_monitor.test()
                        if detected:
                            self._active_buffer += 1
                        else:
                            self._active_buffer = 0
                    elif livesplit.connected:
                        self._state = self._last_state
                        if file.pause_when_inactive and self._state != "pause":
                            if not livesplit.send("unpausegametime\r\n".encode()): self._state = "reconnect"
                        window.led_1.changeImage(self.leds[0][3])
                        window.updateStatus("Returned to game")

    def _testFalseSplit(self, last_time):
        # Save false-positives for pattern review.
        if time.time() - last_time < file.false_split_period:
            if not livesplit.send("unsplit\r\n".encode()): self._state = "reconnect"
            img = self.run_monitor.shot_history[1]
            save_to = resource_path(os.path.join("falsies", f"{last_time / 10000}.png"))
            cv2.imwrite(save_to, img)

    def _standby(self):
        if self._state != self._last_state:
            self._last_state = self._state
            self._colorLED(2)
            window.updateStatus("Standby mode")
        if self.standby_monitor.test():
            self._state = "armed"
        self.updateDetected(self.standby_monitor.last_test["name"])

    def _ready(self, seek=False):
        if self._state != self._last_state:
            self._last_state = self._state
            self._colorLED(1)
            if seek:
                window.updateStatus("Armed and Seeking")
            else:
                window.updateStatus("Ready to begin")
        else:
            if self.prerun_monitor.test() and self._state != "roulette":
                if self.prerun_monitor.last_test["action"] == "STANDBY":
                    self._state = "standby"
                elif seek:
                    self._state = "ready"
            elif not seek:
                if file.roulette:
                    if self._state == "ready":
                        self.rouletteSelect()
                        return
                    else:
                        if len(self.roulette_order) == file.roulette_total - 1:
                            if not livesplit.send("unpausegametime\r\nstarttimer\r\nsetgametime 0.0\r\n".encode()):
                                self._state = "reconnect"
                        elif not livesplit.send("unpausegametime\r\n".encode()): self._state = "reconnect"
                else:
                    if not livesplit.send((self.prerun_monitor.last_test["action"]).encode()): self._state = "reconnect"
                self._state = "running"
            self.updateDetected(self.prerun_monitor.last_test["name"])

    def _running(self):
        if self._state != self._last_state:
            self._last_state = self._state
            self._colorLED(0)
            self.updateDetected("RT:Running")
            window.updateStatus("Speedrunning!")
        if self.run_monitor.test():
            self._state = "pause"
            if not livesplit.send(self.run_monitor.last_test["action"].encode()): self._state = "reconnect"

            if self.run_monitor.last_test["action"].find("split") != -1:
                if file.roulette:
                    self._state = "ready"
                else:
                    if file.autoclicker_active and file.auto_click is not None:
                        click(file.auto_click[0], file.auto_click[1], 3)

                # Ask livesplit if the run is over. If so, reset internal run-state.
                if not livesplit.send("getcurrenttimerphase\r\n".encode()): self._state = "reconnect"
                if livesplit.recv(1024)[:-2] == "Ended":
                    window.updateStatus("- Run Complete -")
                    self._state = "reset"
                    return

                # Save false-negatives for pattern review.
                self._testFalseSplit(self._last_found_time)
                self._last_found_time = time.time()


    def _pause(self):
        if self._state != self._last_state:
            window.updateStatus(f"Found: {self.run_monitor.last_test['name'][3:]}")
            self._last_state = self._state
            self._colorLED(0)
        if not self.run_monitor.test():
            self._state = "running"
            if not livesplit.send("unpausegametime\r\n".encode()): self._state = "reconnect"
            self._testFalseSplit(self._last_dropped_time)       # Save false positives for pattern review.
            self._last_dropped_time = time.time()
        self.updateDetected(self.run_monitor.last_test["name"])

    def rouletteSelect(self):
        window.update()
        if len(self.roulette_order) < 0:
            self._state = "reset"
            return

        self.mouse_speed = get_mouse_speed()
        change_mouse_speed(1)

        if self._state == "ready":
            for action in file.roulette_backout:
                if action[0] == "press":
                    keyboard.send(action[1])
                elif action[0] == "click":
                    click(action[1][0], action[1][1], 1)
                sleep(file.roulette_delay)

        done = False
        level = self.roulette_order[0]
        window.updateStatus(
            f"Loading level: {level} [{file.roulette_total - len(self.roulette_order)} of {file.roulette_total}]")
        print("Loading Level:",level)

        while not done:
            if level <= self.roulette_current or level > self.roulette_current + file.roulette_clicks[-1][0]:
                x, y, add = self.rouletteMax(self.roulette_current, level, file.roulette_page_clicks)
                self.roulette_current += add
            else:
                x, y, add = self.rouletteMax(self.roulette_current, level, file.roulette_clicks)
                done = True
                click(x, y, 1)
                sleep(file.roulette_delay)
            click(x, y, 1)
            sleep(file.roulette_delay)

        change_mouse_speed(self.mouse_speed)
        self.roulette_order = self.roulette_order[1:]
        self._state = "roulette"

    def rouletteMax(self, current, goto, possibles):
        for click in range(len(possibles)-1, -1, -1):
            if current + possibles[click][0] <= goto:
                return possibles[click][1][0], possibles[click][1][1], possibles[click][0]
        return possibles[0][1][0], possibles[0][1][1], possibles[0][0]


# ---Initialization---
fps = FPSTimer()
fpms = FPSTimer(1/100)
livesplit = LivesplitClient()
speedrun = autoSplitter()
file = fileAccess(speedrun)
window = GUI(file, speedrun)

speedrun.mainloop()
