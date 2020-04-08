import tkinter as tk
from time import time as time
from warnings import warn


def limitMove(start, size, low_bound, high_bound):
    if start < low_bound:
        return low_bound
    elif start + size > high_bound:
        return high_bound - size
    return start


def getLocalMouse(widget):
    x = widget.winfo_pointerx() - widget.winfo_rootx()
    y = widget.winfo_pointery() - widget.winfo_rooty()
    if x < 0 or x > widget.winfo_width():
        return x, y, False
    if y < 0 or y > widget.winfo_height():
        return x, y, False
    return x, y, True   # Returns local x and y coordinates of mouse, and whether mouse is over widget.


def updateHover(widget):
    x, y, mouse_in = getLocalMouse(widget)
    if widget.enabled:
        widget.mouseIn(None) if mouse_in else widget.mouseOut(None)
    else:
        widget.disable()
    

def drawBar(trough_image, cap_image, width, height, horizontal=False):
    newimg = tk.PhotoImage(width=width, height=height)
    cap_w, cap_h = cap_image.width(), cap_image.height()

    if horizontal or width > height:
        putToImage(cap_image, newimg, (0, 0, cap_h, cap_w), rotate=True)
        putToImage(trough_image, newimg, (cap_h, 0, width-cap_h, height), rotate=True)
        putToImage(cap_image, newimg, (width-cap_h, 0, width, height), mirror_x=True, rotate=True)
    else:
        cap_h = cap_image.height()
        putToImage(cap_image, newimg, (0, 0, cap_w, cap_h))
        putToImage(trough_image, newimg, (0, cap_h, width, height-cap_h))
        putToImage(cap_image, newimg, (0, height-cap_h, width, height), mirror_y=True)
    return newimg


def putToImage(brush, canvas, bbox, mirror_x=False, mirror_y=False, rotate=False):
    value1 = brush.height() if rotate else brush.width()
    value2 = brush.width() if rotate else brush.height()
    start1, end1, increment1 = (value1-1, -1, -1) if mirror_x else (0, value1, 1)
    start2, end2, increment2 = (value2-1, -1, -1) if mirror_y else (0, value2, 1)

    data = ""
    for col in range(start2, end2, increment2):
        data = data + "{"
        for row in range(start1, end1, increment1):
            data = data + "#%02x%02x%02x " % brush.get(col if rotate else row, row if rotate else col)
        data = data + "} "
    canvas.put(data, to=bbox)


