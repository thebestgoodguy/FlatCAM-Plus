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
    def __init__(self, text="", color="#444", hover="#555", text_color="white", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: #222; }}
            QPushButton:disabled {{ background-color: #333; color: #666; }}
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

        # Style constants
        self.bg_dark = "#121212"
        self.bg_panel = "#1e1e1e"
        self.accent = "#ff7043" # Orange/Coral

        container = QtWidgets.QWidget()
        container.setStyleSheet(f"background-color: {self.bg_dark}; color: white; font-family: 'Segoe UI', sans-serif;")
        self.layout.addWidget(container)
        self.main_lay = QtWidgets.QVBoxLayout(container)
        self.main_lay.setContentsMargins(10, 10, 10, 10)
        self.main_lay.setSpacing(10)

        # --- HEADER ---
        header = QtWidgets.QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(f"background-color: {self.bg_panel}; border-radius: 8px;")
        h_lay = QtWidgets.QHBoxLayout(header)
        
        # Machine Status
        self.state_indicator = QtWidgets.QFrame(); self.state_indicator.setFixedSize(12, 12)
        self.state_label = FCLabel("DISCONNECTED"); self.state_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        h_lay.addWidget(FCLabel(_("Machine:")))
        h_lay.addWidget(self.state_indicator); h_lay.addWidget(self.state_label)
        
        h_lay.addSpacing(20)
        self.com_port = FCComboBox(); self.com_port.setMinimumWidth(100)
        self.com_refresh = RotatedToolButton(); self.com_refresh.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.connect_btn = AxioStyleButton(_("Connect"), self.accent, "#ff8a65")
        h_lay.addWidget(self.com_port); h_lay.addWidget(self.com_refresh); h_lay.addWidget(self.connect_btn)
        
        h_lay.addStretch()
        self.play_btn = AxioStyleButton("▶", "#2e7d32", "#388e3c"); self.pause_btn = AxioStyleButton("‖", "#f57c00", "#ff9800"); self.stop_btn = AxioStyleButton("■", "#c62828", "#d32f2f")
        h_lay.addWidget(self.play_btn); h_lay.addWidget(self.pause_btn); h_lay.addWidget(self.stop_btn)
        h_lay.addSpacing(10)
        self.reset_btn = AxioStyleButton(_("Reset"), "#424242", "#616161")
        self.estop_btn = AxioStyleButton(_("E-STOP"), "#d32f2f", "#f44336")
        h_lay.addWidget(self.reset_btn); h_lay.addWidget(self.estop_btn)
        self.main_lay.addWidget(header)

        # --- CENTER CONTENT ---
        center = QtWidgets.QHBoxLayout()
        self.main_lay.addLayout(center)

        # LEFT SIDEBAR
        sidebar = QtWidgets.QVBoxLayout()
        sidebar.setSpacing(10)
        center.addLayout(sidebar, 1)

        # Position Panel
        pos_box = QtWidgets.QGroupBox(_("Position"))
        pos_box.setStyleSheet(f"QGroupBox {{ background-color: {self.bg_panel}; border: 1px solid #333; border-radius: 8px; margin-top: 15px; font-weight: bold; }} QGroupBox::title {{ color: {self.accent}; subcontrol-origin: margin; left: 10px; }}")
        sidebar.addWidget(pos_box)
        pos_lay = GLay(pos_box)
        
        def add_pos_row(axis, color, row):
            l = FCLabel(axis); l.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12pt;")
            zero = FCButton("Ø"); zero.setFixedSize(25, 25); zero.setStyleSheet("background: #333; border-radius: 4px;")
            val = FCLabel("0.000"); val.setStyleSheet("font-size: 18pt; font-family: 'Consolas'; color: white;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            pos_lay.addWidget(l, row, 0); pos_lay.addWidget(zero, row, 1); pos_lay.addWidget(val, row, 2)
            return zero, val

        self.zero_x, self.x_val = add_pos_row("X", "#ff4444", 0)
        self.zero_y, self.y_val = add_pos_row("Y", "#44ff44", 1)
        self.zero_z, self.z_val = add_pos_row("Z", "#4444ff", 2)
        
        self.zero_all = AxioStyleButton(_("Zero All"), "#333", "#444")
        self.home_btn = AxioStyleButton(_("Home"), "#333", "#444")
        pos_lay.addWidget(self.zero_all, 3, 0, 1, 2); pos_lay.addWidget(self.home_btn, 3, 2)

        # Jog Control
        jog_box = QtWidgets.QGroupBox(_("Jog Control"))
        jog_box.setStyleSheet(pos_box.styleSheet())
        sidebar.addWidget(jog_box)
        jog_lay = QtWidgets.QVBoxLayout(jog_box)
        
        self.step_radio = RadioSet([{"label": "0.1", "value": "0.1"}, {"label": "1", "value": "1"}, {"label": "10", "value": "10"}], orientation='horizontal', compact=True)
        jog_lay.addWidget(self.step_radio)
        
        jog_btns = QtWidgets.QGridLayout()
        self.jog_up = FCButton("▲"); self.jog_down = FCButton("▼"); self.jog_left = FCButton("◀"); self.jog_right = FCButton("▶")
        self.jog_z_up = FCButton("Z+"); self.jog_z_down = FCButton("Z-")
        for b in [self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down]:
            b.setFixedSize(40, 40); b.setStyleSheet(f"background: #333; border: 1px solid #444; border-radius: 20px; font-weight: bold;")
        jog_btns.addWidget(self.jog_up, 0, 1); jog_btns.addWidget(self.jog_left, 1, 0); jog_btns.addWidget(self.jog_right, 1, 2); jog_btns.addWidget(self.jog_down, 2, 1)
        jog_btns.addWidget(self.jog_z_up, 0, 3); jog_btns.addWidget(self.jog_z_down, 2, 3)
        jog_lay.addLayout(jog_btns)
        
        self.unlock_btn = AxioStyleButton(_("Unlock Machine"), "#333", "#444")
        jog_lay.addWidget(self.unlock_btn)

        # RIGHT AREA (CONSOLE)
        right_area = QtWidgets.QVBoxLayout()
        center.addLayout(right_area, 2)
        
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid #333; background: {self.bg_panel}; border-radius: 8px; }} QTabBar::tab {{ background: #222; padding: 8px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }} QTabBar::tab:selected {{ background: {self.bg_panel}; color: {self.accent}; }}")
        right_area.addWidget(tabs)
        
        # Console Tab
        console_page = QtWidgets.QWidget()
        console_lay = QtWidgets.QVBoxLayout(console_page)
        self.console = FCTextArea(); self.console.setReadOnly(True)
        self.console.setStyleSheet("background: #0a0a0a; color: #bbb; font-family: 'Consolas'; font-size: 10pt; border: none;")
        console_lay.addWidget(self.console)
        
        cmd_lay = QtWidgets.QHBoxLayout()
        self.command_entry = FCEntry(); self.command_entry.setPlaceholderText(_("G-Code command..."))
        self.command_entry.setStyleSheet("background: #1a1a1a; border: 1px solid #333; padding: 5px; color: white;")
        cmd_lay.addWidget(self.command_entry)
        console_lay.addLayout(cmd_lay)
        tabs.addTab(console_page, _("Console"))
        
        # Streaming Status
        stream_pane = QtWidgets.QFrame()
        stream_pane.setStyleSheet(f"background: {self.bg_panel}; border-radius: 8px;")
        stream_lay = QtWidgets.QHBoxLayout(stream_pane)
        self.object_combo = FCComboBox(); stream_lay.addWidget(FCLabel(_("Job:"))); stream_lay.addWidget(self.object_combo)
        self.progress = QtWidgets.QProgressBar(); self.progress.setFixedHeight(10); stream_lay.addWidget(self.progress)
        right_area.addWidget(stream_pane)

        # --- FOOTER (Tool Library) ---
        footer = QtWidgets.QGroupBox(_("Tool Library"))
        footer.setStyleSheet(pos_box.styleSheet())
        footer.setFixedHeight(120)
        foot_lay = QtWidgets.QHBoxLayout(footer)
        for i in range(4):
            t_card = QtWidgets.QFrame(); t_card.setStyleSheet("background: #252525; border: 1px dashed #444; border-radius: 6px;")
            t_lay = QtWidgets.QVBoxLayout(t_card)
            t_lay.addWidget(FCLabel(f"T{i+1}", color=self.accent))
            t_lay.addWidget(FCLabel(_("Not Configured"), size=8))
            foot_lay.addWidget(t_card)
        self.main_lay.addWidget(footer)

    def set_connected(self, connected):
        self.connect_btn.setText(_("Disconnect") if connected else _("Connect"))
        self.connect_btn.setStyleSheet(f"background-color: {'#e67e22' if connected else self.accent}; border-radius: 4px; font-weight: bold;")
        for w in [self.play_btn, self.pause_btn, self.stop_btn, self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down, self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_btn, self.unlock_btn]:
            w.setEnabled(connected)

    def append_console(self, text, type):
        color = {"tx": self.accent, "rx": "#2ecc71", "error": "#e74c3c"}.get(type, "#888")
        self.console.appendHtml(f'<span style="color: {color};">{"> " if type=="tx" else "< "}{text}</span>')
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)
