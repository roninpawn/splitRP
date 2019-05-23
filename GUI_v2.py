from guiABLE import *
from tkinter import filedialog
from tkinter import font
import keyboard
from time import sleep
import webbrowser


class CheckList(tk.Frame):
    def __init__(self, master, pattern=None, name="", txt="", bg_color="white", skin1=None, skin2=None, **kwargs):
        super().__init__(master, height=23, highlightthickness=0, bg=bg_color, **kwargs)
        self.name = name
        self.pattern = pattern
        if pattern is None: self.pattern = {"name": self.name, "enabled": True}
        self.checkbtn = Toggleable(self, self.pattern["enabled"], self.togglePattern, skin1, skin2,
                                   width=10, height=10, bg=bg_color)
        self.lbl = tk.Label(self, text=txt, font=tk.font.Font(font="Courier 9"), fg="#5bc8c8", bg="#214449", bd=0, pady=0)
        self.lbl.text = txt
        self.checkbtn.grid(row=0, column=0, padx=(11,7))
        self.lbl.grid(row=0, column=1, pady=0, sticky=tk.NE)

    def togglePattern(self):
        self.pattern["enabled"] = not self.pattern["enabled"]
        print(self.pattern["name"], "-", self.pattern["enabled"])



class HoverableButton(tk.Button):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.bind("<Enter>", lambda e: self.config(bg="#3b3b3b"))
        self.bind("<Leave>", lambda e: self.config(bg="#1b1b1b"))

class Weblink(tk.Button):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.bind("<Enter>", lambda e: self.config(pady=1, padx=3))
        self.bind("<Leave>", lambda e: self.config(pady=0, padx=2))