class Windowable(tk.Tk):
    def __init__(self, geometry="200x200", title=""):
        self._mid_width = 0
        self._mid_height = 0
        self._lost_focus = time()
        self.child_list = []
        self.lock_handle = True

        super().__init__()
        self.overrideredirect(True)
        self.title(title)
        self.geometry(geometry)

        self.taskbar_handle = tk.Toplevel(self)
        self.taskbar_handle.title(title)

        taskbar_geometry = self.geometry()
        self.taskbar_handle.geometry(f"0x0+{taskbar_geometry.split('+', 1)[1]}")
        self.taskbar_handle.wm_attributes('-alpha', 0.0)     # On windows, calling early prevents white-flash.
        self.taskbar_handle.wait_visibility()                # On linux, alpha change has no effect until first load.
        self.taskbar_handle.wm_attributes('-alpha', 0.0)
        self.taskbar_handle.iconify()

        self.bind("<ButtonRelease-1>", self.mouseUp)
        self.bind("<FocusIn>", self.tookFocus)
        self.bind("<FocusOut>", self.lostFocus)
        self.taskbar_handle.bind("<Map>", self.deiconify)

        self.update_idletasks()

    def bindDrag(self, widget):
        if widget is None:
            widget.unbind("<B1-Motion>")
        else:
            widget.bind("<B1-Motion>", self.mouseDrag)

    def bindChild(self, ChildableWindow): self.child_list.append(ChildableWindow)

    def loadTabImage(self, image_path):
        img = tk.PhotoImage(file=image_path)
        img_w, img_h = img.width(), img.height()
        self._mid_width = int((img_w - self.winfo_width()) / 2)
        self._mid_height = int((img_h - self.winfo_height()) / 2)

        self.lock_handle = False
        self.taskbar_handle.deiconify()
        self.taskbar_handle.geometry(f"{img_w}x{img_h}"
                                     f"+{self.winfo_rootx() - self._mid_width}+{self.winfo_rooty() - self._mid_height}")
        tab_image = Backgroundable(self.taskbar_handle, img_w, img_h)
        tab_image.directSetImage(img)
        tab_image.place(x=0, y=0)
        self.taskbar_handle.update()
        self.taskbar_handle.iconify()
        self.lock_handle = True

    def mouseDrag(self, event):
        if self.lock_handle:
            self.x = event.x
            self.y = event.y
            self.lock_handle = False
            self.taskbar_handle.deiconify()
            self.focus_force()
            self.active_children = [child for child in self.child_list if child.visible]

        x = self.winfo_x() + event.x - self.x
        y = self.winfo_y() + event.y - self.y
        self.taskbar_handle.geometry(f"+{x - self._mid_width}+{y - self._mid_height}")
        self.geometry(f"+{x}+{y}")
        [child.geometry(f"+{x + child.winfo_x()}+{y + child.winfo_y()}") for child in self.active_children]

    def mouseUp(self, event):
        if not self.lock_handle:
            self.taskbar_handle.wm_iconify()
            self.focus_force()
            self.lock_handle = True

    def tookFocus(self, event):
        [child.lift() for child in self.child_list]

    def lostFocus(self, event):
        self._lost_focus = time() + .4

    def iconify(self, event=None):
        [child.withdraw() for child in self.child_list]
        self.withdraw()
        self.taskbar_handle.iconify()

    def deiconify(self, event=None):
        if self.lock_handle:
            if self.wm_state() == tk.NORMAL and time() < self._lost_focus:
                self.iconify()
            else:
                super().deiconify()
                [child.deiconify() for child in self.child_list]
                self.focus_force()
            self.taskbar_handle.wm_iconify()


class ChildableWindow(tk.Toplevel):
    def __init__(self, parent, position=(100, 100), visible=False, **kwargs):
        parent.bindChild(self)
        self._visible = visible

        super().__init__(parent, **kwargs)
        self.overrideredirect(True)
        self.geometry(f"+{self.master.winfo_rootx() + position[0]}+{self.master.winfo_rooty() + position[1]}")
        self.update_idletasks()

        if not self._visible:
            self.withdraw()

    def winfo_x(self): return self.winfo_rootx() - self.master.winfo_rootx()

    def winfo_y(self): return self.winfo_rooty() - self.master.winfo_rooty()

    def deiconify(self):
        if self._visible:
            self.geometry(f"+{self.master.winfo_rootx() + self.winfo_x()}+{self.master.winfo_rooty() + self.winfo_y()}")
            super().deiconify()

    def visible(self, bool=None):
        if bool is not None:
            self._visible = bool
        else:
            return self._visible
        self.deiconify() if self._visible else self.withdraw()


class Canvasable(tk.Text):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bd=0, padx=0, pady=0, state=tk.DISABLED, cursor="arrow", **kwargs)
        self.configure(selectbackground=self.cget("bg"))

    def _configure(self, cmd, cnf, kw):
        if "bg" in kw:
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super()._configure(cmd, cnf, kw)


