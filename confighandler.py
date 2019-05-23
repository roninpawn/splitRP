import configparser
import os
from random import shuffle

# ---Functions---

def resource_path(relative_path):
    return os.path.join(os.path.abspath("."), relative_path)


def patternToDict(pattern, config, prefix=""):
    pattern = pattern.strip()
    enabled = config[pattern].getboolean('enabled')
    area = [int(n) for n in config[pattern]['area'].split(",")]
    origin = [int(n) for n in config[pattern]['origin'].split(":")]
    edges = [int(n) for n in config[pattern]['edges'].split(",")]
    shade = config[pattern].getint('shade')
    planes = config[pattern]['planes'].split(",")
    for i in range(len(planes)):
        planes[i] = planes[i].strip().split(":")
        planes[i][0] = int(planes[i][0])
        planes[i][1] = int(planes[i][1])
    max = config[pattern].getint('max')
    soften = config[pattern].getint('soften')
    thresh = config[pattern].getint('thresh')
    action = config[pattern]['action'].replace("\\r\\n", "\r\n")

    dicto = {"name": f"{prefix}:{pattern}", "area": area,
              "properties": [origin, edges, [shade] + planes, max, soften],
              "threshold": thresh,
              "action": action,
              "enabled": enabled}
    return dicto


def stringToClicks(string):
    out = []
    string = string.replace(' ', '').split(",")
    for n in string:
        n = n.split(":")
        n[1] = [int(p) for p in n[1].split("+")]
        out.append([int(n[0]), n[1]])
    return out


def stringToActions(string):
    out = []
    string = string.replace(' ', '').split(",")
    for n in string:
        n = n.split(":")
        if "+" in n[1]:
            n[1] = [int(p) for p in n[1].split("+")]
        out.append([n[0], n[1]])
    return out


def randomList(total, force_last):
    out = [i for i in range(1, total + 1 - force_last)]
    shuffle(out)
    if force_last: out.append(total)
    return out


def convertResolution(screen_list, detection_list, original_scale, resize_to, translation, click_list=None):
    if resize_to != original_scale or translation != (0, 0):
        sx = resize_to[0] / original_scale[0]
        sy = resize_to[1] / original_scale[1]
        scaleScreens(screen_list, sx, sy, translation[0], translation[1])
        scaleDetections(detection_list, sx, sy, translation[0], translation[1])
        if click_list is not None:
            scaleClicks(click_list, sx, sy, translation[0], translation[1])
        print("Converted Screen Space")


def scaleScreens(screen_list, sx, sy, tx=0, ty=0):
    for screen in screen_list:
        screen["top"] = round(screen["top"] * sy) + ty
        screen["left"] = round(screen["left"] * sx) + tx
        screen["width"] = round(screen["width"] * sx) + tx
        screen["height"] = round(screen["height"] * sy) + ty


def scaleDetections(dict_list, sx, sy, tx=0, ty=0):
    for dicto in dict_list:
        dicto["area"][0] = round(dicto["area"][0] * sx) + tx
        dicto["area"][1] = round(dicto["area"][1] * sy) + ty
        dicto["area"][2] = round(dicto["area"][2] * sx) + tx

        dicto["properties"][0] = [round(i * sx) for i in dicto["properties"][0]]
        dicto["properties"][1] = [round(i * sx) for i in dicto["properties"][1]]
        dicto["properties"][2][1:] = [[round(i[0] * sx), round(i[1] * sx)] for i in dicto["properties"][2][1:]]
        dicto["properties"][3] = round(dicto["properties"][3] * sx)
        dicto["properties"][4] = round(dicto["properties"][4] * sx)


def scaleClicks(click_list, sx, sy, tx=0, ty=0):
    for click in range(len(click_list)):
        click_list[click][1][0] = round(click_list[click][1][0] * sx) + tx
        click_list[click][1][1] = round(click_list[click][1][1] * sy) + ty


