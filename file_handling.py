import configparser
import os.path
import cv2
import copy
import numpy as np


# Public Functions
def resource_path(relative_path):
    return os.path.join(os.path.abspath("."), relative_path)


def xywh2dict(x, y, w, h): return {'left':x,'top':y,'width':w,'height':h}


def processing(img, color=None, resize=None, crop=None):
    if crop is not None:
        img = img[crop["top"]:crop["top"] + crop["height"], crop["left"]:crop["left"] + crop["width"]]
    if color is not None:
        img = cv2.cvtColor(img, color)
    if resize is not None:
        img = cv2.resize(img, None, fx=resize, fy=resize, interpolation=cv2.INTER_AREA)
    return img


# Classes
class ImagePack:
    def __init__(self, name, directory, files, match_percent=100.0, unmatch_percent=0.0):
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
            for x in range(0, len(file_arr), 1):
                file_arr[x] = "images" + "/" + dir + "/" + file_arr[x]
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
        self.update_tests(unmatch_test, nomatch_test)
        self.image_tests = []

        if crop_area is None:
            crop_area = {"left":0,"top":0,"width":master_crop["width"],"height":master_crop["height"]}
            self.crop_area = crop_area
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

        self.process_images(master_crop)

    def update_tests(self, unmatch_test=None, nomatch_test=None):
        self.unmatch_test = self if unmatch_test is None else unmatch_test
        self.nomatch_test = self if nomatch_test is None else nomatch_test

    def process_images(self, master_area):
        for pack in self.img_packs:
            for img in pack.images:
                out = np.copy(img)
                out = out[  master_area["top"]:master_area["top"] + master_area["height"],
                            master_area["left"]:master_area["left"] + master_area["width"]]
                out = processing(out, self.color_proc, self.scale_img, self.crop_area)
                self.image_tests.append([out, pack.match_percent, pack.unmatch_percent])


class FileAccess:
    def __init__(self, filename):
        self.cfg = configparser.ConfigParser(inline_comment_prefixes="#")
        self.cfg.read_file(open(resource_path(filename)))

        self.master_crop = xywh2dict(
            *[int(n) for n in self.cfg["Settings"]["ScreenshotArea"].replace(" ", "").replace(":", ",").split(",")])

        self.packs = {}
        packs = [s.strip() for s in self.cfg["Settings"]["ImagePacks"].strip().split(",")]
        for pack in packs:
            self.packs[pack] = self.build_pack(pack)

        self.tests = {}
        tests = [s.strip() for s in self.cfg["Settings"]["Tests"].strip().split(",")]
        for test in tests:
            self.tests[test] = self.build_test(test)
        for name, test in self.tests.items():
            unmatch = self.tests[test.unmatch_test] if type(test.unmatch_test) is str else None
            nomatch = self.tests[test.nomatch_test] if type(test.nomatch_test) is str else None
            test.update_tests(unmatch, nomatch)

        self.first_test = self.tests[self.cfg["Settings"]["FirstTest"].strip()]

    def build_pack(self, name):
        dir = self.cfg[name]["Directory"].strip()
        imgs = "|".join([s.strip() for s in self.cfg[name]["Images"].strip().split("|")])
        match = float(self.cfg[name]["Match"].strip())
        unmatch = float(self.cfg[name]["Unmatch"].strip())

        pack = ImagePack(name, dir, imgs, match, unmatch)
        return pack

    def build_test(self, name):
        packs = [self.packs[s.strip()] for s in self.cfg[name]["ImagePacks"].strip().split(",")]
        match_send = self.cfg[name]["MatchSend"].strip() if "MatchSend" in self.cfg[name].keys() else ""
        nomatch_send = self.cfg[name]["NoMatchSend"].strip() if "NoMatchSend" in self.cfg[name].keys() else ""
        unmatch = self.cfg[name]["UnMatch"].strip() if "UnMatch" in self.cfg[name].keys() else None
        nomatch = self.cfg[name]["NoMatch"].strip() if "NoMatch" in self.cfg[name].keys() else None
        if "Crop" in self.cfg[name].keys():
            crop = xywh2dict(*[int(n) for n in self.cfg[name]["Crop"].replace(" ", "").replace(":", ",").split(",")])
        else:
            crop = None
        resize = float(self.cfg[name]["Resize"].strip()) if "Resize" in self.cfg[name].keys() else None
        color = int(self.cfg[name]["Color"].strip()) if "Color" in self.cfg[name].keys() else None

        test = TestObject(name, self.master_crop, packs, match_send, unmatch, nomatch, nomatch_send,
                          crop, resize, color)
        return test