class Backgroundable(tk.Frame):
    def __init__(self, parent, width, height, image_path=None, **kwargs):
        super().__init__(parent, width=width, height=height)
        self.pack_propagate(tk.FALSE)
        self.inner = Canvasable(self, **kwargs)

        if image_path is not None:
            self.setImage(image_path)
        self.inner.pack(fill=tk.BOTH, expand=True)

    def setImage(self, image_path):
        try:
            self.directSetImage(tk.PhotoImage(file=image_path))
        except tk.TclError:
            warn(f"guiABLE: Image not found: {image_path}", RuntimeWarning)

    def directSetImage(self, image):
        self.inner.configure(state=tk.NORMAL)
        self.inner.delete(1.0, tk.END)
        self._img = image
        self.inner.image_create(tk.END, image=self._img)
        self.inner.configure(state=tk.DISABLED)


class Skinnable():
    def __init__(self, normal_path=None, hover_path=None, active_path=None, disabled_path=None):
        self._recipients = []
        self._paths = [normal_path, hover_path, active_path, disabled_path]
        self._images = [None, None, None, None]

        self.changePaths(normal_path, hover_path, active_path, disabled_path)

        if self._images[0] is None:
            for n in range(1, 4):
                if self._images[n] is not None:
                    self._images[0] = self._images[n]
                    break
            if self._images[0] is None:
                self._images[0] = tk.PhotoImage(width=0, height=0)

        for n in range(1, 3):
            if self._images[n] is None:
                self._images[n] = self._images[n-1]
                self._paths[n] = self._paths[n-1]

        if self._images[3] is None:
            self._paths[3] = self._paths[0]
            self._images[3] = self._images[0]

    def changePaths(self, normal_path=None, hover_path=None, active_path=None, disabled_path=None, _direct=False):
        paths = [normal_path, hover_path, active_path, disabled_path]
        for n in range(4):
            if paths[n] is not None:
                if not self._checkDuplicates(paths[n], n):
                    self._paths[n] = paths[n]
                    if _direct:
                        self._images[n] = paths[n]
                    else:
                        self._loadImg(paths[n], n)

    def directSetImages(self, normal_img=None, hover_img=None, active_img=None, disabled_img=None):
        self.changePaths(normal_img, hover_img, active_img, disabled_img, True)

    def bindWidget(self, widget): self._recipients.append(widget)

    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def updateRecipients(self): [updateHover(recipient) for recipient in self._recipients]

    def paths(self): return self._paths

    def images(self): return self._images

    def _checkDuplicates(self, reference, index):
        for i in range(4):
            if self._images[i] is not None and self._paths[i] == reference:
                self._paths[index] = reference
                self._images[index] = self._images[i]
                return True
        return False

    def _loadImg(self, img_path, index):
        if img_path is not None:
            try:
                self._images[index] = tk.PhotoImage(file=img_path)
            except tk.TclError:
                warn(f"guiABLE: Image not found: {img_path}", RuntimeWarning)


