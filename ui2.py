from guiABLE import *
import cv2
import PIL.Image, PIL.ImageTk
from tkinter import filedialog
from math import floor
from sys import exit
import time
from os import path
from find_image import *


def array2tk(array, width, height):
    out = cv2.resize(array, (width, height), interpolation=cv2.INTER_NEAREST)
    out = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
    out = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(out))
    return out


def time_to_hms(t):
    return f"{time.strftime('%H:%M:%S', time.localtime(t))}.{repr(t).split('.')[1][:3]}"


def secs_to_hms(dur, hms_style=False):
    style = [":", ":", ".", ""] if not hms_style else ["h ", "m ", "s ", "ms"]

    if dur <= 0:
        return f"0{style[2]}000{style[3]}"
    else:
        h = floor(dur / 3600)
        dur -= h * 3600
        m, s = divmod(int(dur), 60)
        ms = '{:.03f}'.format(dur)[-3:]
        out = f"{h}{style[0]}" if h > 0 else ""
        if m > 0:
            out += f"{'{:02d}'.format(m)}{style[1]}{'{:02d}'.format(s)}{style[2]}{ms}{style[3]}"
        else:
            out += f"{s}{style[2]}{ms}{style[3]}"
        return out


def frames_to_hms(f, rate, hms_style=False):
    return secs_to_hms(f / rate, hms_style)


