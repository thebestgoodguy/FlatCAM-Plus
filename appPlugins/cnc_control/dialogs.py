import builtins
import gettext

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from appGUI.GUIElements import FCComboBox, FCLabel, FCTable

from .widgets import FluidStyleButton

import appTranslation as fcTranslate

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class FileSystemDialog(QtWidgets.QDialog):
    def __init__(self, owner, parent=None):
        parent_widget = parent if parent is not None else owner.app.ui
        super().__init__(parent_widget)
        self.owner = owner
        self.setWindowTitle(_("Flash Filesystem"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(760, 520)
        self.setStyleSheet(owner.stylesheet())

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        panel, body = owner.create_panel(_("Flash Filesystem"))
        lay.addWidget(panel, 1)

        toolbar = QtWidgets.QHBoxLayout()
        self.files_fs_combo = FCComboBox()
        owner.setup_input(self.files_fs_combo)
        self.files_fs_combo.setMinimumWidth(160)
        self.files_fs_combo.addItem(_("Flash filesystem"), "/files")
        self.files_fs_combo.addItem(_("Direct SD"), "/upload")

        self.files_refresh_btn = FluidStyleButton(_("Refresh"), "#337ab7", "#286090")
        self.files_upload_btn = FluidStyleButton(_("Upload"), "#5bc0de", "#31b0d5")
        self.files_mkdir_btn = FluidStyleButton(_("New folder"), "#5bc0de", "#31b0d5")
        self.files_delete_btn = FluidStyleButton(_("Delete"), "#d9534f", "#c9302c")
        self.files_root_btn = FluidStyleButton("/", "#ffffff", "#f5f5f5", "#333333")
        self.files_up_btn = FluidStyleButton(_("Up"), "#ffffff", "#f5f5f5", "#333333")

        owner.setup_button(self.files_refresh_btn, "replot16.png", _("Refresh file list."))
        owner.setup_button(self.files_upload_btn, "folder16.png", _("Upload files to the controller."))
        owner.setup_button(self.files_mkdir_btn, "plus16.png", _("Create a folder."))
        owner.setup_button(self.files_delete_btn, "trash16.png", _("Delete selected file or folder."))
        owner.setup_button(self.files_root_btn, "home16.png", _("Go to root folder."))
        owner.setup_button(self.files_up_btn, "up-arrow32.png", _("Go to parent folder."))

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
        self.busy_label = FCLabel("", color="#31708f")
        body.addWidget(self.file_status)
        body.addWidget(self.busy_label)

        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch()
        close_btn = QtWidgets.QPushButton(_("Close"))
        close_btn.clicked.connect(self.hide)
        bottom.addWidget(close_btn)
        lay.addLayout(bottom)


class MacroDialog(QtWidgets.QDialog):
    def __init__(self, macros, parent=None):
        super().__init__(parent)
        self.macros = list(macros) # Copy
        self.setWindowTitle("Macro Management")
        self.setMinimumSize(600, 400)

        # UI from parent theme
        self.setStyleSheet(parent.ui.stylesheet())

        lay = QtWidgets.QVBoxLayout(self)

        main_h = QtWidgets.QHBoxLayout()
        lay.addLayout(main_h)

        # List
        list_panel = QtWidgets.QGroupBox("Saved Macros")
        list_lay = QtWidgets.QVBoxLayout(list_panel)
        self.macro_list = QtWidgets.QListWidget()
        self.macro_add_btn = FluidStyleButton("NEW MACRO", "#5cb85c", "#449d44")
        list_lay.addWidget(self.macro_list)
        list_lay.addWidget(self.macro_add_btn)
        main_h.addWidget(list_panel, 1)

        # Editor
        edit_panel = QtWidgets.QGroupBox("Edit Macro")
        edit_lay = QtWidgets.QVBoxLayout(edit_panel)
        self.macro_name_edit = QtWidgets.QLineEdit()
        self.macro_content_edit = QtWidgets.QPlainTextEdit()
        self.macro_content_edit.setPlaceholderText("Enter G-Code commands...")
        edit_lay.addWidget(QtWidgets.QLabel("Name:"))
        edit_lay.addWidget(self.macro_name_edit)
        edit_lay.addWidget(QtWidgets.QLabel("Commands:"))
        edit_lay.addWidget(self.macro_content_edit)

        btn_lay = QtWidgets.QHBoxLayout()
        self.macro_save_btn = FluidStyleButton("SAVE", "#337ab7", "#286090")
        self.macro_delete_btn = FluidStyleButton("DELETE", "#d9534f", "#c9302c")
        btn_lay.addWidget(self.macro_save_btn)
        btn_lay.addWidget(self.macro_delete_btn)
        edit_lay.addLayout(btn_lay)
        main_h.addWidget(edit_panel, 2)

        # Bottom Buttons
        bottom = QtWidgets.QHBoxLayout()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        lay.addLayout(bottom)

        # Signals
        self.macro_add_btn.clicked.connect(self.on_add)
        self.macro_save_btn.clicked.connect(self.on_save)
        self.macro_delete_btn.clicked.connect(self.on_delete)
        self.macro_list.itemSelectionChanged.connect(self.on_selection_changed)

        self.refresh_list()

    def refresh_list(self):
        self.macro_list.clear()
        for m in self.macros:
            self.macro_list.addItem(m["name"])

    def on_add(self):
        self.macro_list.clearSelection()
        self.macro_name_edit.setText("New Macro")
        self.macro_content_edit.clear()

    def on_save(self):
        name = self.macro_name_edit.text().strip()
        content = self.macro_content_edit.toPlainText().strip()
        if not name: return

        sel = self.macro_list.selectedItems()
        if sel:
            idx = self.macro_list.row(sel[0])
            self.macros[idx] = {"name": name, "content": content}
        else:
            self.macros.append({"name": name, "content": content})
        self.refresh_list()

    def on_delete(self):
        sel = self.macro_list.selectedItems()
        if not sel: return
        idx = self.macro_list.row(sel[0])
        self.macros.pop(idx)
        self.refresh_list()
        self.macro_name_edit.clear()
        self.macro_content_edit.clear()

    def on_selection_changed(self):
        sel = self.macro_list.selectedItems()
        if not sel: return
        idx = self.macro_list.row(sel[0])
        m = self.macros[idx]
        self.macro_name_edit.setText(m["name"])
        self.macro_content_edit.setPlainText(m["content"])
