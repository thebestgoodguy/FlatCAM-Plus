# ##########################################################
# FlatCAM Plus: 2D Post-processing for Manufacturing        #
# File by:  Antigravity (AI)                               #
# Date:     05/01/2026                                     #
# License:  MIT Licence                                    #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal, QThread
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


class ToolCNCControl(AppTool):
    """
    CNC Connection and Management Tool for FlatCAM Plus.
    Supports GRBL-based controllers.
    Organized Dashboard Edition.
    """

    update_status_sig = pyqtSignal(dict)
    append_console_sig = pyqtSignal(str, str)  # text, type (tx/rx)
    update_progress_sig = pyqtSignal(float, str) # percent, remaining_time

    def __init__(self, app):
        self.app = app
        self.decimals = self.app.decimals
        AppTool.__init__(self, app)

        self.ui = CNCControlUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName

        self.ser = None
        self.receiver_thread = None
        self.is_connected = False
        self.stop_thread = threading.Event()
        
        self.last_status_query = 0
        self.status_interval = 0.5  # seconds
        
        self.machine_state = "Disconnected"
        self.mpos = [0.0, 0.0, 0.0]
        self.wpos = [0.0, 0.0, 0.0]

        # Streaming state
        self.is_streaming = False
        self.streaming_paused = False
        self.gcode_lines = []
        self.current_line_idx = 0
        self.start_time = 0
        self.ok_received = threading.Event()

        self.scroll_area = None

        self.connect_signals_at_init()

    def install(self, icon=None, separator=None, shortcut=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut=shortcut, **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolCNCControl()")
        
        # Check if tab already exists in plot_tab_area
        tab_exists = False
        for i in range(self.app.ui.plot_tab_area.count()):
            if self.app.ui.plot_tab_area.tabText(i) == _("CNC Settings"):
                self.app.ui.plot_tab_area.setCurrentIndex(i)
                tab_exists = True
                break
        
        if not tab_exists:
            self.scroll_area = VerticalScrollArea()
            self.scroll_area.setWidget(self)
            self.scroll_area.setWidgetResizable(True)
            self.app.ui.plot_tab_area.addTab(self.scroll_area, _("CNC Settings"))
            self.app.ui.plot_tab_area.setCurrentIndex(self.app.ui.plot_tab_area.count() - 1)
            
        self.set_tool_ui()

    def set_tool_ui(self):
        self.on_refresh_ports()
        
        # Populate CNC Objects
        self.ui.object_combo.clear()
        for obj in self.app.collection.get_list():
            if obj.kind == 'cncjob':
                self.ui.object_combo.addItem(obj.obj_options['name'])

        if not self.is_connected:
            self.ui.set_disconnected_ui()
        else:
            self.ui.set_connected_ui()

    def connect_signals_at_init(self):
        self.ui.com_refresh_button.clicked.connect(self.on_refresh_ports)
        self.ui.connect_button.clicked.connect(self.on_connect_clicked)
        self.ui.command_entry.returnPressed.connect(self.on_send_command)
        self.ui.send_button.clicked.connect(self.on_send_command)
        
        self.update_status_sig.connect(self.update_status_display)
        self.append_console_sig.connect(self.ui.append_console)
        self.update_progress_sig.connect(self.update_progress_ui)
        
        # Jogging (Directional)
        self.ui.jog_up.clicked.connect(lambda: self.send_jog('Y', 1))
        self.ui.jog_down.clicked.connect(lambda: self.send_jog('Y', -1))
        self.ui.jog_left.clicked.connect(lambda: self.send_jog('X', -1))
        self.ui.jog_right.clicked.connect(lambda: self.send_jog('X', 1))
        self.ui.jog_z_up.clicked.connect(lambda: self.send_jog('Z', 1))
        self.ui.jog_z_down.clicked.connect(lambda: self.send_jog('Z', -1))
        
        # Zeroing
        self.ui.zero_x.clicked.connect(lambda: self.send_command("G10 L20 P1 X0"))
        self.ui.zero_y.clicked.connect(lambda: self.send_command("G10 L20 P1 Y0"))
        self.ui.zero_z.clicked.connect(lambda: self.send_command("G10 L20 P1 Z0"))
        self.ui.zero_all.clicked.connect(lambda: self.send_command("G10 L20 P1 X0 Y0 Z0"))
        self.ui.home_button.clicked.connect(lambda: self.send_command("$H"))

        # Actions
        self.ui.reset_button.clicked.connect(self.on_reset)
        self.ui.unlock_button.clicked.connect(lambda: self.send_command("$X"))
        self.ui.estop_button.clicked.connect(self.on_stop)

        # Spindle
        self.ui.spindle_on.clicked.connect(lambda: self.send_command(f"M3 S{self.ui.spindle_speed_entry.get_value()}"))
        self.ui.spindle_off.clicked.connect(lambda: self.send_command("M5"))

        # Streaming
        self.ui.stream_start_button.clicked.connect(self.on_stream_start)
        self.ui.stream_pause_button.clicked.connect(self.on_stream_pause)
        self.ui.stream_stop_button.clicked.connect(self.on_stream_stop)

        # Overrides
        self.ui.f_100.clicked.connect(lambda: self.send_byte(0x90))
        self.ui.f_plus_10.clicked.connect(lambda: self.send_byte(0x91))
        self.ui.f_minus_10.clicked.connect(lambda: self.send_byte(0x92))
        self.ui.f_plus_1.clicked.connect(lambda: self.send_byte(0x93))
        self.ui.f_minus_1.clicked.connect(lambda: self.send_byte(0x94))
        
        self.ui.s_100.clicked.connect(lambda: self.send_byte(0x99))
        self.ui.s_plus_10.clicked.connect(lambda: self.send_byte(0x9A))
        self.ui.s_minus_10.clicked.connect(lambda: self.send_byte(0x9B))
        self.ui.s_plus_1.clicked.connect(lambda: self.send_byte(0x9C))
        self.ui.s_minus_1.clicked.connect(lambda: self.send_byte(0x9D))

    def on_refresh_ports(self):
        self.ui.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ui.com_port_combo.addItem(port.device)
        if self.ui.com_port_combo.count() == 0:
            self.ui.com_port_combo.addItem("None")

    def on_connect_clicked(self):
        if not self.is_connected:
            port = self.ui.com_port_combo.currentText()
            if port == "None":
                self.app.inform.emit("[WARNING_NOTCL] No COM port available.")
                return
            baud = int(self.ui.baud_rate_combo.currentText())
            try:
                self.ser = serial.Serial(port, baud, timeout=0.1)
                self.is_connected = True
                self.ui.set_connected_ui()
                self.ui.append_console(_("Connected to") + f" {port} @ {baud}", "info")
                self.stop_thread.clear()
                self.receiver_thread = threading.Thread(target=self.receive_loop, daemon=True)
                self.receiver_thread.start()
                self.send_command("?")
            except Exception as e:
                self.app.inform.emit(f"[ERROR_NOTCL] Connection failed: {str(e)}")
                self.ui.append_console(f"Connection error: {str(e)}", "error")
        else:
            self.disconnect()

    def disconnect(self):
        if self.is_streaming: self.on_stream_stop()
        self.stop_thread.set()
        if self.ser: self.ser.close(); self.ser = None
        self.is_connected = False
        self.ui.set_disconnected_ui()
        self.ui.append_console(_("Disconnected"), "info")
        self.machine_state = "Disconnected"
        self.update_status_sig.emit({})

    def on_send_command(self):
        cmd = self.ui.command_entry.text().strip()
        if cmd: self.send_command(cmd); self.ui.command_entry.clear()

    def send_command(self, cmd):
        if not self.is_connected or not self.ser: return
        try:
            self.ser.write((cmd + "\n").encode())
            self.append_console_sig.emit(cmd, "tx")
        except Exception as e:
            log.error(f"Send error: {str(e)}"); self.disconnect()

    def send_byte(self, byte):
        if not self.is_connected or not self.ser: return
        try:
            self.ser.write(bytes([byte]))
            self.append_console_sig.emit(f"0x{byte:02X}", "tx")
        except Exception as e:
            log.error(f"Byte send error: {str(e)}"); self.disconnect()

    def send_jog(self, axis, direction):
        step = float(self.ui.step_radio.get_value())
        feed = self.ui.jog_feed_entry.get_value()
        dist = step * direction
        cmd = f"$J=G91 G21 {axis}{dist} F{feed}"
        self.send_command(cmd)

    def on_reset(self):
        if not self.is_connected or not self.ser: return
        self.ser.write(b'\x18')
        self.ui.append_console("Soft Reset (0x18)", "tx")

    def on_stop(self):
        if not self.is_connected or not self.ser: return
        self.ser.write(b'!')
        self.ui.append_console("Feed Hold (!)", "tx")
        if self.is_streaming: self.on_stream_pause()

    def receive_loop(self):
        while not self.stop_thread.is_set():
            if self.ser and self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    if line:
                        if line == "ok": self.ok_received.set()
                        elif line.startswith("error:"):
                            self.append_console_sig.emit(line, "error"); self.ok_received.set()
                        else:
                            self.append_console_sig.emit(line, "rx")
                            self.parse_line(line)
                except: break
            now = time.time()
            if now - self.last_status_query > self.status_interval:
                self.send_command("?")
                self.last_status_query = now
            time.sleep(0.01)

    def parse_line(self, line):
        if line.startswith("<") and line.endswith(">"):
            parts = line[1:-1].split("|")
            status_dict = {"state": parts[0]}
            for part in parts[1:]:
                if ":" in part:
                    try:
                        key, val = part.split(":")
                        status_dict[key] = val
                    except: pass
            self.update_status_sig.emit(status_dict)

    def update_status_display(self, data):
        if not data:
            self.ui.status_label.setText("DISCONNECTED")
            self.ui.status_label.setStyleSheet("background-color: #555; color: white; padding: 5px; border-radius: 4px;")
            self.ui.x_val.setText("0.000"); self.ui.y_val.setText("0.000"); self.ui.z_val.setText("0.000")
            return
        self.machine_state = data.get("state", "Unknown")
        self.ui.status_label.setText(f"<b>{self.machine_state.upper()}</b>")
        colors = {"Idle": ("green", "white"), "Alarm": ("red", "white"), "Run": ("blue", "white")}
        bg, fg = colors.get(self.machine_state, ("orange", "black"))
        self.ui.status_label.setStyleSheet(f"background-color: {bg}; color: {fg}; padding: 5px; border-radius: 4px; font-weight: bold;")
        if "WPos" in data:
            try:
                coords = [float(x) for x in data["WPos"].split(",")]
                self.ui.x_val.setText(f"{coords[0]:.3f}"); self.ui.y_val.setText(f"{coords[1]:.3f}"); self.ui.z_val.setText(f"{coords[2]:.3f}")
            except: pass
        if "FS" in data:
            try:
                fs = data["FS"].split(",")
                self.ui.f_real.setText(f"F: {fs[0]}")
                self.ui.s_real.setText(f"S: {fs[1]}")
            except: pass

    def on_stream_start(self):
        if self.is_streaming:
            if self.streaming_paused: self.streaming_paused = False; self.ui.stream_pause_button.setText(_("Pause")); return
            return
        obj = self.app.collection.get_by_name(self.ui.object_combo.currentText())
        if not obj or not obj.source_file:
            self.app.inform.emit("[WARNING_NOTCL] No valid CNC Job source."); return
        self.gcode_lines = [line.strip() for line in obj.source_file.split("\n") if line.strip() and not line.startswith("(")]
        self.current_line_idx = 0; self.is_streaming = True; self.streaming_paused = False; self.start_time = time.time()
        self.ui.stream_start_button.setDisabled(True); self.ui.stream_pause_button.setDisabled(False); self.ui.stream_stop_button.setDisabled(False)
        threading.Thread(target=self.stream_loop, daemon=True).start()

    def on_stream_pause(self):
        if not self.is_streaming: return
        self.streaming_paused = not self.streaming_paused
        self.ui.stream_pause_button.setText(_("Resume") if self.streaming_paused else _("Pause"))

    def on_stream_stop(self):
        self.is_streaming = False
        self.ui.stream_start_button.setDisabled(False); self.ui.stream_pause_button.setDisabled(True); self.ui.stream_stop_button.setDisabled(True)
        self.update_progress_sig.emit(0, "00:00")

    def stream_loop(self):
        while self.is_streaming and self.current_line_idx < len(self.gcode_lines):
            if self.streaming_paused: time.sleep(0.1); continue
            self.ok_received.clear(); self.send_command(self.gcode_lines[self.current_line_idx])
            self.ok_received.wait(timeout=10.0); self.current_line_idx += 1
            progress = (self.current_line_idx / len(self.gcode_lines)) * 100
            elapsed = time.time() - self.start_time
            rem = (elapsed / (progress / 100.0) - elapsed) if progress > 0 else 0
            self.update_progress_sig.emit(progress, time.strftime('%M:%S', time.gmtime(rem)))
        self.is_streaming = False
        QtCore.QMetaObject.invokeMethod(self.ui.stream_start_button, "setEnabled", Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(bool, True))

    def update_progress_ui(self, percent, remaining):
        self.ui.progress_bar.setValue(int(percent))
        self.ui.remaining_label.setText(f"{_('Remaining:')} {remaining}")


class CNCControlUI:
    pluginName = _("CNC Settings")

    def __init__(self, layout, app):
        self.app = app
        self.layout = layout
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # --- Dashboard Layout (Grid) ---
        main_grid = QtWidgets.QGridLayout()
        main_grid.setSpacing(10)
        self.layout.addLayout(main_grid)

        # ==========================================
        # SECTION: CONNECTION (Top Row, Span all)
        # ==========================================
        self.conn_group = QtWidgets.QGroupBox(_("Connection & Control"))
        main_grid.addWidget(self.conn_group, 0, 0, 1, 3)
        conn_lay = QtWidgets.QHBoxLayout(self.conn_group)
        
        self.com_port_combo = FCComboBox()
        self.com_port_combo.setMinimumWidth(100)
        self.com_refresh_button = RotatedToolButton()
        self.com_refresh_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.baud_rate_combo = FCComboBox()
        self.baud_rate_combo.addItems(["9600", "115200", "250000"])
        self.baud_rate_combo.set_value("115200")
        self.baud_rate_combo.setMinimumWidth(80)
        self.connect_button = FCButton(_("Connect"))
        self.connect_button.setMinimumWidth(120)
        
        self.estop_button = FCButton(_("E-STOP"))
        self.estop_button.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 5px 20px;")
        
        conn_lay.addWidget(FCLabel(_("Port:")))
        conn_lay.addWidget(self.com_port_combo)
        conn_lay.addWidget(self.com_refresh_button)
        conn_lay.addWidget(FCLabel(_("Baud:")))
        conn_lay.addWidget(self.baud_rate_combo)
        conn_lay.addWidget(self.connect_button)
        conn_lay.addStretch()
        conn_lay.addWidget(self.estop_button)

        # ==========================================
        # SECTION: DRO & JOG (Middle Column)
        # ==========================================
        mid_col = QtWidgets.QVBoxLayout()
        main_grid.addLayout(mid_col, 1, 1)

        # DRO
        dro_frame = FCFrame()
        dro_frame.setStyleSheet("background-color: #1a1a1a; border: 2px solid #333; border-radius: 6px;")
        mid_col.addWidget(dro_frame)
        dro_lay = GLay(dro_frame)
        dro_lay.setContentsMargins(15, 10, 15, 10)
        
        def add_dro(axis, color, row):
            l = FCLabel(axis); l.setStyleSheet(f"color: {color}; font-size: 18pt; font-weight: bold;")
            v = FCLabel("0.000"); v.setStyleSheet("color: white; font-size: 24pt; font-family: 'Consolas', monospace;")
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            dro_lay.addWidget(l, row, 0); dro_lay.addWidget(v, row, 1)
            return v
        
        self.x_val = add_dro("X", "#ff4444", 0)
        self.y_val = add_dro("Y", "#44ff44", 1)
        self.z_val = add_dro("Z", "#4444ff", 2)

        # Jog
        jog_group = QtWidgets.QGroupBox(_("Jogging"))
        mid_col.addWidget(jog_group)
        jog_grid = QtWidgets.QGridLayout(jog_group)
        
        self.jog_up = FCButton(); self.jog_up.setIcon(QtGui.QIcon(self.app.resource_location + '/up-arrow32.png'))
        self.jog_down = FCButton(); self.jog_down.setIcon(QtGui.QIcon(self.app.resource_location + '/down-arrow32.png'))
        self.jog_left = FCButton(); self.jog_left.setIcon(QtGui.QIcon(self.app.resource_location + '/left_arrow32.png'))
        self.jog_right = FCButton(); self.jog_right.setIcon(QtGui.QIcon(self.app.resource_location + '/right_arrow32.png'))
        for b in [self.jog_up, self.jog_down, self.jog_left, self.jog_right]: b.setFixedSize(45, 45)
        
        jog_grid.addWidget(self.jog_up, 0, 1)
        jog_grid.addWidget(self.jog_left, 1, 0)
        jog_grid.addWidget(self.jog_right, 1, 2)
        jog_grid.addWidget(self.jog_down, 2, 1)

        self.jog_z_up = FCButton("+Z"); self.jog_z_down = FCButton("-Z")
        for b in [self.jog_z_up, self.jog_z_down]: b.setFixedSize(45, 45)
        jog_grid.addWidget(self.jog_z_up, 0, 3); jog_grid.addWidget(self.jog_z_down, 2, 3)

        self.step_radio = RadioSet([
            {"label": "0.1", "value": "0.1"}, {"label": "1", "value": "1"}, 
            {"label": "10", "value": "10"}, {"label": "50", "value": "50"}, {"label": "100", "value": "100"}
        ], orientation='vertical', compact=True)
        self.step_radio.set_value("10")
        jog_grid.addWidget(self.step_radio, 0, 4, 3, 1)

        self.jog_feed_entry = FCSpinner(); self.jog_feed_entry.set_range(1, 10000); self.jog_feed_entry.set_value(1000)
        jog_grid.addWidget(FCLabel(_("Feed:")), 3, 0); jog_grid.addWidget(self.jog_feed_entry, 3, 1, 1, 2)

        # Zeroing
        zero_group = QtWidgets.QGroupBox(_("Zeroing"))
        mid_col.addWidget(zero_group)
        zero_lay = QtWidgets.QHBoxLayout(zero_group)
        self.zero_x = FCButton("Ø X"); self.zero_y = FCButton("Ø Y"); self.zero_z = FCButton("Ø Z"); self.zero_all = FCButton("Ø ALL")
        for b in [self.zero_x, self.zero_y, self.zero_z, self.zero_all]: zero_lay.addWidget(b); b.setStyleSheet("font-weight: bold;")

        # ==========================================
        # SECTION: TERMINAL & OVERRIDES (Left Column)
        # ==========================================
        left_col = QtWidgets.QVBoxLayout()
        main_grid.addLayout(left_col, 1, 0)

        # Terminal
        term_group = QtWidgets.QGroupBox(_("Terminal"))
        left_col.addWidget(term_group, 2)
        term_lay = QtWidgets.QVBoxLayout(term_group)
        self.console_output = FCTextArea()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Consolas', monospace; font-size: 9pt;")
        term_lay.addWidget(self.console_output)
        
        in_lay = QtWidgets.QHBoxLayout()
        self.command_entry = FCEntry(); self.command_entry.setPlaceholderText(_("G-Code..."))
        self.send_button = FCButton(_("Send"))
        in_lay.addWidget(self.command_entry); in_lay.addWidget(self.send_button)
        term_lay.addLayout(in_lay)

        # Overrides
        over_group = QtWidgets.QGroupBox(_("Overrides"))
        left_col.addWidget(over_group, 1)
        over_lay = GLay(over_group)
        
        def add_over_row(label, row):
            over_lay.addWidget(FCLabel(f"<b>{label}</b>"), row, 0)
            b_lay = QtWidgets.QHBoxLayout()
            m10 = FCButton("-10"); m1 = FCButton("-1"); c100 = FCButton("100"); p1 = FCButton("+1"); p10 = FCButton("+10")
            for b in [m10, m1, c100, p1, p10]: b_lay.addWidget(b); b.setStyleSheet("padding: 2px; font-size: 8pt;")
            over_lay.addLayout(b_lay, row, 1)
            return m10, m1, c100, p1, p10

        self.f_minus_10, self.f_minus_1, self.f_100, self.f_plus_1, self.f_plus_10 = add_over_row(_("F"), 0)
        self.s_minus_10, self.s_minus_1, self.s_100, self.s_plus_1, self.s_plus_10 = add_over_row(_("S"), 1)

        # ==========================================
        # SECTION: STATUS & SPINDLE & STREAM (Right)
        # ==========================================
        right_col = QtWidgets.QVBoxLayout()
        main_grid.addLayout(right_col, 1, 2)

        # Status
        stat_group = QtWidgets.QGroupBox(_("Status"))
        right_col.addWidget(stat_group)
        stat_lay = GLay(stat_group)
        self.status_label = FCLabel("DISCONNECTED")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stat_lay.addWidget(self.status_label, 0, 0, 1, 2)
        
        self.f_real = FCLabel("F: 0"); self.s_real = FCLabel("S: 0")
        stat_lay.addWidget(self.f_real, 1, 0); stat_lay.addWidget(self.s_real, 1, 1)
        
        self.home_button = FCButton(_("HOME")); self.home_button.setIcon(QtGui.QIcon(self.app.resource_location + '/home16.png'))
        self.unlock_button = FCButton(_("UNLOCK")); self.reset_button = FCButton(_("RESET"))
        stat_lay.addWidget(self.home_button, 2, 0); stat_lay.addWidget(self.unlock_button, 2, 1); stat_lay.addWidget(self.reset_button, 3, 0, 1, 2)

        # Spindle
        spin_group = QtWidgets.QGroupBox(_("Spindle"))
        right_col.addWidget(spin_group)
        spin_lay = GLay(spin_group)
        self.spindle_speed_entry = FCSpinner()
        self.spindle_speed_entry.set_range(0, 30000)
        self.spindle_speed_entry.set_value(10000)
        self.spindle_speed_entry.setMaximumWidth(100)
        spin_lay.addWidget(FCLabel(_("RPM:")), 0, 0)
        spin_lay.addWidget(self.spindle_speed_entry, 0, 1)
        spin_lay.setRowStretch(2, 1)
        self.spindle_on = FCButton(_("M3 ON")); self.spindle_off = FCButton(_("M5 OFF"))
        spin_lay.addWidget(self.spindle_on, 1, 0); spin_lay.addWidget(self.spindle_off, 1, 1)

        # Streaming
        stream_group = QtWidgets.QGroupBox(_("Streaming"))
        right_col.addWidget(stream_group)
        stream_lay = GLay(stream_group)
        self.object_combo = FCComboBox(); stream_lay.addWidget(FCLabel(_("Job:")), 0, 0); stream_lay.addWidget(self.object_combo, 0, 1)
        self.stream_start_button = FCButton(_("START")); self.stream_start_button.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 30px;")
        self.stream_pause_button = FCButton(_("PAUSE")); self.stream_stop_button = FCButton(_("STOP"))
        stream_lay.addWidget(self.stream_start_button, 1, 0, 1, 2)
        stream_lay.addWidget(self.stream_pause_button, 2, 0); stream_lay.addWidget(self.stream_stop_button, 2, 1)
        self.progress_bar = QtWidgets.QProgressBar(); stream_lay.addWidget(self.progress_bar, 3, 0, 1, 2)
        self.remaining_label = FCLabel(_("Remaining: 00:00")); self.remaining_label.setAlignment(Qt.AlignmentFlag.AlignCenter); stream_lay.addWidget(self.remaining_label, 4, 0, 1, 2)

        self.layout.addStretch()

    def set_connected_ui(self):
        self.connect_button.setText(_("Disconnect")); self.connect_button.setStyleSheet("background-color: #e67e22; color: white;")
        for w in [self.estop_button, self.command_entry, self.send_button, self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down, 
                  self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_button, self.unlock_button, self.reset_button, self.spindle_on, self.spindle_off, 
                  self.stream_start_button, self.f_100, self.f_plus_10, self.f_minus_10, self.f_plus_1, self.f_minus_1, self.s_100, self.s_plus_10, self.s_minus_10, self.s_plus_1, self.s_minus_1]:
            w.setDisabled(False)
        self.stream_pause_button.setDisabled(True); self.stream_stop_button.setDisabled(True)
        self.com_port_combo.setDisabled(True); self.baud_rate_combo.setDisabled(True); self.com_refresh_button.setDisabled(True)

    def set_disconnected_ui(self):
        self.connect_button.setText(_("Connect")); self.connect_button.setStyleSheet("background-color: #27ae60; color: white;")
        for w in [self.estop_button, self.command_entry, self.send_button, self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down, 
                  self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_button, self.unlock_button, self.reset_button, self.spindle_on, self.spindle_off, 
                  self.stream_start_button, self.stream_pause_button, self.stream_stop_button, self.f_100, self.f_plus_10, self.f_minus_10, self.f_plus_1, self.f_minus_1, self.s_100, self.s_plus_10, self.s_minus_10, self.s_plus_1, self.s_minus_1]:
            w.setDisabled(True)
        self.com_port_combo.setDisabled(False); self.baud_rate_combo.setDisabled(False); self.com_refresh_button.setDisabled(False)

    def append_console(self, text, type):
        colors = {"tx": "#3498db", "rx": "#2ecc71", "error": "#e74c3c", "info": "#f1c40f"}
        prefix = { "tx": "> ", "rx": "< ", "error": "!! ", "info": "i " }.get(type, "")
        self.console_output.appendHtml(f'<span style="color: {colors.get(type, "#aaa")};">{prefix}{text}</span>')
        self.console_output.moveCursor(QtGui.QTextCursor.MoveOperation.End)
