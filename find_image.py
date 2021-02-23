import cv2
import numpy as np
import os.path
# from time import time


def resource_path(relative_path): return os.path.join(os.path.abspath("."), relative_path)


def load_image(file):
    return cv2.imread(resource_path(file), 1)


def likeness(img1, img2, max_pixel_sum):
    diff_map = cv2.absdiff(img1, img2)  # Composite images into difference map.
    return 100 * (1 - (np.sum(diff_map) / max_pixel_sum))   # Sum difference map and express as percent similarity.


def test_xy_range(img, field, yx1, yx2):
    best = (0.0, 0, 0)  # (match percentage, y, x)
    h, w, channels = np.shape(img)
    max_pixel_sum = h * w * channels * 255

    for y in range(yx1[0], yx2[0] + 1):
        for x in range(yx1[1], yx2[1] + 1):
            cropped_field = field[y:y+h, x:x+w, :]
            match_per = likeness(img, cropped_field, max_pixel_sum)
            if match_per > best[0]:
                best = (match_per, y, x)
    return list(best)


def test_scale_range(img, field, yx1, yx2, s1, s2, s_rate):
    best = (0.0, 0, 0, 0.0, 0.0)    # match_percentage, y, x, best_scale, scale_rate

    for scale in np.arange(s1, s2, s_rate):
        s_img = cv2.resize(img, None, None, scale, scale, cv2.INTER_NEAREST)

        # If scaled image is larger than the field, swap scaled image for field. (due cropping in xy_test)
        img_pair = [(s_img, *np.shape(s_img)), (field, *np.shape(field))]
        if img_pair[0][1] > img_pair[1][1] or img_pair[0][2] > img_pair[1][2]:
            img_pair = img_pair[::-1]

        # Conform yx pairs to valid masking boundaries.
        bound_max = [img_pair[1][1] - img_pair[0][1], img_pair[1][2] - img_pair[0][2]]
        bound_min = [0, 0]
        if yx2[0] < bound_max[0]: bound_max[0] = yx2[0]
        if yx2[1] < bound_max[1]: bound_max[1] = yx2[1]
        if yx1[0] > bound_min[0]: bound_min[0] = yx1[0]
        if yx1[1] > bound_min[1]: bound_min[1] = yx1[1]

        # Conduct translation-limited similarity testing.
        match_xy = test_xy_range(img_pair[0][0], img_pair[1][0], bound_min, bound_max)
        if match_xy[0] > best[0]:
            best = match_xy
            best.extend([scale, s_rate])
#           print(">", best, bound_min, bound_max)
#       else: print(" ", best, bound_min, bound_max)

    return best


def find_image(img, field, field_scale=0.125, yx1=(0,0), yx2=(1000000000, 1000000000), s1=1.2, s2=.2, s_rate=-.2):
    # Single, first-pass test to establish baseline values from calling argument.
    scaled_img = cv2.resize(img, None, None, field_scale, field_scale, cv2.INTER_NEAREST)
    scaled_field = cv2.resize(field, None, None, field_scale, field_scale, cv2.INTER_NEAREST)
    percent, y, x, best_scale, rate = test_scale_range(scaled_img, scaled_field, yx1, yx2, s1, s2, s_rate)
    brute = True

    while field_scale < 1:  # Iterative testing at all scales up to 1.0
        last = None
        if not brute:       # After brute-force testing, conduct targeted, translation-limited, pixel-scale testing.
            field_scale *= 2
            scaled_img = cv2.resize(img, None, None, field_scale, field_scale, cv2.INTER_NEAREST)
            scaled_field = cv2.resize(field, None, None, field_scale, field_scale, cv2.INTER_NEAREST)
            s_rate = -1 / len(scaled_field)
            yx1 = ((y * 2) - 2, (x * 2) - 2)
            yx2 = ((y * 2) + 2, (x * 2) + 2)
            rate *= 4

        while True:
            if brute: s_rate /= 2   # During brute-force, 10%, 5%, 2.5%, 1.25%, 0.625%, etc until same match twice.
            percent, y, x, best_scale, rate = test_scale_range(scaled_img, scaled_field, yx1, yx2, best_scale - rate,
                                                              best_scale + rate, s_rate)
            if last == (percent, x, y): break
            else: last = (percent, x, y)
        brute = False   # End brute-mode after first complete test at lowest resolution.

    h, w = int(best_scale * len(scaled_img)), int(best_scale * len(scaled_img[0]))
    return percent, x, y, w, h      # Return in user-friendly x,y - width,height format.


def valid_halves(width, height, min=100):
    out = [(1.0, width, height)]
    w, h = width, height

    # Seemingly over-complicated way of finding square half-resolutions.
    while w > 1 and h > 1:      # All the way down.
        w, wm = divmod(w, 2)
        h, hm = divmod(h, 2)
        if not wm and not hm:   # If w and h are whole numbers.
            wr = w / width
            hr = h / height
            if wr == hr and w >= min and h >= min:    # If the ratio is square and both values above minimum.
                out.append((wr, w, h))
    return out[::-1]    # Return list, reversed.


# img = load_image('images/Clustertruck/sel1.png')
# field = load_image('test_find3.png')
#
# print("\r\nSearching...")
# start = time()
# percent, x, y, w, h = find_image(img, field)
# print(f"Best match @ xy: {x},{y}  wh: {w},{h}  [{round(percent, 3)}...%] found in {round(time() - start, 3)}s")
#
# for show_off in range(3):
#     out_img = cv2.rectangle(np.copy(field), (x, y), (x + w, y + h), (255, 80, 80), 1)
#     cv2.imshow('images', out_img)
#     cv2.waitKey(0)
#     cv2.imshow('images', field)
#     cv2.waitKey(0)
