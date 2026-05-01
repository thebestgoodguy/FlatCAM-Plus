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
            # Create a scroll area to host the tool UI
            self.scroll_area = VerticalScrollArea()
            self.scroll_area.setWidget(self)
            self.scroll_area.setWidgetResizable(True)
            
            # Add to plot_tab_area
            self.app.ui.plot_tab_area.addTab(self.scroll_area, _("CNC Settings"))
            self.app.ui.plot_tab_area.setCurrentWidget(self.scroll_area)
            
        self.set_tool_ui()

    def set_tool_ui(self):
        self.ui.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ui.com_port_combo.addItem(port.device)
        
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
                
                # Request initial status
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
                            self.ok_received.set() # Don't block streaming on error for now
                        else:
                            self.append_console_sig.emit(line, "rx")
                            self.parse_line(line)
                except Exception as e:
                    log.error(f"Receive error: {str(e)}")
                    break
            
            # Periodically poll status (only if not streaming or at low rate)
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
                    key, val = part.split(":")
                    status_dict[key] = val
            
            self.update_status_sig.emit(status_dict)

    def update_status_display(self, data):
        if not data:
            self.ui.status_label.setText(_("Disconnected"))
            self.ui.pos_label.setText("X: 0.000 Y: 0.000 Z: 0.000")
            return

        self.machine_state = data.get("state", "Unknown")
        self.ui.status_label.setText(f"<b>{self.machine_state}</b>")
        
        if self.machine_state == "Idle":
            self.ui.status_label.setStyleSheet("color: green;")
        elif "Alarm" in self.machine_state:
            self.ui.status_label.setStyleSheet("color: red;")
        elif "Run" in self.machine_state:
            self.ui.status_label.setStyleSheet("color: blue;")
        else:
            self.ui.status_label.setStyleSheet("color: orange;")

        if "WPos" in data:
            self.wpos = [float(x) for x in data["WPos"].split(",")]
            self.ui.pos_label.setText(f"X: {self.wpos[0]:.3f} Y: {self.wpos[1]:.3f} Z: {self.wpos[2]:.3f}")

    # --- Streaming Logic ---
    def on_stream_start(self):
        if self.is_streaming:
            if self.streaming_paused:
                self.streaming_paused = False
                self.ui.stream_pause_button.setText(_("Pause"))
                self.ui.append_console(_("Streaming Resumed"), "info")
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
        self.ui.append_console(_("Streaming Started") + f": {len(self.gcode_lines)} lines", "info")

        threading.Thread(target=self.stream_loop, daemon=True).start()

    def on_stream_pause(self):
        if not self.is_streaming:
            return
        self.streaming_paused = not self.streaming_paused
        self.ui.stream_pause_button.setText(_("Resume") if self.streaming_paused else _("Pause"))
        self.ui.append_console(_("Streaming Paused") if self.streaming_paused else _("Streaming Resumed"), "info")

    def on_stream_stop(self):
        self.is_streaming = False
        self.ui.stream_start_button.setDisabled(False)
        self.ui.stream_pause_button.setDisabled(True)
        self.ui.stream_stop_button.setDisabled(True)
        self.ui.append_console(_("Streaming Stopped"), "info")
        self.update_progress_sig.emit(0, "00:00")

    def stream_loop(self):
        while self.is_streaming and self.current_line_idx < len(self.gcode_lines):
            if self.streaming_paused:
                time.sleep(0.1)
                continue

            line = self.gcode_lines[self.current_line_idx]
            self.ok_received.clear()
            self.send_command(line)
            
            # Wait for 'ok' from GRBL
            if not self.ok_received.wait(timeout=5.0):
                self.append_console_sig.emit("Timeout waiting for 'ok'", "error")
            
            self.current_line_idx += 1
            
            # Update progress
            progress = (self.current_line_idx / len(self.gcode_lines)) * 100
            elapsed = time.time() - self.start_time
            if progress > 0:
                total_est = elapsed / (progress / 100.0)
                remaining = total_est - elapsed
                rem_str = time.strftime('%M:%S', time.gmtime(remaining))
            else:
                rem_str = "--:--"
            
            self.update_progress_sig.emit(progress, rem_str)

        if self.current_line_idx >= len(self.gcode_lines):
            self.append_console_sig.emit(_("Streaming Finished Successfully"), "info")
            self.is_streaming = False
            # Call back to UI thread to reset buttons
            QtCore.QMetaObject.invokeMethod(self.ui.stream_start_button, "setEnabled", Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(bool, True))

    def update_progress_ui(self, percent, remaining):
        self.ui.progress_bar.setValue(int(percent))
        self.ui.remaining_label.setText(f"{_('Remaining:')} {remaining}")


