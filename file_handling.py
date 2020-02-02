import configparser
import os.path
import cv2
import copy
import numpy as np


# Public Functions
def resource_path(relative_path): return os.path.join(os.path.abspath("."), relative_path)


def xywh2dict(x, y, w, h): return {'left': x, 'top': y, 'width': w, 'height': h}


def dict2xywh(d): return [d["left"], d["top"], d["width"], d["height"]]


def processing(img, color=None, resize=None, crop=None):
    if crop is not None:
        img = img[crop["top"]:crop["top"] + crop["height"], crop["left"]:crop["left"] + crop["width"]]
    if color is not None:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if type(color) is int:
            (thresh, img) = cv2.threshold(img, color, 255, cv2.THRESH_BINARY)
    if resize is not None:
        img = cv2.resize(img, None, fx=resize, fy=resize, interpolation=cv2.INTER_AREA)
    return img


# Classes
class ImagePack:
    def __init__(self, name, directory, files, match_percent=100.0, unmatch_percent=0.0, scale=1.0):
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

    def resize(self, scale_x=1.0, scale_y=None):
        if scale_y is None:
            scale_y = scale_x
        for n in range(0, len(self.images), 1):
            self.images[n] = cv2.resize(self.images[n], None, scale_x, scale_y, cv2.INTER_AREA)


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

        self.resolution = [int(n) for n in self.cfg["Settings"]["NativeResolution"].replace(" ", "").split("x")]
        self.master_crop = xywh2dict(
            *[int(n) for n in self.cfg["Settings"]["ScreenshotArea"].replace(" ", "").replace(":", ",").split(",")])

        self.packs = {}
        pack_list = [s.strip() for s in self.cfg["Settings"]["ImagePacks"].strip().split(",")]
        for pack in pack_list:
            self.packs[pack] = self.build_pack(pack)

        self.tests = {}
        self._test_list = [s.strip() for s in self.cfg["Settings"]["Tests"].strip().split(",")]

        self.runlog = int(self.cfg["Settings"]["RunLogging"].strip())

    def init_tests(self):
        for test in self._test_list:
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
        match_send = self.cfg[name]["MatchSend"].strip().replace("\\r\\n", "\r\n")\
            if "MatchSend" in self.cfg[name].keys() else ''
        nomatch_send = self.cfg[name]["NoMatchSend"].strip().replace("\\r\\n", "\r\n")\
            if "NoMatchSend" in self.cfg[name].keys() else ''
        unmatch = self.cfg[name]["UnMatch"].strip() if "UnMatch" in self.cfg[name].keys() else None
        nomatch = self.cfg[name]["NoMatch"].strip() if "NoMatch" in self.cfg[name].keys() else None
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
        test = TestObject(name, self.master_crop, packs, match_send, unmatch, nomatch, nomatch_send,
                          crop, resize, color)
        return test

    def convert(self, resolution):
        def scale(screen_dict, h, w):
            coords = dict2xywh(screen_dict)
            return xywh2dict(int(coords[0] * w), int(coords[1] * h), int(coords[2] * w), int(coords[3] * h))

        if resolution["height"] != self.resolution[1] or resolution["width"] != self.resolution[0]:
            print("Resizing values to different resolution.")
            dif_h = resolution["height"] / self.resolution[1]
            dif_w = resolution["width"] / self.resolution[0]
            diff = dif_w if dif_w > dif_h else dif_h

            if '{0:.3f}'.format(dif_h) != '{0:.3f}'.format(dif_w):
                print("[Warning: Screen resolution does not match aspect ratio of tests.\r\n"
                      "          No guarantees on this working.]")
            self.master_crop = scale(self.master_crop, dif_h, dif_w)
            for pack in self.packs.values():
                pack.resize(dif_w, dif_h)
            for test in self.tests.values():
                test.crop_area = scale(test.crop_area, dif_h, dif_w)
                test.scale_img /= diff
                test.process_images(self.master_crop)
