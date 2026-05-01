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
                border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: {hover}; border-color: #204d74; }}
            QPushButton:pressed {{ background-color: #1b6d85; }}
            QPushButton:disabled {{ background-color: #ddd; color: #888; border-color: #ccc; }}
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

        # FluidNC Features
        self.ui.cfg_dump.clicked.connect(lambda: self.send_command("$Config/Dump"))
        self.ui.sd_list.clicked.connect(lambda: self.send_command("$SD/List"))
        self.ui.info_btn.clicked.connect(lambda: self.send_command("$I"))

        # Overrides
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

        # Jogging
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
                    elif line: 
                        self.append_console_sig.emit(line, "rx")
                        self.parse_status(line)
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

    def on_stream_pause(self): self.streaming_paused = not self.streaming_paused

    def on_stream_stop(self): self.is_streaming = False

    def stream_worker(self):
        while self.is_streaming and self.current_line_idx < len(self.gcode_lines):
            if self.streaming_paused: time.sleep(0.1); continue
            self.ok_received.clear(); self.send_command(self.gcode_lines[self.current_line_idx])
            self.ok_received.wait(timeout=5.0); self.current_line_idx += 1
            self.update_progress_sig.emit(self.current_line_idx / len(self.gcode_lines) * 100, "")
        self.is_streaming = False

    def update_progress_ui(self, p, r): self.ui.progress.setValue(int(p))

class CNCControlUI:
    pluginName = _("CNC Settings")

    def __init__(self, layout, app):
        self.app = app
        self.layout = layout
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Style constants (FluidNC / ESP3D Theme)
        self.bg_main = "#f4f7f6"
        self.bg_card = "white"
        self.primary = "#31b0d5"
        self.dark_text = "#333"

        container = QtWidgets.QWidget()
        container.setStyleSheet(f"background-color: {self.bg_main}; color: {self.dark_text}; font-family: 'Segoe UI', sans-serif;")
        self.layout.addWidget(container)
        self.main_lay = QtWidgets.QVBoxLayout(container)
        self.main_lay.setContentsMargins(15, 15, 15, 15)
        self.main_lay.setSpacing(20)

        # --- FLUIDNC TOP BAR ---
        header = QtWidgets.QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(f"background-color: {self.primary}; border-radius: 8px; color: white;")
        h_lay = QtWidgets.QHBoxLayout(header)
        h_lay.setContentsMargins(20, 0, 20, 0)
        
        logo_lbl = FCLabel("<b>FluidNC</b> Control", size=14); logo_lbl.setStyleSheet("color: white;")
        h_lay.addWidget(logo_lbl)
        h_lay.addSpacing(40)
        
        self.state_indicator = QtWidgets.QFrame(); self.state_indicator.setFixedSize(12, 12); self.state_indicator.setStyleSheet("background-color: #ddd; border-radius: 6px;")
        self.state_label = FCLabel("DISCONNECTED", bold=True); self.state_label.setStyleSheet("color: white;")
        h_lay.addWidget(self.state_indicator); h_lay.addWidget(self.state_label)
        
        h_lay.addStretch()
        self.com_port = FCComboBox(); self.com_port.setMinimumWidth(150); self.com_port.setStyleSheet("color: #333; background: white;")
        self.com_refresh = RotatedToolButton(); self.com_refresh.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.connect_btn = FluidStyleButton(_("CONNECT"), "white", "#eee", self.primary)
        h_lay.addWidget(self.com_port); h_lay.addWidget(self.com_refresh); h_lay.addWidget(self.connect_btn)
        self.main_lay.addWidget(header)

        # --- DASHBOARD CONTENT ---
        dashboard = QtWidgets.QHBoxLayout()
        dashboard.setSpacing(20)
        self.main_lay.addLayout(dashboard)

        # LEFT COLUMN (Control & DRO)
        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(20)
        dashboard.addLayout(left_col, 2)

        # DRO Card
        dro_card = self.create_card(_("POSITION"))
        left_col.addWidget(dro_card)
        dro_lay = GLay()
        dro_card.layout().addLayout(dro_lay)
        
        def add_dro(axis, r):
            l = FCLabel(axis, bold=True, size=12); l.setStyleSheet(f"color: {self.primary};")
            z = FluidStyleButton("0", self.primary, "#269abc")
            z.setFixedSize(30, 30)
            v = FCLabel("0.000", bold=True, size=24); v.setStyleSheet("color: #333; font-family: 'Consolas';")
            dro_lay.addWidget(l, r, 0); dro_lay.addWidget(z, r, 1); dro_lay.addWidget(v, r, 2)
            return z, v

        self.zero_x, self.x_val = add_dro("X", 0)
        self.zero_y, self.y_val = add_dro("Y", 1)
        self.zero_z, self.z_val = add_dro("Z", 2)
        
        btn_box = QtWidgets.QHBoxLayout()
        self.zero_all = FluidStyleButton(_("ZERO ALL")); self.home_btn = FluidStyleButton(_("HOME"), "#5bc0de")
        self.unlock_btn = FluidStyleButton(_("UNLOCK"), "#f0ad4e")
        btn_box.addWidget(self.zero_all); btn_box.addWidget(self.home_btn); btn_box.addWidget(self.unlock_btn)
        dro_card.layout().addLayout(btn_box)

        # Jog Card
        jog_card = self.create_card(_("JOG CONTROL"))
        left_col.addWidget(jog_card)
        jog_lay = QtWidgets.QVBoxLayout(jog_card.layout())
        
        self.step_radio = RadioSet([{"label": "0.1", "value": "0.1"}, {"label": "1", "value": "1"}, {"label": "10", "value": "10"}, {"label": "100", "value": "100"}], orientation='horizontal', compact=True)
        jog_lay.addWidget(self.step_radio)
        
        jg = QtWidgets.QGridLayout(); jg.setSpacing(10); jg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.jog_up = FluidStyleButton("Y+"); self.jog_down = FluidStyleButton("Y-"); self.jog_left = FluidStyleButton("X-"); self.jog_right = FluidStyleButton("X+")
        self.jog_z_up = FluidStyleButton("Z+"); self.jog_z_down = FluidStyleButton("Z-")
        for b in [self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down]: b.setFixedSize(50, 50)
        jg.addWidget(self.jog_up, 0, 1); jg.addWidget(self.jog_left, 1, 0); jg.addWidget(self.jog_right, 1, 2); jg.addWidget(self.jog_down, 2, 1)
        jg.addWidget(self.jog_z_up, 0, 3); jg.addWidget(self.jog_z_down, 2, 3)
        jog_lay.addLayout(jg)

        # RIGHT COLUMN (Files & Overrides)
        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(20)
        dashboard.addLayout(right_col, 1)

        # Overrides Card
        ovr_card = self.create_card(_("OVERRIDES"))
        right_col.addWidget(ovr_card)
        ovr_lay = QtWidgets.QGridLayout(ovr_card.layout())
        self.feed_plus = FluidStyleButton("F+"); self.feed_minus = FluidStyleButton("F-"); self.feed_reset = FluidStyleButton("100%")
        self.spindle_plus = FluidStyleButton("S+"); self.spindle_minus = FluidStyleButton("S-"); self.spindle_reset = FluidStyleButton("100%")
        ovr_lay.addWidget(FCLabel("FEED"), 0, 0); ovr_lay.addWidget(self.feed_minus, 0, 1); ovr_lay.addWidget(self.feed_reset, 0, 2); ovr_lay.addWidget(self.feed_plus, 0, 3)
        ovr_lay.addWidget(FCLabel("SPINDLE"), 1, 0); ovr_lay.addWidget(self.spindle_minus, 1, 1); ovr_lay.addWidget(self.spindle_reset, 1, 2); ovr_lay.addWidget(self.spindle_plus, 1, 3)

        # System Features Card
        feat_card = self.create_card(_("SYSTEM"))
        right_col.addWidget(feat_card)
        feat_lay = QtWidgets.QGridLayout(feat_card.layout())
        self.cfg_dump = FluidStyleButton("Config Dump"); self.sd_list = FluidStyleButton("List SD Files"); self.info_btn = FluidStyleButton("System Info")
        feat_lay.addWidget(self.cfg_dump, 0, 0); feat_lay.addWidget(self.sd_list, 0, 1); feat_lay.addWidget(self.info_btn, 1, 0)
        
        self.estop_btn = FluidStyleButton(_("E-STOP"), "#d9534f"); self.reset_btn = FluidStyleButton(_("RESET"), "#5cb85c")
        feat_lay.addWidget(self.estop_btn, 2, 0); feat_lay.addWidget(self.reset_btn, 2, 1)

        # TERMINAL (Bottom Full Width)
        term_card = self.create_card(_("CONSOLE"))
        self.main_lay.addWidget(term_card, 1)
        term_lay = QtWidgets.QVBoxLayout(term_card.layout())
        self.console = FCTextArea(); self.console.setReadOnly(True); self.console.setStyleSheet("background: #222; color: #eee; font-family: 'Consolas'; border-radius: 4px;")
        term_lay.addWidget(self.console)
        
        inp_lay = QtWidgets.QHBoxLayout()
        self.command_entry = FCEntry(); self.command_entry.setPlaceholderText(_("G-Code or FluidNC command..."))
        inp_lay.addWidget(self.command_entry)
        
        self.play_btn = FluidStyleButton("▶ RUN", "#5cb85c"); self.pause_btn = FluidStyleButton("‖ PAUSE", "#f0ad4e"); self.stop_btn = FluidStyleButton("■ STOP", "#d9534f")
        inp_lay.addWidget(self.play_btn); inp_lay.addWidget(self.pause_btn); inp_lay.addWidget(self.stop_btn)
        term_lay.addLayout(inp_lay)
        
        prog_lay = QtWidgets.QHBoxLayout()
        self.object_combo = FCComboBox(); self.progress = QtWidgets.QProgressBar()
        prog_lay.addWidget(FCLabel(_("Job:"))); prog_lay.addWidget(self.object_combo); prog_lay.addWidget(self.progress)
        term_lay.addLayout(prog_lay)

    def create_card(self, title):
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"background: {self.bg_card}; border-radius: 8px; border: 1px solid #ddd;")
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(15, 15, 15, 15)
        title_lbl = FCLabel(f"<b>{title}</b>", size=10, color=self.primary)
        lay.addWidget(title_lbl)
        line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.Shape.HLine); line.setStyleSheet("color: #eee;"); lay.addWidget(line)
        return card

    def set_connected(self, connected):
        self.connect_btn.setText(_("DISCONNECT") if connected else _("CONNECT"))
        btns = [self.play_btn, self.pause_btn, self.stop_btn, self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down, 
                self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_btn, self.unlock_btn, self.cfg_dump, self.sd_list, self.info_btn,
                self.feed_plus, self.feed_minus, self.feed_reset, self.spindle_plus, self.spindle_minus, self.spindle_reset]
        for b in btns: b.setEnabled(connected)

    def append_console(self, text, type):
        color = {"tx": self.primary, "rx": "#aaa", "error": "#d9534f"}.get(type, "#888")
        if "MSG:ERR" in text: color = "#d9534f"
        elif "MSG:INFO" in text: color = "#5cb85c"
        elif "MSG:WARN" in text: color = "#f0ad4e"
        
        prefix = f'<span style="color: #666;">[{"TX" if type=="tx" else "RX"}]</span> '
        self.console.appendHtml(f'{prefix}<span style="color: {color};">{text}</span>')
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)
