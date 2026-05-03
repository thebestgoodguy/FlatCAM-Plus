# ##########################################################
# FlatCAM PLUS: 2D Post-processing for Manufacturing       #
# File Updated By Sadri ERCAN - 2026                        #
# File Author: Sadri ERCAN                                 #
# Date:     05/01/2026                                     #
# License:  MIT Licence                                    #
# ##########################################################

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import Qt, pyqtSignal

from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea
from appPlugins.cnc_control.dialogs import MacroDialog
from appPlugins.cnc_control.profiles import CNC_PROFILES
from appPlugins.cnc_control.transports import HttpTransport, SerialTransport, TcpTransport
from appPlugins.cnc_control.ui import CNCControlUI

import builtins
import gettext
import logging
import re
import threading
import time

import serial.tools.list_ports

import appTranslation as fcTranslate

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolCNCControl(AppTool):
    update_status_sig = pyqtSignal(dict)
    append_console_sig = pyqtSignal(str, str)
    update_progress_sig = pyqtSignal(float, str)
    connection_state_sig = pyqtSignal(bool, str)
    files_update_sig = pyqtSignal(dict)
    sd_file_sig = pyqtSignal(str)
    clear_sd_files_sig = pyqtSignal()
    controller_info_sig = pyqtSignal(dict)
    busy_sig = pyqtSignal(bool, str)
    test_connection_sig = pyqtSignal(bool, str)

    def __init__(self, app):
        self.app = app
        AppTool.__init__(self, app)

        self.transport = None
        self.is_connected = False
        self.stop_thread = threading.Event()
        self.macros = []
        self.load_macros()
        self.receiver_thread = None
        self.io_lock = threading.RLock()
        self.ok_received = threading.Event()
        self.last_status_query = 0
        self.status_interval = 0.1
        self.sd_collecting = False
        self.active_profile_key = "fluidnc"
        self.status_poll_enabled = True
        self.hide_status_reports = True

        self.is_streaming = False
        self.streaming_paused = False
        self.current_line_idx = 0
        self.gcode_lines = []

        self.ui = CNCControlUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.active_profile_key = self.ui.profile_combo.currentData() or "fluidnc"
        self.load_macros()
        self.connect_signals_at_init()
        self.ui.set_connected(False)
        self.register_toolbar_connection_handler()
        self.update_toolbar_connection_status(False, "")

    def run(self, toggle=True):
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

        self.on_refresh_ports()
        self.update_tool_list()
        self.load_macros()

    def connect_signals_at_init(self):
        self.ui.connect_btn.clicked.connect(self.on_connect_clicked)
        self.ui.test_connection_btn.clicked.connect(self.on_test_connection_clicked)
        self.ui.disconnect_btn.clicked.connect(self.disconnect)
        self.ui.com_refresh.clicked.connect(self.on_refresh_ports)
        self.ui.connection_mode_combo.currentIndexChanged.connect(self.ui.on_connection_mode_changed)
        self.ui.profile_combo.currentIndexChanged.connect(self.on_profile_changed)
        self.ui.poll_status_cb.toggled.connect(self.on_poll_status_changed)
        self.ui.hide_status_reports_cb.toggled.connect(self.on_hide_status_reports_changed)

        self.ui.home_btn.clicked.connect(lambda: self.send_profile_command("home"))
        self.ui.unlock_btn.clicked.connect(lambda: self.send_profile_command("unlock"))
        self.ui.reset_btn.clicked.connect(lambda: self.send_profile_command("reset"))
        self.ui.estop_btn.clicked.connect(lambda: self.send_profile_command("hold"))
        self.ui.resume_btn.clicked.connect(lambda: self.send_profile_command("resume"))
        self.ui.info_btn.clicked.connect(self.on_info_clicked)
        self.ui.cfg_dump.clicked.connect(lambda: self.send_profile_command("config"))

        self.ui.zero_x.clicked.connect(lambda: self.send_zero("X"))
        self.ui.zero_y.clicked.connect(lambda: self.send_zero("Y"))
        self.ui.zero_z.clicked.connect(lambda: self.send_zero("Z"))
        self.ui.zero_all.clicked.connect(lambda: self.send_profile_command("zero_all"))

        self.ui.feed_plus.clicked.connect(lambda: self.send_profile_command("feed_plus"))
        self.ui.feed_minus.clicked.connect(lambda: self.send_profile_command("feed_minus"))
        self.ui.feed_reset.clicked.connect(lambda: self.send_profile_command("feed_reset"))
        self.ui.feed_set_btn.clicked.connect(lambda: self.on_set_override("feed_set", self.ui.feed_override_entry))
        self.ui.spindle_plus.clicked.connect(lambda: self.send_profile_command("spindle_plus"))
        self.ui.spindle_minus.clicked.connect(lambda: self.send_profile_command("spindle_minus"))
        self.ui.spindle_reset.clicked.connect(lambda: self.send_profile_command("spindle_reset"))
        self.ui.spindle_override_set_btn.clicked.connect(
            lambda: self.on_set_override("spindle_override_set", self.ui.spindle_override_entry)
        )
        self.ui.spindle_set_btn.clicked.connect(self.on_set_spindle_rpm)
        self.ui.spindle_stop_btn.clicked.connect(lambda: self.send_profile_command("spindle_stop"))

        self.ui.macro_probe.clicked.connect(lambda: self.send_profile_command("probe_z"))
        self.ui.macro_laser.clicked.connect(self.on_toggle_laser)

        self.ui.jog_up.clicked.connect(lambda: self.send_jog("Y", 1))
        self.ui.jog_down.clicked.connect(lambda: self.send_jog("Y", -1))
        self.ui.jog_left.clicked.connect(lambda: self.send_jog("X", -1))
        self.ui.jog_right.clicked.connect(lambda: self.send_jog("X", 1))
        self.ui.jog_z_up.clicked.connect(lambda: self.send_jog("Z", 1))
        self.ui.jog_z_down.clicked.connect(lambda: self.send_jog("Z", -1))

        self.ui.sd_list_btn.clicked.connect(self.on_sd_list)
        self.ui.run_sd_btn.clicked.connect(self.on_run_sd)
        self.ui.refresh_jobs_btn.clicked.connect(self.update_tool_list)

        self.ui.command_entry.returnPressed.connect(self.on_send_command)
        self.ui.play_btn.clicked.connect(self.on_stream_start)
        self.ui.pause_btn.clicked.connect(self.on_stream_pause)
        self.ui.stop_btn.clicked.connect(self.on_stream_stop)

        self.ui.files_refresh_btn.clicked.connect(self.on_refresh_files)
        self.ui.files_upload_btn.clicked.connect(self.on_upload_files)
        self.ui.files_mkdir_btn.clicked.connect(self.on_create_dir)
        self.ui.files_delete_btn.clicked.connect(self.on_delete_file)
        self.ui.files_up_btn.clicked.connect(self.on_files_up)
        self.ui.files_root_btn.clicked.connect(self.on_files_root)
        self.ui.files_fs_combo.currentIndexChanged.connect(self.on_filesystem_changed)
        self.ui.files_table.itemDoubleClicked.connect(self.on_file_double_clicked)

        self.ui.files_dialog_btn.clicked.connect(self.on_open_files_dialog)
        self.ui.manage_macros_btn.clicked.connect(self.on_manage_macros)

        self.update_status_sig.connect(self.update_status_display)
        self.append_console_sig.connect(self.ui.append_console)
        self.update_progress_sig.connect(self.update_progress_ui)
        self.connection_state_sig.connect(self.on_connection_state_changed)
        self.files_update_sig.connect(self.ui.update_files_table)
        self.sd_file_sig.connect(self.ui.add_sd_file)
        self.clear_sd_files_sig.connect(self.ui.clear_sd_files)
        self.controller_info_sig.connect(self.ui.update_controller_info)
        self.busy_sig.connect(self.ui.set_busy)
        self.test_connection_sig.connect(self.on_test_connection_finished)

    def update_tool_list(self):
        self.ui.object_combo.clear()
        for obj in self.app.collection.get_list():
            if getattr(obj, "kind", None) == "cncjob":
                self.ui.object_combo.addItem(obj.obj_options["name"])

    def on_refresh_ports(self):
        self.ui.com_port.clear()
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            description = port.description if port.description else port.device
            self.ui.com_port.addItem(f"{port.device} - {description}", port.device)
        if self.ui.com_port.count() == 0:
            self.ui.com_port.addItem("None", "None")

    def current_profile(self):
        return CNC_PROFILES.get(self.active_profile_key, CNC_PROFILES["fluidnc"])

    def current_profile_key(self):
        return self.active_profile_key

    def update_toolbar_connection_status(self, connected=False, description="", state=None):
        updater = getattr(getattr(self.app, "ui", None), "update_cnc_toolbar_status", None)
        if callable(updater):
            updater(connected, description or "", state=state)

    def register_toolbar_connection_handler(self):
        setter = getattr(getattr(self.app, "ui", None), "set_cnc_toolbar_connection_handler", None)
        if callable(setter):
            setter(self.on_toolbar_connection_clicked)

    def on_toolbar_connection_clicked(self):
        self.on_refresh_ports()
        self.ui.show_connection_dialog(self.is_connected)

    def on_open_files_dialog(self):
        self.ui.show_file_system_dialog()
        if self.is_connected:
            self.on_refresh_files()

    def on_profile_changed(self):
        self.active_profile_key = self.ui.profile_combo.currentData() or "fluidnc"

    def on_poll_status_changed(self, enabled):
        self.status_poll_enabled = bool(enabled)

    def on_hide_status_reports_changed(self, enabled):
        self.hide_status_reports = bool(enabled)

    def on_connect_clicked(self):
        if self.is_connected:
            self.disconnect()
            return

        config = self.ui.connection_config()
        message = self.validate_connection_config(config)
        if message:
            self.append_console_sig.emit(message, "error")
            return

        self.ui.set_connection_actions_enabled(False)
        self.append_console_sig.emit(_("Connecting..."), "info")
        threading.Thread(target=self._connect_worker, args=(config,), daemon=True).start()

    def validate_connection_config(self, config):
        if config["mode"] == "serial" and config["port"] == "None":
            return _("No COM port selected.")
        if config["mode"] == "tcp" and not config["host"]:
            return _("No host selected.")
        if config["mode"] == "http" and not config["web_url"]:
            return _("No URL selected.")
        return ""

    def build_transport(self, config):
        if config["mode"] == "serial":
            return SerialTransport(config["port"], config["baudrate"])
        if config["mode"] == "tcp":
            return TcpTransport(config["host"], config["tcp_port"])
        return HttpTransport(config["web_url"], config["user"], config["password"])

    def _connect_worker(self, config):
        try:
            transport = self.build_transport(config)
            transport.open()
            with self.io_lock:
                self.transport = transport
                self.is_connected = True
                self.stop_thread.clear()

            self.connection_state_sig.emit(True, transport.description())
            self.receiver_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receiver_thread.start()

            if isinstance(transport, HttpTransport) and transport.info_text:
                self.parse_controller_info(transport.info_text)
            else:
                self.send_profile_command("info", log=False)
        except Exception as e:
            log.error("CNC connection error: %s", e)
            self.append_console_sig.emit(f"{_('Connection failed')}: {e}", "error")
            self.connection_state_sig.emit(False, "")

    def on_connection_state_changed(self, connected, description):
        self.ui.set_connection_actions_enabled(True)
        self.ui.set_connected(connected)
        self.update_toolbar_connection_status(connected, description)
        if connected:
            self.append_console_sig.emit(f"{_('Connected')}: {description}", "info")
            self.ui.connection_desc.setText(description)
            self.on_refresh_files()
        else:
            self.ui.connection_desc.setText(_("Offline"))
            self.append_console_sig.emit(_("Disconnected"), "info")
        self.ui.sync_connection_dialog(connected)

    # ##########################################################
    # ##################### MACRO SYSTEM #######################
    # ##########################################################

    def load_macros(self):
        settings = QtCore.QSettings("Open Source", "FlatCAM_Plus")
        if settings.contains("cnc_macros"):
            import json
            try:
                self.macros = json.loads(settings.value("cnc_macros"))
            except Exception:
                self.macros = []
        else:
            self.macros = [
                {"name": "Home & Zero", "content": "G28\nG10 L20 P1 X0 Y0 Z0"},
                {"name": "Probe Z", "content": "G38.2 Z-50 F100\nG92 Z0"}
            ]

        # Only update an inline macro list if a future CNC subplugin provides one.
        if hasattr(self, 'ui') and self.ui and hasattr(self.ui, "macro_list"):
            self.ui.macro_list.clear()
            for macro in self.macros:
                self.ui.macro_list.addItem(macro["name"])

    def save_macros_to_storage(self):
        settings = QtCore.QSettings("Open Source", "FlatCAM_Plus")
        import json
        settings.setValue("cnc_macros", json.dumps(self.macros))

    def on_manage_macros(self):
        dialog = MacroDialog(self.macros, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.macros = dialog.macros
            self.save_macros_to_storage()
            self.load_macros()

    def on_test_connection_clicked(self):
        if self.is_connected:
            self.append_console_sig.emit(_("Already connected."), "info")
            return

        config = self.ui.connection_config()
        message = self.validate_connection_config(config)
        if message:
            self.append_console_sig.emit(message, "error")
            return

        self.ui.set_connection_actions_enabled(False)
        self.append_console_sig.emit(_("Testing connection..."), "info")
        threading.Thread(target=self._test_connection_worker, args=(config,), daemon=True).start()

    def _test_connection_worker(self, config):
        transport = None
        try:
            transport = self.build_transport(config)
            transport.open()
            self.test_connection_sig.emit(True, transport.description())
        except Exception as e:
            log.error("CNC test connection error: %s", e)
            self.test_connection_sig.emit(False, str(e))
        finally:
            if transport:
                try:
                    transport.close()
                except Exception:
                    pass

    def on_test_connection_finished(self, success, message):
        self.ui.set_connection_actions_enabled(True)
        if success:
            text = f"{_('Connection test succeeded')}: {message}"
            self.append_console_sig.emit(text, "info")
            try:
                self.app.inform.emit('[success] %s' % text)
            except Exception:
                pass
        else:
            text = f"{_('Connection test failed')}: {message}"
            self.append_console_sig.emit(text, "error")
            try:
                self.app.inform.emit('[ERROR_NOTCL] %s' % text)
            except Exception:
                pass

    def disconnect(self):
        self.stop_thread.set()
        with self.io_lock:
            transport = self.transport
            self.transport = None
            self.is_connected = False

        if transport:
            try:
                transport.close()
            except Exception:
                pass

        self.is_streaming = False
        self.connection_state_sig.emit(False, "")

    def on_send_command(self):
        command = self.ui.command_entry.text().strip()
        if command:
            self.ui.command_entry.clear()
            self.queue_command(command)

    def queue_command(self, command, log=True):
        self.queue_commands([command], log=log)

    def queue_commands(self, commands, log=True):
        normalized = [cmd.strip() for cmd in commands if str(cmd).strip()]
        if not normalized:
            return
        threading.Thread(target=self._send_commands_worker, args=(normalized, log), daemon=True).start()

    def _send_commands_worker(self, commands, log=True):
        for command in commands:
            self.send_command(command, log=log)

    def send_command(self, command, log=True):
        command = (command or "").strip()
        if not command:
            return []
        if not self.is_connected or not self.transport:
            message = _("Controller is not connected.")
            self.append_console_sig.emit(message, "error")
            try:
                self.app.inform.emit("[WARNING_NOTCL] %s" % message)
            except Exception:
                pass
            return []

        try:
            if log:
                self.append_console_sig.emit(command, "tx")
            with self.io_lock:
                responses = self.transport.send_line(command)
            for line in responses:
                self.handle_line(line, echo=True)
            return responses
        except Exception as e:
            self.append_console_sig.emit(f"{_('Communication error')}: {e}", "error")
            self.disconnect()
            return []

    def send_raw(self, data, label=""):
        if not data:
            return []
        if isinstance(data, str):
            return self.send_command(data)
        if not self.is_connected or not self.transport:
            message = _("Controller is not connected.")
            self.append_console_sig.emit(message, "error")
            try:
                self.app.inform.emit("[WARNING_NOTCL] %s" % message)
            except Exception:
                pass
            return []

        try:
            if label:
                self.append_console_sig.emit(label, "tx")
            with self.io_lock:
                responses = self.transport.send_raw(data)
            for line in responses:
                self.handle_line(line, echo=True)
            return responses
        except Exception as e:
            self.append_console_sig.emit(f"{_('Communication error')}: {e}", "error")
            self.disconnect()
            return []

    def send_profile_command(self, key, log=True):
        command = self.current_profile().get(key, "")
        if not command:
            self.append_console_sig.emit(f"{key}: {_('not supported by selected profile')}", "warn")
            return

        if isinstance(command, bytes):
            self.send_raw(command, label=key.upper() if log else "")
            return

        self.queue_commands(str(command).splitlines(), log=log)

    def send_zero(self, axis):
        command = self.current_profile().get("zero_axis", "").format(axis=axis)
        self.queue_command(command)

    def send_jog(self, axis, direction):
        try:
            step = float(self.ui.get_jog_step())
            feed = int(self.ui.jog_feed.value())
        except Exception:
            step = 1.0
            feed = 1000

        template = self.current_profile().get("jog", "")
        distance = step * direction
        command = template.format(axis=axis, distance=distance, feed=feed)
        self.queue_commands(command.splitlines())

    def on_set_spindle_rpm(self):
        try:
            rpm = int(self.ui.spindle_rpm.value())
        except Exception:
            rpm = 0

        template = self.current_profile().get("spindle_set", "")
        if not template:
            self.append_console_sig.emit(f"spindle_set: {_('not supported by selected profile')}", "warn")
            return

        command = template.format(rpm=rpm)
        self.queue_commands(command.splitlines())

    def on_set_override(self, key, widget):
        try:
            percent = int(widget.value())
        except Exception:
            percent = 100

        template = self.current_profile().get(key, "")
        if not template:
            self.append_console_sig.emit(f"{key}: {_('not supported by selected profile')}", "warn")
            return

        command = template.format(percent=percent)
        self.queue_commands(command.splitlines())

    def on_toggle_laser(self):
        if self.ui.macro_laser.isChecked():
            self.send_profile_command("laser_on")
            self.ui.macro_laser.setText("LASER OFF")
        else:
            self.send_profile_command("laser_off")
            self.ui.macro_laser.setText("LASER ON")

    def on_info_clicked(self):
        if isinstance(self.transport, HttpTransport):
            self.queue_command(self.current_profile().get("web_info", "[ESP800]"))
        else:
            self.send_profile_command("info")

    def on_sd_list(self):
        self.clear_sd_files_sig.emit()
        self.sd_collecting = False
        self.send_profile_command("sd_list")

    def on_run_sd(self):
        filename = self.ui.sd_combo.currentText().strip()
        if not filename:
            return
        command = self.current_profile().get("sd_run", "")
        if not command:
            self.append_console_sig.emit(_("SD run is not supported by selected profile."), "warn")
            return
        self.queue_commands(command.format(file=filename).splitlines())

    def receive_loop(self):
        while not self.stop_thread.is_set():
            try:
                if self.transport:
                    for line in self.transport.read_lines():
                        self.handle_line(line, echo=True)
            except Exception as e:
                if self.is_connected:
                    self.append_console_sig.emit(f"{_('Read error')}: {e}", "error")
                    self.disconnect()
                break

            if self.is_connected and self.status_poll_enabled:
                now = time.time()
                if now - self.last_status_query >= self.status_interval:
                    self.poll_status()
                    self.last_status_query = now

            time.sleep(0.02)

    def poll_status(self):
        profile = self.current_profile()
        raw = profile.get("status_raw")
        command = profile.get("status", "")
        if not raw and not command:
            return

        try:
            with self.io_lock:
                if raw and not isinstance(self.transport, HttpTransport):
                    responses = self.transport.send_raw(raw)
                else:
                    responses = self.transport.send_line(command)
            for line in responses:
                self.handle_line(line, echo=False)
        except Exception:
            pass

    def handle_line(self, line, echo=True):
        line = (line or "").strip()
        if not line:
            return

        lower = line.lower()

        if lower == "ok" or lower.startswith("error"):
            self.ok_received.set()

        if line.startswith("<") and line.endswith(">"):
            self.parse_status(line)
            if echo and not self.hide_status_reports:
                self.append_console_sig.emit(line, "rx")
            return

        if self.parse_marlin_position(line):
            if echo:
                self.append_console_sig.emit(line, "rx")
            return

        if line.startswith("FW version") or "# FW target" in line or "[ESP800]" in line:
            self.parse_controller_info(line)

        self.parse_sd_listing(line)

        if echo:
            stream_type = "error" if lower.startswith("error") or "alarm" in lower else "rx"
            self.append_console_sig.emit(line, stream_type)

    def parse_status(self, line):
        parts = line[1:-1].split("|")
        if not parts:
            return

        data = {"state": parts[0]}
        for part in parts[1:]:
            if ":" in part:
                key, value = part.split(":", 1)
                data[key] = value
        self.update_status_sig.emit(data)

    def parse_marlin_position(self, line):
        if not ("X:" in line and "Y:" in line and "Z:" in line):
            return False

        matches = dict(re.findall(r"([XYZ]):\s*(-?\d+(?:\.\d+)?)", line))
        if not matches:
            return False

        self.update_status_sig.emit({
            "state": "Idle",
            "WPos": "{},{},{}".format(matches.get("X", "0"), matches.get("Y", "0"), matches.get("Z", "0"))
        })
        return True

    def parse_sd_listing(self, line):
        lower = line.lower().strip()
        if lower == "begin file list":
            self.clear_sd_files_sig.emit()
            self.sd_collecting = True
            return
        if lower == "end file list":
            self.sd_collecting = False
            return

        if line.startswith("[FILE:"):
            filename = line.split("|", 1)[0].split(":", 1)[1].strip("]")
            self.sd_file_sig.emit(filename)
            return

        if self.sd_collecting and line and not lower.startswith(("ok", "echo:")):
            filename = line.split()[0]
            self.sd_file_sig.emit(filename)

    def parse_controller_info(self, text):
        info = {}
        cleaned = text.replace("\r", "\n")
        for chunk in cleaned.replace("\n", "#").split("#"):
            if ":" not in chunk:
                continue
            key, value = chunk.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key:
                info[key] = value

        if info:
            self.controller_info_sig.emit(info)

    def update_status_display(self, data):
        state = data.get("state", "Idle")
        self.ui.state_label.setText(state.upper())
        self.update_toolbar_connection_status(True, self.ui.connection_desc.text(), state=state)

        colors = {
            "Idle": "#5cb85c",
            "Run": "#337ab7",
            "Jog": "#31b0d5",
            "Hold": "#f0ad4e",
            "Home": "#5bc0de",
            "Alarm": "#d9534f",
            "Door": "#d9534f",
            "Check": "#777777",
            "Sleep": "#777777",
        }
        self.ui.state_indicator.setStyleSheet(
            f"background-color: {colors.get(state, '#999999')}; border-radius: 6px;"
        )

        if "WPos" in data:
            coords = (data["WPos"].split(",") + ["0.000", "0.000", "0.000"])[:3]
            self.ui.x_val.setText(coords[0])
            self.ui.y_val.setText(coords[1])
            self.ui.z_val.setText(coords[2])
        elif "MPos" in data and "WCO" in data:
            # Calculate WPos from MPos and WCO if WPos is not directly provided
            m_coords = [float(x) for x in (data["MPos"].split(",") + ["0", "0", "0"])[:3]]
            wco = [float(x) for x in (data["WCO"].split(",") + ["0", "0", "0"])[:3]]
            self.ui.x_val.setText(f"{m_coords[0] - wco[0]:.3f}")
            self.ui.y_val.setText(f"{m_coords[1] - wco[1]:.3f}")
            self.ui.z_val.setText(f"{m_coords[2] - wco[2]:.3f}")

        if "MPos" in data:
            coords = (data["MPos"].split(",") + ["0.000", "0.000", "0.000"])[:3]
            self.ui.mx_val.setText(coords[0])
            self.ui.my_val.setText(coords[1])
            self.ui.mz_val.setText(coords[2])

        if "FS" in data:
            values = (data["FS"].split(",") + ["0", "0"])[:2]
            self.ui.feed_value.setText(values[0])
            self.ui.spindle_value.setText(values[1])
            try:
                feed = float(values[0])
            except ValueError:
                feed = 0.0
            try:
                spindle = float(values[1])
            except ValueError:
                spindle = 0.0
            self.ui.update_dashboard_gauges(feed, spindle)

        if "Ov" in data:
            values = (data["Ov"].split(",") + ["100", "100", "100"])[:3]
            self.ui.feed_override_value.setText(values[0] + "%")
            self.ui.rapid_override_value.setText(values[1] + "%")
            self.ui.spindle_override_value.setText(values[2] + "%")

    def on_stream_start(self):
        if not self.is_connected:
            self.append_console_sig.emit(_("Controller is not connected."), "error")
            return

        obj = self.app.collection.get_by_name(self.ui.object_combo.currentText())
        if not obj:
            self.append_console_sig.emit(_("No CNCJob object selected."), "error")
            return

        source = getattr(obj, "source_file", "")
        self.gcode_lines = [line.strip() for line in source.splitlines() if line.strip()]
        if not self.gcode_lines:
            self.append_console_sig.emit(_("Selected CNCJob has no G-code."), "error")
            return

        self.current_line_idx = 0
        self.is_streaming = True
        self.streaming_paused = False
        self.ui.pause_btn.setText("PAUSE")
        threading.Thread(target=self.stream_worker, daemon=True).start()

    def on_stream_pause(self):
        if not self.is_streaming:
            return
        self.streaming_paused = not self.streaming_paused
        if self.streaming_paused:
            self.send_profile_command("hold")
            self.ui.pause_btn.setText("RESUME")
        else:
            self.send_profile_command("resume")
            self.ui.pause_btn.setText("PAUSE")

    def on_stream_stop(self):
        self.is_streaming = False
        self.streaming_paused = False
        self.ui.pause_btn.setText("PAUSE")

    def stream_worker(self):
        total = len(self.gcode_lines)
        while self.is_streaming and self.current_line_idx < total:
            if self.streaming_paused:
                time.sleep(0.1)
                continue

            command = self.gcode_lines[self.current_line_idx]
            self.ok_received.clear()
            self.send_command(command, log=True)
            self.ok_received.wait(timeout=5.0)
            self.current_line_idx += 1
            self.update_progress_sig.emit(self.current_line_idx / total * 100.0, command)

        self.is_streaming = False
        self.update_progress_sig.emit(100.0 if total else 0.0, _("Done"))

    def update_progress_ui(self, percent, _text):
        self.ui.progress.setValue(int(percent))

    def http_transport(self):
        if isinstance(self.transport, HttpTransport):
            return self.transport
        return None

    def on_refresh_files(self):
        if not self.is_connected:
            return

        transport = self.http_transport()
        if transport:
            endpoint = self.ui.files_fs_combo.currentData()
            path = self.ui.current_path
            self.busy_sig.emit(True, _("Refreshing files..."))
            threading.Thread(target=self._refresh_files_worker, args=(transport, endpoint, path), daemon=True).start()
        else:
            # Fallback to Serial/TCP SD List command
            self.on_sd_list()

    def _refresh_files_worker(self, transport, endpoint, path):
        try:
            data = transport.list_files(endpoint, path)
            if "path" not in data:
                data["path"] = path
            self.files_update_sig.emit(data)
        except Exception as e:
            self.append_console_sig.emit(f"{_('File list failed')}: {e}", "error")
        finally:
            self.busy_sig.emit(False, "")

    def on_upload_files(self):
        transport = self.http_transport()
        if not transport:
            return

        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            _("Upload files"),
            "",
            _("All Files") + " (*)"
        )
        if not files:
            return

        endpoint = self.ui.files_fs_combo.currentData()
        path = self.ui.current_path
        self.busy_sig.emit(True, _("Uploading files..."))
        threading.Thread(target=self._upload_files_worker, args=(transport, endpoint, path, files), daemon=True).start()

    def _upload_files_worker(self, transport, endpoint, path, files):
        try:
            data = transport.upload_files(endpoint, path, files)
            self.files_update_sig.emit(data)
            self.append_console_sig.emit(_("Upload finished."), "info")
        except Exception as e:
            self.append_console_sig.emit(f"{_('Upload failed')}: {e}", "error")
        finally:
            self.busy_sig.emit(False, "")

    def on_create_dir(self):
        transport = self.http_transport()
        if not transport:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, _("Create directory"), _("Directory name:"))
        if not ok or not name.strip():
            return
        self._file_action("createdir", name.strip())

    def on_delete_file(self):
        item = self.ui.selected_file_item()
        if not item:
            return

        action = "deletedir" if item.get("is_dir") else "delete"
        answer = QtWidgets.QMessageBox.question(
            self,
            _("Confirm deletion"),
            "%s: %s" % (_("Delete"), item["name"])
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self._file_action(action, item["name"])

    def _file_action(self, action, filename):
        transport = self.http_transport()
        if not transport:
            return
        endpoint = self.ui.files_fs_combo.currentData()
        path = self.ui.current_path
        self.busy_sig.emit(True, _("Updating files..."))
        threading.Thread(
            target=self._file_action_worker,
            args=(transport, endpoint, path, action, filename),
            daemon=True
        ).start()

    def _file_action_worker(self, transport, endpoint, path, action, filename):
        try:
            data = transport.list_files(endpoint, path, action=action, filename=filename)
            self.files_update_sig.emit(data)
        except Exception as e:
            self.append_console_sig.emit(f"{_('File action failed')}: {e}", "error")
        finally:
            self.busy_sig.emit(False, "")

    def on_files_up(self):
        path = self.ui.current_path.rstrip("/")
        if not path:
            self.ui.current_path = "/"
        else:
            parent = path.rsplit("/", 1)[0]
            self.ui.current_path = (parent + "/") if parent else "/"
        self.on_refresh_files()

    def on_files_root(self):
        self.ui.current_path = "/"
        self.on_refresh_files()

    def on_filesystem_changed(self):
        self.ui.current_path = "/"
        if self.is_connected and isinstance(self.transport, HttpTransport):
            self.on_refresh_files()

    def on_file_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data.get("is_dir"):
            self.ui.current_path = self.ui.current_path.rstrip("/") + "/" + data["name"] + "/"
            self.on_refresh_files()