class LabeledCheckbox(tk.Frame):
    def __init__(self, parent, text, skin1=None, skin2=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.checkbox = Toggleable(self, skinnable_1=skin1, skinnable_2=skin2, width=14, height=14, **kwargs)
        self.label = tk.Label(self, text=text, **kwargs)
        self.checkbox.grid(row=0, column=0, padx=5)
        self.label.grid(row=0, column=1)


class LabeledTextInput(tk.Frame):
    def __init__(self, parent, label, text, width, height, **kwargs):
        super().__init__(parent, **kwargs)
        self.label = tk.Label(self, text=label, **kwargs)
        self.textbox = tk.Text(self, width=width, height=height)
        self.textbox.insert(tk.CURRENT, text)
        self.label.grid(row=0, column=0, padx=(5,2))
        self.textbox.grid(row=0, column=1, padx=(0,5))


class GUI(Windowable):
    def __init__(self, file, speedrun):
        self.file = file
        self.speedrun = speedrun
        super().__init__("207x384" + self.file.window_position, "SplitRP")
        # Setup window and background
        self.closing = False
        self.background = Backgroundable(self, 207, 384, "UI/new_bg.png")
        self.background.place(x=0, y=0)

        self.bindDrag(self.background.inner)
        self.loadTabImage("UI/tab_image.png")

        # Settings window
        self.settings = ChildableWindow(self, (self.winfo_width(), 34), True, width=10, height=316)
        self.settings.grid_propagate(False)

        self.settings_bg = Backgroundable(self.settings, 176, 316, "UI/settings_bg.png")
        self.settings_bg.place(x=-166, y=0)
        dip_skin_on = Skinnable("UI/settings_dip.png", "UI/settings_dip_mo.png", "UI/settings_dip_off.png")
        dip_skin_off = Skinnable("UI/settings_dip_off.png", "UI/settings_dip_mo.png", "UI/settings_dip.png")

        self.auto_click = Toggleable(self.settings_bg, self.file.autoclicker_active, self.autoclicker_flip,
                                     dip_skin_on, dip_skin_off, width=24, height=14)
        self.auto_click.place(x=22, y=103)
        self.active_lock = Toggleable(self.settings_bg, self.file.lock_to_window, self.lock_to_window_flip,
                                      dip_skin_on, dip_skin_off, width=24, height=14)
        self.active_lock.place(x=22, y=123)
        self.active_pause = Toggleable(self.settings_bg, self.file.pause_when_inactive, self.pause_when_inactive_flip,
                                       dip_skin_on, dip_skin_off, width=24, height=14)
        self.active_pause.place(x=22, y=143)
        self.set_defaults_skin = Skinnable("UI/settings_button.png", "UI/settings_button_mo.png", "UI/settings_button_active.png")

        validate_int = (self.register(self.valid_int), '%P')
        validate_posint = (self.register(self.valid_posint), '%P')
        validate_port = (self.register(self.valid_port), '%P')
        self.origin_x = tk.Entry(self.settings_bg, width=5, font=font.Font(font="Courier 9"), bg="#1b1b1b", selectbackground="darkred",
                                 foreground="lightgray", bd=0, justify=tk.RIGHT, insertbackground="lightgray",
                                 validate="key", validatecommand=validate_int)
        self.origin_x.place(x=41, y=23)

        self.origin_y = tk.Entry(self.settings_bg, width=5, font=font.Font(font="Courier 9"), bg="#1b1b1b", selectbackground="darkred",
                                 foreground="lightgray", bd=0, justify=tk.RIGHT, insertbackground="lightgray",
                                 validate="key", validatecommand=validate_int)
        self.origin_y.place(x=105, y=23)

        self.res_width = tk.Entry(self.settings_bg, width=5, font=font.Font(font="Courier 9"), bg="#1b1b1b", selectbackground="darkred",
                                  foreground="lightgray", bd=0, justify=tk.RIGHT, insertbackground="lightgray",
                                 validate="key", validatecommand=validate_posint)
        self.res_width.place(x=41, y=64)
        self.res_height = tk.Entry(self.settings_bg, width=5, font=font.Font(font="Courier 9"), bg="#1b1b1b", selectbackground="darkred",
                                   foreground="lightgray", bd=0, justify=tk.RIGHT, insertbackground="lightgray",
                                 validate="key", validatecommand=validate_posint)
        self.res_height.place(x=105, y=64)

        self.reset_key = HoverableButton(self.settings_bg, font=font.Font(font="Courier 9"), bg="#1b1b1b", width=6,
                                  foreground="lightgray", bd=0, padx=0, pady=0, highlightthickness=0, relief=tk.SOLID,
                                  justify=tk.CENTER, text="PRESS", command=self.getKey)
        self.reset_key.place(x=75, y=185)

        self.ls_host = tk.Entry(self.settings_bg, width=15, font=font.Font(font="Courier 9"), bg="#1b1b1b", selectbackground="darkred",
                                foreground="lightgray", bd=0, justify=tk.LEFT, insertbackground="lightgray")
        self.ls_host.place(x=55, y=250)
        self.ls_port = tk.Entry(self.settings_bg, width=5, font=font.Font(font="Courier 9"), bg="#1b1b1b", selectbackground="darkred",
                                foreground="lightgray", bd=0, justify=tk.LEFT, insertbackground="lightgray",
                                validate="key", validatecommand=validate_port)
        self.ls_port.place(x=53, y=275)

        self.set_defaults_btn = Pushable(self.settings_bg, self.setDefaults, self.set_defaults_skin,
                                         width=24, height=24)
        self.set_defaults_btn.disable()
        self.set_defaults_btn.place(x=145, y=286)

        rp_btn_skin = Skinnable("UI/rp_pixel.png", "UI/rp_pixel_mo.png", "UI/rp_pixel_active.png", "UI/rp_pixel_active.png")
        self.rp_btn = Pushable(self.settings_bg, self.warrantyVoid, rp_btn_skin, width=19, height=19)
        self.rp_btn.place(x=21, y=190)

        # Main Window
        self.checkbox_true = Skinnable("UI/new_checkbox.png", "UI/new_checkbox_mo.png", "UI/new_checkbox_active.png",
                                       "UI/new_checkbox_empty_active.png")
        self.checkbox_false = Skinnable("UI/new_checkbox_empty.png", "UI/new_checkbox_empty_mo.png",
                                        "UI/new_checkbox_empty_active.png", "UI/new_checkbox_empty_active.png")

        self.osd_frm = Backgroundable(self, 164, 290, "UI/new_osd_bg.png")
        self.osd_frm.place(x=20, y=46)
        status_line_skin = Skinnable("UI/new_hr_line.png")
        status_line = Imageable(self.osd_frm, status_line_skin, width=157, height=1)
        status_line.place(x=4, y=268)

        # Place buttons
        close_skin = Skinnable("UI/new_x.png", "UI/new_x_active.png")
        close_btn = Pushable(self, self.on_exit, close_skin, width=22, height=22)
        close_btn.place(x=179, y=2)
        min_skin = Skinnable("UI/new_min.png", "UI/new_min_active.png")
        min_btn = Pushable(self, lambda: self.iconify(), min_skin, width=22, height=22)
        min_btn.place(x=154, y=2)
        load_skin = Skinnable("UI/new_load_file.png", "UI/new_load_file_mo.png", None, "UI/new_load_file_mo.png")
        self.load_btn = Pushable(self.osd_frm, self.loadFile, load_skin, width=157, height=24)
        self.load_btn.place(x=4, y=3)

        self.power_images = Skinnable("UI/power_green.png", None, "UI/power_red.png", "UI/power_disabled.png")
        self.power_skin = Skinnable()
        self.power_skin2 = Skinnable()
        self.power_skin.directSetImages(self.power_images.images()[2], None, self.power_images.images()[3])
        self.power_skin2.directSetImages(self.power_images.images()[3], None, self.power_images.images()[2])
        self.power_btn = Toggleable(self, True, self.activeFlip, self.power_skin, self.power_skin2, width=28, height=28)
        self.power_btn.place(x=89, y=347)

        config_skin = Skinnable("UI/new_settings.png", active_path="UI/new_settings_mo.png")
        config_btn = Pushable(self, self.animate_settings, config_skin, width=80, height=27)
        config_btn.place(x=127, y=357)
        self.led_1_skin = Skinnable("UI/LED_green.png", "UI/LED_yellow.png", "UI/LED_red.png", "UI/LED_off.png")
        self.led_1 = Imageable(self, self.led_1_skin, width=10, height=10)
        self.led_1.place(x=76, y=349)
        self.led_2_skin = Skinnable("UI/LED_blue.png", "UI/LED_off.png", disabled_path="UI/LED_off.png")
        self.led_2 = Imageable(self, self.led_2_skin, width=10, height=10)
        self.led_2.place(x=76, y=363)

        # Place text labels

        self.file_lbl = tk.Label(self.osd_frm, text=self.file.pattern_file.split("/")[-1] if self.file.pattern_file != ""
                                 else "No File Loaded", bg="#214449", fg="#5bc8c8", width=21,
                                 font=font.Font(font="Courier 8"), bd=0, pady=0, anchor=tk.NW)
        self.file_lbl.place(x=8, y=32)
        self.fps_lbl = tk.Label(self.osd_frm, text="60 / 59", bg="#214449", fg="#5bc8c8", font=font.Font(font="Courier 7"),
                                bd=0, pady=0)
        self.fps_lbl.place(x=160, y=20, anchor=tk.E)
        self.status_lbl = tk.Label(self.osd_frm, font=font.Font(font="Courier 8"), width=22, bd=0, bg="#214449", fg="#5bc8c8")
        self.status_lbl.place(x=82, y=278, anchor=tk.CENTER)

        trough_mids = Skinnable("UI/new_trough_mid_empty.png", "UI/new_trough_mid_half.png",
                                "UI/new_trough_mid_dense.png")
        trough_caps = Skinnable("UI/new_trough_cap.png")
        scroll_mids = Skinnable("UI/new_handle_mid.png", disabled_path="UI/new_handle_mid_empty.png")
        scroll_caps = Skinnable(disabled_path="UI/new_handle_cap.png")
        scrollpane_skin = ScrollablePaneSkin(trough_mids, trough_caps, scroll_mids, scroll_caps)

        # Create insanely convoluted nest of objects required for simple vertical scrollbar on the checkbox list

        self.scroll_test = ScrollablePane(self.osd_frm, 156, 218, 14, scrollpane_skin, auto=(False, True))
        self.scroll_test.inner.config(bg="#214449")
        self.scroll_test.config(bg="#214449")
        self.scroll_test.collapse.config(bg="#214449")
        self.scroll_test.place(x=4, y=50)
        self.scroll_test.update()
        self._last_pattern = tk.Frame()
        self._last_pattern.lbl = tk.Label(self._last_pattern)

        # Warranty Voided Overlay
        self.voided = tk.Frame(self, width=160, height=285, bg="#214449")
        self.voided.pack_propagate(False)
        self.voided.place(x=22, y=48)
        self.voided.lower(self.background)
        big_text = tk.Label(self.voided, text=" WARRANTY \rVOID", justify=tk.CENTER, fg="#214449", bg="#5bc8c8",
                            font=font.Font(font="Courier 21 bold"), bd=0)
        big_text.pack(anchor=tk.N, pady=10)
        small_text = tk.Label(self.voided, justify=tk.LEFT, bg="#214449", fg="#5bc8c8", wraplength=160,
                              font=font.Font(font="Courier 8"), bd=0,
                              text="Special thanks to:\r" \
                                   "AJ213, Noahkra,\rGreg Aubry...\r\r"
                                   "And everyone who watched and helped with development at:\r\r\r"
                                   "Like the thing?\rBuy me a coffee.")
        small_text.pack(anchor=tk.N, padx=(5, 0))
        smol_text = tk.Label(self.voided, justify=tk.LEFT, bg="#214449", fg="#5bc8c8",
                              font=font.Font(font="Courier 7"), text='"Coffee" is code for beer.')
        smol_text.place(x=27, y=270)
        twitch_link = Weblink(self.voided, command=self.openTwitch, bd=0, padx=2, pady=0, fg="#214449", bg="#5bc8c8",
                                activebackground="#5bc8c8", activeforeground="#214449", highlightthickness=0,
                                font=font.Font(font="Courier 9"), text="twitch.tv/roninpawn")
        twitch_link.place(x=11, y=188)
        paypal_link = Weblink(self.voided, command=self.openPaypal, bd=0, padx=2, pady=0, fg="#214449", bg="#5bc8c8",
                                activebackground="#5bc8c8", activeforeground="#214449", highlightthickness=0,
                                font=font.Font(font="Courier 9"), text="Or don't. Your call")
        paypal_link.place(x=11, y=245)

        self.focus_force()

    def openTwitch(self):
        webbrowser.open("http://www.twitch.tv/roninpawn", new=1)

    def openPaypal(self):
        webbrowser.open("https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=ZFUSRYTKDAGGQ&source=url", new=1)

    def animate_settings(self):
        if not self.settings.visible():
            self.settings.visible(True)
        self.settings.update_idletasks()
        # Close from opened state.
        if self.settings.winfo_width() == 176:
            self.speedrun.active = True
            while self.settings.winfo_width() > 10:
                if self.settings.winfo_width() - 6 < 10:
                    self.settings.configure(width=10)
                    self.settings_bg.place_configure(x=-166)
                    break
                self.settings.configure(width=self.settings.winfo_width() - 6)
                self.settings_bg.place_configure(x=self.settings_bg.winfo_x() - 6)
                self.settings.update()

            self.voided.lower(self.background)
            self.osd_frm.lift(self.background)
            self.power_btn.state(True)
            self.power_btn.enable()
            self.led_1.enable()
            self.led_2.changeImage(self.led_2_last)
            self.led_2.enable()
            self.rp_btn.enable()
            self.set_defaults_btn.disable()

            ox, oy = self.origin_x.get(), self.origin_y.get()
            ox = self.file.default_origin[0] if ox == "" or ox == "-" else int(self.origin_x.get())
            oy = self.file.default_origin[1] if oy == "" or oy == "-" else int(self.origin_y.get())
            rw = self.file.default_resolution[0] if self.res_width.get() == "" else int(self.res_width.get())
            rh = self.file.default_resolution[1] if self.res_height.get() == "" else int(self.res_height.get())
            self.file.pattern_translation = [ox, oy]
            self.file.pattern_scale = [rw, rh]
            self.file.loadPattern()
            self.speedrun.loadFile()

            if self.file.livesplit_host != self.ls_host.get() or self.file.livesplit_port != int(self.ls_port.get()):
                if self.ls_host.get() != "": self.file.livesplit_host = self.ls_host.get()
                if self.ls_port.get() != "": self.file.livesplit_port = int(self.ls_port.get())
                self.speedrun._state = "reconnect"

        else:
            # Open from closed state.
            self.speedrun.active = False
            self.loadSettings()
            self.osd_frm.lower(self.background)
            self.power_btn.state(False)
            self.power_btn.disable()
            self.led_1.disable()
            self.led_2_last = self.led_2.current_image
            self.led_2.changeImage(3)
            self.led_2.disable()
            self.set_defaults_btn.enable()
            while self.settings.winfo_width() < 176:
                if self.settings.winfo_width() + 6 > 176:
                    self.settings.configure(width=176)
                    self.settings_bg.place_configure(x=0)
                    self.settings.update()
                    break
                self.settings.configure(width=self.settings.winfo_width() + 6)
                self.settings_bg.place_configure(x=self.settings_bg.winfo_x() + 6)
                self.settings.update()
        return

    def activeFlip(self):
        if self.settings.winfo_width() < 11:
            if not self.speedrun.active:
                self.speedrun.active = True
                self.osd_frm.lift(self.background)
                self.led_1.enable()
                self.led_2.enable()
            else:
                self.speedrun.active = False
                self.osd_frm.lower(self.background)
                self.led_1.disable()
                self.led_2.disable()

    def warrantyVoid(self):
        self.rp_btn.disable()
        self.voided.lift(self.background)

    def autoclicker_flip(self):
        self.file.autoclicker_active = not self.file.autoclicker_active

    def lock_to_window_flip(self):
        self.file.lock_to_window = not self.file.lock_to_window
        self.speedrun._state = "armed" if self.speedrun._last_state == "ready" else self.speedrun._last_state
        if not self.file.lock_to_window and self.file.pause_when_inactive:
            self.active_pause.state(False)
            self.pause_when_inactive_flip()

    def pause_when_inactive_flip(self):
        if self.active_lock.state():
            self.file.pause_when_inactive = not self.file.pause_when_inactive
        else:
            self.active_pause.state(False)
            self.file.pause_when_inactive = False

    def valid_int(self, proposed):
        if proposed == "" or proposed == "-":
            return True
        if len(proposed) > len(proposed.strip()):
            return False
        try:
            proposed = int(proposed)
        except:
            return False
        return True if -100000 < proposed < 100000 else False

    def valid_posint(self, proposed):
        if proposed == "":
            return True
        if len(proposed) > len(proposed.strip()):
            return False
        try:
            proposed = int(proposed)
        except:
            return False
        return True if 0 < proposed < 100000 else False

    def valid_port(self, proposed):
        if proposed == "":
            return True
        if len(proposed) > len(proposed.strip()):
            return False
        try:
            proposed = int(proposed)
        except:
            return False
        return True if -1 < proposed < 65536 else False

    def getKey(self):
        def cancel(event=None):
            nonlocal done
            self.reset_key.unbind("<Button-1>", click_id)
            self.reset_key.unbind("<FocusOut>", focus_id)
            keyboard.unhook(key_hook)
            self.reset_key.config(text=lastkey)
            done = "Cancel"

        def do_it(event):
            nonlocal lastkey, hotkey, done
            if event.event_type == keyboard.KEY_UP:
                done = True
                return
            elif lastkey != event.name:
                hotkey[event.name] = event.scan_code
                lastkey = event.name

        done = False
        lastkey = ""
        hotkey = {}

        self.reset_key.config(text="PRESS")

        key_hook = keyboard.hook(do_it, True)
        click_id = self.reset_key.bind_all("<Button-1>", cancel)
        focus_id = self.reset_key.bind_all("<FocusOut>", cancel)
        while not done:
            self.update()
            sleep(.015)
        if hotkey != {}: lastkey, lastcode = list(hotkey.items())[-1]
        if done != "Cancel":
            self.file.reset_key = hotkey
            print(hotkey, lastkey, self.file.reset_key)
            cancel()

    def setEntry(self, entry, value):
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def loadSettings(self):
        self.setEntry(self.origin_x, self.file.pattern_translation[0])
        self.setEntry(self.origin_y, self.file.pattern_translation[1])
        self.setEntry(self.res_width, self.file.pattern_scale[0])
        self.setEntry(self.res_height, self.file.pattern_scale[1])
        self.auto_click.state(self.file.autoclicker_active)
        self.active_lock.state(self.file.lock_to_window)
        self.active_pause.state(self.file.pause_when_inactive)
        self.reset_key.config(text=list(self.file.reset_key.keys())[-1])
        self.setEntry(self.ls_host, self.file.livesplit_host)
        self.setEntry(self.ls_port, self.file.livesplit_port)

    def setDefaults(self):
        self.file.setDefaults()
        self.loadSettings()

    def load_patterns(self, patterns=None):
        [child.destroy() for child in self.scroll_test.inner.winfo_children()]
        if patterns is not None:
            chklst = CheckList(self.scroll_test.inner, None, "Running", "Running", "#214449",
                               self.checkbox_true, self.checkbox_false)
            chklst.name = "RT:Running"
            chklst.checkbtn.disable()
            chklst.grid(row=0, column=0, pady=0, sticky=tk.W)
            for p in range(0, len(patterns)):
                chklst = CheckList(self.scroll_test.inner, patterns[p], patterns[p]["name"], patterns[p]["name"][3:], "#214449",
                                   self.checkbox_true, self.checkbox_false)
                chklst.grid(row=p+1, column=0, pady=0, sticky=tk.W)
                self._last_pattern = chklst

    def highlight_pattern(self, pattern=None):
        if pattern == None:
            self._last_pattern.lbl.config(bg="#214449", fg="#5bc8c8")
        for child in self.scroll_test.inner.winfo_children():
            if type(child) == CheckList and child.name == pattern:
                self._last_pattern.lbl.config(bg="#214449", fg="#5bc8c8")
                child.lbl.config(bg="#5bc8c8", fg="#214449")
                self._last_pattern = child

    def loadFile(self):
        filename = filedialog.askopenfilename(initialdir=".", title="Select file",
                                              filetypes=(("cfg files", "*.cfg"), ("all files", "*.*")))
        if filename != "":
            self.file.pattern_file = filename
            success = self.file.loadPattern()
            if success:
                filename = filename.split("/")
                self.file_lbl.configure(text=filename[-1])
                self.updateStatus(f"{filename[-1]} loaded")
                self.load_patterns(self.file.all_patterns)
                self.speedrun.loadFile()
                self.speedrun.reset()
            else:
                self.file.pattern_file = ""
                self.file_lbl.config(text="Incompatible File")
                self.status_lbl.config(text="No patterns loaded")
                [child.destroy() for child in self.scroll_test.inner.winfo_children()]

    def on_exit(self):
        self.closing = True

    def updateFPS(self, fps, fpms):
        self.fps_lbl.configure(text=f"{fps:02.0f} / {fpms:02.0f}")
        self.update()

    def updateStatus(self, txt):
        self.status_lbl.configure(text=str(txt)[:22])
        print(txt)
