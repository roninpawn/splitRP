import ffmpeg
import numpy as np
from warnings import warn
# import cv2
# from time import time as time


# ----> REQUIRES ffmpeg.exe AND ffprobe.exe ADDED TO CALLING DIRECTORY <----


class VideoStream:
    def __init__(self, path, start=0, end=None, xywh=None):
        self.path = path
        self.start = start

        probe = ffmpeg.probe(self.path)
        inspect = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)

        rate = [float(s) for s in inspect['r_frame_rate'].split("/")]
        self.frame_rate = rate[0] / rate[1]
        self.total_frames = int(inspect['nb_frames'])
        self.end = self.total_frames if end is None else end
        self.frame_range = self.end - self.start
        self.resolution = (int(inspect['width']), int(inspect['height']))
        self.xywh = [0, 0, *self.resolution] if xywh is None else xywh

        self._frame_bytes = self.xywh[2] * self.xywh[3] * 3
        self._frame = []
        self._raw = None
        self._EOF = False

        self.cur_frame = self.start

    def config(self, start=None, end=None, xywh=None):
        if start is not None:
            self.start = start
            self.cur_frame = self.start
        if end is not None: self.end = end
        self.frame_range = self.end - self.start
        if xywh is not None: self.xywh = xywh

    def shape(self): return self.xywh[-2:]

    def _even_test(self):
        w, h = self.xywh[2:]
        if w % 2 > 0: w -= 1
        if h % 2 > 0: h -= 1
        out = [self.xywh[0], self.xywh[1], w, h]
        if out != self.xywh:
            warn("\n'width/height' VALUE IN 'xywh' IS NOT AN EVEN NUMBER\n(Forcing values to lower, even integer. "
                 "This may cause errors in operations that rely on matched resolutions.)\n")

            self.xywh = out

    def open_stream(self):
        self._even_test()
        self.cur_frame = self.start

        self._raw = (ffmpeg
                     .input(self.path)
                     .crop(x=self.xywh[0], y=self.xywh[1], width=self.xywh[2], height=self.xywh[3])
                     .trim(start_frame=self.start, end_frame=self.end)
                     .setpts('PTS-STARTPTS')
                     .output('pipe:', format='rawvideo', pix_fmt='bgr24')
                     .run_async(pipe_stdout=True)
                     )
        self._frame_bytes = self.xywh[2] * self.xywh[3] * 3

    def read(self):
        if not self._EOF:
            byte_stream = self._raw.stdout.read(self._frame_bytes)
            byte_arr = np.frombuffer(byte_stream, np.uint8)
            if len(byte_arr):
                self._frame = byte_arr.reshape([self.xywh[3], self.xywh[2], 3])
                self.cur_frame += 1
            else:
                self._raw.stdout.close()
                self._EOF = True

        return self._EOF, self._frame


# --- BASIC IMPLEMENTATION ---
# path = '720_test.mp4'
# crop = (277, 0, 447, 347)
#
# video = VideoStream(path, xywh=crop)
# start = 10
# end = video.total_frames - 10     # Init'ing the VideoStream without start/end configurations allows programmatic
# video.config(start, end)          # methods using the ffprobe information spawned at creation. (not required)
#
# start = time()
# video.open_stream()
# while True:
#     eof, frame = video.read()
#     if eof: break
#     cv2.imshow('window-name', frame)   # Import cv2 at the top to see the frames as fast as they can be drawn.
#     cv2.waitKey(1)
#
# print(f"\nRead entire file in {round(time() - start, 3)} seconds.")
