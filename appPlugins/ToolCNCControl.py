# ##########################################################
# FlatCAM Plus: 2D Post-processing for Manufacturing        #
# File by:  Antigravity (AI)                               #
# Date:     05/01/2026                                     #
# License:  MIT Licence                                    #
# ##########################################################

from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt, pyqtSignal

from appTool import AppTool
from appGUI.GUIElements import (
    VerticalScrollArea, FCLabel, FCComboBox,
    FCSpinner, FCEntry, FCTable
)

import builtins
import gettext
import html
import http.cookiejar
import logging
import os
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import uuid

import serial
import serial.tools.list_ports

import appTranslation as fcTranslate

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


CNC_PROFILES = {
    "fluidnc": {
        "label": "FluidNC / GRBL",
        "info": "$I",
        "web_info": "[ESP800]",
        "config": "$Config/Dump",
        "home": "$H",
        "unlock": "$X",
        "reset": b"\x18",
        "hold": b"!",
        "resume": b"~",
        "status": "?",
        "status_raw": b"?",
        "zero_axis": "G10 L20 P1 {axis}0",
        "zero_all": "G10 L20 P1 X0 Y0 Z0",
        "jog": "$J=G91 G21 {axis}{distance:.4f} F{feed}",
        "sd_list": "$SD/List",
        "sd_run": "$SD/Run={file}",
        "feed_plus": b"\x91",
        "feed_minus": b"\x92",
        "feed_reset": b"\x90",
        "spindle_plus": b"\x9a",
        "spindle_minus": b"\x9b",
        "spindle_reset": b"\x99",
        "probe_z": "G38.2 Z-50 F100",
        "laser_on": "M3 S100",
        "laser_off": "M5",
    },
    "grbl": {
        "label": "GRBL",
        "info": "$I",
        "config": "$$",
        "home": "$H",
        "unlock": "$X",
        "reset": b"\x18",
        "hold": b"!",
        "resume": b"~",
        "status": "?",
        "status_raw": b"?",
        "zero_axis": "G10 L20 P1 {axis}0",
        "zero_all": "G10 L20 P1 X0 Y0 Z0",
        "jog": "$J=G91 G21 {axis}{distance:.4f} F{feed}",
        "sd_list": "$SD/List",
        "sd_run": "$SD/Run={file}",
        "feed_plus": b"\x91",
        "feed_minus": b"\x92",
        "feed_reset": b"\x90",
        "spindle_plus": b"\x9a",
        "spindle_minus": b"\x9b",
        "spindle_reset": b"\x99",
        "probe_z": "G38.2 Z-50 F100",
        "laser_on": "M3 S100",
        "laser_off": "M5",
    },
    "marlin": {
        "label": "Marlin",
        "info": "M115",
        "config": "M503",
        "home": "G28",
        "unlock": "M999",
        "reset": "M999",
        "hold": "M0",
        "resume": "M24",
        "status": "M114",
        "zero_axis": "G92 {axis}0",
        "zero_all": "G92 X0 Y0 Z0",
        "jog": "G91\nG0 {axis}{distance:.4f} F{feed}\nG90",
        "sd_list": "M20",
        "sd_run": "M23 {file}\nM24",
        "feed_plus": "M220 S110",
        "feed_minus": "M220 S90",
        "feed_reset": "M220 S100",
        "probe_z": "G30",
        "laser_on": "M3 S100",
        "laser_off": "M5",
    },
    "smoothie": {
        "label": "Smoothieware",
        "info": "version",
        "config": "config-get sd",
        "home": "G28",
        "unlock": "M999",
        "reset": b"\x18",
        "hold": "M600",
        "resume": "M601",
        "status": "?",
        "status_raw": b"?",
        "zero_axis": "G92 {axis}0",
        "zero_all": "G92 X0 Y0 Z0",
        "jog": "G91\nG0 {axis}{distance:.4f} F{feed}\nG90",
        "probe_z": "G30",
        "laser_on": "M3 S100",
        "laser_off": "M5",
    },
    "generic": {
        "label": "Generic G-code",
        "info": "",
        "config": "",
        "home": "G28",
        "unlock": "",
        "reset": "",
        "hold": "M0",
        "resume": "",
        "status": "",
        "zero_axis": "G92 {axis}0",
        "zero_all": "G92 X0 Y0 Z0",
        "jog": "G91\nG0 {axis}{distance:.4f} F{feed}\nG90",
        "probe_z": "G30",
        "laser_on": "M3 S100",
        "laser_off": "M5",
    },
}


class FluidStyleButton(QtWidgets.QToolButton):
    def __init__(self, text="", color="#31b0d5", hover="#269abc", text_color="white", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QtCore.QSize(18, 18))
        self.setMinimumHeight(28)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)


class SerialTransport:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.handle = None

    def open(self):
        self.handle = serial.serial_for_url(
            self.port,
            self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.08,
            write_timeout=1.0,
            xonxoff=False,
            rtscts=False
        )
        try:
            self.handle.reset_input_buffer()
        except Exception:
            pass

    def close(self):
        if self.handle:
            try:
                self.handle.close()
            except Exception:
                pass
        self.handle = None

    def description(self):
        return f"{self.port} @ {self.baudrate}"

    def send_line(self, text):
        if not self.handle:
            raise ConnectionError("Serial port is closed")
        self.handle.write((text.rstrip() + "\n").encode("utf-8", errors="ignore"))
        return []

    def send_raw(self, data):
        if not self.handle:
            raise ConnectionError("Serial port is closed")
        self.handle.write(data)
        return []

    def read_lines(self):
        if not self.handle:
            return []

        lines = []
        while self.handle and self.handle.in_waiting:
            raw = self.handle.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                lines.append(line)
        return lines


class TcpTransport:
    IAC = 255
    DO = 253
    DONT = 254
    WILL = 251
    WONT = 252

    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        self.sock = None
        self.buffer = b""

    def open(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=4.0)
        self.sock.settimeout(0.06)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    def description(self):
        return f"{self.host}:{self.port}"

    def send_line(self, text):
        if not self.sock:
            raise ConnectionError("TCP socket is closed")
        self.sock.sendall((text.rstrip() + "\n").encode("utf-8", errors="ignore"))
        return []

    def send_raw(self, data):
        if not self.sock:
            raise ConnectionError("TCP socket is closed")
        self.sock.sendall(data)
        return []

    def _strip_telnet(self, data):
        clean = bytearray()
        reply = bytearray()
        i = 0

        while i < len(data):
            byte = data[i]
            if byte == self.IAC and i + 2 < len(data):
                cmd = data[i + 1]
                opt = data[i + 2]
                if cmd == self.DO:
                    reply.extend([self.IAC, self.WONT, opt])
                elif cmd == self.WILL:
                    reply.extend([self.IAC, self.DONT, opt])
                i += 3
                continue
            clean.append(byte)
            i += 1

        if reply and self.sock:
            try:
                self.sock.sendall(bytes(reply))
            except Exception:
                pass
        return bytes(clean)

    def read_lines(self):
        if not self.sock:
            return []

        while True:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                raise ConnectionError("TCP socket closed by remote host")
            self.buffer += self._strip_telnet(chunk)

        if b"\n" not in self.buffer:
            return []

        raw_lines = self.buffer.splitlines(keepends=True)
        if raw_lines and not raw_lines[-1].endswith((b"\n", b"\r")):
            self.buffer = raw_lines.pop()
        else:
            self.buffer = b""

        lines = []
        for raw in raw_lines:
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                lines.append(line)
        return lines


