# ##########################################################
# FlatCAM Plus: 2D Post-processing for Manufacturing        #
# File by:  Antigravity (AI)                               #
# Date:     05/01/2026                                     #
# License:  MIT Licence                                    #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize
from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, FCComboBox, FCCheckBox, \
    FCJog, RadioSet, FCDoubleSpinner, FCSpinner, FCFileSaveDialog, FCDetachableTab, FCTable, \
    FCZeroAxes, FCSliderWithDoubleSpinner, FCEntry, RotatedToolButton, FCTextArea

import logging
import time
import serial
import serial.tools.list_ports
import threading
import queue
import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')

class FluidStyleButton(FCButton):
    def __init__(self, text="", color="#31b0d5", hover="#269abc", text_color="white", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: {text_color}; border: 1px solid #2e6da4;
                border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: {hover}; border-color: #204d74; }}
            QPushButton:pressed {{ background-color: #1b6d85; }}
            QPushButton:disabled {{ background-color: #eee; color: #999; border-color: #ddd; }}
        """)

class ToolCNCControl(AppTool):
    update_status_sig = pyqtSignal(dict)
    append_console_sig = pyqtSignal(str, str)
    update_progress_sig = pyqtSignal(float, str)

    def __init__(self, app):
        self.app = app
        AppTool.__init__(self, app)
        self.ser = None
        self.is_connected = False
        self.stop_thread = threading.Event()
        self.is_streaming = False
        self.streaming_paused = False
        self.current_line_idx = 0
        self.ok_received = threading.Event()
        self.last_status_query = 0
        self.status_interval = 0.5

        self.ui = CNCControlUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

    def run(self, toggle=True):
        tab_exists = False
        for i in range(self.app.ui.plot_tab_area.count()):
            if self.app.ui.plot_tab_area.tabText(i) == _("CNC Settings"):
                self.app.ui.plot_tab_area.setCurrentIndex(i); tab_exists = True; break
        if not tab_exists:
            self.scroll_area = VerticalScrollArea()
            self.scroll_area.setWidget(self); self.scroll_area.setWidgetResizable(True)
            self.app.ui.plot_tab_area.addTab(self.scroll_area, _("CNC Settings"))
            self.app.ui.plot_tab_area.setCurrentIndex(self.app.ui.plot_tab_area.count() - 1)
        self.on_refresh_ports()
        self.update_tool_list()

    def update_tool_list(self):
        self.ui.object_combo.clear()
        for obj in self.app.collection.get_list():
            if obj.kind == 'cncjob': self.ui.object_combo.addItem(obj.obj_options['name'])

    def connect_signals_at_init(self):
        self.ui.connect_btn.clicked.connect(self.on_connect_clicked)
        self.ui.com_refresh.clicked.connect(self.on_refresh_ports)
        self.ui.estop_btn.clicked.connect(self.on_stop)
        self.ui.reset_btn.clicked.connect(self.on_reset)
        self.ui.home_btn.clicked.connect(lambda: self.send_command("$H"))
        self.ui.unlock_btn.clicked.connect(lambda: self.send_command("$X"))
        
        self.ui.zero_x.clicked.connect(lambda: self.send_command("G10 L20 P1 X0"))
        self.ui.zero_y.clicked.connect(lambda: self.send_command("G10 L20 P1 Y0"))
        self.ui.zero_z.clicked.connect(lambda: self.send_command("G10 L20 P1 Z0"))
        self.ui.zero_all.clicked.connect(lambda: self.send_command("G10 L20 P1 X0 Y0 Z0"))

        self.ui.cfg_dump.clicked.connect(lambda: self.send_command("$Config/Dump"))
        self.ui.sd_list.clicked.connect(lambda: self.send_command("$SD/List"))
        self.ui.info_btn.clicked.connect(lambda: self.send_command("$I"))

        self.ui.feed_plus.clicked.connect(lambda: self.send_raw(b'\x91'))
        self.ui.feed_minus.clicked.connect(lambda: self.send_raw(b'\x92'))
        self.ui.feed_reset.clicked.connect(lambda: self.send_raw(b'\x90'))
        self.ui.spindle_plus.clicked.connect(lambda: self.send_raw(b'\x9a'))
        self.ui.spindle_minus.clicked.connect(lambda: self.send_raw(b'\x9b'))
        self.ui.spindle_reset.clicked.connect(lambda: self.send_raw(b'\x99'))

        self.ui.play_btn.clicked.connect(self.on_stream_start)
        self.ui.pause_btn.clicked.connect(self.on_stream_pause)
        self.ui.stop_btn.clicked.connect(self.on_stream_stop)

        self.update_status_sig.connect(self.update_status_display)
        self.append_console_sig.connect(self.ui.append_console)
        self.update_progress_sig.connect(self.update_progress_ui)

        self.ui.jog_up.clicked.connect(lambda: self.send_jog('Y', 1))
        self.ui.jog_down.clicked.connect(lambda: self.send_jog('Y', -1))
        self.ui.jog_left.clicked.connect(lambda: self.send_jog('X', -1))
        self.ui.jog_right.clicked.connect(lambda: self.send_jog('X', 1))
        self.ui.jog_z_up.clicked.connect(lambda: self.send_jog('Z', 1))
        self.ui.jog_z_down.clicked.connect(lambda: self.send_jog('Z', -1))

        self.ui.command_entry.returnPressed.connect(self.on_send_command)

    def on_refresh_ports(self):
        self.ui.com_port.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports: self.ui.com_port.addItem(p.device)
        if self.ui.com_port.count() == 0: self.ui.com_port.addItem("None")

    def on_connect_clicked(self):
        if not self.is_connected:
            port = self.ui.com_port.currentText()
            if port == "None": return
            try:
                self.ser = serial.Serial(port, 115200, timeout=0.1)
                self.is_connected = True; self.ui.set_connected(True)
                self.stop_thread.clear()
                self.receiver_thread = threading.Thread(target=self.receive_loop, daemon=True)
                self.receiver_thread.start()
                self.send_command("$I")
            except Exception as e: log.error(f"Conn err: {e}")
        else: self.disconnect()

    def disconnect(self):
        self.stop_thread.set()
        if self.ser: self.ser.close(); self.ser = None
        self.is_connected = False; self.ui.set_connected(False)

    def on_send_command(self):
        cmd = self.ui.command_entry.text().strip()
        if cmd: self.send_command(cmd); self.ui.command_entry.clear()

    def send_command(self, cmd):
        if self.ser: self.ser.write((cmd + "\n").encode()); self.append_console_sig.emit(cmd, "tx")

    def send_raw(self, byte_cmd):
        if self.ser: self.ser.write(byte_cmd)

    def send_jog(self, axis, dir):
        step = float(self.ui.step_radio.get_value())
        self.send_command(f"$J=G91 G21 {axis}{step*dir} F1000")

    def on_reset(self):
        if self.ser: self.ser.write(b'\x18')

    def on_stop(self):
        if self.ser: self.ser.write(b'!')

    def receive_loop(self):
        while not self.stop_thread.is_set():
            if self.ser and self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    if line == "ok": self.ok_received.set()
                    elif line: self.append_console_sig.emit(line, "rx"); self.parse_status(line)
                except: break
            if time.time() - self.last_status_query > self.status_interval:
                self.send_command("?"); self.last_status_query = time.time()
            time.sleep(0.01)

    def parse_status(self, line):
        if line.startswith("<") and line.endswith(">"):
            parts = line[1:-1].split("|")
            data = {"state": parts[0]}
            for p in parts[1:]:
                if ":" in p: k, v = p.split(":", 1); data[k] = v
            self.update_status_sig.emit(data)

    def update_status_display(self, data):
        state = data.get("state", "Idle")
        self.ui.state_label.setText(state.upper())
        colors = {"Idle": "#27ae60", "Run": "#3498db", "Alarm": "#e74c3c", "Home": "#f1c40f"}
        self.ui.state_indicator.setStyleSheet(f"background-color: {colors.get(state, '#aaa')}; border-radius: 6px;")
        if "WPos" in data:
            coords = data["WPos"].split(",")
            self.ui.x_val.setText(coords[0]); self.ui.y_val.setText(coords[1]); self.ui.z_val.setText(coords[2])

    def on_stream_start(self):
        obj = self.app.collection.get_by_name(self.ui.object_combo.currentText())
        if not obj: return
        self.gcode_lines = [l for l in obj.source_file.split("\n") if l.strip()]
        self.current_line_idx = 0; self.is_streaming = True; self.streaming_paused = False
        threading.Thread(target=self.stream_worker, daemon=True).start()

    def update_progress_ui(self, p, r): self.ui.progress.setValue(int(p))
    def on_stream_pause(self): self.streaming_paused = not self.streaming_paused
    def on_stream_stop(self): self.is_streaming = False

class CNCControlUI:
    pluginName = _("CNC Settings")

    def __init__(self, layout, app):
        self.app = app
        self.layout = layout
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Theme (FluidNC / ESP3D)
        self.bg_main = "#ecf0f1"
        self.bg_card = "#ffffff"
        self.primary = "#31b0d5"
        self.dark_gray = "#2c3e50"

        container = QtWidgets.QWidget()
        container.setStyleSheet(f"background-color: {self.bg_main}; color: {self.dark_gray}; font-family: 'Segoe UI', sans-serif;")
        self.layout.addWidget(container)
        self.main_lay = QtWidgets.QVBoxLayout(container)
        self.main_lay.setContentsMargins(10, 10, 10, 10)
        self.main_lay.setSpacing(10)

        # --- HEADER ---
        header = QtWidgets.QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background-color: {self.primary}; border-radius: 4px; color: white;")
        h_lay = QtWidgets.QHBoxLayout(header)
        h_lay.addWidget(FCLabel("<b>FluidNC</b> Control", size=12, color="white"))
        h_lay.addStretch()
        self.state_indicator = QtWidgets.QFrame(); self.state_indicator.setFixedSize(10, 10); self.state_indicator.setStyleSheet("background: #bdc3c7; border-radius: 5px;")
        self.state_label = FCLabel("OFFLINE", bold=True, color="white")
        h_lay.addWidget(self.state_indicator); h_lay.addWidget(self.state_label)
        h_lay.addSpacing(20)
        self.com_port = FCComboBox(); self.com_port.setMinimumWidth(120); self.com_port.setStyleSheet("color: #333; background: white;")
        self.com_refresh = RotatedToolButton(); self.com_refresh.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.connect_btn = FluidStyleButton(_("CONNECT"), "white", "#eee", self.primary)
        h_lay.addWidget(self.com_port); h_lay.addWidget(self.com_refresh); h_lay.addWidget(self.connect_btn)
        self.main_lay.addWidget(header)

        # --- DASHBOARD (Two Column) ---
        dashboard = QtWidgets.QHBoxLayout()
        dashboard.setSpacing(10)
        self.main_lay.addLayout(dashboard)

        # LEFT COLUMN
        left_col = QtWidgets.QVBoxLayout(); dashboard.addLayout(left_col, 2)

        # POSITION Card (Compact)
        pos_card = self.create_card(_("POSITION"))
        left_col.addWidget(pos_card)
        pos_grid = GLay(); pos_card.layout().addLayout(pos_grid)
        
        def add_dro(axis, r, color):
            l = FCLabel(axis, bold=True, size=11); l.setStyleSheet(f"color: {color};")
            z = FluidStyleButton("0", self.primary); z.setFixedSize(28, 28)
            v = FCLabel("0.000", bold=True, size=22); v.setStyleSheet("font-family: 'Consolas'; color: #333;")
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            pos_grid.addWidget(l, r, 0); pos_grid.addWidget(z, r, 1); pos_grid.addWidget(v, r, 2)
            return z, v
        self.zero_x, self.x_val = add_dro("X", 0, "#e74c3c")
        self.zero_y, self.y_val = add_dro("Y", 1, "#27ae60")
        self.zero_z, self.z_val = add_dro("Z", 2, "#2980b9")
        
        pos_btns = QtWidgets.QHBoxLayout()
        self.zero_all = FluidStyleButton(_("ZERO ALL")); self.home_btn = FluidStyleButton(_("HOME"), "#3498db"); self.unlock_btn = FluidStyleButton(_("UNLOCK"), "#f39c12")
        pos_btns.addWidget(self.zero_all); pos_btns.addWidget(self.home_btn); pos_btns.addWidget(self.unlock_btn)
        pos_card.layout().addLayout(pos_btns)

        # JOG Card (Fixed Layout)
        jog_card = self.create_card(_("JOG CONTROL"))
        left_col.addWidget(jog_card)
        jog_lay = QtWidgets.QVBoxLayout(); jog_card.layout().addLayout(jog_lay)
        self.step_radio = RadioSet([{"label": "0.1", "value": "0.1"}, {"label": "1", "value": "1"}, {"label": "10", "value": "10"}, {"label": "100", "value": "100"}], orientation='horizontal', compact=True)
        jog_lay.addWidget(self.step_radio, alignment=Qt.AlignmentFlag.AlignCenter)
        
        jg = QtWidgets.QGridLayout(); jg.setSpacing(5); jg.setContentsMargins(50, 0, 50, 0)
        self.jog_up = FluidStyleButton("Y+"); self.jog_down = FluidStyleButton("Y-"); self.jog_left = FluidStyleButton("X-"); self.jog_right = FluidStyleButton("X+")
        self.jog_z_up = FluidStyleButton("Z+"); self.jog_z_down = FluidStyleButton("Z-")
        for b in [self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down]: b.setFixedSize(45, 45)
        jg.addWidget(self.jog_up, 0, 1); jg.addWidget(self.jog_left, 1, 0); jg.addWidget(self.jog_right, 1, 2); jg.addWidget(self.jog_down, 2, 1)
        jg.addWidget(self.jog_z_up, 0, 3); jg.addWidget(self.jog_z_down, 2, 3)
        jog_lay.addLayout(jg)
        left_col.addStretch()

        # RIGHT COLUMN
        right_col = QtWidgets.QVBoxLayout(); dashboard.addLayout(right_col, 1)

        # Overrides Card
        ovr_card = self.create_card(_("OVERRIDES"))
        right_col.addWidget(ovr_card)
        ovr_grid = QtWidgets.QGridLayout(); ovr_card.layout().addLayout(ovr_grid)
        self.feed_plus = FluidStyleButton("+"); self.feed_minus = FluidStyleButton("-"); self.feed_reset = FluidStyleButton("100%")
        self.spindle_plus = FluidStyleButton("+"); self.spindle_minus = FluidStyleButton("-"); self.spindle_reset = FluidStyleButton("100%")
        for b in [self.feed_plus, self.feed_minus, self.feed_reset, self.spindle_plus, self.spindle_minus, self.spindle_reset]: b.setFixedWidth(50)
        ovr_grid.addWidget(FCLabel(_("FEED")), 0, 0); ovr_grid.addWidget(self.feed_minus, 0, 1); ovr_grid.addWidget(self.feed_reset, 0, 2); ovr_grid.addWidget(self.feed_plus, 0, 3)
        ovr_grid.addWidget(FCLabel(_("SPINDLE")), 1, 0); ovr_grid.addWidget(self.spindle_minus, 1, 1); ovr_grid.addWidget(self.spindle_reset, 1, 2); ovr_grid.addWidget(self.spindle_plus, 1, 3)

        # System Card
        sys_card = self.create_card(_("SYSTEM"))
        right_col.addWidget(sys_card)
        sys_lay = QtWidgets.QVBoxLayout(); sys_card.layout().addLayout(sys_lay)
        self.cfg_dump = FluidStyleButton("Config Dump"); self.sd_list = FluidStyleButton("List SD Files"); self.info_btn = FluidStyleButton("System Info")
        sys_lay.addWidget(self.cfg_dump); sys_lay.addWidget(self.sd_list); sys_lay.addWidget(self.info_btn)
        
        h_sys = QtWidgets.QHBoxLayout()
        self.estop_btn = FluidStyleButton(_("E-STOP"), "#e74c3c"); self.reset_btn = FluidStyleButton(_("RESET"), "#2ecc71")
        h_sys.addWidget(self.estop_btn); h_sys.addWidget(self.reset_btn)
        sys_lay.addLayout(h_sys)
        right_col.addStretch()

        # --- TERMINAL (Bottom) ---
        term_card = self.create_card(_("TERMINAL"))
        self.main_lay.addWidget(term_card, 1)
        term_lay = QtWidgets.QVBoxLayout(); term_card.layout().addLayout(term_lay)
        self.console = FCTextArea(); self.console.setReadOnly(True); self.console.setStyleSheet("background: #2c3e50; color: #ecf0f1; font-family: 'Consolas'; border-radius: 4px;")
        term_lay.addWidget(self.console)
        
        inp_lay = QtWidgets.QHBoxLayout()
        self.command_entry = FCEntry(); self.command_entry.setPlaceholderText(_("G-Code / FluidNC command..."))
        inp_lay.addWidget(self.command_entry)
        self.play_btn = FluidStyleButton("▶", "#2ecc71"); self.pause_btn = FluidStyleButton("‖", "#f1c40f"); self.stop_btn = FluidStyleButton("■", "#e74c3c")
        for b in [self.play_btn, self.pause_btn, self.stop_btn]: b.setFixedWidth(40)
        inp_lay.addWidget(self.play_btn); inp_lay.addWidget(self.pause_btn); inp_lay.addWidget(self.stop_btn)
        term_lay.addLayout(inp_lay)
        
        prog_lay = QtWidgets.QHBoxLayout()
        self.object_combo = FCComboBox(); self.progress = QtWidgets.QProgressBar(); self.progress.setFixedHeight(6)
        prog_lay.addWidget(FCLabel(_("Job:"), size=8)); prog_lay.addWidget(self.object_combo); prog_lay.addWidget(self.progress)
        term_lay.addLayout(prog_lay)

    def create_card(self, title):
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"background: {self.bg_card}; border-radius: 6px; border: 1px solid #dcdde1;")
        lay = QtWidgets.QVBoxLayout(card); lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(8)
        t_lbl = FCLabel(f"<b>{title}</b>", size=9, color=self.primary)
        lay.addWidget(t_lbl)
        line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.Shape.HLine); line.setStyleSheet("color: #f1f2f6;"); lay.addWidget(line)
        return card

    def set_connected(self, connected):
        self.connect_btn.setText(_("DISCONNECT") if connected else _("CONNECT"))
        btns = [self.play_btn, self.pause_btn, self.stop_btn, self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down, 
                self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_btn, self.unlock_btn, self.cfg_dump, self.sd_list, self.info_btn,
                self.feed_plus, self.feed_minus, self.feed_reset, self.spindle_plus, self.spindle_minus, self.spindle_reset]
        for b in btns: b.setEnabled(connected)

    def append_console(self, text, type):
        color = {"tx": "#3498db", "rx": "#bdc3c7", "error": "#e74c3c"}.get(type, "#888")
        if "MSG:ERR" in text: color = "#e74c3c"
        elif "MSG:INFO" in text: color = "#2ecc71"
        elif "MSG:WARN" in text: color = "#f1c40f"
        self.console.appendHtml(f'<span style="color: #95a5a6;">[{time.strftime("%H:%M:%S")}]</span> <span style="color: {color};">{text}</span>')
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)
