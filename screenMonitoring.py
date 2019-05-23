import numpy
import mss.tools
import cv2
import time

# ---Classes---


class screenTest:
    def __init__(self, cap_area, tests):
        self.cap_area = cap_area
        self.tests = tests
        self.last_test = {"name": "Uninitialized", "action": "None"}
        self.shot_history = [screenShot(cap_area)]

    def test(self):
        self.screen = screenShot(self.cap_area)
        self.shot_history = [self.screen, self.shot_history[0]]
        for test in self.tests:
            if test["enabled"]:
                test_area = getRow(self.screen, test["area"], test["threshold"])
                if matchPattern(test_area, test["properties"]):
                    self.last_time = time.time()
                    self.last_test = test
                    return True
        return False



# ---Functions---

def showImage(img, wait=0):
    cv2.imshow("imgWin", img)
    cv2.waitKey(wait)
    cv2.destroyAllWindows()


def screenShot(area):
    with mss.mss() as sct:
        shot = numpy.array(sct.grab(area))
    shot = cv2.cvtColor(shot, cv2.COLOR_BGR2GRAY)
    return shot

def getRow(img, area, thresh):
    if area[0] > area[2]:
        step = -1
    else:
        step = 1
    ar = img[area[1]:area[1]+1, area[0]:area[2]: step]
    ar = cv2.threshold(ar, thresh, 255, cv2.THRESH_BINARY)[1]
    return ar


def matchPattern(img, properties):
    origin, edges, solids, limit, soften = properties
    for start_x in range(0, limit):
        if img[0][start_x] == -(solids[0] - 255):  # Start at first pixel with opposing shade in row.
            img = img[:, start_x:]  # Crop image at first non-white column.
            for new_origin in range(origin[0], origin[0] + origin[1]):
                if img[0][new_origin] == -(solids[0] - 255):  # Re-establish origin as first opposing pixel.
                    if detectEdges(img, edges, soften, new_origin):
                        if detectSolid(img, solids[1:], solids[0], new_origin):
                            return True
                    return False
            return False
    return False


def detectEdges(img, edges, soften=1, origin=0):
    last_pixel = len(img[0]) - 1
    for edge in edges:
        # Soften pattern by building range of area where edge should appear.
        start_soft = edge + origin - soften
        end_soft = edge + origin + soften
        # Constrain values to range of img[]
        if start_soft < 0:
            start_soft = 0
        if end_soft > last_pixel:
            end_soft = last_pixel
        # Find average of the area sliced from img
        sliced = img[0][start_soft:end_soft]  # Slice of img +/- soften'd pixels
        softened = numpy.mean(sliced)
        # Test for edge by demanding non-uniformity
        if softened == 255 or softened == 0:
            return False
    return True


def detectSolid(img, solids, match, origin=0):
    for solid in solids:
        sliced = img[0][solid[0] + origin: solid[0] + origin + solid[1]]
        if len(sliced) > 0 and numpy.mean(sliced[0]) != match:
            return False
    return True
