import builtins
import gettext

from PyQt6 import QtWidgets

from .widgets import DashboardGauge, FluidStyleButton

import appTranslation as fcTranslate

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class CNCSectionPlugin:
    section_id = ""
    title = ""

    def build_panel(self, ui):
        panel, body = ui.create_panel(self.title)
        self.build(ui, body)
        return panel

    def build(self, ui, body):
        raise NotImplementedError


class GaugeSection(CNCSectionPlugin):
    section_id = "gauges"
    title = _("Feed / Spindle")

    def build(self, ui, body):
        gauge_lay = QtWidgets.QHBoxLayout()
        gauge_lay.setContentsMargins(0, 0, 0, 0)
        gauge_lay.setSpacing(8)
        body.addLayout(gauge_lay)

        ui.feed_gauge = DashboardGauge(_("Feed"), "mm/min", 6000, "#31b0d5")
        ui.spindle_gauge = DashboardGauge(_("Spindle"), "RPM", 24000, "#d9534f")
        ui.feed_gauge.setToolTip(_("Live feed rate from controller status."))
        ui.spindle_gauge.setToolTip(_("Live spindle speed from controller status."))
        gauge_lay.addWidget(ui.feed_gauge, 1)
        gauge_lay.addWidget(ui.spindle_gauge, 1)


class JobStreamingSection(CNCSectionPlugin):
    section_id = "job_streaming"
    title = _("G-Code Job Streaming")

    def build(self, ui, body):
        ui.build_direct_job(body)
        ui.build_sd_job(body)


class PositionSection(CNCSectionPlugin):
    section_id = "position"
    title = _("Position")

    def build(self, ui, body):
        ui.build_dro(body)


class JogSection(CNCSectionPlugin):
    section_id = "jog"
    title = _("Jog")

    def build(self, ui, body):
        ui.build_jog(body)


class OverridesSystemSection(CNCSectionPlugin):
    section_id = "overrides_system"
    title = _("Overrides & System")

    def build(self, ui, body):
        ui.build_system(body)


class MacroSection(CNCSectionPlugin):
    section_id = "macros"
    title = _("Saved Macros")

    def build(self, ui, body):
        ui.macro_list = QtWidgets.QListWidget()
        ui.macro_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        ui.macro_list.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        ui.macro_list.setMinimumHeight(140)
        body.addWidget(ui.macro_list, 1)

        ui.manage_macros_btn = FluidStyleButton(_("Manage Macros"), "#337ab7", "#286090")
        ui.setup_button(ui.manage_macros_btn, "settings18.png", _("Open Macro Management Dialog."))
        body.addWidget(ui.manage_macros_btn)


class TerminalSection(CNCSectionPlugin):
    section_id = "terminal"
    title = _("Terminal Console")

    def build(self, ui, body):
        ui.build_terminal_console(body)


class ModalActionsSection:
    section_id = "modal_actions"

    def build_widget(self, ui):
        actions_frame = QtWidgets.QFrame()
        actions_frame.setObjectName("cnc_strip")
        actions_lay = QtWidgets.QHBoxLayout(actions_frame)
        actions_lay.setContentsMargins(8, 6, 8, 6)
        actions_lay.setSpacing(8)

        ui.files_dialog_btn = FluidStyleButton(_("Flash File System"), "#337ab7", "#286090")
        ui.setup_button(ui.files_dialog_btn, "folder16.png", _("Open Flash Filesystem operations."))

        actions_lay.addWidget(ui.files_dialog_btn)
        actions_lay.addStretch()
        return actions_frame


DEFAULT_CNC_SECTIONS = {
    "gauges": GaugeSection,
    "job_streaming": JobStreamingSection,
    "position": PositionSection,
    "jog": JogSection,
    "overrides_system": OverridesSystemSection,
    "macros": MacroSection,
    "terminal": TerminalSection,
    "modal_actions": ModalActionsSection,
}
