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
    Fluid UI Edition.
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
            self.app.ui.plot_tab_area.setCurrentWidget(self.scroll_area)
            
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
        
        # Jogging
        self.ui.jog_wdg.jog_up_button.clicked.connect(lambda: self.send_jog('Y', 1))
        self.ui.jog_wdg.jog_down_button.clicked.connect(lambda: self.send_jog('Y', -1))
        self.ui.jog_wdg.jog_left_button.clicked.connect(lambda: self.send_jog('X', -1))
        self.ui.jog_wdg.jog_right_button.clicked.connect(lambda: self.send_jog('X', 1))
        self.ui.jog_wdg.jog_z_up_button.clicked.connect(lambda: self.send_jog('Z', 1))
        self.ui.jog_wdg.jog_z_down_button.clicked.connect(lambda: self.send_jog('Z', -1))
        
        # Zeroing
        self.ui.zero_wdg.grbl_zerox_button.clicked.connect(lambda: self.send_command("G10 L20 P1 X0"))
        self.ui.zero_wdg.grbl_zeroy_button.clicked.connect(lambda: self.send_command("G10 L20 P1 Y0"))
        self.ui.zero_wdg.grbl_zeroz_button.clicked.connect(lambda: self.send_command("G10 L20 P1 Z0"))
        self.ui.zero_wdg.grbl_zero_all_button.clicked.connect(lambda: self.send_command("G10 L20 P1 X0 Y0 Z0"))
        self.ui.zero_wdg.grbl_homing_button.clicked.connect(lambda: self.send_command("$H"))

        # Actions
        self.ui.reset_button.clicked.connect(self.on_reset)
        self.ui.unlock_button.clicked.connect(lambda: self.send_command("$X"))
        self.ui.stop_button.clicked.connect(self.on_stop)

        # Spindle
        self.ui.spindle_on_button.clicked.connect(lambda: self.send_command(f"M3 S{self.ui.spindle_speed_entry.get_value()}"))
        self.ui.spindle_off_button.clicked.connect(lambda: self.send_command("M5"))

        # Streaming
        self.ui.stream_start_button.clicked.connect(self.on_stream_start)
        self.ui.stream_pause_button.clicked.connect(self.on_stream_pause)
        self.ui.stream_stop_button.clicked.connect(self.on_stream_stop)

    def on_refresh_ports(self):
        self.ui.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ui.com_port_combo.addItem(port.device)

    def on_connect_clicked(self):
        if not self.is_connected:
            port = self.ui.com_port_combo.currentText()
            baud = int(self.ui.baud_rate_combo.currentText())
            
            if not port:
                self.app.inform.emit("[WARNING_NOTCL] No COM port selected.")
                return

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
        if self.is_streaming:
            self.on_stream_stop()
        self.stop_thread.set()
        if self.ser:
            self.ser.close()
            self.ser = None
        self.is_connected = False
        self.ui.set_disconnected_ui()
        self.ui.append_console(_("Disconnected"), "info")
        self.machine_state = "Disconnected"
        self.update_status_sig.emit({})

    def on_send_command(self):
        cmd = self.ui.command_entry.text().strip()
        if cmd:
            self.send_command(cmd)
            self.ui.command_entry.clear()

    def send_command(self, cmd):
        if not self.is_connected or not self.ser:
            return
        try:
            self.ser.write((cmd + "\n").encode())
            self.append_console_sig.emit(cmd, "tx")
        except Exception as e:
            log.error(f"Send error: {str(e)}")
            self.disconnect()

    def send_jog(self, axis, direction):
        step = self.ui.jog_step_entry.get_value()
        feed = self.ui.jog_feed_entry.get_value()
        dist = step * direction
        cmd = f"$J=G91 G21 {axis}{dist} F{feed}"
        self.send_command(cmd)

    def on_reset(self):
        if not self.is_connected or not self.ser:
            return
        self.ser.write(b'\x18')
        self.ui.append_console("Soft Reset (0x18)", "tx")

    def on_stop(self):
        if not self.is_connected or not self.ser:
            return
        self.ser.write(b'!')
        self.ui.append_console("Feed Hold (!)", "tx")
        if self.is_streaming:
            self.on_stream_pause()

    def receive_loop(self):
        while not self.stop_thread.is_set():
            if self.ser and self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    if line:
                        if line == "ok":
                            self.ok_received.set()
                        elif line.startswith("error:"):
                            self.append_console_sig.emit(line, "error")
                            self.ok_received.set()
                        else:
                            self.append_console_sig.emit(line, "rx")
                            self.parse_line(line)
                except Exception as e:
                    log.error(f"Receive error: {str(e)}")
                    break
            
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
            self.ui.status_label.setText(_("Disconnected"))
            self.ui.status_label.setStyleSheet("background-color: #555; color: white; padding: 5px; border-radius: 4px;")
            self.ui.x_val.setText("0.000")
            self.ui.y_val.setText("0.000")
            self.ui.z_val.setText("0.000")
            return

        self.machine_state = data.get("state", "Unknown")
        self.ui.status_label.setText(f"<b>{self.machine_state.upper()}</b>")
        
        if self.machine_state == "Idle":
            self.ui.status_label.setStyleSheet("background-color: green; color: white; padding: 5px; border-radius: 4px;")
        elif "Alarm" in self.machine_state:
            self.ui.status_label.setStyleSheet("background-color: red; color: white; padding: 5px; border-radius: 4px;")
        elif "Run" in self.machine_state:
            self.ui.status_label.setStyleSheet("background-color: blue; color: white; padding: 5px; border-radius: 4px;")
        else:
            self.ui.status_label.setStyleSheet("background-color: orange; color: black; padding: 5px; border-radius: 4px;")

        if "WPos" in data:
            try:
                coords = [float(x) for x in data["WPos"].split(",")]
                self.ui.x_val.setText(f"{coords[0]:.3f}")
                self.ui.y_val.setText(f"{coords[1]:.3f}")
                self.ui.z_val.setText(f"{coords[2]:.3f}")
            except: pass

    # --- Streaming Logic ---
    def on_stream_start(self):
        if self.is_streaming:
            if self.streaming_paused:
                self.streaming_paused = False
                self.ui.stream_pause_button.setText(_("Pause"))
                return
            return

        obj_name = self.ui.object_combo.currentText()
        obj = self.app.collection.get_by_name(obj_name)
        if not obj:
            self.app.inform.emit("[WARNING_NOTCL] No CNC Job selected.")
            return

        gcode = obj.source_file
        if not gcode:
            self.app.inform.emit("[WARNING_NOTCL] CNC Job has no G-Code.")
            return

        self.gcode_lines = [line.strip() for line in gcode.split("\n") if line.strip() and not line.startswith("(")]
        self.current_line_idx = 0
        self.is_streaming = True
        self.streaming_paused = False
        self.start_time = time.time()
        
        self.ui.stream_start_button.setDisabled(True)
        self.ui.stream_pause_button.setDisabled(False)
        self.ui.stream_stop_button.setDisabled(False)
        self.ui.append_console(_("Streaming Started"), "info")

        threading.Thread(target=self.stream_loop, daemon=True).start()

    def on_stream_pause(self):
        if not self.is_streaming: return
        self.streaming_paused = not self.streaming_paused
        self.ui.stream_pause_button.setText(_("Resume") if self.streaming_paused else _("Pause"))

    def on_stream_stop(self):
        self.is_streaming = False
        self.ui.stream_start_button.setDisabled(False)
        self.ui.stream_pause_button.setDisabled(True)
        self.ui.stream_stop_button.setDisabled(True)
        self.update_progress_sig.emit(0, "00:00")

    def stream_loop(self):
        while self.is_streaming and self.current_line_idx < len(self.gcode_lines):
            if self.streaming_paused:
                time.sleep(0.1)
                continue

            line = self.gcode_lines[self.current_line_idx]
            self.ok_received.clear()
            self.send_command(line)
            self.ok_received.wait(timeout=10.0)
            self.current_line_idx += 1
            
            progress = (self.current_line_idx / len(self.gcode_lines)) * 100
            elapsed = time.time() - self.start_time
            rem_str = "--:--"
            if progress > 0:
                total_est = elapsed / (progress / 100.0)
                remaining = total_est - elapsed
                rem_str = time.strftime('%M:%S', time.gmtime(remaining))
            
            self.update_progress_sig.emit(progress, rem_str)

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

        # Header: Connection & Status
        header_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(header_layout)

        # --- Connection Group ---
        self.conn_frame = FCFrame()
        header_layout.addWidget(self.conn_frame, 2)
        self.conn_layout = GLay(self.conn_frame)
        
        self.com_port_combo = FCComboBox()
        self.conn_layout.addWidget(FCLabel(_("Port:")), 0, 0)
        self.conn_layout.addWidget(self.com_port_combo, 0, 1)

        self.com_refresh_button = RotatedToolButton()
        self.com_refresh_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.conn_layout.addWidget(self.com_refresh_button, 0, 2)

        self.baud_rate_combo = FCComboBox()
        self.baud_rate_combo.addItems(["9600", "115200", "250000"])
        self.baud_rate_combo.set_value("115200")
        self.conn_layout.addWidget(FCLabel(_("Baud:")), 1, 0)
        self.conn_layout.addWidget(self.baud_rate_combo, 1, 1)

        self.connect_button = FCButton(_("Connect"))
        self.connect_button.setMinimumHeight(40)
        self.conn_layout.addWidget(self.connect_button, 0, 3, 2, 1)

        # --- Machine State Group ---
        self.state_frame = FCFrame()
        header_layout.addWidget(self.state_frame, 1)
        self.state_layout = QtWidgets.QVBoxLayout(self.state_frame)
        self.state_layout.setContentsMargins(5, 5, 5, 5)
        
        self.state_title = FCLabel(f"<b>{_('Machine State')}</b>")
        self.state_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_layout.addWidget(self.state_title)
        self.status_label = FCLabel("DISCONNECTED")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("background-color: #555; color: white; padding: 5px; border-radius: 4px; font-weight: bold;")
        self.state_layout.addWidget(self.status_label)

        # --- DRO (Digital Read Out) Section ---
        self.dro_frame = FCFrame()
        self.dro_frame.setStyleSheet("background-color: #1a1a1a; border: 2px solid #333; border-radius: 8px;")
        self.layout.addWidget(self.dro_frame)
        self.dro_layout = GLay(self.dro_frame)
        self.dro_layout.setContentsMargins(20, 15, 20, 15)

        def create_dro_row(label, color):
            lbl = FCLabel(f"<b>{label}</b>")
            lbl.setStyleSheet(f"color: {color}; font-size: 24pt; font-family: 'Segoe UI', Arial;")
            val = FCLabel("0.000")
            val.setStyleSheet(f"color: white; font-size: 32pt; font-family: 'Consolas', monospace;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return lbl, val

        self.x_lbl, self.x_val = create_dro_row("X", "#ff4444")
        self.y_lbl, self.y_val = create_dro_row("Y", "#44ff44")
        self.z_lbl, self.z_val = create_dro_row("Z", "#4444ff")

        self.dro_layout.addWidget(self.x_lbl, 0, 0)
        self.dro_layout.addWidget(self.x_val, 0, 1)
        self.dro_layout.addWidget(self.y_lbl, 1, 0)
        self.dro_layout.addWidget(self.y_val, 1, 1)
        self.dro_layout.addWidget(self.z_lbl, 2, 0)
        self.dro_layout.addWidget(self.z_val, 2, 1)

        # Bottom Area: Controls, Spindle, Streaming
        bottom_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(bottom_layout)

        # Left Column: Jogging & Overrides
        left_col = QtWidgets.QVBoxLayout()
        bottom_layout.addLayout(left_col, 2)

        # --- Jogging ---
        self.jog_group = QtWidgets.QGroupBox(_("Movement Controls"))
        left_col.addWidget(self.jog_group)
        self.jog_layout = GLay(self.jog_group)
        
        self.jog_wdg = FCJog(self.app)
        self.jog_layout.addWidget(self.jog_wdg, 0, 0, 1, 2)

        self.jog_step_entry = FCDoubleSpinner()
        self.jog_step_entry.set_range(0.001, 100.0)
        self.jog_step_entry.set_value(1.0)
        self.jog_layout.addWidget(FCLabel(_("Step (mm):")), 1, 0)
        self.jog_layout.addWidget(self.jog_step_entry, 1, 1)

        self.jog_feed_entry = FCSpinner()
        self.jog_feed_entry.set_range(1, 5000)
        self.jog_feed_entry.set_value(1000)
        self.jog_layout.addWidget(FCLabel(_("Feed (mm/min):")), 2, 0)
        self.jog_layout.addWidget(self.jog_feed_entry, 2, 1)

        # --- Zeroing & System ---
        self.sys_group = QtWidgets.QGroupBox(_("Zeroing & Homing"))
        left_col.addWidget(self.sys_group)
        self.sys_layout = GLay(self.sys_group)
        self.zero_wdg = FCZeroAxes(self.app)
        self.sys_layout.addWidget(self.zero_wdg, 0, 0, 1, 2)

        self.unlock_button = FCButton(_("Unlock"))
        self.reset_button = FCButton(_("Reset"))
        self.stop_button = FCButton(_("STOP"))
        self.stop_button.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; height: 40px;")
        
        self.sys_layout.addWidget(self.unlock_button, 1, 0)
        self.sys_layout.addWidget(self.reset_button, 1, 1)
        self.sys_layout.addWidget(self.stop_button, 2, 0, 1, 2)

        # Right Column: Spindle, Streaming, Console
        right_col = QtWidgets.QVBoxLayout()
        bottom_layout.addLayout(right_col, 3)

        # --- Spindle Control ---
        self.spindle_group = QtWidgets.QGroupBox(_("Spindle Control"))
        right_col.addWidget(self.spindle_group)
        self.spindle_layout = GLay(self.spindle_group)
        
        self.spindle_speed_entry = FCSpinner()
        self.spindle_speed_entry.set_range(0, 30000)
        self.spindle_speed_entry.set_value(10000)
        self.spindle_layout.addWidget(FCLabel(_("Speed (RPM):")), 0, 0)
        self.spindle_layout.addWidget(self.spindle_speed_entry, 0, 1)

        self.spindle_on_button = FCButton(_("Spindle ON"))
        self.spindle_on_button.setStyleSheet("background-color: #388e3c; color: white;")
        self.spindle_off_button = FCButton(_("Spindle OFF"))
        self.spindle_off_button.setStyleSheet("background-color: #555; color: white;")
        
        self.spindle_layout.addWidget(self.spindle_on_button, 1, 0)
        self.spindle_layout.addWidget(self.spindle_off_button, 1, 1)

        # --- G-Code Sender ---
        self.stream_group = QtWidgets.QGroupBox(_("Job Streaming"))
        right_col.addWidget(self.stream_group)
        self.stream_layout = GLay(self.stream_group)

        self.object_combo = FCComboBox()
        self.stream_layout.addWidget(FCLabel(_("Job:")), 0, 0)
        self.stream_layout.addWidget(self.object_combo, 0, 1)

        self.stream_start_button = FCButton(_("Start Job"))
        self.stream_start_button.setMinimumHeight(40)
        self.stream_start_button.setStyleSheet("background-color: #1976d2; color: white; font-weight: bold;")
        self.stream_pause_button = FCButton(_("Pause"))
        self.stream_stop_button = FCButton(_("Stop"))
        
        self.stream_layout.addWidget(self.stream_start_button, 1, 0, 1, 2)
        self.stream_layout.addWidget(self.stream_pause_button, 2, 0)
        self.stream_layout.addWidget(self.stream_stop_button, 2, 1)

        self.progress_bar = QtWidgets.QProgressBar()
        self.stream_layout.addWidget(self.progress_bar, 3, 0, 1, 2)
        self.remaining_label = FCLabel(_("Remaining: 00:00"))
        self.remaining_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stream_layout.addWidget(self.remaining_label, 4, 0, 1, 2)

        # --- Console ---
        self.console_group = QtWidgets.QGroupBox(_("Console"))
        right_col.addWidget(self.console_group)
        self.console_layout = GLay(self.console_group)

        self.console_output = FCTextArea()
        self.console_output.setReadOnly(True)
        self.console_output.setMinimumHeight(120)
        self.console_output.setStyleSheet("background-color: #111; color: #0f0; font-family: monospace;")
        self.console_layout.addWidget(self.console_output, 0, 0, 1, 2)

        self.command_entry = FCEntry()
        self.command_entry.setPlaceholderText(_("Enter G-Code command..."))
        self.console_layout.addWidget(self.command_entry, 1, 0)
        self.send_button = FCButton(_("Send"))
        self.console_layout.addWidget(self.send_button, 1, 1)

    def set_connected_ui(self):
        self.connect_button.setText(_("Disconnect"))
        self.connect_button.setStyleSheet("background-color: #f57c00; color: white; font-weight: bold;")
        self.conn_frame.setDisabled(False) 
        self.com_port_combo.setDisabled(True)
        self.baud_rate_combo.setDisabled(True)
        self.com_refresh_button.setDisabled(True)
        
        self.dro_frame.setDisabled(False)
        self.jog_group.setDisabled(False)
        self.sys_group.setDisabled(False)
        self.spindle_group.setDisabled(False)
        self.stream_group.setDisabled(False)
        self.console_group.setDisabled(False)
        self.state_frame.setDisabled(False)
        
        self.stream_pause_button.setDisabled(True)
        self.stream_stop_button.setDisabled(True)

    def set_disconnected_ui(self):
        self.connect_button.setText(_("Connect"))
        self.connect_button.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.com_port_combo.setDisabled(False)
        self.baud_rate_combo.setDisabled(False)
        self.com_refresh_button.setDisabled(False)
        
        self.dro_frame.setDisabled(True)
        self.jog_group.setDisabled(True)
        self.sys_group.setDisabled(True)
        self.spindle_group.setDisabled(True)
        self.stream_group.setDisabled(True)
        self.console_group.setDisabled(True)
        self.state_frame.setDisabled(True)
        
        self.status_label.setText("DISCONNECTED")
        self.status_label.setStyleSheet("background-color: #555; color: white; padding: 5px; border-radius: 4px;")
        self.x_val.setText("0.000")
        self.y_val.setText("0.000")
        self.z_val.setText("0.000")

    def append_console(self, text, type):
        color = "#aaa"
        prefix = ""
        if type == "tx": color = "#3498db"; prefix = "> "
        elif type == "rx": color = "#2ecc71"; prefix = "< "
        elif type == "error": color = "#e74c3c"; prefix = "!! "
        elif type == "info": color = "#f1c40f"; prefix = "i "
        
        self.console_output.appendHtml(f'<span style="color: {color};">{prefix}{text}</span>')
        self.console_output.moveCursor(QtGui.QTextCursor.MoveOperation.End)