class CNCControlUI:
    pluginName = _("CNC Settings")

    def __init__(self, layout, app):
        self.app = app
        self.layout = layout

        # Title
        self.title_label = FCLabel(f"<b>{self.pluginName}</b>", size=16)
        self.layout.addWidget(self.title_label)

        # --- Connection Frame ---
        self.conn_frame = FCFrame()
        self.layout.addWidget(self.conn_frame)
        self.conn_layout = GLay(self.conn_frame)

        self.conn_label = FCLabel(f"<b>{_('Connection')}</b>")
        self.conn_layout.addWidget(self.conn_label, 0, 0, 1, 2)

        self.com_port_combo = FCComboBox()
        self.conn_layout.addWidget(FCLabel(_("Port:")), 1, 0)
        self.conn_layout.addWidget(self.com_port_combo, 1, 1)

        self.com_refresh_button = RotatedToolButton()
        self.com_refresh_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reload32.png'))
        self.conn_layout.addWidget(self.com_refresh_button, 1, 2)

        self.baud_rate_combo = FCComboBox()
        self.baud_rate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_rate_combo.set_value("115200")
        self.conn_layout.addWidget(FCLabel(_("Baud:")), 2, 0)
        self.conn_layout.addWidget(self.baud_rate_combo, 2, 1)

        self.connect_button = FCButton(_("Connect"))
        self.conn_layout.addWidget(self.connect_button, 3, 0, 1, 3)

        # --- Status Frame ---
        self.status_frame = FCFrame()
        self.layout.addWidget(self.status_frame)
        self.status_layout = GLay(self.status_frame)

        self.status_title = FCLabel(f"<b>{_('Machine Status')}</b>")
        self.status_layout.addWidget(self.status_title, 0, 0, 1, 2)

        self.status_label = FCLabel("<b>Disconnected</b>")
        self.status_layout.addWidget(FCLabel(_("State:")), 1, 0)
        self.status_layout.addWidget(self.status_label, 1, 1)

        self.pos_label = FCLabel("X: 0.000 Y: 0.000 Z: 0.000")
        self.pos_label.setStyleSheet("font-family: monospace; font-size: 12pt;")
        self.status_layout.addWidget(self.pos_label, 2, 0, 1, 2)

        # --- Jogging Frame ---
        self.jog_frame = FCFrame()
        self.layout.addWidget(self.jog_frame)
        self.jog_layout = GLay(self.jog_frame)
        
        self.jog_title = FCLabel(f"<b>{_('Jogging')}</b>")
        self.jog_layout.addWidget(self.jog_title, 0, 0, 1, 2)

        self.jog_wdg = FCJog(self.app)
        self.jog_layout.addWidget(self.jog_wdg, 1, 0, 1, 2)

        self.jog_step_entry = FCDoubleSpinner()
        self.jog_step_entry.set_range(0.001, 1000.0)
        self.jog_step_entry.set_value(1.0)
        self.jog_layout.addWidget(FCLabel(_("Step:")), 2, 0)
        self.jog_layout.addWidget(self.jog_step_entry, 2, 1)

        self.jog_feed_entry = FCSpinner()
        self.jog_feed_entry.set_range(1, 10000)
        self.jog_feed_entry.set_value(1000)
        self.jog_layout.addWidget(FCLabel(_("Feed:")), 3, 0)
        self.jog_layout.addWidget(self.jog_feed_entry, 3, 1)

        # --- Control & Zeroing ---
        self.ctrl_frame = FCFrame()
        self.layout.addWidget(self.ctrl_frame)
        self.ctrl_layout = GLay(self.ctrl_frame)

        self.zero_wdg = FCZeroAxes(self.app)
        self.ctrl_layout.addWidget(self.zero_wdg, 0, 0, 1, 2)

        self.unlock_button = FCButton(_("Unlock ($X)"))
        self.reset_button = FCButton(_("Reset (Ctrl+X)"))
        self.stop_button = FCButton(_("STOP (!)"))
        self.stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        
        self.ctrl_layout.addWidget(self.unlock_button, 1, 0)
        self.ctrl_layout.addWidget(self.reset_button, 1, 1)
        self.ctrl_layout.addWidget(self.stop_button, 2, 0, 1, 2)

        # --- G-Code Sender Frame ---
        self.stream_frame = FCFrame()
        self.layout.addWidget(self.stream_frame)
        self.stream_layout = GLay(self.stream_frame)

        self.stream_title = FCLabel(f"<b>{_('G-Code Sender')}</b>")
        self.stream_layout.addWidget(self.stream_title, 0, 0, 1, 2)

        self.object_combo = FCComboBox()
        self.stream_layout.addWidget(FCLabel(_("Job:")), 1, 0)
        self.stream_layout.addWidget(self.object_combo, 1, 1)

        self.stream_start_button = FCButton(_("Start Streaming"))
        self.stream_pause_button = FCButton(_("Pause"))
        self.stream_stop_button = FCButton(_("Stop"))
        
        self.stream_layout.addWidget(self.stream_start_button, 2, 0, 1, 2)
        self.stream_layout.addWidget(self.stream_pause_button, 3, 0)
        self.stream_layout.addWidget(self.stream_stop_button, 3, 1)

        self.progress_bar = QtWidgets.QProgressBar()
        self.stream_layout.addWidget(self.progress_bar, 4, 0, 1, 2)

        self.remaining_label = FCLabel(_("Remaining: 00:00"))
        self.stream_layout.addWidget(self.remaining_label, 5, 0, 1, 2)

        # --- Console ---
        self.console_frame = FCFrame()
        self.layout.addWidget(self.console_frame)
        self.console_layout = GLay(self.console_frame)

        self.console_title = FCLabel(f"<b>{_('Console')}</b>")
        self.console_layout.addWidget(self.console_title, 0, 0, 1, 2)

        self.console_output = FCTextArea()
        self.console_output.setReadOnly(True)
        self.console_output.setMinimumHeight(150)
        self.console_layout.addWidget(self.console_output, 1, 0, 1, 2)

        self.command_entry = FCEntry()
        self.command_entry.setPlaceholderText(_("Enter G-Code..."))
        self.console_layout.addWidget(self.command_entry, 2, 0)

        self.send_button = FCButton(_("Send"))
        self.console_layout.addWidget(self.send_button, 2, 1)

        self.layout.addStretch()

    def set_connected_ui(self):
        self.connect_button.setText(_("Disconnect"))
        self.connect_button.setStyleSheet("background-color: orange;")
        self.conn_frame.setDisabled(False) 
        self.com_port_combo.setDisabled(True)
        self.baud_rate_combo.setDisabled(True)
        self.com_refresh_button.setDisabled(True)
        
        self.status_frame.setDisabled(False)
        self.jog_frame.setDisabled(False)
        self.ctrl_frame.setDisabled(False)
        self.stream_frame.setDisabled(False)
        self.console_frame.setDisabled(False)
        
        self.stream_pause_button.setDisabled(True)
        self.stream_stop_button.setDisabled(True)

    def set_disconnected_ui(self):
        self.connect_button.setText(_("Connect"))
        self.connect_button.setStyleSheet("")
        self.com_port_combo.setDisabled(False)
        self.baud_rate_combo.setDisabled(False)
        self.com_refresh_button.setDisabled(False)
        
        self.status_frame.setDisabled(True)
        self.jog_frame.setDisabled(True)
        self.ctrl_frame.setDisabled(True)
        self.stream_frame.setDisabled(True)
        self.console_frame.setDisabled(True)
        
        self.status_label.setText("<b>Disconnected</b>")
        self.status_label.setStyleSheet("")
        self.pos_label.setText("X: 0.000 Y: 0.000 Z: 0.000")

    def append_console(self, text, type):
        color = "black"
        prefix = ""
        if type == "tx":
            color = "blue"
            prefix = "> "
        elif type == "rx":
            color = "green"
            prefix = "< "
        elif type == "error":
            color = "red"
            prefix = "!! "
        elif type == "info":
            color = "gray"
            prefix = "i "
        
        self.console_output.appendHtml(f'<span style="color: {color};">{prefix}{text}</span>')
        self.console_output.moveCursor(QtGui.QTextCursor.MoveOperation.End)
