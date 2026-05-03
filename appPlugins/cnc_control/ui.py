import builtins
import gettext
import html
import os
import time

from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt

from appGUI.GUIElements import (
    FCLabel, FCComboBox, FCSpinner, FCEntry, FCTable
)

from .dialogs import FileSystemDialog
from .profiles import CNC_PROFILES
from .sections import DEFAULT_CNC_SECTIONS
from .widgets import FluidStyleButton

import appTranslation as fcTranslate

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class CNCControlUI:
    pluginName = _("CNC Settings")

    def __init__(self, layout, app):
        self.app = app
        self.layout = layout
        self.current_path = "/"
        self.primary = "#31b0d5"
        self.primary_dark = "#269abc"
        self.section_plugins = {
            key: section_cls() for key, section_cls in DEFAULT_CNC_SECTIONS.items()
        }

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
        self.build_connection_state_cache()
        self.build_file_system_dialog()

        # Vertical Scrollable Area
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.main_lay.addWidget(self.scroll)

        self.content_widget = QtWidgets.QWidget()
        self.content_lay = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_lay.setContentsMargins(0, 0, 0, 0)
        self.content_lay.setSpacing(12)
        self.scroll.setWidget(self.content_widget)

        self.build_dashboard_layout()

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
        arrow_icon = os.path.join(self.app.resource_location, "down-arrow32.png").replace("\\", "/")

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
            QComboBox#cnc_input {{
                padding-right: 28px;
            }}
            QComboBox#cnc_input:focus,
            QLineEdit#cnc_input:focus,
            QSpinBox#cnc_input:focus {{
                border-color: {highlight};
            }}
            QComboBox#cnc_input::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                border-left: 1px solid {mid};
                width: 26px;
            }}
            QComboBox#cnc_input::down-arrow {{
                image: url({arrow_icon});
                width: 10px;
                height: 10px;
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

    def setup_icon_button(self, button, icon_file=None, tooltip=None):
        self.setup_button(button, icon_file, tooltip, text_beside=False)
        button.setFixedSize(34, 32)
        button.setText(button.text())
        return button

    def setup_input(self, widget):
        widget.setObjectName("cnc_input")
        return widget

    def setup_connection_input(self, widget, min_width=None, fixed_width=None):
        self.setup_input(widget)
        widget.setFixedHeight(34)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        if min_width is not None:
            widget.setMinimumWidth(min_width)
        if fixed_width is not None:
            widget.setFixedWidth(fixed_width)
        return widget

    def field_label(self, text):
        label = FCLabel(text)
        label.setObjectName("cnc_field_label")
        return label

    def connection_field_label(self, text):
        label = self.field_label(text)
        label.setFixedHeight(34)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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

    def override_stepper(self, minus_btn, reset_btn, plus_btn):
        lay = QtWidgets.QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(minus_btn)
        lay.addWidget(reset_btn)
        lay.addWidget(plus_btn)
        lay.addStretch()
        return lay

    def build_dashboard_layout(self):
        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        self.content_lay.addLayout(top_row)

        top_row.addWidget(self.section_plugins["gauges"].build_panel(self), 1)
        top_row.addWidget(self.section_plugins["job_streaming"].build_panel(self), 2)

        machine_grid = QtWidgets.QGridLayout()
        machine_grid.setContentsMargins(0, 0, 0, 0)
        machine_grid.setSpacing(8)
        self.content_lay.addLayout(machine_grid)

        machine_grid.addWidget(self.section_plugins["position"].build_panel(self), 0, 0)
        machine_grid.addWidget(self.section_plugins["jog"].build_panel(self), 0, 1)
        machine_grid.addWidget(self.section_plugins["overrides_system"].build_panel(self), 0, 2)
        machine_grid.addWidget(self.section_plugins["macros"].build_panel(self), 0, 3)
        for column in range(4):
            machine_grid.setColumnStretch(column, 1)

        self.content_lay.addWidget(self.section_plugins["terminal"].build_panel(self), 1)
        self.content_lay.addWidget(self.section_plugins["modal_actions"].build_widget(self))

    def build_file_system_dialog(self):
        self.file_system_dialog = FileSystemDialog(self)
        for attr in [
            "files_fs_combo", "files_refresh_btn", "files_upload_btn", "files_mkdir_btn",
            "files_delete_btn", "files_root_btn", "files_up_btn", "files_table",
            "path_label", "file_status", "busy_label"
        ]:
            setattr(self, attr, getattr(self.file_system_dialog, attr))

    def show_file_system_dialog(self):
        self.file_system_dialog.show()
        self.file_system_dialog.raise_()
        self.file_system_dialog.activateWindow()

    def build_connection_state_cache(self):
        self.state_indicator = QtWidgets.QFrame()
        self.state_indicator.setFixedSize(12, 12)
        self.state_indicator.setStyleSheet("background-color: #999999; border-radius: 6px;")
        self.state_label = FCLabel("OFFLINE", bold=True)
        self.connection_desc = FCLabel(_("Offline"), color="#777777")
        self.controller_info_label = FCLabel("", color="#777777")

    def build_connection_dialog(self):
        self.connection_dialog = QtWidgets.QDialog(self.app.ui)
        self.connection_dialog.setWindowTitle(_("Connection"))
        self.connection_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.connection_dialog.setMinimumWidth(620)
        self.connection_dialog.setStyleSheet(self.stylesheet())

        dialog_lay = QtWidgets.QVBoxLayout(self.connection_dialog)
        dialog_lay.setContentsMargins(10, 10, 10, 10)
        dialog_lay.setSpacing(8)
        dialog_lay.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)

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
        self.setup_connection_input(self.connection_mode_combo, min_width=210)
        self.connection_mode_combo.addItem(_("COM / USB"), "serial")
        self.connection_mode_combo.addItem(_("WiFi TCP/Telnet"), "tcp")
        self.connection_mode_combo.addItem(_("FluidNC Web"), "http")

        self.profile_combo = FCComboBox()
        self.setup_connection_input(self.profile_combo, min_width=210)
        for key, profile in CNC_PROFILES.items():
            self.profile_combo.addItem(profile["label"], key)

        selector_lay = QtWidgets.QHBoxLayout()
        selector_lay.setSpacing(8)
        selector_lay.addWidget(self.connection_field_label(_("Mode")))
        selector_lay.addWidget(self.connection_mode_combo, 1)
        selector_lay.addWidget(self.connection_field_label(_("Controller")))
        selector_lay.addWidget(self.profile_combo, 1)
        fields_lay.addLayout(selector_lay)

        self.connection_stack = QtWidgets.QStackedWidget()
        self.connection_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )
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

    def show_connection_dialog(self, connected=False):
        self.sync_connection_dialog(connected)
        self.connection_dialog.adjustSize()
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

    def set_connection_actions_enabled(self, enabled):
        self.connect_btn.setEnabled(enabled)
        self.test_connection_btn.setEnabled(enabled)
        self.disconnect_btn.setEnabled(enabled)
        self.com_refresh.setEnabled(enabled and self.connection_mode_combo.currentData() == "serial")

    def build_serial_connection_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.com_port = FCComboBox()
        self.setup_connection_input(self.com_port, min_width=320)
        self.com_port.setEditable(True)
        self.baudrate_combo = FCComboBox()
        self.setup_connection_input(self.baudrate_combo, fixed_width=135)
        for baud in ["115200", "250000", "230400", "57600", "38400", "19200", "9600"]:
            self.baudrate_combo.addItem(baud)
        self.baudrate_combo.setCurrentText("115200")

        lay.addWidget(self.connection_field_label(_("Port")))
        lay.addWidget(self.com_port, 1)
        lay.addWidget(self.connection_field_label(_("Baud")))
        lay.addWidget(self.baudrate_combo)
        self.connection_stack.addWidget(page)

    def build_tcp_connection_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.tcp_host = FCEntry()
        self.setup_connection_input(self.tcp_host, min_width=340)
        self.tcp_host.setPlaceholderText("192.168.0.10")
        self.tcp_host.setText("fluidnc.local")
        self.tcp_port = FCSpinner()
        self.setup_connection_input(self.tcp_port, fixed_width=115)
        self.tcp_port.set_range(1, 65535)
        self.tcp_port.setValue(23)

        lay.addWidget(self.connection_field_label(_("Host")))
        lay.addWidget(self.tcp_host, 1)
        lay.addWidget(self.connection_field_label(_("Port")))
        lay.addWidget(self.tcp_port)
        self.connection_stack.addWidget(page)

    def build_http_connection_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QGridLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(6)

        self.web_url = FCEntry()
        self.setup_connection_input(self.web_url, min_width=500)
        self.web_url.setText("http://fluidnc.local")
        self.web_user = FCEntry()
        self.setup_connection_input(self.web_user, min_width=500)
        self.web_password = FCEntry()
        self.setup_connection_input(self.web_password, min_width=500)
        self.web_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        lay.addWidget(self.connection_field_label(_("URL")), 0, 0)
        lay.addWidget(self.web_url, 0, 1)
        lay.addWidget(self.connection_field_label(_("User")), 1, 0)
        lay.addWidget(self.web_user, 1, 1)
        lay.addWidget(self.connection_field_label(_("Password")), 2, 0)
        lay.addWidget(self.web_password, 2, 1)
        lay.setColumnStretch(1, 1)
        self.connection_stack.addWidget(page)

    def build_dro(self, body):
        self.dro_grid = QtWidgets.QGridLayout()
        self.dro_grid.setContentsMargins(8, 8, 8, 8)
        self.dro_grid.setSpacing(10)
        body.addLayout(self.dro_grid)

        # Headers
        self.dro_grid.addWidget(FCLabel(_("Work"), bold=True, size=11), 0, 1, Qt.AlignmentFlag.AlignCenter)
        self.dro_grid.addWidget(FCLabel(_("Machine"), bold=True, size=11), 0, 2, Qt.AlignmentFlag.AlignCenter)
        self.dro_grid.addWidget(FCLabel(_("Zero"), bold=True, size=11), 0, 3, Qt.AlignmentFlag.AlignCenter)

        # Rows
        self.zero_x, self.x_val, self.mx_val = self.add_dro_row(1, "X", "#d9534f")
        self.zero_y, self.y_val, self.my_val = self.add_dro_row(2, "Y", "#5cb85c")
        self.zero_z, self.z_val, self.mz_val = self.add_dro_row(3, "Z", "#337ab7")

        # Bottom Buttons
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

    def add_dro_row(self, row, axis, color):
        axis_label = FCLabel(axis, bold=True, size=15, color=color)
        work = FCLabel("0.000", bold=True, size=22)
        machine = FCLabel("0.000", color="#666666", size=14)
        zero = FluidStyleButton(f"{axis}0", "#444444", "#222222")
        self.setup_button(zero, "origin16.png", _("Zero this axis."))
        zero.setFixedWidth(60)

        work.setAlignment(Qt.AlignmentFlag.AlignCenter)
        machine.setAlignment(Qt.AlignmentFlag.AlignCenter)
        work.setStyleSheet("font-family: 'Consolas', 'Monospace'; font-weight: bold;")
        machine.setStyleSheet("font-family: 'Consolas', 'Monospace';")

        self.dro_grid.addWidget(axis_label, row, 0, Qt.AlignmentFlag.AlignCenter)
        self.dro_grid.addWidget(work, row, 1, Qt.AlignmentFlag.AlignCenter)
        self.dro_grid.addWidget(machine, row, 2, Qt.AlignmentFlag.AlignCenter)
        self.dro_grid.addWidget(zero, row, 3, Qt.AlignmentFlag.AlignCenter)

        return zero, work, machine

    def build_jog(self, body):
        settings_lay = QtWidgets.QHBoxLayout()
        settings_lay.setContentsMargins(0, 0, 0, 0)
        settings_lay.setSpacing(8)

        step_frame = QtWidgets.QFrame()
        step_frame.setObjectName("cnc_segment")
        step_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
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
        self.jog_feed.setFixedSize(150, 34)
        self.jog_feed.set_range(1, 60000)
        self.jog_feed.setValue(1000)
        self.jog_feed.setSuffix(" mm/min")
        self.jog_feed.setToolTip(_("Jog feed rate."))

        settings_lay.addWidget(self.field_label(_("Step")))
        settings_lay.addWidget(step_frame)
        settings_lay.addSpacing(8)
        settings_lay.addWidget(self.field_label(_("Feed")))
        settings_lay.addWidget(self.jog_feed)
        settings_lay.addStretch()
        body.addLayout(settings_lay)

        jog_wrap = QtWidgets.QHBoxLayout()
        jog_wrap.setContentsMargins(0, 0, 0, 0)
        jog_wrap.setSpacing(8)
        body.addLayout(jog_wrap)

        xy_pad = QtWidgets.QFrame()
        xy_pad.setObjectName("cnc_jog_pad")
        xy_pad.setMinimumSize(282, 218)
        xy_pad.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        xy_lay = QtWidgets.QGridLayout(xy_pad)
        xy_lay.setContentsMargins(12, 10, 12, 10)
        xy_lay.setHorizontalSpacing(8)
        xy_lay.setVerticalSpacing(7)

        z_pad = QtWidgets.QFrame()
        z_pad.setObjectName("cnc_jog_pad")
        z_pad.setFixedSize(108, 218)
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

        jog_wrap.addWidget(xy_pad, 1)
        jog_wrap.addWidget(z_pad)

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

        self.feed_override_entry = FCSpinner()
        self.setup_connection_input(self.feed_override_entry, fixed_width=112)
        self.feed_override_entry.set_range(10, 200)
        self.feed_override_entry.setValue(100)
        self.feed_override_entry.setSuffix("%")
        self.feed_override_entry.setToolTip(_("Target feed override percent."))
        self.feed_set_btn = FluidStyleButton("SET", "#337ab7", "#286090")
        self.setup_button(self.feed_set_btn, "apply32.png", _("Set feed override percent."))

        self.spindle_override_entry = FCSpinner()
        self.setup_connection_input(self.spindle_override_entry, fixed_width=112)
        self.spindle_override_entry.set_range(10, 200)
        self.spindle_override_entry.setValue(100)
        self.spindle_override_entry.setSuffix("%")
        self.spindle_override_entry.setToolTip(_("Target spindle override percent."))
        self.spindle_override_set_btn = FluidStyleButton("SET", "#337ab7", "#286090")
        self.setup_button(self.spindle_override_set_btn, "apply32.png", _("Set spindle override percent."))

        self.feed_minus = FluidStyleButton("-")
        self.feed_reset = FluidStyleButton("100")
        self.feed_plus = FluidStyleButton("+")
        self.spindle_minus = FluidStyleButton("-")
        self.spindle_reset = FluidStyleButton("100")
        self.spindle_plus = FluidStyleButton("+")
        self.setup_icon_button(self.feed_minus, None, _("Decrease feed override."))
        self.setup_icon_button(self.feed_reset, None, _("Reset feed override."))
        self.setup_icon_button(self.feed_plus, None, _("Increase feed override."))
        self.setup_icon_button(self.spindle_minus, None, _("Decrease spindle override."))
        self.setup_icon_button(self.spindle_reset, None, _("Reset spindle override."))
        self.setup_icon_button(self.spindle_plus, None, _("Increase spindle override."))

        self.spindle_rpm = FCSpinner()
        self.setup_connection_input(self.spindle_rpm, fixed_width=150)
        self.spindle_rpm.set_range(0, 60000)
        self.spindle_rpm.setValue(12000)
        self.spindle_rpm.setSuffix(" RPM")
        self.spindle_rpm.setToolTip(_("Target spindle RPM."))
        self.spindle_set_btn = FluidStyleButton("SET RPM", "#337ab7", "#286090")
        self.spindle_stop_btn = FluidStyleButton("STOP", "#d9534f", "#c9302c")
        self.setup_button(self.spindle_set_btn, "apply32.png", _("Set spindle speed with the selected RPM."))
        self.setup_button(self.spindle_stop_btn, "power16.png", _("Stop spindle."))

        ov_grid.addWidget(FCLabel(_("RPM"), bold=True), 0, 0)
        ov_grid.addWidget(self.spindle_rpm, 0, 1)
        ov_grid.addWidget(self.spindle_set_btn, 0, 2)
        ov_grid.addWidget(self.spindle_stop_btn, 0, 3)
        ov_grid.addWidget(FCLabel(_("FEED"), bold=True), 1, 0)
        ov_grid.addWidget(self.feed_override_entry, 1, 1)
        ov_grid.addWidget(self.feed_set_btn, 1, 2)
        ov_grid.addLayout(self.override_stepper(self.feed_minus, self.feed_reset, self.feed_plus), 1, 3)
        ov_grid.addWidget(FCLabel(_("SPINDLE %"), bold=True), 2, 0)
        ov_grid.addWidget(self.spindle_override_entry, 2, 1)
        ov_grid.addWidget(self.spindle_override_set_btn, 2, 2)
        ov_grid.addLayout(self.override_stepper(self.spindle_minus, self.spindle_reset, self.spindle_plus), 2, 3)

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
        self.connection_stack.setFixedHeight(120 if mode == "http" else 38)
        self.com_refresh.setVisible(mode == "serial")
        self.com_refresh.setEnabled(mode == "serial")
        if mode == "http":
            fluid_idx = self.profile_combo.findData("fluidnc")
            if fluid_idx >= 0:
                self.profile_combo.setCurrentIndex(fluid_idx)
        self.sync_connection_dialog(False)
        self.connection_dialog.adjustSize()
        self.set_file_tools_enabled(self.disconnect_btn.isVisible())

    def set_connected(self, connected):
        self.state_label.setText("IDLE" if connected else "OFFLINE")
        if not connected:
            self.state_indicator.setStyleSheet("background-color: #999999; border-radius: 6px;")
            if hasattr(self, 'feed_gauge'):
                self.update_dashboard_gauges(0, 0)
        self.sync_connection_dialog(connected)

        controls = [
            self.play_btn, self.pause_btn, self.stop_btn,
            self.jog_up, self.jog_down, self.jog_left, self.jog_right, self.jog_z_up, self.jog_z_down,
            self.zero_x, self.zero_y, self.zero_z, self.zero_all, self.home_btn, self.unlock_btn,
            self.reset_btn, self.estop_btn, self.resume_btn, self.cfg_dump, self.info_btn,
            self.sd_list_btn, self.run_sd_btn, self.feed_override_entry, self.feed_set_btn,
            self.feed_plus, self.feed_minus, self.feed_reset, self.spindle_override_entry,
            self.spindle_override_set_btn, self.spindle_plus, self.spindle_minus, self.spindle_reset,
            self.spindle_rpm, self.spindle_set_btn, self.spindle_stop_btn, self.macro_probe, self.macro_laser,
            self.command_entry, self.refresh_jobs_btn,
            self.files_refresh_btn, self.files_upload_btn, self.files_mkdir_btn,
            self.files_delete_btn, self.files_up_btn, self.files_root_btn
        ]
        for control in controls:
            if control is not None and hasattr(control, 'setEnabled'):
                control.setEnabled(connected)

        self.set_file_tools_enabled(connected)

    def set_file_tools_enabled(self, enabled):
        for widget in [
            self.files_refresh_btn, self.files_upload_btn, self.files_mkdir_btn, self.files_delete_btn,
            self.files_root_btn, self.files_up_btn, self.files_fs_combo
        ]:
            widget.setEnabled(enabled)

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

    def update_dashboard_gauges(self, feed, spindle):
        if hasattr(self, 'feed_gauge'):
            self.feed_gauge.set_value(feed)
        if hasattr(self, 'spindle_gauge'):
            self.spindle_gauge.set_value(spindle)

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