class MainUI(tk.Tk):
    def __init__(self, engine, settings):
        self.engine = engine
        self.settings = settings
        self.mark_in, self.mark_out = 0, 0
        # Insantiate and Configure Window
        super().__init__()
        self.configure(bg='darkblue')
        self.minsize(1024, 576)

        self.magic_override = None

        # --- Menu Bar ---
        menu = tk.Menu(self)
        self.config(menu=menu)
        self.resizable(0, 0)
        file = tk.Menu(menu, tearoff=False)
        file.add_command(label="Open", command=self.openfile)
        file.add_command(label="Exit", command=exit)
        menu.add_cascade(label="File", menu=file)
        # --- Screen ---
        topframe = tk.Frame(self, pady=10, bg='darkblue')
        self.screen = VideoPlayer(topframe, width=800, height=450, bg='black')
        self.screen.pack(padx=5, side=tk.LEFT)
        # --- Right Bar ---
        self.rundata = ScrollablePane(topframe, 200, 450, auto=(True, True))
        self.rundata.pack(padx=5, side=tk.RIGHT)
        self.rundata.update()
        topframe.pack(side=tk.TOP, expand=tk.TRUE, fill=tk.BOTH)

        self.notice = tk.Label(self, text="!! In this version: App will freeze during Analysis !!",
                               font=("", 12), bg='yellow')
        self.notice.pack(side=tk.TOP)

        # --- Timeline ---
        trough_wrap = tk.Frame(self, width=800, padx=5, pady=5, bg='lightblue')
        self.timeline = Timeline(trough_wrap, width=800, height=50, bg='darkgray')
        self.timeline.pack(padx=5, pady=3, side=tk.BOTTOM)
        self.timeline.link_player(self.screen)
        # --- Labels ---
        self.in_lbl = tk.Label(trough_wrap, text=f"IN: {0}", font=("", 12), bg='lightblue')
        self.out_lbl = tk.Label(trough_wrap, text=f"OUT: {0}", font=("", 12), bg='lightblue')

        self.in_lbl.pack(side=tk.LEFT)
        self.out_lbl.pack(side=tk.RIGHT)

        # --- Button ---
        self.analyze_button = tk.Button(trough_wrap, text="Analyze", pady=5, padx=10, bd=2, state=tk.DISABLED)
        self.magic_button = tk.Button(self, text="Magic Button", pady=5, padx=10, bd=2, state=tk.DISABLED)
        self.analyze_button.pack(side=tk.TOP)
        self.magic_button.place(x=600, y=499)

        trough_wrap.pack(side=tk.TOP)

    def update_inout(self):
        if self.screen.total_frames > 0:
            m_in = self.timeline.cursors['in'].frame
            m_out = self.timeline.cursors['out'].frame
            # Flip in and out, if needed, based on frame.
            if m_in < m_out:
                self.mark_in = m_in
                self.mark_out = m_out
            elif m_in > m_out:
                self.mark_in = m_out
                self.mark_out = m_in

            self.in_lbl.configure(text=f'IN: {frames_to_hms(self.mark_in, self.screen.frame_rate)}')
            self.out_lbl.configure(text=f'OUT: {frames_to_hms(self.mark_out, self.screen.frame_rate)}')

    def openfile(self):
        filename = filedialog.askopenfilename(initialdir=self.settings.last_dir, title="Select file",
                                              filetypes=(("MP4s", "*.mp4"), ("all files", "*.*")))
        if filename is not "":
            self.settings.last_dir = path.split(filename)[0]
            self.settings.save()
            self.screen.load_video(filename)
            self.rundata.empty()
            self.timeline.reset()
            self.timeline.set_frames(self.screen.total_frames)
            self.timeline.add_cursor("in", 0, self.update_inout)
            self.timeline.add_cursor("out", self.screen.total_frames, self.update_inout)
            self.update_inout()
            self.screen.draw_frame()
            self.analyze_button.configure(state=tk.ACTIVE, command=self.analyze)
            self.magic_button.configure(state=tk.ACTIVE, command=self.magic_find)
            self.magic_override = None

    def analyze(self):
        self.analyze_button.configure(state=tk.DISABLED)
        self.magic_button.configure(state=tk.DISABLED)
        self.rundata.empty()
        self.timeline.reset()
        [cursor.place_forget() for name, cursor in self.timeline.cursors.items() if type(name) is int]
        self.timeline.add_cursor("scrubber", self.mark_in)
        self.timeline.cursors["scrubber"].configure(bg='red', width=1)
        [cursor.disable() for cursor in self.timeline.cursors.values()]
        self.update()
        self.engine.analyze(self.screen.filename, start=self.mark_in, end=self.mark_out, override=self.magic_override)
        [cursor.enable() for name, cursor in self.timeline.cursors.items() if type(name) is not int]
        self.timeline.cursors["scrubber"].place_forget()
        self.timeline.add_cursor("in", 0, self.update_inout)
        self.timeline.add_cursor("out", self.screen.total_frames, self.update_inout)
        self.update_inout()
        self.magic_button.configure(state=tk.ACTIVE)
        self.analyze_button.configure(state=tk.ACTIVE)

    def magic_find(self):
        filename = filedialog.askopenfilename(initialdir="./images", title="Select Image to Match",
                                              filetypes=(("PNGs", "*.png"), ("all files", "*.*")))
        if filename is not "":
            self.analyze_button.configure(state=tk.DISABLED)
            self.magic_button.configure(state=tk.DISABLED)
            [cursor.disable() for cursor in self.timeline.cursors.values()]
            self.update()

            img = load_image(filename)
            self.screen.video.set(cv2.CAP_PROP_POS_FRAMES, self.timeline.selected_frame)
            has_frames, field = self.screen.video.read()
            print("Searching image for best match...")
            percent, x, y, w, h = find_image(img, field)
            print(f"Best match: {percent} @ xy: {x},{y} wh: {w},{h}")

            self.magic_override = ((x, y), (w, h))

            field = cv2.rectangle(field, (x, y), (x + w, y + h), (255, 255, 80), 2)
            self.screen.image = array2tk(field, 800, 450)
            self.screen.create_image(0, 0, anchor=tk.NW, image=self.screen.image)
            self.screen._last_draw = time.time()

            [cursor.enable() for name, cursor in self.timeline.cursors.items() if type(name) is not int]
            self.magic_button.configure(state=tk.ACTIVE)
            self.analyze_button.configure(state=tk.ACTIVE)


    def pop_splits(self, splits, rate):
        for split in splits:
            rta_time = frames_to_hms(split.rta, rate)
            igt_time = frames_to_hms(split.igt, rate)
            waste_time = frames_to_hms(split.waste, rate)

            out = f"- {split.num} -  ({frames_to_hms(split.sum_rta, rate)} | {frames_to_hms(split.sum_igt, rate)})\n" \
                f"          RTA: {rta_time} ({split.rta})\n" \
                f"          IGT: {igt_time} ({split.igt})\n" \
                f"          WASTE: {waste_time} ({split.waste})"

            self.add_text_entry(out)
            self.timeline.add_block(split.start + split.waste, split.start + split.rta)

        if len(splits):
            split = splits[-1]
            out = f"-TOTAL -\n" \
                f"          RTA: {frames_to_hms(split.sum_rta, rate)} ({split.sum_rta})\n" \
                f"          IGT: {frames_to_hms(split.sum_igt, rate)} ({split.sum_igt})\n" \
                f"          WASTE: {frames_to_hms(split.sum_waste, rate)} ({split.sum_waste})"

            self.add_text_entry(out)

    def add_text_entry(self, text):
        # Text to scroll frame
        w = self.rundata.inner_width-self.rundata.v_scroll.winfo_width()
        frame1 = tk.Frame(self.rundata.inner, bg='purple', width=w, bd=2, relief='ridge')
        data1 = tk.Label(self.rundata.inner, bg='yellow', justify=tk.LEFT, anchor=tk.W)
        data1.configure(text=text)
        data1.configure(wraplength=w)
        data1.pack(anchor=tk.NW, expand=tk.TRUE, fill=tk.X)
        frame1.pack(fill=tk.X, expand=tk.TRUE)