class HttpTransport:
    def __init__(self, base_url, user="", password=""):
        self.base_url = self._normalize_base_url(base_url)
        self.user = user
        self.password = password
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.info_text = ""

    @staticmethod
    def _normalize_base_url(url):
        url = (url or "").strip()
        if not url:
            url = "http://fluidnc.local"
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        return url.rstrip("/")

    def open(self):
        if self.user or self.password:
            login_query = urllib.parse.urlencode({
                "USER": self.user,
                "PASSWORD": self.password,
                "SUBMIT": "yes"
            })
            self._request_text(f"/login?{login_query}")
        self.info_text = self.send_command_text("[ESP800]")

    def close(self):
        self.cookie_jar.clear()

    def description(self):
        return self.base_url

    def _url(self, path):
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _request_text(self, path, data=None, headers=None, timeout=8.0):
        req = urllib.request.Request(self._url(path), data=data, headers=headers or {})
        with self.opener.open(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")

    def send_command_text(self, text):
        upper = text.strip().upper()
        param = "commandText" if upper.startswith("[ESP") or upper.startswith("$/") else "plain"
        query = urllib.parse.urlencode({param: text})
        return self._request_text(f"/command?{query}")

    def send_line(self, text):
        return self._split_response(self.send_command_text(text))

    def send_raw(self, data):
        query = urllib.parse.quote_from_bytes(data)
        return self._split_response(self._request_text(f"/command?plain={query}"))

    def read_lines(self):
        return []

    @staticmethod
    def _split_response(response):
        lines = []
        for line in response.replace("\r", "\n").split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        return lines

    def list_files(self, endpoint, path="/", action="list", filename="all"):
        query = urllib.parse.urlencode({
            "action": action,
            "filename": filename,
            "path": path or "/"
        })
        response = self._request_text(f"{endpoint}?{query}")
        return self._json_response(response)

    def upload_files(self, endpoint, path, files):
        boundary = "----FlatCAMFluidNC" + uuid.uuid4().hex
        fields = [("path", path or "/")]
        file_fields = []

        for file_path in files:
            filename = os.path.basename(file_path)
            remote_name = (path or "/").rstrip("/") + "/" + filename
            size_arg = f"{(path or '/').rstrip('/')}/{filename}S"
            with open(file_path, "rb") as f:
                payload = f.read()
            fields.append((size_arg, str(len(payload))))
            file_fields.append(("myfiles[]", remote_name, "application/octet-stream", payload))

        response = self._multipart_post(endpoint, fields, file_fields, boundary)
        return self._json_response(response)

    def _multipart_post(self, endpoint, fields, files, boundary, timeout=60.0):
        body = bytearray()

        for name, value in fields:
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")

        for name, filename, content_type, payload in files:
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
            body.extend(payload)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("ascii"))
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._request_text(endpoint, data=bytes(body), headers=headers, timeout=timeout)

    @staticmethod
    def _json_response(response):
        import json

        try:
            return json.loads(response)
        except Exception:
            return {"status": response.strip() or "OK", "files": []}


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
        self.receiver_thread = None
        self.io_lock = threading.RLock()
        self.ok_received = threading.Event()
        self.last_status_query = 0
        self.status_interval = 0.5
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

    def connect_signals_at_init(self):
        self.ui.connect_btn.clicked.connect(self.on_connect_clicked)
        self.ui.test_connection_btn.clicked.connect(self.on_test_connection_clicked)
        self.ui.disconnect_btn.clicked.connect(self.disconnect)
        self.ui.open_connection_btn.clicked.connect(self.on_toolbar_connection_clicked)
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
        self.ui.spindle_plus.clicked.connect(lambda: self.send_profile_command("spindle_plus"))
        self.ui.spindle_minus.clicked.connect(lambda: self.send_profile_command("spindle_minus"))
        self.ui.spindle_reset.clicked.connect(lambda: self.send_profile_command("spindle_reset"))

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
            if isinstance(self.transport, HttpTransport):
                self.on_refresh_files()
        else:
            self.ui.connection_desc.setText(_("Offline"))
            self.append_console_sig.emit(_("Disconnected"), "info")
        self.ui.sync_connection_dialog(connected)

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
            coords = (data["WPos"].split(",") + ["0", "0", "0"])[:3]
            self.ui.x_val.setText(coords[0])
            self.ui.y_val.setText(coords[1])
            self.ui.z_val.setText(coords[2])

        if "MPos" in data:
            coords = (data["MPos"].split(",") + ["0", "0", "0"])[:3]
            self.ui.mx_val.setText(coords[0])
            self.ui.my_val.setText(coords[1])
            self.ui.mz_val.setText(coords[2])

        if "FS" in data:
            values = (data["FS"].split(",") + ["0", "0"])[:2]
            self.ui.feed_value.setText(values[0])
            self.ui.spindle_value.setText(values[1])

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
        message = _("File tools require a FluidNC Web connection.")
        self.append_console_sig.emit(message, "warn")
        self.ui.file_status.setText(message)
        try:
            self.app.inform.emit("[WARNING_NOTCL] %s" % message)
        except Exception:
            pass
        return None

    def on_refresh_files(self):
        transport = self.http_transport()
        if not transport:
            return
        endpoint = self.ui.files_fs_combo.currentData()
        path = self.ui.current_path
        self.busy_sig.emit(True, _("Refreshing files..."))
        threading.Thread(target=self._refresh_files_worker, args=(transport, endpoint, path), daemon=True).start()

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


