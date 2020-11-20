import configparser
import numpy as np
import os.path
import copy
import cv2
from warnings import warn


# Public Functions
def resource_path(relative_path): return os.path.join(os.path.abspath("."), relative_path)


def xywh_scale(xywh, h, w): return [int(xywh[0] * w), int(xywh[1] * h), int(xywh[2] * w), int(xywh[3] * h)]


def processing(img, color=None, resize=None, crop=None):
    if crop is not None:
        img = img[crop[1]:crop[1] + crop[3], crop[0]:crop[0] + crop[2]]
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
    def __init__(self, name, image_paths, match_per, unmatch_per, crop_area, resize, color_proc):
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
            self.crop_area = xywh_scale(self.crop_area, resize[1], resize[0])
            for i in range(2):
                if area[i] + area[i+2] > self.crop_area[i] >= area[i]:    # First:  left + width > left >= left
                    self.crop_area[i] -= area[i]                          # Then:   top + height > top >= top
                else:
                    self.crop_area[i] = 0
        else:
            self.crop_area = [0, 0, area[2], area[3]]

    def load_images(self, area, scale):
        self.conform_crop(area, scale)
        if self.resize is not None:
            self.resize = np.divide(self.resize, scale)
        self.images = []
        for file in self.image_paths:
            img = cv2.imread(resource_path(file), 1)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            img = cv2.resize(img, None, None, scale[0], scale[1], cv2.INTER_AREA)
            img = img[area[1]: area[1] + area[3], area[0]: area[0] + area[2]]   # top: top + height, left: left + width
            img = processing(img, self.color_proc, self.resize, self.crop_area)

            shape = np.shape(img)  # [Pixel height, width, (color channels)]
            color_channels = 1 if len(shape) == 2 else shape[2]
            depth = 255  # depth ought to be resolved based on data type? (uint8 = 255, float = 1?)
            max_pixel_sum = shape[0] * shape[1] * color_channels * depth
            img_sum = int(np.sum(img))  # Add all actual pixel values within image.

            self.images.append([img, img_sum, max_pixel_sum])


class TestPack:
    def __init__(self, name, match_tests, match_actions, unmatch_packs, nomatch_pack, nomatch_actions):
        self.name = name
        self.match_tests = match_tests
        self.match_actions = match_actions
        self.unmatch_packs = unmatch_packs
        self.nomatch_pack = nomatch_pack
        self.nomatch_actions = nomatch_actions


class FileRP:
    def __init__(self, filename):
        self.path = resource_path(filename)
        self.cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        self.cfg.read_file(open(self.path))

        self.resolution = [int(n) for n in self.cfg["Settings"]["NativeResolution"].replace(" ", "").split("x")]
        self.master_crop = [
            int(n) for n in self.cfg["Settings"]["ScreenshotArea"].replace(" ", "").replace(":", ",").split(",")]

        # Optional values Translate / ReScale for processing 'nested' video.
        if "Translate" in self.cfg["Settings"].keys():
            self.translation = [int(n) for n in self.cfg["Settings"]["Translate"].replace(" ", "").split("x")]
        else:
            self.translation = [0, 0]
        if "ReScale" in self.cfg["Settings"].keys():
            self.rescale_values = [int(n) for n in self.cfg["Settings"]["ReScale"].replace(" ", "").split("x")]
        else:
            self.rescale_values = None

        self.directory = resource_path(self.cfg['Settings']['ImageDirectory'].strip() + "/")
        self.tests = {}
        for test in [s.strip() for s in self.cfg["Settings"]["Tests"].strip().split(",")]:
            self.tests[test] = self.build_test(test)
        self.test_packs = {}
        for pack in [s.strip() for s in self.cfg["Settings"]["TestPacks"].strip().split(",")]:
            self.test_packs[pack] = self.build_pack(pack)
        self.first_pack = self.test_packs[self.cfg["Settings"]["StartPack"].strip()]

    def init_packs(self):       # Can this be part of TestPack class?
        for name, pack in self.test_packs.items():
            if pack.unmatch_packs is not None:
                for p in range(0, len(pack.unmatch_packs), 1):
                    pack.unmatch_packs[p] = self.test_packs[pack.unmatch_packs[p]]
            pack.nomatch_pack = self.test_packs[pack.nomatch_pack] if pack.nomatch_pack is not None else pack

        self.first_pack = self.test_packs[self.cfg["Settings"]["StartPack"].strip()]

    def build_test(self, name):
        keys = self.cfg[name].keys()
        imgs = [self.directory + s.strip() for s in self.cfg[name]["Images"].strip().split("|")]
        match = float(self.cfg[name]["Match"].strip())
        unmatch = float(self.cfg[name]["Unmatch"].strip())
        crop = [int(n) for n in self.cfg[name]["Crop"].replace(" ", "").replace(":", ",").split(",")] if "Crop" \
                                                                                                      in keys else None
        resize = float(self.cfg[name]["Resize"].strip()) if "Resize" in keys else None

        if "Color" in keys:
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
        keys = self.cfg[name].keys()
        match = [self.tests[s.strip()] for s in self.cfg[name]["Match"].split(",")]
        unmatch = [s.strip() for s in self.cfg[name]["Unmatch"].split(",")] if "UnMatch" in keys else None
        nomatch = self.cfg[name]["NoMatch"].strip() if "NoMatch" in keys else None
        match_actions = [s.strip().lower() for s in self.cfg[name]["MatchAction"].split(",")] if "MatchAction" \
                                                                                                      in keys else ''
        nomatch_actions = [s.strip().lower() for s in self.cfg[name]["NoMatchAction"].split(",")] if "NoMatchAction" \
                                                                                                      in keys else ''
        return TestPack(name, match, match_actions, unmatch, nomatch, nomatch_actions)

    def convert(self, width, height):
        if height != self.resolution[1] or width != self.resolution[0]:
            dif_h = height / self.resolution[1]
            dif_w = width / self.resolution[0]
            self.master_crop = xywh_scale(self.master_crop, dif_h, dif_w)
        else:
            dif_h, dif_w = 1.0, 1.0

        # Test width/height values of master_crop. Must be even numbers for FFmpeg byte-stream method.
        odd_warning = False
        for i in range(2, 4):   # Force width/height parameters to be even (not odd) integers.
            if self.master_crop[i] % 2 > 0:
                odd_warning = True
                self.master_crop[i] -= 1
        if odd_warning:
            warn(f"\n'ScreenshotArea' in {self.path} contains ODD 'width' and/or 'height.\n"
                 f"Adjusting value(s) to next lower EVEN integer. {self.master_crop[2:]}")

        # Load Images into memory with crop and scale.
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