class VideoPlayer(tk.Canvas):
    def __init__(self, parent, width, height, **kwargs):
        super().__init__(parent, width=width, height=height, bd=0, highlightthickness=0, **kwargs)
        self.total_frames = 0
        self.video = None
        self.image = None
        self.filename = None
        self._last_draw = time.time()

    def load_video(self, filename):
        if filename is not "":
            self.filename = filename
            self.video = cv2.VideoCapture(filename)
            self.total_frames = self.video.get(cv2.CAP_PROP_FRAME_COUNT)
            self.frame_rate = self.video.get(cv2.CAP_PROP_FPS)

    def draw_frame(self, frame=0, limit=0, gray=False):
        if self.video is not None:
            if limit == 0 or time.time() - self._last_draw > limit:
                self.video.set(cv2.CAP_PROP_POS_FRAMES, frame)
                has_frames, self.image = self.video.read()
                if has_frames:
                    self.image = array2tk(self.image, 800, 450)
                    self.create_image(0, 0, anchor=tk.NW, image=self.image)
                    self._last_draw = time.time()


class Timeline(Backgroundable):
    def __init__(self, parent, width, height, frames=1, cursor_width=10, image_path=None, **kwargs):
        super().__init__(parent, width, height, image_path, **kwargs)
        self.width = width
        self.height = height
        self._frames, self._frame_width = 1, 1
        self.set_frames(frames, width)
        self.cursor_width = cursor_width if cursor_width < width else width - 1
        self.cursors = {}
        self.blocks = {}
        self.selected_frame = 0
        self._player = None

    def reset(self):
        for c in self.cursors.values():
            c.destroy()
        for b in self.blocks.values():
            b.destroy()
        self.cursors = {}

    def link_player(self, player):
        self._player = player

    def add_cursor(self, name, frame, function=lambda: None):
        new_cursor = Cursor(self, function, width=self.cursor_width, height=self.height)
        new_cursor.frame, new_cursor.width = int(frame), self.cursor_width
        x = int(frame * self._frame_width)
        self.cursors[name] = new_cursor
        new_cursor.place(x=x, y=0)
        return new_cursor

    def move_to(self, cursor, frame):
        cursor.place_configure(x=floor(frame * self._frame_width))

    def cursor_move(self, cursor, event):
        x = event.x - cursor.x + cursor.winfo_x()
        new_x, cursor.frame = self.snap(x)
        cursor.place_configure(x=new_x)
        self.selected_frame = cursor.frame

        if self._player is not None:
            self._player.draw_frame(cursor.frame, 1/20)

    def cursor_release(self, cursor):
        if self._player is not None:
            self._player.draw_frame(cursor.frame)

    def cursor_click(self, cursor):
        if self._player is not None:
            self._player.draw_frame(cursor.frame)

    def set_frames(self, total_frames, width=None):
        self._frames = int(total_frames) if total_frames > 0 else 1
        if width is None : width = self.winfo_width() - self.cursor_width
        self._frame_width = width / self._frames

    def snap(self, x):
        if x <= 0:
            return 0, 0
        else:
            per = x / (self.winfo_width() - self.cursor_width)
            frame = int(per * self._frames)
            if frame > self._frames : frame = self._frames
            snap_x = floor(frame * self._frame_width)
            return snap_x, frame

    def add_block(self, start, end):
        def draw_cursor(frame, color):
            self.add_cursor(frame, frame)
            self.cursors[frame].configure(bg=color, width=1)
            self.cursors[frame].disable()

        draw_cursor(start, 'purple')
        draw_cursor(end, 'green')
        x = start * self._frame_width
        width = (end - start) * self._frame_width
        new_trough = Backgroundable(self, width, self.height, bg='yellow')
        new_trough.place(x=x, y=0)
        new_trough.lower(self.cursors[list(self.cursors.keys())[0]])
        self.blocks[start] = new_trough


class Cursor(Draggable):
    def __init__(self, parent, function=lambda: None, skinnable=None, delay=50, init_delay=1, **kwargs):
        super().__init__(parent, function, skinnable, delay, init_delay, **kwargs)
        self.frame = 0

    def mouseUp(self, event):
        super().mouseUp(event)
        self.master.cursor_release(self)
        self.function()

    def clicked(self, event):
        self.master.cursor_click(self)
        super().clicked(event)

    def mouseDrag(self, event):
        self.master.cursor_move(self, event)
        self.function()