class CNCControlUI:
    pluginName = _("CNC Settings")

    def __init__(self, layout, app):
        self.app = app
        self.layout = layout
        self.current_path = "/"
        self.primary = "#31b0d5"
        self.primary_dark = "#269abc"

        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.container = QtWidgets.QWidget()
        self.container.setObjectName("cnc_root")
        self.container.setStyleSheet(self.stylesheet())
        self.layout.addWidget(self.container)

        self.main_lay = QtWidgets.QVBoxLayout(self.container)
        self.main_lay.setContentsMargins(8, 8, 8, 8)
        self.main_lay.setSpacing(8)

        self.build_connection_dialog()
        self.build_work_header()
        self.build_tabs()
        self.on_connection_mode_changed()

    def stylesheet(self):
        palette = QtWidgets.QApplication.palette()
        window = palette.color(QtGui.QPalette.ColorRole.Window).name()
        base = palette.color(QtGui.QPalette.ColorRole.Base).name()
        button = palette.color(QtGui.QPalette.ColorRole.Button).name()
        text = palette.color(QtGui.QPalette.ColorRole.WindowText).name()
        mid = palette.color(QtGui.QPalette.ColorRole.Mid).name()
        highlight = palette.color(QtGui.QPalette.ColorRole.Highlight).name()
        hover = palette.color(QtGui.QPalette.ColorRole.AlternateBase).name()
        selected = palette.color(QtGui.QPalette.ColorRole.Highlight).lighter(175).name()

        return f"""
            QWidget#cnc_root {{
                background: transparent;
            }}
            QGroupBox#cnc_panel {{
                background: {window};
                border: 1px solid {mid};
                border-radius: 6px;
                margin-top: 13px;
                padding: 9px 8px 8px 8px;
                font-weight: 600;
            }}
            QGroupBox#cnc_panel::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 5px;
                color: {text};
            }}
            QFrame#cnc_strip {{
                background: {hover};
                border: 1px solid {mid};
                border-radius: 5px;
            }}
            QFrame#cnc_field_cell {{
                background: {base};
                border: 1px solid {mid};
                border-radius: 5px;
            }}
            QFrame#cnc_dro_row {{
                background: {base};
                border: 1px solid {mid};
                border-radius: 5px;
            }}
            QFrame#cnc_segment {{
                background: {base};
                border: 1px solid {mid};
                border-radius: 5px;
            }}
            QFrame#cnc_jog_pad {{
                background: {base};
                border: 1px solid {mid};
                border-radius: 6px;
            }}
            QFrame#cnc_status_pill {{
                background: {base};
                border: 1px solid {mid};
                border-radius: 5px;
            }}
            QFrame#cnc_button_help_pair {{
                background: transparent;
                border: 0;
            }}
            QLabel#cnc_field_label {{
                font-weight: 600;
                padding-right: 4px;
            }}
            QLabel#cnc_axis_label {{
                font-weight: 700;
                font-size: 12pt;
                min-width: 24px;
            }}
            QLabel#cnc_jog_group_label {{
                font-weight: 700;
                padding: 3px 0;
            }}
            QLabel#cnc_jog_center {{
                color: {mid};
                font-weight: 700;
                min-width: 44px;
            }}
            QLabel#cnc_hint_label {{
                color: {mid};
                font-weight: 600;
            }}
            QToolButton#cnc_button {{
                background: {button};
                color: {text};
                border: 1px solid {mid};
                border-radius: 4px;
                padding: 5px 8px;
                font-weight: 600;
                min-height: 24px;
            }}
            QToolButton#cnc_button:hover {{
                background: {hover};
                border-color: {highlight};
            }}
            QToolButton#cnc_button:pressed,
            QToolButton#cnc_button:checked {{
                background: {selected};
                border-color: {highlight};
            }}
            QToolButton#cnc_button:disabled {{
                color: {mid};
            }}
            QToolButton#cnc_segment_button {{
                background: transparent;
                color: {text};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: 700;
                min-width: 42px;
            }}
            QToolButton#cnc_segment_button:hover {{
                background: {hover};
            }}
            QToolButton#cnc_segment_button:checked {{
                background: {selected};
                border: 1px solid {highlight};
            }}
            QToolButton#cnc_axis_button {{
                background: {button};
                color: {text};
                border: 1px solid {mid};
                border-radius: 4px;
                padding: 5px 8px;
                min-width: 62px;
                min-height: 38px;
                font-weight: 700;
            }}
            QToolButton#cnc_axis_button:hover {{
                background: {hover};
                border-color: {highlight};
            }}
            QToolButton#cnc_axis_button:pressed,
            QToolButton#cnc_axis_button:checked {{
                background: {selected};
                border-color: {highlight};
            }}
            QToolButton#cnc_help_button {{
                background: {button};
                color: {text};
                border: 1px solid {mid};
                border-radius: 4px;
                padding: 4px;
                min-width: 24px;
                min-height: 24px;
            }}
            QToolButton#cnc_help_button:hover {{
                background: {hover};
                border-color: {highlight};
            }}
            QComboBox#cnc_input,
            QLineEdit#cnc_input,
            QSpinBox#cnc_input {{
                background: {base};
                color: {text};
                border: 1px solid {mid};
                border-radius: 4px;
                padding: 3px 6px;
                min-height: 28px;
            }}
            QComboBox#cnc_input:focus,
            QLineEdit#cnc_input:focus,
            QSpinBox#cnc_input:focus {{
                border-color: {highlight};
            }}
            QComboBox#cnc_input::drop-down {{
                border-left: 1px solid {mid};
                width: 24px;
            }}
            QProgressBar#cnc_progress {{
                border: 1px solid {mid};
                border-radius: 4px;
                background: {base};
                text-align: center;
                min-height: 18px;
            }}
            QProgressBar#cnc_progress::chunk {{
                background: {highlight};
                border-radius: 3px;
            }}
            QTextEdit#cnc_console {{
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid {mid};
                border-radius: 5px;
                padding: 6px;
                font-family: Consolas, monospace;
            }}
        """

    def icon(self, filename):
        return QtGui.QIcon(os.path.join(self.app.resource_location, filename))

    def setup_button(self, button, icon_file=None, tooltip=None, text_beside=True):
        button.setObjectName("cnc_button")
        button.setAutoRaise(False)
        if icon_file:
            button.setIcon(self.icon(icon_file))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if text_beside else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        if tooltip:
            button.setToolTip(tooltip)
        return button

    def setup_input(self, widget):
        widget.setObjectName("cnc_input")
        return widget

    def field_label(self, text):
        label = FCLabel(text)
        label.setObjectName("cnc_field_label")
        return label

    def field_cell(self, label_text, widget):
        frame = QtWidgets.QFrame()
        frame.setObjectName("cnc_field_cell")
        lay = QtWidgets.QVBoxLayout(frame)
        lay.setContentsMargins(6, 4, 6, 6)
        lay.setSpacing(3)
        lay.addWidget(self.field_label(label_text))
        lay.addWidget(widget)
        return frame

    def help_button(self, tooltip):
        button = QtWidgets.QToolButton()
        button.setObjectName("cnc_help_button")
        button.setAutoRaise(False)
        button.setIcon(self.icon("help.png"))
        button.setIconSize(QtCore.QSize(14, 14))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def action_with_help(self, button, tooltip):
        frame = QtWidgets.QFrame()
        frame.setObjectName("cnc_button_help_pair")
        lay = QtWidgets.QHBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        lay.addWidget(button, 1)
        lay.addWidget(self.help_button(tooltip))
        return frame

    def build_work_header(self):
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.main_lay.addLayout(header)

        connection_panel = self.build_connection_panel()
        connection_panel.setMinimumWidth(260)
        connection_panel.setMaximumWidth(340)
        connection_panel.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)
        header.addWidget(connection_panel, 0, Qt.AlignmentFlag.AlignTop)

        job_col = QtWidgets.QVBoxLayout()
        job_col.setContentsMargins(0, 0, 0, 0)
        job_col.setSpacing(8)
        header.addLayout(job_col, 1)

        direct_panel, direct_body = self.create_panel(_("Direct G-code Send"))
        self.build_direct_job(direct_body)
        job_col.addWidget(direct_panel)

        sd_panel, sd_body = self.create_panel(_("Optional SD Job"))
        self.build_sd_job(sd_body)
        job_col.addWidget(sd_panel)
        job_col.addStretch()

    def build_connection_dialog(self):
        self.connection_dialog = QtWidgets.QDialog(self.app.ui)
        self.connection_dialog.setWindowTitle(_("Connection"))
        self.connection_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.connection_dialog.setMinimumWidth(520)
        self.connection_dialog.setStyleSheet(self.stylesheet())

        dialog_lay = QtWidgets.QVBoxLayout(self.connection_dialog)
        dialog_lay.setContentsMargins(10, 10, 10, 10)
        dialog_lay.setSpacing(8)

        self.dialog_status_frame = QtWidgets.QFrame()
        self.dialog_status_frame.setObjectName("cnc_strip")
        dialog_status_lay = QtWidgets.QVBoxLayout(self.dialog_status_frame)
        dialog_status_lay.setContentsMargins(8, 6, 8, 6)
        dialog_status_lay.setSpacing(3)

        self.dialog_state_label = FCLabel(_("Connect"), bold=True)
        self.dialog_connection_desc = FCLabel("", color="#777777")
        dialog_status_lay.addWidget(self.dialog_state_label)
        dialog_status_lay.addWidget(self.dialog_connection_desc)
        dialog_lay.addWidget(self.dialog_status_frame)

        self.connection_fields_widget = QtWidgets.QWidget()
        fields_lay = QtWidgets.QVBoxLayout(self.connection_fields_widget)
        fields_lay.setContentsMargins(0, 0, 0, 0)
        fields_lay.setSpacing(8)

        self.connection_mode_combo = FCComboBox()
        self.setup_input(self.connection_mode_combo)
        self.connection_mode_combo.setMinimumWidth(185)
        self.connection_mode_combo.addItem(_("COM / USB"), "serial")
        self.connection_mode_combo.addItem(_("WiFi TCP/Telnet"), "tcp")
        self.connection_mode_combo.addItem(_("FluidNC Web"), "http")

        self.profile_combo = FCComboBox()
        self.setup_input(self.profile_combo)
        self.profile_combo.setMinimumWidth(185)
        for key, profile in CNC_PROFILES.items():
            self.profile_combo.addItem(profile["label"], key)

        selector_lay = QtWidgets.QGridLayout()
        selector_lay.setHorizontalSpacing(8)
        selector_lay.setVerticalSpacing(5)
        selector_lay.addWidget(self.field_label(_("Mode")), 0, 0)
        selector_lay.addWidget(self.connection_mode_combo, 0, 1)
        selector_lay.addWidget(self.field_label(_("Controller")), 0, 2)
        selector_lay.addWidget(self.profile_combo, 0, 3)
        selector_lay.setColumnStretch(1, 1)
        selector_lay.setColumnStretch(3, 1)
        fields_lay.addLayout(selector_lay)

        self.connection_stack = QtWidgets.QStackedWidget()
        fields_lay.addWidget(self.connection_stack)
        dialog_lay.addWidget(self.connection_fields_widget)

        self.connect_btn = FluidStyleButton(_("Connect"), "#337ab7", "#286090")
        self.setup_button(self.connect_btn, "link32.png", _("Connect to the CNC controller."))
        self.test_connection_btn = FluidStyleButton(_("Test Connection"), "#5bc0de", "#31b0d5")
        self.setup_button(self.test_connection_btn, "replot16.png", _("Test the selected connection."))
        self.disconnect_btn = FluidStyleButton(_("Disconnect"), "#d9534f", "#c9302c")
        self.setup_button(self.disconnect_btn, "power16.png", _("Disconnect the CNC controller."))
        self.com_refresh = FluidStyleButton(_("Refresh"), "#5bc0de", "#31b0d5")
        self.setup_button(self.com_refresh, "replot16.png", _("Refresh COM ports."))
        self.close_connection_btn = FluidStyleButton(_("Close"), "#777777", "#666666")
        self.setup_button(self.close_connection_btn, None, _("Close this window."))
        self.close_connection_btn.clicked.connect(self.connection_dialog.hide)

        action_lay = QtWidgets.QHBoxLayout()
        action_lay.setSpacing(6)
        action_lay.addWidget(self.com_refresh)
        action_lay.addStretch()
        action_lay.addWidget(self.test_connection_btn)
        action_lay.addWidget(self.connect_btn)
        action_lay.addWidget(self.disconnect_btn)
        action_lay.addWidget(self.close_connection_btn)
        dialog_lay.addLayout(action_lay)

        self.build_serial_connection_page()
        self.build_tcp_connection_page()
        self.build_http_connection_page()

    def build_connection_panel(self):
        panel, body = self.create_panel(_("Connection"))

        self.state_indicator = QtWidgets.QFrame()
        self.state_indicator.setFixedSize(12, 12)
        self.state_indicator.setStyleSheet("background-color: #999999; border-radius: 6px;")
        self.state_label = FCLabel("OFFLINE", bold=True)
        self.connection_desc = FCLabel(_("Offline"), color="#777777")
        self.controller_info_label = FCLabel("", color="#777777")

        self.status_frame = QtWidgets.QFrame()
        self.status_frame.setObjectName("cnc_status_pill")
        status_lay = QtWidgets.QHBoxLayout(self.status_frame)
        status_lay.setContentsMargins(8, 5, 8, 5)
        status_lay.setSpacing(5)
        status_lay.addWidget(self.state_indicator)
        status_lay.addWidget(self.state_label)
        status_lay.addWidget(self.connection_desc)
        status_lay.addWidget(self.controller_info_label, 1)

        self.open_connection_btn = FluidStyleButton(_("Connect"), "#337ab7", "#286090")
        self.setup_button(self.open_connection_btn, "link32.png", _("Open CNC connection."))
        self.open_connection_btn.setMinimumHeight(34)

        body.addWidget(self.status_frame)
        body.addWidget(self.open_connection_btn)

        return panel

    def show_connection_dialog(self, connected=False):
        self.sync_connection_dialog(connected)
        self.connection_dialog.show()
        self.connection_dialog.raise_()
        self.connection_dialog.activateWindow()

    def sync_connection_dialog(self, connected=False):
        description = self.connection_desc.text().strip() if hasattr(self, "connection_desc") else ""
        controller = self.controller_info_label.text().strip() if hasattr(self, "controller_info_label") else ""
        mode = self.connection_mode_combo.currentText()
        profile = self.profile_combo.currentText()

        if connected:
            self.dialog_state_label.setText(_("Connected"))
            info = description or _("Connected")
            details = [info, mode, profile]
            if controller:
                details.append(controller)
            self.dialog_connection_desc.setText(" | ".join(details))
        else:
            self.dialog_state_label.setText(_("Connect"))
            self.dialog_connection_desc.setText("%s | %s" % (mode, profile))

        self.connection_fields_widget.setEnabled(not connected)
        self.connect_btn.setVisible(not connected)
        self.test_connection_btn.setVisible(not connected)
        self.disconnect_btn.setVisible(connected)
        self.com_refresh.setEnabled(not connected and self.connection_mode_combo.currentData() == "serial")
        self.open_connection_btn.setText(_("Connected") if connected else _("Connect"))

    def set_connection_actions_enabled(self, enabled):
        self.connect_btn.setEnabled(enabled)
        self.test_connection_btn.setEnabled(enabled)
        self.disconnect_btn.setEnabled(enabled)
        self.open_connection_btn.setEnabled(enabled)
        self.com_refresh.setEnabled(enabled and self.connection_mode_combo.currentData() == "serial")

    def build_serial_connection_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.com_port = FCComboBox()
        self.setup_input(self.com_port)
        self.com_port.setFixedWidth(360)
        self.com_port.setEditable(True)
        self.baudrate_combo = FCComboBox()
        self.setup_input(self.baudrate_combo)
        self.baudrate_combo.setFixedWidth(360)
        for baud in ["115200", "250000", "230400", "57600", "38400", "19200", "9600"]:
            self.baudrate_combo.addItem(baud)
        self.baudrate_combo.setCurrentText("115200")

        port_lay = QtWidgets.QHBoxLayout()
        port_lay.setSpacing(8)
        port_lay.addWidget(self.field_label(_("Port")))
        port_lay.addWidget(self.com_port)
        port_lay.addStretch()

        baud_lay = QtWidgets.QHBoxLayout()
        baud_lay.setSpacing(8)
        baud_lay.addWidget(self.field_label(_("Baud")))
        baud_lay.addWidget(self.baudrate_combo)
        baud_lay.addStretch()

        lay.addLayout(port_lay)
        lay.addLayout(baud_lay)
        self.connection_stack.addWidget(page)

    def build_tcp_connection_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.tcp_host = FCEntry()
        self.setup_input(self.tcp_host)
        self.tcp_host.setFixedWidth(360)
        self.tcp_host.setPlaceholderText("192.168.0.10")
        self.tcp_host.setText("fluidnc.local")
        self.tcp_port = FCSpinner()
        self.setup_input(self.tcp_port)
        self.tcp_port.setFixedWidth(360)
        self.tcp_port.set_range(1, 65535)
        self.tcp_port.setValue(23)

        host_lay = QtWidgets.QHBoxLayout()
        host_lay.setSpacing(8)
        host_lay.addWidget(self.field_label(_("Host")))
        host_lay.addWidget(self.tcp_host, 1)

        port_lay = QtWidgets.QHBoxLayout()
        port_lay.setSpacing(8)
        port_lay.addWidget(self.field_label(_("Port")))
        port_lay.addWidget(self.tcp_port)
        port_lay.addStretch()

        lay.addLayout(host_lay)
        lay.addLayout(port_lay)
        self.connection_stack.addWidget(page)

    def build_http_connection_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.web_url = FCEntry()
        self.setup_input(self.web_url)
        self.web_url.setFixedWidth(360)
        self.web_url.setText("http://fluidnc.local")
        self.web_user = FCEntry()
        self.setup_input(self.web_user)
        self.web_user.setFixedWidth(360)
        self.web_password = FCEntry()
        self.setup_input(self.web_password)
        self.web_password.setFixedWidth(360)
        self.web_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        url_lay = QtWidgets.QHBoxLayout()
        url_lay.setSpacing(8)
        url_lay.addWidget(self.field_label(_("URL")))
        url_lay.addWidget(self.web_url)
        url_lay.addStretch()

        auth_lay = QtWidgets.QHBoxLayout()
        auth_lay.setSpacing(8)
        auth_lay.addWidget(self.field_label(_("User")))
        auth_lay.addWidget(self.web_user)
        auth_lay.addStretch()

        password_lay = QtWidgets.QHBoxLayout()
        password_lay.setSpacing(8)
        password_lay.addWidget(self.field_label(_("Password")))
        password_lay.addWidget(self.web_password)
        password_lay.addStretch()

        lay.addLayout(url_lay)
        lay.addLayout(auth_lay)
        lay.addLayout(password_lay)
        self.connection_stack.addWidget(page)

    def build_tabs(self):
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.build_control_tab(), _("Control"))
        self.tabs.addTab(self.build_files_tab(), _("Files"))
        self.main_lay.addWidget(self.tabs, 1)

    def build_control_tab(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)
        lay.addLayout(grid)

        dro_panel, dro_body = self.create_panel(_("Position"))
        grid.addWidget(dro_panel, 0, 0)
        self.build_dro(dro_body)

        jog_panel, jog_body = self.create_panel(_("Jog"))
        grid.addWidget(jog_panel, 0, 1)
        self.build_jog(jog_body)

        system_panel, system_body = self.create_panel(_("Overrides & System"))
        grid.addWidget(system_panel, 0, 2)
        self.build_system(system_body)

        terminal_panel, terminal_body = self.create_panel(_("Terminal Console"))
        lay.addWidget(terminal_panel, 1)
        self.build_terminal_console(terminal_body)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        return page

    def build_dro(self, body):
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.addSpacing(34)
        header.addWidget(FCLabel(_("Work"), bold=True), 2)
        header.addWidget(FCLabel(_("Machine"), bold=True), 2)
        header.addWidget(FCLabel(_("Zero"), bold=True), 0)
        body.addLayout(header)

        self.zero_x, self.x_val, self.mx_val = self.add_dro_row(body, "X", "#d9534f")
        self.zero_y, self.y_val, self.my_val = self.add_dro_row(body, "Y", "#5cb85c")
        self.zero_z, self.z_val, self.mz_val = self.add_dro_row(body, "Z", "#337ab7")

        buttons = QtWidgets.QHBoxLayout()
        self.zero_all = FluidStyleButton(_("ZERO ALL"), "#444444", "#222222")
        self.home_btn = FluidStyleButton(_("HOME"), "#337ab7", "#286090")
        self.unlock_btn = FluidStyleButton(_("UNLOCK"), "#f0ad4e", "#ec971f")
        self.setup_button(self.zero_all, "origin16.png", _("Set work position to zero."))
        self.setup_button(self.home_btn, "home16.png", _("Home the machine."))
        self.setup_button(self.unlock_btn, "power16.png", _("Unlock the controller."))
        buttons.addWidget(self.zero_all)
        buttons.addWidget(self.home_btn)
        buttons.addWidget(self.unlock_btn)
        body.addLayout(buttons)

    def add_dro_row(self, body, axis, color):
        row_frame = QtWidgets.QFrame()
        row_frame.setObjectName("cnc_dro_row")
        row_lay = QtWidgets.QHBoxLayout(row_frame)
        row_lay.setContentsMargins(8, 5, 8, 5)
        row_lay.setSpacing(8)

        axis_label = FCLabel(axis, bold=True, size=13, color=color)
        axis_label.setObjectName("cnc_axis_label")
        work = FCLabel("0.000", bold=True, size=20)
        machine = FCLabel("0.000", color="#666666")
        zero = FluidStyleButton(f"{axis}0", "#ffffff", "#f5f5f5", "#333333")
        self.setup_button(zero, "origin16.png", _("Zero this axis."))
        zero.setObjectName("cnc_axis_button")
        zero.setFixedWidth(62)

        work.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        machine.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        work.setStyleSheet("font-family: Consolas, monospace;")
        machine.setStyleSheet("font-family: Consolas, monospace;")

        row_lay.addWidget(axis_label, 0)
        row_lay.addWidget(work, 2)
        row_lay.addWidget(machine, 2)
        row_lay.addWidget(zero, 0)
        body.addWidget(row_frame)
        return zero, work, machine

    def build_jog(self, body):
        settings_frame = QtWidgets.QFrame()
        settings_frame.setObjectName("cnc_strip")
        settings_lay = QtWidgets.QHBoxLayout(settings_frame)
        settings_lay.setContentsMargins(8, 6, 8, 6)
        settings_lay.setSpacing(8)

        step_frame = QtWidgets.QFrame()
        step_frame.setObjectName("cnc_segment")
        step_lay = QtWidgets.QHBoxLayout(step_frame)
        step_lay.setContentsMargins(2, 2, 2, 2)
        step_lay.setSpacing(2)
        self.step_group = QtWidgets.QButtonGroup(step_frame)
        self.step_group.setExclusive(True)
        self.step_buttons = []
        for idx, value in enumerate(["0.1", "1", "10", "100"]):
            step_btn = FluidStyleButton(value)
            step_btn.setObjectName("cnc_segment_button")
            step_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            step_btn.setCheckable(True)
            step_btn.setProperty("step_value", value)
            step_btn.setAutoRaise(False)
            if value == "1":
                step_btn.setChecked(True)
            self.step_group.addButton(step_btn, idx)
            self.step_buttons.append(step_btn)
            step_lay.addWidget(step_btn)

        self.jog_feed = FCSpinner()
        self.setup_input(self.jog_feed)
        self.jog_feed.setFixedWidth(122)
        self.jog_feed.set_range(1, 60000)
        self.jog_feed.setValue(1000)
        self.jog_feed.setSuffix(" mm/min")
        self.jog_feed.setToolTip(_("Jog feed rate."))

        settings_lay.addWidget(self.field_label(_("Step")))
        settings_lay.addWidget(step_frame)
        settings_lay.addSpacing(12)
        settings_lay.addWidget(self.field_label(_("Feed")))
        settings_lay.addWidget(self.jog_feed)
        settings_lay.addStretch()
        body.addWidget(settings_frame)

        jog_wrap = QtWidgets.QHBoxLayout()
        jog_wrap.setSpacing(10)
        body.addLayout(jog_wrap)

        xy_pad = QtWidgets.QFrame()
        xy_pad.setObjectName("cnc_jog_pad")
        xy_lay = QtWidgets.QGridLayout(xy_pad)
        xy_lay.setContentsMargins(12, 10, 12, 10)
        xy_lay.setHorizontalSpacing(8)
        xy_lay.setVerticalSpacing(7)

        z_pad = QtWidgets.QFrame()
        z_pad.setObjectName("cnc_jog_pad")
        z_lay = QtWidgets.QVBoxLayout(z_pad)
        z_lay.setContentsMargins(12, 10, 12, 10)
        z_lay.setSpacing(7)

        self.jog_up = FluidStyleButton("Y+")
        self.jog_down = FluidStyleButton("Y-")
        self.jog_left = FluidStyleButton("X-")
        self.jog_right = FluidStyleButton("X+")
        self.jog_z_up = FluidStyleButton("Z+")
        self.jog_z_down = FluidStyleButton("Z-")
        self.setup_button(self.jog_up, "up-arrow32.png", _("Jog Y+"))
        self.setup_button(self.jog_down, "down-arrow32.png", _("Jog Y-"))
        self.setup_button(self.jog_left, "left_arrow32.png", _("Jog X-"))
        self.setup_button(self.jog_right, "right_arrow32.png", _("Jog X+"))
        self.setup_button(self.jog_z_up, "up-arrow32.png", _("Jog Z+"))
        self.setup_button(self.jog_z_down, "down-arrow32.png", _("Jog Z-"))
        for button in [self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down]:
            button.setObjectName("cnc_axis_button")
            button.setFixedSize(78, 40)

        xy_title = FCLabel(_("XY Axes"), bold=True)
        xy_title.setObjectName("cnc_jog_group_label")
        xy_center = FCLabel("X / Y")
        xy_center.setObjectName("cnc_jog_center")
        xy_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        xy_lay.addWidget(xy_title, 0, 0, 1, 3, alignment=Qt.AlignmentFlag.AlignCenter)
        xy_lay.addWidget(self.jog_up, 1, 1)
        xy_lay.addWidget(self.jog_left, 2, 0)
        xy_lay.addWidget(xy_center, 2, 1)
        xy_lay.addWidget(self.jog_right, 2, 2)
        xy_lay.addWidget(self.jog_down, 3, 1)

        z_title = FCLabel(_("Z Axis"), bold=True)
        z_title.setObjectName("cnc_jog_group_label")
        z_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        z_lay.addWidget(z_title)
        z_lay.addWidget(self.jog_z_up)
        z_mid = FCLabel("Z")
        z_mid.setObjectName("cnc_jog_center")
        z_mid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        z_lay.addWidget(z_mid)
        z_lay.addWidget(self.jog_z_down)
        z_lay.addStretch()

        jog_wrap.addStretch()
        jog_wrap.addWidget(xy_pad)
        jog_wrap.addWidget(z_pad)
        jog_wrap.addStretch()

    def build_system(self, body):
        values = QtWidgets.QGridLayout()
        values.setHorizontalSpacing(8)
        body.addLayout(values)

        self.feed_value = FCLabel("0", bold=True)
        self.spindle_value = FCLabel("0", bold=True)
        self.feed_override_value = FCLabel("100%")
        self.rapid_override_value = FCLabel("100%")
        self.spindle_override_value = FCLabel("100%")

        values.addWidget(FCLabel(_("Feed"), bold=True), 0, 0)
        values.addWidget(self.feed_value, 0, 1)
        values.addWidget(FCLabel(_("Spindle"), bold=True), 0, 2)
        values.addWidget(self.spindle_value, 0, 3)
        values.addWidget(FCLabel(_("Feed %"), bold=True), 1, 0)
        values.addWidget(self.feed_override_value, 1, 1)
        values.addWidget(FCLabel(_("Rapid %"), bold=True), 1, 2)
        values.addWidget(self.rapid_override_value, 1, 3)
        values.addWidget(FCLabel(_("Spindle %"), bold=True), 2, 0)
        values.addWidget(self.spindle_override_value, 2, 1)

        ov_grid = QtWidgets.QGridLayout()
        ov_grid.setSpacing(6)
        body.addLayout(ov_grid)

        self.feed_minus = FluidStyleButton("-", "#ffffff", "#f5f5f5", "#333333")
        self.feed_reset = FluidStyleButton("100%", "#ffffff", "#f5f5f5", "#333333")
        self.feed_plus = FluidStyleButton("+", "#ffffff", "#f5f5f5", "#333333")
        self.spindle_minus = FluidStyleButton("-", "#ffffff", "#f5f5f5", "#333333")
        self.spindle_reset = FluidStyleButton("100%", "#ffffff", "#f5f5f5", "#333333")
        self.spindle_plus = FluidStyleButton("+", "#ffffff", "#f5f5f5", "#333333")

        ov_grid.addWidget(FCLabel(_("FEED"), bold=True), 0, 0)
        ov_grid.addWidget(self.feed_minus, 0, 1)
        ov_grid.addWidget(self.feed_reset, 0, 2)
        ov_grid.addWidget(self.feed_plus, 0, 3)
        ov_grid.addWidget(FCLabel(_("SPINDLE"), bold=True), 1, 0)
        ov_grid.addWidget(self.spindle_minus, 1, 1)
        ov_grid.addWidget(self.spindle_reset, 1, 2)
        ov_grid.addWidget(self.spindle_plus, 1, 3)

        sys_lay = QtWidgets.QGridLayout()
        sys_lay.setSpacing(6)
        body.addLayout(sys_lay)

        self.info_btn = FluidStyleButton("INFO", "#5bc0de", "#31b0d5")
        self.cfg_dump = FluidStyleButton("CFG", "#444444", "#222222")
        self.reset_btn = FluidStyleButton("RESET", "#5cb85c", "#449d44")
        self.estop_btn = FluidStyleButton("HOLD", "#d9534f", "#c9302c")
        self.resume_btn = FluidStyleButton("RESUME", "#5bc0de", "#31b0d5")
        self.macro_probe = FluidStyleButton("PROBE Z", "#337ab7", "#286090")
        self.macro_laser = FluidStyleButton("LASER ON", "#d9534f", "#c9302c")
        self.setup_button(self.info_btn, "info16.png", _("Request controller info."))
        self.setup_button(self.cfg_dump, "settings18.png", _("Request controller settings."))
        self.setup_button(self.reset_btn, "reset32.png", _("Reset controller."))
        self.setup_button(self.estop_btn, "warning.png", _("Feed hold."))
        self.setup_button(self.resume_btn, "apply32.png", _("Resume motion."))
        self.setup_button(self.macro_probe, "machine16.png", _("Run probe macro."))
        self.setup_button(self.macro_laser, "warning.png", _("Toggle laser output."))
        self.macro_laser.setCheckable(True)

        sys_lay.addWidget(self.action_with_help(
            self.info_btn, _("Request controller status and firmware information.")
        ), 0, 0)
        sys_lay.addWidget(self.action_with_help(
            self.cfg_dump, _("Request controller configuration dump.")
        ), 0, 1)
        sys_lay.addWidget(self.action_with_help(
            self.reset_btn, _("Reset the controller connection.")
        ), 0, 2)
        sys_lay.addWidget(self.action_with_help(
            self.estop_btn, _("Pause motion with feed hold.")
        ), 1, 0)
        sys_lay.addWidget(self.action_with_help(
            self.resume_btn, _("Resume motion after hold.")
        ), 1, 1)
        sys_lay.addWidget(self.action_with_help(
            self.macro_probe, _("Run the configured Z probe macro.")
        ), 1, 2)
        sys_lay.addWidget(self.action_with_help(
            self.macro_laser, _("Toggle laser output on or off.")
        ), 2, 0, 1, 3)
        for col in range(3):
            sys_lay.setColumnStretch(col, 1)

    def build_direct_job(self, body):
        job_frame = QtWidgets.QFrame()
        job_frame.setObjectName("cnc_strip")
        job_lay = QtWidgets.QHBoxLayout(job_frame)
        job_lay.setContentsMargins(8, 6, 8, 6)
        job_lay.setSpacing(8)
        self.object_combo = FCComboBox()
        self.setup_input(self.object_combo)
        self.object_combo.setMinimumWidth(240)
        self.refresh_jobs_btn = FluidStyleButton(_("Refresh Jobs"), "#ffffff", "#f5f5f5", "#333333")
        self.play_btn = FluidStyleButton(_("SEND DIRECT"), "#5cb85c", "#449d44")
        self.pause_btn = FluidStyleButton(_("PAUSE"), "#f0ad4e", "#ec971f")
        self.stop_btn = FluidStyleButton(_("STOP"), "#d9534f", "#c9302c")
        self.setup_button(self.refresh_jobs_btn, "replot16.png", _("Refresh CNCJob list."))
        self.setup_button(self.play_btn, "cnc16.png", _("Stream selected G-code directly to the controller."))
        self.setup_button(self.pause_btn, "warning.png", _("Pause direct streaming."))
        self.setup_button(self.stop_btn, "power16.png", _("Stop direct streaming."))

        job_lay.addWidget(FCLabel(_("CNCJob"), bold=True))
        job_lay.addWidget(self.object_combo, 1)
        job_lay.addWidget(self.refresh_jobs_btn)
        job_lay.addWidget(self.play_btn)
        job_lay.addWidget(self.pause_btn)
        job_lay.addWidget(self.stop_btn)
        body.addWidget(job_frame)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setObjectName("cnc_progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        body.addWidget(self.progress)

    def build_sd_job(self, body):
        row_frame = QtWidgets.QFrame()
        row_frame.setObjectName("cnc_strip")
        lay = QtWidgets.QHBoxLayout(row_frame)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)
        self.sd_combo = FCComboBox()
        self.setup_input(self.sd_combo)
        self.sd_combo.setMinimumWidth(240)
        self.sd_list_btn = FluidStyleButton(_("Refresh SD"), "#444444", "#222222")
        self.run_sd_btn = FluidStyleButton(_("Run SD"), "#5cb85c", "#449d44")
        self.setup_button(self.sd_list_btn, "replot16.png", _("Refresh SD file list."))
        self.setup_button(self.run_sd_btn, "apply32.png", _("Run selected SD file."))
        lay.addWidget(FCLabel("SD:", bold=True))
        lay.addWidget(self.sd_combo, 1)
        lay.addWidget(self.sd_list_btn)
        lay.addWidget(self.run_sd_btn)
        body.addWidget(row_frame)

    def build_files_tab(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        panel, body = self.create_panel(_("Flash Filesystem"))
        lay.addWidget(panel, 1)

        toolbar = QtWidgets.QHBoxLayout()
        self.files_fs_combo = FCComboBox()
        self.setup_input(self.files_fs_combo)
        self.files_fs_combo.setMinimumWidth(150)
        self.files_fs_combo.addItem(_("Flash filesystem"), "/files")
        self.files_fs_combo.addItem(_("Direct SD"), "/upload")
        self.files_refresh_btn = FluidStyleButton(_("Refresh"), "#337ab7", "#286090")
        self.files_upload_btn = FluidStyleButton(_("Upload"), "#5bc0de", "#31b0d5")
        self.files_mkdir_btn = FluidStyleButton(_("New folder"), "#5bc0de", "#31b0d5")
        self.files_delete_btn = FluidStyleButton(_("Delete"), "#d9534f", "#c9302c")
        self.files_root_btn = FluidStyleButton("/", "#ffffff", "#f5f5f5", "#333333")
        self.files_up_btn = FluidStyleButton("Up", "#ffffff", "#f5f5f5", "#333333")
        self.setup_button(self.files_refresh_btn, "replot16.png", _("Refresh file list."))
        self.setup_button(self.files_upload_btn, "folder16.png", _("Upload files to the controller."))
        self.setup_button(self.files_mkdir_btn, "plus16.png", _("Create a folder."))
        self.setup_button(self.files_delete_btn, "trash16.png", _("Delete selected file or folder."))
        self.setup_button(self.files_root_btn, "home16.png", _("Go to root folder."))
        self.setup_button(self.files_up_btn, "up-arrow32.png", _("Go to parent folder."))
        self.path_label = FCLabel("/", color="#31708f")

        toolbar.addWidget(self.files_fs_combo)
        toolbar.addWidget(self.files_refresh_btn)
        toolbar.addWidget(self.files_upload_btn)
        toolbar.addWidget(self.files_mkdir_btn)
        toolbar.addWidget(self.files_delete_btn)
        toolbar.addWidget(self.files_root_btn)
        toolbar.addWidget(self.files_up_btn)
        toolbar.addWidget(self.path_label, 1)
        body.addLayout(toolbar)

        self.files_table = FCTable()
        self.files_table.setColumnCount(4)
        self.files_table.setHorizontalHeaderLabels([_("Type"), _("Name"), _("Size"), _("Time")])
        self.files_table.setAlternatingRowColors(True)
        self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.files_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.files_table.verticalHeader().hide()
        body.addWidget(self.files_table, 1)

        self.file_status = FCLabel(_("HTTP file manager is available in FluidNC Web mode."), color="#31708f")
        body.addWidget(self.file_status)
        self.busy_label = FCLabel("", color="#31708f")
        body.addWidget(self.busy_label)
        return page

    def build_terminal_console(self, body):
        options = QtWidgets.QHBoxLayout()
        self.poll_status_cb = QtWidgets.QCheckBox(_("Poll status"))
        self.poll_status_cb.setChecked(True)
        self.hide_status_reports_cb = QtWidgets.QCheckBox(_("Hide status reports"))
        self.hide_status_reports_cb.setChecked(True)
        options.addWidget(self.poll_status_cb)
        options.addWidget(self.hide_status_reports_cb)
        options.addStretch()
        body.addLayout(options)

        self.console = QtWidgets.QTextEdit()
        self.console.setObjectName("cnc_console")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(360)
        body.addWidget(self.console, 1)

        command_lay = QtWidgets.QHBoxLayout()
        self.command_entry = FCEntry()
        self.setup_input(self.command_entry)
        self.command_entry.setMinimumHeight(30)
        self.command_entry.setPlaceholderText(_("G-code / controller command"))
        command_lay.addWidget(self.command_entry, 1)
        body.addLayout(command_lay)

    def create_panel(self, title):
        panel = QtWidgets.QGroupBox(title)
        panel.setObjectName("cnc_panel")
        body_lay = QtWidgets.QVBoxLayout(panel)
        body_lay.setContentsMargins(8, 10, 8, 8)
        body_lay.setSpacing(6)
        return panel, body_lay

    def connection_config(self):
        port = self.com_port.currentText().strip().split(" - ", 1)[0]
        return {
            "mode": self.connection_mode_combo.currentData(),
            "port": port,
            "baudrate": int(self.baudrate_combo.currentText()),
            "host": self.tcp_host.text().strip(),
            "tcp_port": int(self.tcp_port.value()),
            "web_url": self.web_url.text().strip(),
            "user": self.web_user.text().strip(),
            "password": self.web_password.text(),
        }

    def get_jog_step(self):
        checked = self.step_group.checkedButton()
        if checked:
            return checked.property("step_value") or "1"
        return "1"

    def on_connection_mode_changed(self):
        index = self.connection_mode_combo.currentIndex()
        self.connection_stack.setCurrentIndex(index)

        mode = self.connection_mode_combo.currentData()
        self.com_refresh.setVisible(mode == "serial")
        self.com_refresh.setEnabled(mode == "serial")
        if mode == "http":
            fluid_idx = self.profile_combo.findData("fluidnc")
            if fluid_idx >= 0:
                self.profile_combo.setCurrentIndex(fluid_idx)
        self.sync_connection_dialog(False)
        self.set_file_tools_enabled(True)

    def set_connected(self, connected):
        self.state_label.setText("IDLE" if connected else "OFFLINE")
        if not connected:
            self.state_indicator.setStyleSheet("background-color: #999999; border-radius: 6px;")
        self.sync_connection_dialog(connected)

        controls = [
            self.play_btn, self.pause_btn, self.stop_btn,
            self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down,
            self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_btn, self.unlock_btn,
            self.reset_btn, self.estop_btn, self.resume_btn, self.cfg_dump, self.info_btn,
            self.sd_list_btn, self.run_sd_btn, self.feed_plus, self.feed_minus, self.feed_reset,
            self.spindle_plus, self.spindle_minus, self.spindle_reset, self.macro_probe, self.macro_laser,
            self.command_entry, self.refresh_jobs_btn
        ]
        for control in controls:
            control.setEnabled(True)

        self.set_file_tools_enabled(True)

    def set_file_tools_enabled(self, enabled):
        for widget in [
            self.files_refresh_btn, self.files_upload_btn, self.files_mkdir_btn, self.files_delete_btn,
            self.files_root_btn, self.files_up_btn, self.files_fs_combo
        ]:
            widget.setEnabled(True)

    def update_files_table(self, data):
        self.files_table.setRowCount(0)

        path = data.get("path", self.current_path) or "/"
        if not path.startswith("/"):
            path = "/" + path
        if not path.endswith("/"):
            path += "/"
        self.current_path = path
        self.path_label.setText(path)

        files = data.get("files", [])
        files = sorted(files, key=lambda f: (str(f.get("size")) != "-1", str(f.get("name", "")).lower()))

        for file_info in files:
            name = str(file_info.get("name", ""))
            size = str(file_info.get("size", ""))
            is_dir = size == "-1"
            row = self.files_table.rowCount()
            self.files_table.insertRow(row)

            type_item = QtWidgets.QTableWidgetItem("DIR" if is_dir else "FILE")
            name_item = QtWidgets.QTableWidgetItem(name)
            size_item = QtWidgets.QTableWidgetItem("" if is_dir else size)
            time_item = QtWidgets.QTableWidgetItem(str(file_info.get("time", "")))

            payload = {"name": name, "is_dir": is_dir, "raw": file_info}
            for item in [type_item, name_item, size_item, time_item]:
                item.setData(Qt.ItemDataRole.UserRole, payload)

            self.files_table.setItem(row, 0, type_item)
            self.files_table.setItem(row, 1, name_item)
            self.files_table.setItem(row, 2, size_item)
            self.files_table.setItem(row, 3, time_item)

        status = data.get("status", "OK")
        total = data.get("total", "")
        used = data.get("used", "")
        occupation = data.get("occupation", "")
        parts = [f"Status: {status}"]
        if total:
            parts.append(f"Total: {total}")
        if used:
            parts.append(f"Used: {used}")
        if occupation:
            parts.append(f"Occupation: {occupation}%")
        self.file_status.setText(" | ".join(parts))

    def selected_file_item(self):
        selected = self.files_table.selectedItems()
        if not selected:
            return None
        return selected[0].data(Qt.ItemDataRole.UserRole)

    def clear_sd_files(self):
        self.sd_combo.clear()

    def add_sd_file(self, filename):
        if filename and self.sd_combo.findText(filename) < 0:
            self.sd_combo.addItem(filename)

    def update_controller_info(self, info):
        hostname = info.get("hostname", "")
        target = info.get("FW target", "")
        details = " | ".join(value for value in [hostname, target] if value)
        self.controller_info_label.setText(details)
        self.sync_connection_dialog(self.disconnect_btn.isVisible())

    def set_busy(self, busy, message):
        self.busy_label.setText(message if busy else "")

    def append_console(self, text, entry_type):
        color = {
            "tx": "#569cd6",
            "rx": "#d4d4d4",
            "info": "#6a9955",
            "warn": "#d7ba7d",
            "error": "#f44747",
        }.get(entry_type, "#d4d4d4")

        safe_text = html.escape(str(text))
        timestamp = time.strftime("%H:%M:%S")
        self.console.append(
            f'<span style="color:#808080;">[{timestamp}]</span> '
            f'<span style="color:{color};">{safe_text}</span>'
        )
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)
