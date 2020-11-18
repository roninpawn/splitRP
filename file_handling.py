import configparser
import numpy as np
import os.path
import copy
import cv2


# Public Functions
def resource_path(relative_path): return os.path.join(os.path.abspath("."), relative_path)


def xywh2dict(x, y, w, h): return {'left': x, 'top': y, 'width': w, 'height': h}


def dict2xywh(d): return [d["left"], d["top"], d["width"], d["height"]]


def dict_scale(screen_dict, h, w):
    coords = dict2xywh(screen_dict)
    return xywh2dict(int(coords[0] * w), int(coords[1] * h), int(coords[2] * w), int(coords[3] * h))


def processing(img, color=None, resize=None, crop=None):
    if crop is not None:
        img = img[crop["top"]:crop["top"] + crop["height"], crop["left"]:crop["left"] + crop["width"]]
    if color is not None:
        # Grayscale by luminance. Y of XYZ = Luminance. Extract Y channel.
        img = cv2.cvtColor(img, cv2.COLOR_BGR2XYZ)
        img = img[:, :, 1]
        if type(color) is int:      # Thresh to black/white
            (thresh, img) = cv2.threshold(img, color, 255, cv2.THRESH_BINARY)
    if resize is not None:
        img = cv2.resize(img, None, None, resize[0], resize[1], cv2.INTER_NEAREST)      # Changed from INTER_AREA.
    return img


# Classes
class Test:
    def __init__(self, name, image_paths, match_per, unmatch_per, crop_area=None, resize=None, color_proc=None):
        self.name = name
        self.image_paths = image_paths
        self.match_percent = match_per
        self.unmatch_percent = unmatch_per
        self.crop_area = copy.copy(crop_area)
        self.resize = [resize, resize] if resize is not None and type(resize) is not list else resize
        self.color_proc = color_proc
        self.images = []

    def conform_crop(self, area, resize):       # Adjust self.crop_area relative to 'area' given.
        if self.crop_area is not None:
            self.crop_area = dict_scale(self.crop_area, resize[1], resize[0])
            if area["left"] + area["width"] > self.crop_area["left"] >= area["left"]:
                self.crop_area["left"] -= area["left"]
            else:
                self.crop_area["left"] = 0
            if area["top"] + area["height"] > self.crop_area["top"] >= area["top"]:
                self.crop_area["top"] -= area["top"]
            else:
                self.crop_area["top"] = 0
        else:
            self.crop_area = xywh2dict(0, 0, area["width"], area["height"])

    def load_images(self, area, scale):
        self.conform_crop(area, scale)
        if self.resize is not None:
            self.resize = np.divide(self.resize, scale)
        self.images = []
        for file in self.image_paths:
            img = cv2.imread(resource_path(file), 1)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            img = cv2.resize(img, None, None, scale[0], scale[1], cv2.INTER_AREA)
            img = img[area["top"]: area["top"] + area["height"], area["left"]: area["left"] + area["width"]]
            img = processing(img, self.color_proc, self.resize, self.crop_area)

            shape = np.shape(img)  # [Pixel height, width, (color channels)]
            color_channels = 1 if len(shape) == 2 else shape[2]
            depth = 255  # depth ought to be resolved based on data type? (uint8 = 255, float = 1?)
            max_pixel_sum = shape[0] * shape[1] * color_channels * depth
            img_sum = int(np.sum(img))  # Add all actual pixel values within image.

            self.images.append([img, img_sum, max_pixel_sum])


class TestPack:
    def __init__(self, name, match_tests, match_actions=None, match_send='', unmatch_packs=None, nomatch_pack=None,
                 nomatch_actions=None, nomatch_send=''):
        self.name = name
        self.match_tests = match_tests
        self.match_actions = match_actions
        self.match_send = match_send
        self.unmatch_packs = unmatch_packs
        self.nomatch_pack = nomatch_pack
        self.nomatch_actions = nomatch_actions
        self.nomatch_send = nomatch_send