class Imageable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.enabled = True

        if skinnable is not None:
            self._skin = None
            self.setSkin(skinnable)
        else:
            self._skin = Skinnable()
        self.current_image = 0
        self.enable()

    def setSkin(self, skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable

    def clearSkin(self):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        self._skin.images = [[],[],[],[]]

    def changeImage(self, img_number):
        self.current_image = img_number
        self.create_image(0, 0, image=self._skin.images()[img_number], anchor=tk.NW)

    def enable(self):
        self.create_image(0, 0, image=self._skin.images()[self.current_image], anchor=tk.NW)
        self.enabled = True

    def disable(self):
        self.create_image(0, 0, image=self._skin.images()[3], anchor=tk.NW)
        self.enabled = False


class Hoverable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)

        self.enabled = True
        self.moused_over = False

        if skinnable is not None:
            self._skin = None
            self.setSkin(skinnable)
        else:
            self._skin = Skinnable()
        self.enable()

    def setSkin(self, skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable
        updateHover(self)

    def clearSkin(self):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        self._skin.images = [[],[],[],[]]

    def mouseIn(self, event):
        self.moused_over = True
        self.configure(bg="white")
        self.create_image(0, 0, image=self._skin.images()[1], anchor=tk.NW)

    def mouseOut(self, event):
        self.moused_over = False
        self.configure(bg="gray")
        self.create_image(0, 0, image=self._skin.images()[0], anchor=tk.NW)

    def enable(self):
        self.bind("<Enter>", self.mouseIn)
        self.bind("<Leave>", self.mouseOut)
        self.enabled = True
        updateHover(self)

    def disable(self):
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.create_image(0, 0, image=self._skin.images()[3], anchor=tk.NW)
        self.enabled = False


class Clickable(Hoverable):
    def __init__(self, parent, function=lambda: None, skinnable=None, **kwargs):
        self.function = function
        super().__init__(parent, skinnable, **kwargs)

    def clicked(self, event):
        self.configure(bg="red")
        self.create_image(0, 0, image=self._skin.images()[2], anchor=tk.NW)
        self.function()
        updateHover(self)

    def mouseUp(self, event):
        self.mouseIn(event) if self.moused_over else self.mouseOut(event)

    def enable(self):
        super().enable()
        self.bind("<Button-1>", self.clicked)
        self.bind("<ButtonRelease-1>", self.mouseUp)

    def disable(self):
        super().disable()
        self.unbind("<Button-1>")
        self.unbind("<ButtonRelease-1>")


class Pushable(Clickable):
    def __init__(self, parent, function=lambda: None, skinnable=None, **kwargs):
        self._clicking = False
        super().__init__(parent, function, skinnable, **kwargs)

    def clicked(self, event):
        self._clicking = True
        self.configure(bg="red")
        self.create_image(0, 0, image=self._skin.images()[2], anchor=tk.NW)

    def mouseUp(self, event):
        self._clicking = False
        super().mouseUp(event)
        if self.moused_over:
            self.function()
            updateHover(self)

    def mouseIn(self, event):
        if not self._clicking:
            super().mouseIn(event)
        else:
            self.moused_over = True
            self.configure(bg="red")
            self.create_image(0, 0, image=self._skin.images()[2], anchor=tk.NW)


class Labelable(Pushable):
    def __init__(self, parent, function=lambda: None, skinnable=None, text="", text_pos=(0,0), font="Times", color="gray",
                 drop_pos=(0, 0), drop_color="black", **kwargs):
        self.text, self.text_pos, self.color, self.font = text, text_pos, color, font
        self.drop_pos, self.drop_color, = drop_pos, drop_color
        super().__init__(parent, function, skinnable, **kwargs)

    def drawText(self, text, text_pos=(0,0), font="Times", color="gray", drop_pos=(0, 0), drop_color="black"):
        x, y = text_pos
        dx, dy = drop_pos
        self.create_text(x+dx, y+dy, text=text, fill=drop_color, font=font, anchor=tk.NW)
        self.create_text(x, y, text=text, fill=color, font=font, anchor=tk.NW)

    def mouseOut(self, event):
        super().mouseOut(event)
        self.drawText(self.text, self.text_pos, self.font, self.color, self.drop_pos, self.drop_color)

    def mouseIn(self, event):
        super().mouseIn(event)
        self.drawText(self.text, self.text_pos, self.font, self.color, self.drop_pos, self.drop_color)

    def clicked(self, event):
        super().clicked(event)
        self.drawText(self.text, self.text_pos, self.font, self.color, self.drop_pos, self.drop_color)

    def mouseUp(self, event):
        super().mouseUp(event)
        self.drawText(self.text, self.text_pos, self.font, self.color, self.drop_pos, self.drop_color)


class Toggleable(Pushable):
    def __init__(self, parent, state=None, function=lambda: None, skinnable_1=None, skinnable_2=None, **kwargs):
        self._state = state
        super().__init__(parent, function, skinnable_1, **kwargs)
        if skinnable_1 is None and skinnable_2 is None:
            self._skins = [[[],[],[],[]], [[],[],[],[]]]
        else:
            if skinnable_2 is None:
                skinnable_1.bindWidget(self)
                skinnable_2 = skinnable_1
            elif skinnable_1 is None:
                skinnable_2.bindWidget(self)
                skinnable_1 = skinnable_2
            else:
                skinnable_1.bindWidget(self)
                skinnable_2.bindWidget(self)

            self._skins = [skinnable_1, skinnable_2]
            self._skin = self._skins[not self._state]

        updateHover(self)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self._state = not self._state
            self._skin = self._skins[not self._state]
            self.function()
            self.configure(bg="gray")
            self.create_image(0, 0, image=self._skin.images()[0], anchor=tk.NW)

    def state(self, state=None):
        if state is None:
            return self._state
        else:
            self._state = state
            self._skin = self._skins[not self._state]
            updateHover(self)


class Holdable(Pushable):
    def __init__(self, parent, function=lambda: None, skinnable=None, delay=100, init_delay=400, **kwargs):
        self.delay = delay
        self.init_delay = init_delay
        super().__init__(parent, function, skinnable, **kwargs)

    def mouseOut(self, event):
        self.moused_over = False if self._clicking else super().mouseOut(None)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.mouseIn(event)

    def clicked(self, event):
        super().clicked(event)
        self.function()
        if self.function is not None:
            self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            self.function()
            self.after(self.delay, self._keepClicking)


class Draggable(Holdable):
    def clicked(self, event):
        self.x = event.x
        self.y = event.y
        super().clicked(event)

    def mouseDrag(self, event):
        x = event.x - self.x + self.winfo_x()
        y = event.y - self.y + self.winfo_y()
        x = limitMove(x, self.winfo_width(), 0, self.master.winfo_width())
        y = limitMove(y, self.winfo_height(), 0, self.master.winfo_height())

        self.place_configure(x=x, y=y)

    def enable(self):
        self.bind("<B1-Motion>", self.mouseDrag)
        super().enable()

    def disable(self):
        self.unbind("<B1-Motion>")
        super().disable()


class Troughable(Backgroundable):
    def __init__(self, parent, width, height, skinnable=None, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)

        self.enabled = True
        self._clicking = False
        self._skin = skinnable if skinnable is not None else Skinnable()
        self.enable()

    def setSkin(self, skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable

    def mouseOut(self, event):
        if not self._clicking:
            self.directSetImage(self._skin.images()[0])
            self.inner.configure(bg="darkgray")
        self.moused_over = False

    def mouseIn(self, event):
        if not self._clicking:
            self.directSetImage(self._skin.images()[1])
            self.inner.configure(bg="lightgray")
        self.moused_over = True

    def clicked(self, event):
        self.directSetImage(self._skin.images()[2])
        self.inner.configure(bg="red")
        self._clicking = True

    def mouseUp(self, event):
        self._clicking = False
        self.mouseIn(event) if self.moused_over else self.mouseOut(event)

    def enable(self):
        self.inner.bind("<Enter>", self.mouseIn)
        self.inner.bind("<Leave>", self.mouseOut)
        self.inner.bind("<Button-1>", self.clicked)
        self.inner.bind("<ButtonRelease-1>", self.mouseUp)
        self.enabled = True
        updateHover(self)

    def disable(self):
        self.inner.unbind("<Enter>")
        self.inner.unbind("<Leave>")
        self.inner.unbind("<Button-1>")
        self.inner.unbind("<ButtonRelease-1>")
        self.directSetImage(self._skin.images()[3])
        self.enabled = False


class Scrollable(Troughable):
    def __init__(self, parent, trough_width, trough_height, handle_width, handle_height, scrollable_skin=None, **kwargs):
        self.scrollwheel_speed = 10
        self.page_percent = .9
        self.init_delay = 400
        self.delay = 100

        skin_troughs = scrollable_skin.troughs if scrollable_skin is not None else None
        self.active_handle_x, self.active_handle_y = True, True

        super().__init__(parent, trough_width, trough_height, skin_troughs, **kwargs)

        if scrollable_skin is None: scrollable_skin = ScrollableSkin()
        self.handle = Draggable(self.inner, skinnable=scrollable_skin.handles, width=handle_width, height=handle_height)
        self.handle.place(x=0, y=0)

    def enable(self):
        if not self.enabled:
            self.handle.enable()
            if self.linked: self._linkTo()
        super().enable()

    def disable(self):
        self.handle.disable()
        super().disable()

    def setSkin(self, scroll_skinnable):
        super().setSkin(scroll_skinnable)
        self.handle.setSkin(scroll_skinnable)

    def linkTo(self, scrollablecanvas, movement_modifier=-1, active_handle_xy=(True, True), canvas_offset=(0.0, 0.0)):
        self.movement_modifier = movement_modifier
        self._linked = scrollablecanvas
        self._linkedwidth, self._linkedheight = self._linked.inner.winfo_width(), self._linked.inner.winfo_height()
        self.active_handle_x, self.active_handle_y = active_handle_xy
        self.x_offset, self.y_offset = canvas_offset
        self._linkTo()

    def _linkTo(self):
        if self.active_handle_y:
            self.bind_all("<MouseWheel>", self.scroll, "+")
        self.handle.bind("<Configure>", self._moveCanvas, "+")
        self.inner.bind("<Button-1>", self.clicked, "+")
        self.inner.bind("<ButtonRelease-1>", self.mouseUp, "+")
        self._linked.inner.bind("<Configure>", self._resize_handle, "+")
        self.bind("<Configure>", self._resize_handle)
        self.linked = True

    def _resize_handle(self, event):
        if self._linkedwidth != self._linked.inner.winfo_width() or self._linkedheight != self._linked.inner.winfo_height():
            self.resize_handle()

    def resize_handle(self):
        if not self.active_handle_x or self._linked.inner.winfo_width() < self._linked.inner_width:
            self.handle.config(width=self.winfo_width())
        else:
            self.enable()
            self._linked.inner.update_idletasks()
            self.handle.config(width=self.winfo_width() / self._linked.inner.winfo_width() * self._linked.inner_width)
        if not self.active_handle_y or self._linked.inner.winfo_height() < self._linked.inner_height:
            self.handle.config(height=self.winfo_height())
        else:
            self.enable()
            self.handle.config(height=self.winfo_height() / self._linked.inner.winfo_height() * self._linked.inner_height)

        self.update_idletasks()
        if self.handle.winfo_width() == self.winfo_width() and \
                self.handle.winfo_height() == self.winfo_height():
            self.disable()

        self.handle._skin.drawBars(self.handle.winfo_width(), self.handle.winfo_height())
        updateHover(self.handle)
        self._skin.drawBars(self.winfo_width(), self.winfo_height())
        updateHover(self)

        self._linkedwidth = self._linked.inner.winfo_width()
        self._linkedheight = self._linked.inner.winfo_height()

    def clicked(self, event):
        if self.active_handle_x:
            new_x = self._limitPage(event.x, self.handle.winfo_x(), self.handle.winfo_width(),
                                    self.winfo_width(), self.page_percent)
            self.handle.place_configure(x=new_x)
        if self.active_handle_y:
            new_y = self._limitPage(event.y, self.handle.winfo_y(), self.handle.winfo_height(),
                                    self.winfo_height(), self.page_percent)
            self.handle.place_configure(y=new_y)

        if not self._clicking:
            self.after(self.init_delay, self._keepClicking)
            self._clicking = True

        super().clicked(event)

    def _keepClicking(self):
        if self._clicking:
            event_x, event_y, mouse_in = getLocalMouse(self.inner)
            self.inner.event_generate("<Button-1>", x=event_x, y=event_y)
            self.after(self.delay, self._keepClicking)

    def scroll(self, event):
        x, y, moused_over = getLocalMouse(self._linked)
        if moused_over and self.enabled:
            y = self.handle.winfo_y()
            speed = event.delta / self.scrollwheel_speed

            if y - speed < 0:
                self.handle.place_configure(y=0)
            else:
                trough_height = self.winfo_height()
                handle_height = self.handle.winfo_height()

                if trough_height < y + handle_height - speed:
                    self.handle.place_configure(y=trough_height-handle_height)
                else:
                    self.handle.place_configure(y=y-speed)

    def _limitPage(self, event, origin, size, max, restrict=1.0):
        if origin < event < origin + size:
            return origin
        if event <= origin:
            size = -size
        return limitMove(origin + size * restrict, size, 0, max)

    def _moveCanvas(self, event):
        if self.active_handle_x:
            if self.handle.winfo_width() < self._linked.inner_width:
                x = event.x * ((self._linked.inner.winfo_width()-self._linked.inner_width) /
                               (self.winfo_width()-self.handle.winfo_width()) * self.movement_modifier)
            else: x = 0.0
            self._linked.inner.place_configure(x=x + self.x_offset)

        if self.active_handle_y:
            if self.handle.winfo_height() < self._linked.inner.winfo_height():
                y = event.y * ((self._linked.inner.winfo_height()-self._linked.inner_height) /
                               (self.winfo_height()-self.handle.winfo_height()) * self.movement_modifier)
            else: y = 0.0
            self._linked.inner.place_configure(y=y + self.y_offset)


class ScrollableCanvas(Backgroundable): pass


class ScrollablePane(ScrollableCanvas):
    def __init__(self, parent, width, height, bar_size=18, scrollable_pane_skin=None, scrollbars=(False, False),
                 auto=(False, False)):
        super().__init__(parent, width=width, height=height)

        self.collapse = tk.Frame(self.inner)
        self.collapse.pack(anchor=tk.W)

        h_on, v_on = scrollbars
        self.h_auto, self.v_auto = auto

        self._skin = scrollable_pane_skin if scrollable_pane_skin is not None else ScrollablePaneSkin()

        self.inner_width = width - bar_size * v_on * (not self.v_auto)
        self.inner_height = height - bar_size * h_on * (not self.h_auto)

        self.v_scroll = Scrollable(self, bar_size, height, bar_size, bar_size, self._skin.v_skin)
        self._skin.v_skin.bindScrollable(self.v_scroll)
        self.v_scroll.place(x=self.inner_width, y=0)
        self.v_scroll.linkTo(self, -1, (False, True))

        self.h_scroll = Scrollable(self, self.inner_width, bar_size, bar_size, bar_size, self._skin.h_skin)
        self._skin.h_skin.bindScrollable(self.h_scroll)
        self.h_scroll.place(x=0, y=self.inner_height)
        self.h_scroll.linkTo(self, -1, (True, False))

        if self.h_auto or self.v_auto:
            self.inner.bind("<Configure>", self.showBars)


    def setSkin(self, scrollablepane_skin):
        if scrollablepane_skin is not None:
            scrollablepane_skin.v_skin.bindScrollable(self.v_scroll)
            scrollablepane_skin.h_skin.bindScrollable(self.h_scroll)

    def showBars(self, event):
        changed = False
        self.update_idletasks()
        if self.v_auto:
            if self.inner.winfo_height() > self.inner_height and self.v_scroll.winfo_x() == self.winfo_width():
                self.inner_width -= self.v_scroll.winfo_width()
                changed = True
            elif self.inner.winfo_height() < self.inner_height and self.v_scroll.winfo_x() < self.winfo_width():
                self.inner_width = self.winfo_width()
                changed = True

        if self.h_auto:
            if self.inner.winfo_width() > self.inner_width and self.h_scroll.winfo_y() == self.winfo_height():
                self.inner_height -= self.h_scroll.winfo_height()
                changed = True
            elif self.inner.winfo_width() < self.inner_width and self.h_scroll.winfo_y() != self.inner_height:
                    self.inner_height = self.winfo_height()
                    changed = True

        if changed:
            if self.v_auto:
                self.h_scroll.configure(width=self.inner_width)
                self.h_scroll.place_configure(width=self.inner_width)
                self.v_scroll.place_configure(x=self.inner_width)
                self.v_scroll.resize_handle()
            if self.h_auto:
                self.h_scroll.place_configure(y=self.inner_height, width=self.inner_width)
                self.h_scroll.configure(width=self.inner_width)
                self.h_scroll.resize_handle()

    def disable(self):
        self.v_scroll.disable()
        self.h_scroll.disable()

    def enable(self):
        self.v_scroll.enable()
        self.h_scroll.enable()


class BarSkin(Skinnable):
    def __init__(self, mids_skinnable=None, ends_skinnable=None, width=20, height=20, horizontal=False):
        super().__init__()
        if mids_skinnable is None:
            mids_skinnable = Skinnable()
        if ends_skinnable is None:
            ends_skinnable = Skinnable()
        self.changeSkins(mids_skinnable, ends_skinnable)

    def drawBars(self, width, height, horizontal=False):
        images = []
        for n in range(4):
            images.append(drawBar(self.mids.images()[n], self.ends.images()[n], width, height, horizontal))
        self.directSetImages(images[0], images[1], images[2], images[3])

    def changeSkins(self, mids_skinnable, ends_skinnable):
        self.mids, self.ends = mids_skinnable, ends_skinnable


class ScrollableSkin:
    def __init__(self, trough_mids=None, trough_caps=None, handle_mids=None, handle_caps=None):
        self.troughs = BarSkin(trough_mids, trough_caps, 0, 0)
        self.handles = BarSkin(handle_mids, handle_caps, 0, 0)
        self._recipients = []

    def redraw(self, width, height, horizontal):
        self.troughs.drawBars(width, height, horizontal)
        self.handles.drawBars(width, height, horizontal)

    def bindScrollable(self, scrollable):
        scrollable.setSkin(self.troughs)
        scrollable.handle.setSkin(self.handles)

    def bindWidget(self, widget):
        self._recipients.append(widget)

    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def updateRecipients(self):
        [updateHover(recipient) for recipient in self._recipients]

    def changeSkins(self, trough_mids, trough_caps, handle_mids, handle_caps):
        self.troughs.changeSkins(trough_mids, trough_caps)
        self.handles.changeSkins(handle_mids, handle_caps)


class ScrollablePaneSkin:
    def __init__(self, trough_mids=None, trough_caps=None, handle_mids=None, handle_caps=None):
        self.v_skin = ScrollableSkin(trough_mids, trough_caps, handle_mids, handle_caps)
        self.h_skin = ScrollableSkin(trough_mids, trough_caps, handle_mids, handle_caps)

    def redraw(self, width, height, horizontal):
        self.v_skin.redraw(width, height, horizontal)
        self.h_skin.redraw(width, height, horizontal)

    def bindScrollables(self, scrollable):
        self.v_skin.bindScrollable(scrollable)
        self.h_skin.bindScrollable(scrollable)

    def bindWidget(self, widget):
        self.v_skin.bindWidget(widget)
        self.h_skin.bindWidget(widget)

    def unbindWidget(self, widget):
        self.v_skin.unbindWidget(widget)
        self.h_skin.unbindWidget(widget)

    def updateRecipients(self):
        self.v_skin.updateRecipients()
        self.h_skin.updateRecipients()

    def changeSkins(self, trough_mids, trough_caps, handle_mids, handle_caps):
        self.v_skin.changeSkins(trough_mids, trough_caps, handle_mids, handle_caps)
        self.h_skin.changeSkins(trough_mids, trough_caps, handle_mids, handle_caps)
