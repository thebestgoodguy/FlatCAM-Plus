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

class AxioStyleButton(FCButton):
    def __init__(self, text="", color="#2d2d2d", hover="#3d3d3d", text_color="#ddd", parent=None, icon=None):
        super().__init__(text, parent)
        if icon: self.setIcon(QtGui.QIcon(icon))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: {text_color}; border: 1px solid #444;
                border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: {hover}; border: 1px solid #ff7043; }}
            QPushButton:pressed {{ background-color: #1a1a1a; }}
            QPushButton:disabled {{ background-color: #222; color: #555; border: 1px solid #333; }}
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
        
        # Position Zeroing
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
                self.send_command("$I") # Get FluidNC version info
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

        # Style constants (AxioCNC Theme)
        self.bg_dark = "#0a0a0a"
        self.bg_panel = "#141414"
        self.bg_input = "#1e1e1e"
        self.accent = "#ff7043"

        container = QtWidgets.QWidget()
        container.setStyleSheet(f"background-color: {self.bg_dark}; color: #bbb; font-family: 'Segoe UI', sans-serif;")
        self.layout.addWidget(container)
        self.main_lay = QtWidgets.QVBoxLayout(container)
        self.main_lay.setContentsMargins(15, 15, 15, 15)
        self.main_lay.setSpacing(15)

        # --- TOP HEADER ---
        header = QtWidgets.QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background-color: {self.bg_panel}; border: 1px solid #222; border-radius: 6px;")
        h_lay = QtWidgets.QHBoxLayout(header)
        h_lay.setContentsMargins(15, 0, 15, 0)
        
        self.state_indicator = QtWidgets.QFrame(); self.state_indicator.setFixedSize(10, 10); self.state_indicator.setStyleSheet("background-color: #555; border-radius: 5px;")
        self.state_label = FCLabel("DISCONNECTED"); self.state_label.setStyleSheet("font-weight: bold; color: white; font-size: 10pt;")
        h_lay.addWidget(self.state_indicator); h_lay.addWidget(self.state_label)
        
        h_lay.addSpacing(25)
        self.com_port = FCComboBox(); self.com_port.setMinimumWidth(120); self.com_port.setStyleSheet(f"background: {self.bg_input}; border: 1px solid #333;")
        self.com_refresh = RotatedToolButton(); self.com_refresh.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.connect_btn = AxioStyleButton(_("Connect"), self.accent, "#ff8a65", "white")
        h_lay.addWidget(self.com_port); h_lay.addWidget(self.com_refresh); h_lay.addWidget(self.connect_btn)
        
        h_lay.addStretch()
        self.play_btn = AxioStyleButton("▶", "#2e7d32", "#388e3c", "white"); self.pause_btn = AxioStyleButton("‖", "#f57c00", "#ff9800", "white"); self.stop_btn = AxioStyleButton("■", "#c62828", "#d32f2f", "white")
        for b in [self.play_btn, self.pause_btn, self.stop_btn]: b.setFixedWidth(40)
        h_lay.addWidget(self.play_btn); h_lay.addWidget(self.pause_btn); h_lay.addWidget(self.stop_btn)
        
        h_lay.addSpacing(10)
        self.reset_btn = AxioStyleButton(_("Reset"), "#2d2d2d", "#444")
        self.estop_btn = AxioStyleButton(_("E-STOP"), "#c62828", "#d32f2f", "white")
        h_lay.addWidget(self.reset_btn); h_lay.addWidget(self.estop_btn)
        self.main_lay.addWidget(header)

        # --- MAIN CONTENT ---
        content = QtWidgets.QHBoxLayout()
        self.main_lay.addLayout(content)

        # SIDEBAR (LEFT)
        sidebar = QtWidgets.QVBoxLayout()
        sidebar.setSpacing(15)
        sidebar_widget = QtWidgets.QWidget(); sidebar_widget.setFixedWidth(320); sidebar_widget.setLayout(sidebar)
        content.addWidget(sidebar_widget)

        # Position (DRO) Panel
        pos_frame = QtWidgets.QFrame(); pos_frame.setStyleSheet(f"background: {self.bg_panel}; border: 1px solid #222; border-radius: 6px;")
        sidebar.addWidget(pos_frame)
        pos_lay = QtWidgets.QVBoxLayout(pos_frame)
        pos_lay.addWidget(FCLabel(_("POSITION"), color=self.accent, bold=True, size=9))
        
        pos_grid = GLay()
        def add_pos_grid(axis, color, r):
            l = FCLabel(axis); l.setFixedSize(20, 20); l.setStyleSheet(f"background: {color}; color: white; border-radius: 3px; font-weight: bold;")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            z = FCButton("↺"); z.setFixedSize(24, 24); z.setStyleSheet("background: #2a2a2a; border-radius: 3px;")
            v = FCLabel("0.000"); v.setStyleSheet(f"background: #000; color: white; font-size: 18pt; font-family: 'Consolas'; border-radius: 3px; padding: 2px 10px;")
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            pos_grid.addWidget(l, r, 0); pos_grid.addWidget(z, r, 1); pos_grid.addWidget(v, r, 2)
            return z, v
        self.zero_x, self.x_val = add_pos_grid("X", "#d32f2f", 0)
        self.zero_y, self.y_val = add_pos_grid("Y", "#388e3c", 1)
        self.zero_z, self.z_val = add_pos_grid("Z", "#1976d2", 2)
        pos_lay.addLayout(pos_grid)
        
        btn_row = QtWidgets.QHBoxLayout()
        self.zero_all = AxioStyleButton(_("Zero All"), "#252525", "#333"); self.home_btn = AxioStyleButton(_("Home"), "#252525", "#333"); self.unlock_btn = AxioStyleButton(_("Unlock"), "#252525", "#333")
        btn_row.addWidget(self.zero_all); btn_row.addWidget(self.home_btn); btn_row.addWidget(self.unlock_btn)
        pos_lay.addLayout(btn_row)

        # Jog Control Panel
        jog_frame = QtWidgets.QFrame(); jog_frame.setStyleSheet(pos_frame.styleSheet())
        sidebar.addWidget(jog_frame)
        jog_lay = QtWidgets.QVBoxLayout(jog_frame)
        jog_lay.addWidget(FCLabel(_("JOG CONTROL"), color=self.accent, bold=True, size=9))
        
        self.step_radio = RadioSet([{"label": "0.1", "value": "0.1"}, {"label": "1", "value": "1"}, {"label": "10", "value": "10"}], orientation='horizontal', compact=True)
        jog_lay.addWidget(self.step_radio)
        
        jog_grid = QtWidgets.QGridLayout(); jog_grid.setSpacing(5)
        self.jog_up = AxioStyleButton("▲"); self.jog_down = AxioStyleButton("▼"); self.jog_left = AxioStyleButton("◀"); self.jog_right = AxioStyleButton("▶")
        self.jog_z_up = AxioStyleButton("Z+"); self.jog_z_down = AxioStyleButton("Z-")
        for b in [self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down]: b.setFixedSize(40, 40)
        jog_grid.addWidget(self.jog_up, 0, 1); jog_grid.addWidget(self.jog_left, 1, 0); jog_grid.addWidget(self.jog_right, 1, 2); jog_grid.addWidget(self.jog_down, 2, 1)
        jog_grid.addWidget(self.jog_z_up, 0, 3); jog_grid.addWidget(self.jog_z_down, 2, 3)
        jog_lay.addLayout(jog_grid)

        # FluidNC Features Panel
        feat_frame = QtWidgets.QFrame(); feat_frame.setStyleSheet(pos_frame.styleSheet())
        sidebar.addWidget(feat_frame)
        feat_lay = QtWidgets.QVBoxLayout(feat_frame)
        feat_lay.addWidget(FCLabel(_("FLUIDNC TOOLS"), color=self.accent, bold=True, size=9))
        
        fl_btns = QtWidgets.QGridLayout()
        self.cfg_dump = AxioStyleButton("CFG Dump", "#252525", "#333"); self.sd_list = AxioStyleButton("SD List", "#252525", "#333"); self.info_btn = AxioStyleButton("Sys Info", "#252525", "#333")
        fl_btns.addWidget(self.cfg_dump, 0, 0); fl_btns.addWidget(self.sd_list, 0, 1); fl_btns.addWidget(self.info_btn, 1, 0)
        feat_lay.addLayout(fl_btns)

        # Overrides Panel
        ovr_frame = QtWidgets.QFrame(); ovr_frame.setStyleSheet(pos_frame.styleSheet())
        sidebar.addWidget(ovr_frame)
        ovr_lay = QtWidgets.QVBoxLayout(ovr_frame)
        ovr_lay.addWidget(FCLabel(_("OVERRIDES"), color=self.accent, bold=True, size=9))
        
        ovr_grid = QtWidgets.QGridLayout()
        self.feed_plus = AxioStyleButton("F+10%"); self.feed_minus = AxioStyleButton("F-10%"); self.feed_reset = AxioStyleButton("F 100%")
        self.spindle_plus = AxioStyleButton("S+10%"); self.spindle_minus = AxioStyleButton("S-10%"); self.spindle_reset = AxioStyleButton("S 100%")
        ovr_grid.addWidget(self.feed_minus, 0, 0); ovr_grid.addWidget(self.feed_reset, 0, 1); ovr_grid.addWidget(self.feed_plus, 0, 2)
        ovr_grid.addWidget(self.spindle_minus, 1, 0); ovr_grid.addWidget(self.spindle_reset, 1, 1); ovr_grid.addWidget(self.spindle_plus, 1, 2)
        ovr_lay.addLayout(ovr_grid)

        # CENTER PANEL (Terminal & Console)
        center_panel = QtWidgets.QVBoxLayout()
        content.addLayout(center_panel, 1)
        
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid #222; background: {self.bg_panel}; border-radius: 8px; }} QTabBar::tab {{ background: #111; padding: 10px 25px; margin-right: 2px; }} QTabBar::tab:selected {{ background: {self.bg_panel}; color: {self.accent}; font-weight: bold; }}")
        center_panel.addWidget(tabs)
        
        # Terminal Tab
        terminal_page = QtWidgets.QWidget(); term_lay = QtWidgets.QVBoxLayout(terminal_page)
        self.console = FCTextArea(); self.console.setReadOnly(True); self.console.setStyleSheet("background: #000; color: #888; font-family: 'Consolas'; font-size: 10pt; border: none;")
        term_lay.addWidget(self.console)
        
        cmd_bar = QtWidgets.QHBoxLayout()
        self.command_entry = FCEntry(); self.command_entry.setPlaceholderText(_("Enter FluidNC / G-Code command...")); self.command_entry.setStyleSheet("background: #0d0d0d; border: 1px solid #333; color: #ddd; padding: 6px;")
        cmd_bar.addWidget(self.command_entry)
        term_lay.addLayout(cmd_bar)
        tabs.addTab(terminal_page, _("TERMINAL"))
        
        # Streaming Status Bar
        stream_bar = QtWidgets.QFrame(); stream_bar.setFixedHeight(50); stream_bar.setStyleSheet(f"background: {self.bg_panel}; border: 1px solid #222; border-radius: 6px;")
        sb_lay = QtWidgets.QHBoxLayout(stream_bar)
        self.object_combo = FCComboBox(); self.progress = QtWidgets.QProgressBar(); self.progress.setFixedHeight(4); self.progress.setStyleSheet(f"QProgressBar {{ background: #000; border-radius: 2px; border: none; }} QProgressBar::chunk {{ background: {self.accent}; }}")
        sb_lay.addWidget(FCLabel(_("Job:"), size=8, color="#666")); sb_lay.addWidget(self.object_combo); sb_lay.addWidget(self.progress)
        center_panel.addWidget(stream_bar)

        # FOOTER (Tool Cards)
        footer = QtWidgets.QHBoxLayout()
        self.main_lay.addLayout(footer)
        for i in range(4):
            card = QtWidgets.QFrame(); card.setFixedHeight(90); card.setStyleSheet("background: #111; border: 1px solid #222; border-radius: 6px;")
            cl = QtWidgets.QVBoxLayout(card)
            cl.addWidget(FCLabel(f"T{i+1}", color=self.accent, bold=True, size=10))
            cl.addWidget(FCLabel(_("FluidNC Tool"), size=8, color="#555"))
            footer.addWidget(card)

    def set_connected(self, connected):
        self.connect_btn.setText(_("Disconnect") if connected else _("Connect"))
        for w in [self.play_btn, self.pause_btn, self.stop_btn, self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down, self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_btn, self.unlock_btn, self.cfg_dump, self.sd_list, self.info_btn, self.feed_plus, self.feed_minus, self.feed_reset, self.spindle_plus, self.spindle_minus, self.spindle_reset]:
            w.setEnabled(connected)

    def append_console(self, text, type):
        # FluidNC Style Colorization
        color = {"tx": self.accent, "rx": "#bbb", "error": "#f44336"}.get(type, "#888")
        prefix = '<span style="color: #555;">&gt;</span> ' if type=="tx" else '<span style="color: #555;">&lt;</span> '
        
        # Parse FluidNC Messages
        if "MSG:ERR" in text: color = "#f44336"
        elif "MSG:INFO" in text: color = "#4caf50"
        elif "MSG:WARN" in text: color = "#ff9800"
        elif "MSG:DBG" in text: color = "#9c27b0"
        
        self.console.appendHtml(f'{prefix}<span style="color: {color};">{text}</span>')
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)
