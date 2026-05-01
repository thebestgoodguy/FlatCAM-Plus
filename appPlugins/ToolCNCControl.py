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
        
        self.send_queue = queue.Queue()
        self.sender_thread = None
        
        self.last_status_query = 0
        self.status_interval = 0.5  # seconds
        
        self.machine_state = "Disconnected"
        self.mpos = [0.0, 0.0, 0.0]
        self.wpos = [0.0, 0.0, 0.0]

        self.connect_signals_at_init()

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='', **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolCNCControl()")
        super().run()
        self.set_tool_ui()
        self.app.ui.notebook.setTabText(2, _("CNC Control"))

    def set_tool_ui(self):
        self.ui.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ui.com_port_combo.addItem(port.device)
        
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

    def on_refresh_ports(self):
        self.ui.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ui.com_port_combo.addItem(port.device)

    def on_connect_clicked(self):
        if not self.is_connected:
            port = self.ui.com_port_combo.currentText()
            baud = int(self.ui.baud_rate_combo.currentText())
            
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
        # GRBL Jogging command: $J=G91 G21 X... F...
        cmd = f"$J=G91 G21 {axis}{dist} F{feed}"
        self.send_command(cmd)

    def on_reset(self):
        if not self.is_connected or not self.ser:
            return
        # Soft reset for GRBL is Ctrl+X (0x18)
        self.ser.write(b'\x18')
        self.ui.append_console("Soft Reset (0x18)", "tx")

    def on_stop(self):
        if not self.is_connected or not self.ser:
            return
        # Feed hold is '!'
        self.ser.write(b'!')
        self.ui.append_console("Feed Hold (!)", "tx")

    def receive_loop(self):
        while not self.stop_thread.is_set():
            if self.ser and self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    if line:
                        self.append_console_sig.emit(line, "rx")
                        self.parse_line(line)
                except Exception as e:
                    log.error(f"Receive error: {str(e)}")
                    break
            
            # Periodically poll status
            now = time.time()
            if now - self.last_status_query > self.status_interval:
                self.send_command("?")
                self.last_status_query = now
            
            time.sleep(0.01)

    def parse_line(self, line):
        # GRBL status line: <Idle|MPos:0.000,0.000,0.000|Bf:15,128|FS:0,0|WCO:0.000,0.000,0.000>
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
        
        # Color status
        if self.machine_state == "Idle":
            self.ui.status_label.setStyleSheet("color: green;")
        elif self.machine_state == "Alarm":
            self.ui.status_label.setStyleSheet("color: red;")
        elif self.machine_state == "Run":
            self.ui.status_label.setStyleSheet("color: blue;")
        else:
            self.ui.status_label.setStyleSheet("color: orange;")

        # Update position
        if "WPos" in data:
            self.wpos = [float(x) for x in data["WPos"].split(",")]
            self.ui.pos_label.setText(f"X: {self.wpos[0]:.3f} Y: {self.wpos[1]:.3f} Z: {self.wpos[2]:.3f}")
        elif "MPos" in data:
            # If only MPos is available, we might need WCO to calculate WPos
            # For now just show MPos
            mpos = [float(x) for x in data["MPos"].split(",")]
            self.ui.pos_label.setText(f"MX: {mpos[0]:.3f} MY: {mpos[1]:.3f} MZ: {mpos[2]:.3f}")


class CNCControlUI:
    pluginName = _("CNC Control")

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

        self.jog_wdg = FCJog()
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

        self.zero_wdg = FCZeroAxes()
        self.ctrl_layout.addWidget(self.zero_wdg, 0, 0, 1, 2)

        self.unlock_button = FCButton(_("Unlock ($X)"))
        self.reset_button = FCButton(_("Reset (Ctrl+X)"))
        self.stop_button = FCButton(_("STOP (!)"))
        self.stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        
        self.ctrl_layout.addWidget(self.unlock_button, 1, 0)
        self.ctrl_layout.addWidget(self.reset_button, 1, 1)
        self.ctrl_layout.addWidget(self.stop_button, 2, 0, 1, 2)

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
        self.conn_frame.setDisabled(False) # Keep it enabled to allow disconnect
        self.com_port_combo.setDisabled(True)
        self.baud_rate_combo.setDisabled(True)
        self.com_refresh_button.setDisabled(True)
        
        self.status_frame.setDisabled(False)
        self.jog_frame.setDisabled(False)
        self.ctrl_frame.setDisabled(False)
        self.console_frame.setDisabled(False)

    def set_disconnected_ui(self):
        self.connect_button.setText(_("Connect"))
        self.connect_button.setStyleSheet("")
        self.com_port_combo.setDisabled(False)
        self.baud_rate_combo.setDisabled(False)
        self.com_refresh_button.setDisabled(False)
        
        self.status_frame.setDisabled(True)
        self.jog_frame.setDisabled(True)
        self.ctrl_frame.setDisabled(True)
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
        # Scroll to bottom
        self.console_output.moveCursor(QtGui.QTextCursor.MoveOperation.End)