class FileAccess:
    def __init__(self, filename):
        self.path = resource_path(filename)
        self.cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        self.cfg.read_file(open(self.path))

        self.resolution = [int(n) for n in self.cfg["Settings"]["NativeResolution"].replace(" ", "").split("x")]
        self.master_crop = xywh2dict(
            *[int(n) for n in self.cfg["Settings"]["ScreenshotArea"].replace(" ", "").replace(":", ",").split(",")])
        if self.master_crop['width'] % 2 > 0:
            self.master_crop['width'] -= 1
        if self.master_crop['height'] % 2 > 0:
            self.master_crop['height'] -= 1

        if "Translate" in self.cfg["Settings"].keys():
            self.translation = [int(n) for n in self.cfg["Settings"]["Translate"].replace(" ", "").split("x")]
        else:
            self.translation = [0, 0]
        if "ReScale" in self.cfg["Settings"].keys():
            self.rescale_values = [int(n) for n in self.cfg["Settings"]["ReScale"].replace(" ", "").split("x")]
        else:
            self.rescale_values = None

        self.directory = f"images\\{self.cfg['Settings']['ImageDirectory'].strip()}\\"
        self.runlog = int(self.cfg["Settings"]["RunLogging"].strip())

        self.commands = {}
        for cmd in self.cfg["Commands"]:
            self.commands[cmd] = self.cfg["Commands"][cmd].strip().replace("\\r\\n", "\r\n")

        self.tests = {}
        for test in [s.strip() for s in self.cfg["Settings"]["Tests"].strip().split(",")]:
            self.tests[test] = self.build_test(test)

        self.test_packs = {}
        for pack in [s.strip() for s in self.cfg["Settings"]["TestPacks"].strip().split(",")]:
            self.test_packs[pack] = self.build_pack(pack)
        self.first_pack = self.test_packs[self.cfg["Settings"]["FirstPack"].strip()]

    def init_packs(self):       # Can this be part of TestPack class?
        for name, pack in self.test_packs.items():
            if pack.unmatch_packs is not None:
                for p in range(0, len(pack.unmatch_packs), 1):
                    pack.unmatch_packs[p] = self.test_packs[pack.unmatch_packs[p]]
            pack.nomatch_pack = self.test_packs[pack.nomatch_pack] if pack.nomatch_pack is not None else pack
        self.first_pack = self.test_packs[self.cfg["Settings"]["FirstPack"].strip()]

    def build_test(self, name):
        imgs = [self.directory + s.strip() for s in self.cfg[name]["Images"].strip().split("|")]
        match = float(self.cfg[name]["Match"].strip())
        unmatch = float(self.cfg[name]["Unmatch"].strip())

        if "Crop" in self.cfg[name].keys():
            crop = xywh2dict(*[int(n) for n in self.cfg[name]["Crop"].replace(" ", "").replace(":", ",").split(",")])
        else:
            crop = None

        resize = float(self.cfg[name]["Resize"].strip()) if "Resize" in self.cfg[name].keys() else None

        if "Color" in self.cfg[name].keys():
            color = [s.strip().lower() for s in self.cfg[name]["Color"].split(":")]
            if color[0] == "thresh" and len(color) > 1:
                try:
                    color = int(color[1])
                except:
                    color = None
            elif color[0] != "gray" and color[0] != "grey":
                color = None
        else:
            color = None

        return Test(name, imgs, match, unmatch, crop, resize, color)

    def build_pack(self, name):
        match = [self.tests[s.strip()] for s in self.cfg[name]["Match"].split(",")]
        unmatch = [s.strip() for s in self.cfg[name]["Unmatch"].split(",")] if "UnMatch" in self.cfg[name].keys()\
            else None
        nomatch = self.cfg[name]["NoMatch"].strip() if "NoMatch" in self.cfg[name].keys() else None

        def get_acts_send(pack, key):
            action_list = [s.strip().lower() for s in self.cfg[pack][key].split(",")] \
                if key in self.cfg[pack].keys() else ''
            send = ''
            for action in action_list:
                send += self.commands[action] if action in self.commands.keys() else ''
            return action_list, send

        match_actions, match_send = get_acts_send(name, "MatchAction")
        nomatch_actions, nomatch_send = get_acts_send(name, "NoMatchAction")

        return TestPack(name, match, match_actions, match_send, unmatch, nomatch, nomatch_actions, nomatch_send)

    def convert(self, resolution):
        if resolution["height"] != self.resolution[1] or resolution["width"] != self.resolution[0]:
            dif_h = resolution["height"] / self.resolution[1]
            dif_w = resolution["width"] / self.resolution[0]
            self.master_crop = dict_scale(self.master_crop, dif_h, dif_w)
        else:
            dif_h, dif_w = 1.0, 1.0
        for test in self.tests.values():
            test.load_images(self.master_crop, [dif_w, dif_h])


class SettingsAccess:
    def __init__(self, filename):
        self.cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        self.cfg.read_file(open(resource_path(filename)))

        def get_pairs(name):
            out = {}
            for pair in self.cfg["Settings"][name].replace(" ", "").split(","):
                pair = pair.split(":")
                out[pair[0]] = int(pair[1])
            return out

        self.reset_key = get_pairs("ResetKey")
        self.video_key = get_pairs("VideoKey")
        self.verbose = True if self.cfg["Settings"]["PerSecondLog"].strip() == "True" else False