def repackScreen(screen_str):
    dicto = {}
    arr = screen_str.replace(" ", "").split(",")
    arr = [n.split(":") for n in arr]
    for n in range(len(arr)):
        dicto[arr[n][0]] = int(arr[n][1])
    return dicto


class fileAccess():
    default_origin = [0, 0]
    default_resolution = [1920, 1080]
    default_reset_key = {'3': 81}
    default_autoclicker_active = False
    default_lock_to_window = True
    default_pause_when_inactive = True
    default_pattern_file = ""
    default_livesplit_host = "localhost"
    default_livesplit_port = 16834
    default_window_position = "+100+100"
    default_false_pattern_period = .1

    def __init__(self, mainloop):
        # ---Main Code---
        if not os.path.exists("falsies"):
            os.makedirs("falsies")
        self.mainloop = mainloop
        self.loadSettings()
        self.loadPattern()

    def saveSettings(self):
        settings_cfg = configparser.RawConfigParser()
        settings_cfg.add_section("Default Settings")
        settings_cfg.set("Default Settings", "monitor_origin", f"{self.pattern_translation[0]}, {self.pattern_translation[1]}")
        settings_cfg.set("Default Settings", "monitor_resolution", f"{self.pattern_scale[0]}, {self.pattern_scale[1]}")
        settings_cfg.set("Default Settings", "reset_key", str(self.reset_key)[1:-1].replace(" ", ""))
        settings_cfg.set("Default Settings", "autoclicker_active", str(self.autoclicker_active))
        settings_cfg.set("Default Settings", "lock_to_window", str(self.lock_to_window))
        settings_cfg.set("Default Settings", "pause_when_inactive", str(self.pause_when_inactive))
        settings_cfg.set("Default Settings", "pattern_file", self.pattern_file)
        settings_cfg.set("Default Settings", "false_split_period", str(self.false_split_period))
        settings_cfg.add_section("Livesplit Server")
        settings_cfg.set("Livesplit Server", "host", self.livesplit_host)
        settings_cfg.set("Livesplit Server", "port", str(self.livesplit_port))
        settings_cfg.add_section("GUI Settings")
        settings_cfg.set("GUI Settings", "position", f"{self.window_position.split('+')[1]}, {self.window_position.split('+')[2]}")
        with open(resource_path("settings.cfg"), 'w') as configfile:
            settings_cfg.write(configfile)

    def setDefaults(self):
        self.pattern_translation = self.default_origin
        self.pattern_scale = self.default_resolution
        self.reset_key = self.default_reset_key
        self.autoclicker_active = self.default_autoclicker_active
        self. lock_to_window = self.default_lock_to_window
        self.pause_when_inactive = self.default_pause_when_inactive
        self.livesplit_host = self.default_livesplit_host
        self.livesplit_port = self.default_livesplit_port
        self.window_position = self.default_window_position
        self.false_split_period = self.default_false_pattern_period
        try: self.pattern_file
        except AttributeError: self.pattern_file = self.default_pattern_file

    def loadSettings(self):
        print("Loading default settings.")
        settings_cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        try:
            settings_cfg.read_file(open(resource_path('settings.cfg')))
        except FileNotFoundError:
            self.setDefaults()
            self.saveSettings()
        else:
            self.pattern_translation = [int(n) for n in settings_cfg["Default Settings"]["monitor_origin"].replace(" ", "").split(",")]
            self.pattern_scale = [int(n) for n in settings_cfg["Default Settings"]["monitor_resolution"].replace(" ", "").split(",")]
            self.reset_key = settings_cfg["Default Settings"]["reset_key"].replace(" ", "")
            self.reset_key = dict((k.strip()[1:-1], int(v.strip())) for k, v in (item.split(':') for item in self.reset_key.split(',')))
            self.autoclicker_active = settings_cfg.getboolean("Default Settings", "autoclicker_active")
            self.lock_to_window = settings_cfg.getboolean("Default Settings", "lock_to_window")
            self.pause_when_inactive = settings_cfg.getboolean("Default Settings", "pause_when_inactive")
            self.pattern_file = settings_cfg["Default Settings"]["pattern_file"]
            self.false_split_period = float(settings_cfg["Default Settings"]["false_split_period"])
            self.livesplit_host = settings_cfg["Livesplit Server"]["host"]
            self.livesplit_port = settings_cfg.getint("Livesplit Server", "port")

            self.window_position = "+" + settings_cfg["GUI Settings"]["position"].replace(", ", "+")

        print("Settings loaded.")

    def savePattern(self):
        print("Saving to pattern file.")
        pattern_cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        if self.pattern_file is not None:
            try:
                pattern_cfg.read_file(open(resource_path(self.pattern_file)))
            except FileNotFoundError or FileExistsError:
                return False
            else:
                for pattern in self.all_patterns:
                    pattern_cfg[pattern["name"][3:]]["enabled"] = str(pattern["enabled"])
                try:
                    pattern_cfg['Roulette']['active'] = str(self.roulette)
                except:
                    pass
            with open(resource_path(self.pattern_file), 'w') as patternfile:
                pattern_cfg.write(patternfile)


    def loadPattern(self):
        print("Reading pattern file.")
        pattern_cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        if self.pattern_file is not None:
            try:
                pattern_cfg.read_file(open(resource_path(self.pattern_file)))
            except FileNotFoundError or FileExistsError:
                self.roulette = False
                self.roulette_clicks = None
                return False
            else:
                try:
                    self.game_title = pattern_cfg['General Properties']['game_title']
                except:
                    self.roulette = False
                    self.roulette_clicks = None
                    return False
                else:
                    self.original_scale = [int(n) for n in pattern_cfg['General Properties']['original_scale'].replace(" ", "").split(",")]
                    self.auto_click = [int(n) for n in pattern_cfg['General Properties']['auto_click'].replace(" ", "").split(",")]

                    self.run_screen = repackScreen(pattern_cfg['Screenshot Areas']['runtime'])
                    self.start_screen = repackScreen(pattern_cfg['Screenshot Areas']['prerun'])
                    self.all_screens = [self.run_screen, self.start_screen]

                    self.run_patterns = [patternToDict(n, pattern_cfg, "RT") for n in pattern_cfg['Tests']['runtime'].split(",")]
                    self.prerun_patterns = [patternToDict(n, pattern_cfg, "PR") for n in pattern_cfg['Tests']['prerun'].split(",")]
                    self.standby_patterns = [patternToDict(n, pattern_cfg, "SB") for n in pattern_cfg['Tests']['standby'].split(",")]
                    self.all_patterns = self.run_patterns + self.prerun_patterns + self.standby_patterns

                    try:
                        self.roulette = bool(pattern_cfg['Roulette']['active'].replace(" ", ""))
                    except:
                        self.roulette = False
                        self.roulette_clicks = None
                        pass
                    else:
                        self.roulette_total = int(pattern_cfg['Roulette']['levels'].replace(" ", ""))
                        self.roulette_page_clicks = sorted(stringToClicks(pattern_cfg['Roulette']['page_clicks']),
                                                           key=lambda click: click[0])
                        self.roulette_clicks = sorted(stringToClicks(pattern_cfg['Roulette']['clicks']),
                                                      key=lambda click: click[0])
                        self.roulette_backout = stringToActions(pattern_cfg['Roulette']['backout'])
                        self.roulette_delay = float(pattern_cfg['Roulette']['click_delay'].replace(" ", ""))
                        self.roulette_final = bool(pattern_cfg['Roulette']['last_is_last'].replace(" ", ""))


                    convertResolution(self.all_screens, self.all_patterns, self.original_scale, self.pattern_scale,
                                      self.pattern_translation, self.roulette_clicks)
                    print("Patterns read and stored.")
        return True
