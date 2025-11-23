"""Main window for the Stromschlag GUI."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.exporters import ExportResult, export_icon_pack, install_icon_pack
from ..core.models import IconDefinition, PackSettings
from ..core.project_io import load_project
from ..core.theme_loader import (
    ThemeCandidate,
    load_icon_blueprint,
    load_icons_from_directory,
    list_installed_themes,
)


class MainWindow(QMainWindow):
    """Primary GUI surface for assembling icon pack projects."""

    _CATEGORY_LABELS = {
        "apps": "Applications",
        "actions": "Actions",
        "status": "Status / Tray",
        "panel": "Panel / UI",
        "ui": "UI Elements",
        "system": "System",
        "devices": "Devices",
        "places": "Places",
        "categories": "Categories",
        "mimetypes": "Mimetypes",
        "fallback": "Fallback",
        "custom": "Custom",
        "other": "Other",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stromschlag - Icon Pack Builder")
        self.resize(1280, 800)

        self._icons: List[IconDefinition] = []
        self._settings: PackSettings | None = None
        self._metadata_confirmed = False
        self._project_loaded = False
        self._last_export_result: ExportResult | None = None
        self._settings_store = QSettings("Stromschlag", "Stromschlag")
        self._recent_projects: List[str] = []
        self._recent_menu: QMenu | None = None
        self._recent_list: QListWidget | None = None
        self._recent_placeholder_label: QLabel | None = None

        # Project UI widgets created up front
        self._icon_tree = QTreeWidget()
        self._icon_tree.setHeaderHidden(True)
        self._icon_tree.setAnimated(True)
        self._category_nodes: dict[str, QTreeWidgetItem] = {}
        self._row_to_item: List[QTreeWidgetItem | None] = []
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search icons…")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(self._handle_filter_change)
        self._filter_edit.setEnabled(False)
        self._filter_text = ""
        self._preview_label = QLabel()
        self._icon_name_edit = QLineEdit()
        self._icon_name_edit.setPlaceholderText("Logical icon name (e.g., firefox)")
        self._icon_source_path_display = QLineEdit()
        self._icon_source_path_display.setReadOnly(True)
        self._icon_source_path_display.setPlaceholderText("No artwork selected")
        self._icon_choose_artwork_button = QPushButton("Choose artwork…")
        self._icon_apply_button = QPushButton("Save name")
        self._suppress_form_updates = False
        self._icon_name_edit.editingFinished.connect(self._handle_name_commit)

        self._pack_name_edit = QLineEdit()
        self._pack_author_edit = QLineEdit()
        self._pack_inherits_edit = QLineEdit()
        self._pack_targets_edit = QLineEdit()
        for field, placeholder in (
            (self._pack_name_edit, "Pack name"),
            (self._pack_author_edit, "Author"),
            (self._pack_inherits_edit, "Base theme"),
            (self._pack_targets_edit, "Targets (comma separated)"),
        ):
            field.setPlaceholderText(placeholder)
            field.setEnabled(False)
            field.editingFinished.connect(self._handle_metadata_field_commit)
        self._suppress_metadata_updates = False

        self._stack = QStackedWidget()
        self._placeholder_view = self._build_placeholder_view()
        self._project_view = self._build_project_view()
        self._stack.addWidget(self._placeholder_view)
        self._stack.addWidget(self._project_view)
        self.setCentralWidget(self._stack)

        self._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self._find_shortcut.activated.connect(self._focus_filter_box)

        self._load_recent_projects()
        self._refresh_recent_ui()

        self._create_actions()
        self._create_menus()
        self._refresh_recent_ui()
        self._show_placeholder()

    # ------------------------------------------------------------------
    # UI construction helpers
    def _build_placeholder_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addStretch()
        title = QLabel("Welcome to Stromschlag")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        subtitle = QLabel(
            "Create a new icon project or open an existing Stromschlag project file to get started."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        button_row = QHBoxLayout()
        new_button = QPushButton("Create new project")
        new_button.clicked.connect(self._new_project)
        open_folder_button = QPushButton("Open folder…")
        open_folder_button.clicked.connect(self._open_project_folder)
        button_row.addStretch()
        button_row.addWidget(new_button)
        button_row.addWidget(open_folder_button)
        button_row.addStretch()
        layout.addLayout(button_row)
        layout.addSpacing(24)

        recent_label = QLabel("Recent projects")
        recent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        recent_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.itemActivated.connect(self._handle_recent_item_activation)
        layout.addWidget(self._recent_list)

        self._recent_placeholder_label = QLabel("No recent projects yet.")
        self._recent_placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._recent_placeholder_label.setStyleSheet("color: #666666;")
        layout.addWidget(self._recent_placeholder_label)

        layout.addStretch()
        return widget

    def _build_project_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        splitter = QSplitter()
        splitter.addWidget(self._build_icon_list_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_icon_detail_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        layout.addWidget(splitter)
        return container

    def _build_icon_list_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        header = QLabel("Project icons")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        layout.addWidget(self._filter_edit)

        self._icon_tree.currentItemChanged.connect(self._handle_tree_selection)
        self._icon_tree.itemDoubleClicked.connect(self._handle_tree_double_click)
        layout.addWidget(self._icon_tree)

        button_row = QHBoxLayout()
        add_button = QPushButton("Add icon")
        add_button.clicked.connect(self._add_icon)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_icon)
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addStretch()
        layout.addLayout(button_row)
        return panel

    def _handle_filter_change(self, text: str) -> None:
        self._filter_text = text.strip()
        if not self._project_loaded:
            return
        self._refresh_icon_list()

    def _focus_filter_box(self) -> None:
        if not self._project_loaded:
            return
        self._filter_edit.setFocus()
        self._filter_edit.selectAll()

    def _build_preview_panel(self) -> QWidget:
        panel = QGroupBox("Canvas preview")
        layout = QVBoxLayout(panel)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(360, 360)
        layout.addStretch()
        layout.addWidget(self._preview_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return panel

    def _build_icon_detail_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        icon_group = QGroupBox("Icon options")
        form = QFormLayout(icon_group)
        form.addRow("Name", self._icon_name_edit)

        artwork_row = QHBoxLayout()
        artwork_row.addWidget(self._icon_source_path_display)
        self._icon_choose_artwork_button.clicked.connect(self._choose_icon_file)
        artwork_row.addWidget(self._icon_choose_artwork_button)
        form.addRow("Artwork", artwork_row)

        self._icon_apply_button.clicked.connect(self._apply_icon_changes)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self._icon_apply_button)
        form.addRow(button_row)

        layout.addWidget(icon_group)

        metadata_group = QGroupBox("Pack metadata")
        metadata_form = QFormLayout(metadata_group)
        metadata_form.addRow("Name", self._pack_name_edit)
        metadata_form.addRow("Author", self._pack_author_edit)
        metadata_form.addRow("Base theme", self._pack_inherits_edit)
        metadata_form.addRow("Targets", self._pack_targets_edit)
        layout.addWidget(metadata_group)
        layout.addStretch()

        self._set_icon_form_enabled(False)
        return container

    def _create_actions(self) -> None:
        self._new_action = QAction("New Project", self)
        self._new_action.triggered.connect(self._new_project)

        self._open_folder_action = QAction("Open Folder…", self)
        self._open_folder_action.triggered.connect(self._open_project_folder)

        self._metadata_action = QAction("Edit Metadata…", self)
        self._metadata_action.triggered.connect(self._edit_metadata)

        self._export_action = QAction("Export Icon Theme…", self)
        self._export_action.triggered.connect(self._export_pack)

        self._install_user_action = QAction("Install for Current User", self)
        self._install_user_action.triggered.connect(self._install_pack_local)

        self._install_system_action = QAction("Install System-wide", self)
        self._install_system_action.triggered.connect(self._install_pack_system)

    def _create_menus(self) -> None:
        menubar: QMenuBar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self._new_action)
        file_menu.addAction(self._open_folder_action)
        self._recent_menu = file_menu.addMenu("Open Recent")
        file_menu.addSeparator()
        file_menu.addAction(self._export_action)
        file_menu.addSeparator()
        file_menu.addAction(self._install_user_action)
        file_menu.addAction(self._install_system_action)

        options_menu = menubar.addMenu("&Options")
        options_menu.addAction(self._metadata_action)
        self._update_action_states()

    # ------------------------------------------------------------------
    # Recent project helpers
    def _load_recent_projects(self) -> None:
        stored = self._settings_store.value("recentProjects", [])
        if isinstance(stored, str):
            entries = [stored]
        elif isinstance(stored, (list, tuple)):
            entries = [str(item) for item in stored]
        else:
            entries = []
        self._recent_projects = [entry for entry in entries if entry][:10]

    def _persist_recent_projects(self) -> None:
        self._settings_store.setValue("recentProjects", self._recent_projects)

    def _refresh_recent_ui(self) -> None:
        if self._recent_list is not None and self._recent_placeholder_label is not None:
            self._recent_list.blockSignals(True)
            self._recent_list.clear()
            if self._recent_projects:
                for path in self._recent_projects:
                    item = QListWidgetItem(path)
                    item.setData(Qt.ItemDataRole.UserRole, path)
                    self._recent_list.addItem(item)
                self._recent_list.setVisible(True)
                self._recent_placeholder_label.setVisible(False)
            else:
                self._recent_list.setVisible(False)
                self._recent_placeholder_label.setVisible(True)
            self._recent_list.blockSignals(False)

        if self._recent_menu is not None:
            self._recent_menu.clear()
            if not self._recent_projects:
                self._recent_menu.setEnabled(False)
            else:
                self._recent_menu.setEnabled(True)
                for path in self._recent_projects:
                    action = self._recent_menu.addAction(path)
                    action.setData(path)
                    action.triggered.connect(self._handle_recent_action)
                self._recent_menu.addSeparator()
                clear_action = self._recent_menu.addAction("Clear Recent")
                clear_action.triggered.connect(self._clear_recent_projects)

    def _record_recent_project(self, path: Path) -> None:
        target = path if path.is_dir() else path.parent
        path_str = str(target)
        updated = [path_str]
        for existing in self._recent_projects:
            if existing != path_str:
                updated.append(existing)
        self._recent_projects = updated[:10]
        self._persist_recent_projects()
        self._refresh_recent_ui()

    def _handle_recent_item_activation(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        self._open_recent_project(Path(str(path)))

    def _handle_recent_action(self) -> None:
        action = self.sender()
        if not isinstance(action, QAction):
            return
        path = action.data()
        if not path:
            return
        self._open_recent_project(Path(str(path)))

    def _open_recent_project(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Missing project", f"The project '{path}' no longer exists.")
            self._remove_recent_entry(str(path))
            return
        self._load_project_from_path(path)

    def _remove_recent_entry(self, path_str: str) -> None:
        updated = [entry for entry in self._recent_projects if entry != path_str]
        if updated == self._recent_projects:
            return
        self._recent_projects = updated
        self._persist_recent_projects()
        self._refresh_recent_ui()

    def _clear_recent_projects(self) -> None:
        if not self._recent_projects:
            return
        self._recent_projects = []
        self._persist_recent_projects()
        self._refresh_recent_ui()

    def _discover_descriptor(self, directory: Path) -> Path | None:
        preferred = directory / "stromschlag.yaml"
        if preferred.exists():
            return preferred
        fallback = directory / "Stromschlag.yaml"
        if fallback.exists():
            return fallback
        for candidate in directory.glob("**/stromschlag.yaml"):
            return candidate
        return None

    def _build_project_from_directory(self, directory: Path) -> tuple[PackSettings, List[IconDefinition]]:
        entries = self._collect_icon_sources(directory)
        icons = [
            IconDefinition(name=name, source_path=path, category=category)
            for name, path, category in entries
        ]
        settings = PackSettings(
            name=directory.name or "Imported Icon Pack",
            author="Imported",
            inherits="hicolor",
            output_dir=directory.parent,
        )
        return settings, icons

    def _collect_icon_sources(self, directory: Path) -> List[tuple[str, Path, str | None]]:
        allowed = {".png", ".svg", ".svgz"}
        winners: dict[str, tuple[int, Path, str | None]] = {}
        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue
            suffix = file_path.suffix.lower()
            if suffix not in allowed:
                continue
            name = file_path.stem
            normalized_parts = {part.lower() for part in file_path.parts}
            weight = 0
            if suffix not in {".svg", ".svgz"}:
                weight += 1
            if "scalable" not in normalized_parts:
                weight += 2
            if "apps" not in normalized_parts and "mimetypes" not in normalized_parts:
                weight += 1
            existing = winners.get(name)
            if existing and existing[0] <= weight:
                continue
            category = file_path.parent.name if file_path.parent != directory else None
            winners[name] = (weight, file_path, category)
        return [
            (name, data[1], data[2])
            for name, data in sorted(winners.items(), key=lambda item: item[0])
        ]

    # ------------------------------------------------------------------
    # Project lifecycle
    def _show_placeholder(self) -> None:
        self._project_loaded = False
        self._last_export_result = None
        self._stack.setCurrentWidget(self._placeholder_view)
        self._update_action_states()
        self._icon_tree.clear()
        self._category_nodes.clear()
        self._row_to_item = []
        self._filter_edit.clear()
        self._filter_edit.setEnabled(False)
        self._filter_text = ""
        self._preview_label.clear()
        self._set_icon_form_enabled(False)
        self._set_metadata_form_enabled(False)
        self._update_metadata_panel()

    def _show_project_view(self) -> None:
        self._project_loaded = True
        self._stack.setCurrentWidget(self._project_view)
        self._update_action_states()
        self._filter_edit.clear()
        self._filter_text = ""
        self._filter_edit.setEnabled(True)
        self._set_metadata_form_enabled(True)
        self._update_metadata_panel()
        self._refresh_icon_list()

    def _update_action_states(self) -> None:
        state = self._project_loaded
        for action in (
            self._metadata_action,
            self._export_action,
            self._install_user_action,
            self._install_system_action,
        ):
            action.setEnabled(state)

    def _new_project(self) -> None:
        suggestion = load_icon_blueprint()
        result = BaseThemeDialog.prompt(self, default_theme=suggestion.source_theme)
        if result is None:
            QMessageBox.information(
                self,
                "Base required",
                "Creating a project requires choosing a base icon theme.",
            )
            return
        icons, source_theme, inherits, targets = result

        self._settings = PackSettings(
            name="Untitled Icon Pack",
            author="Unknown",
            inherits=inherits or (source_theme or "breeze"),
            targets=targets,
        )
        self._metadata_confirmed = False
        self._icons = icons
        self._last_export_result = None
        self._show_project_view()
        self._announce_theme_source(source_theme)

    def _open_project_folder(self) -> None:
        path_str = QFileDialog.getExistingDirectory(
            self,
            "Select project folder",
            str(Path.home()),
        )
        if not path_str:
            return
        self._load_project_from_path(Path(path_str))

    def _load_project_from_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Missing project", f"The path '{path}' does not exist.")
            self._remove_recent_entry(str(path))
            return
        if path.is_dir():
            self._load_project_from_directory(path)
            return
        self._load_project_file(path)

    def _load_project_file(self, path: Path) -> None:
        try:
            settings, icons = load_project(path)
        except Exception as exc:  # pragma: no cover - filesystem errors
            QMessageBox.critical(self, "Unable to open project", str(exc))
            return
        self._settings = settings
        self._metadata_confirmed = True
        self._icons = icons
        self._last_export_result = None
        self._show_project_view()
        self._record_recent_project(path.parent)

    def _load_project_from_directory(self, directory: Path) -> None:
        descriptor = self._discover_descriptor(directory)
        if descriptor:
            self._load_project_file(descriptor)
            return
        settings, icons = self._build_project_from_directory(directory)
        if not icons:
            QMessageBox.information(
                self,
                "No icons found",
                "The selected folder does not contain any usable icon files.",
            )
            return
        self._settings = settings
        self._metadata_confirmed = False
        self._icons = icons
        self._last_export_result = None
        self._show_project_view()
        self._record_recent_project(directory)
        self.statusBar().showMessage(
            f"Imported {len(icons)} icons from '{directory}'.",
            5000,
        )

    def _announce_theme_source(self, theme_name: str | None) -> None:
        if theme_name:
            self.statusBar().showMessage(
                f"Loaded icons from '{theme_name}'.",
                5000,
            )

    # ------------------------------------------------------------------
    # Icon manipulation
    def _refresh_icon_list(self, select_index: int | None = None) -> None:
        self._icon_tree.blockSignals(True)
        self._icon_tree.clear()
        self._category_nodes.clear()
        self._row_to_item = [None] * len(self._icons)
        filter_text = (self._filter_text or "").lower()
        matching_indices: List[int] = []

        for idx, icon in enumerate(self._icons):
            if filter_text and filter_text not in icon.name.lower():
                continue
            category_key = (icon.category or "other").lower()
            parent = self._category_nodes.get(category_key)
            if parent is None:
                parent = QTreeWidgetItem([self._category_display_name(category_key)])
                parent.setFirstColumnSpanned(True)
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self._icon_tree.addTopLevelItem(parent)
                self._category_nodes[category_key] = parent
            child = QTreeWidgetItem([icon.name])
            child.setData(0, Qt.ItemDataRole.UserRole, idx)
            pixmap = self._icon_pixmap(icon, 32)
            if pixmap is not None:
                child.setIcon(0, QIcon(pixmap))
            parent.addChild(child)
            self._row_to_item[idx] = child
            matching_indices.append(idx)

        self._icon_tree.expandAll()
        self._icon_tree.blockSignals(False)

        if not self._icons:
            self._handle_selection_change(-1)
            return

        if not matching_indices:
            self._icon_tree.setCurrentItem(None)
            self._handle_selection_change(-1)
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("No icons match the current search.")
            return

        if select_index is not None and select_index in matching_indices:
            target = select_index
        else:
            target = matching_indices[0]
        self._select_row(target)

    def _category_display_name(self, key: str) -> str:
        normalized = key.lower() if key else "other"
        return self._CATEGORY_LABELS.get(normalized, normalized.replace("-", " ").title())

    def _select_row(self, row: int) -> None:
        if not (0 <= row < len(self._row_to_item)):
            self._icon_tree.setCurrentItem(None)
            self._handle_selection_change(-1)
            return
        item = self._row_to_item[row]
        if item is None:
            self._handle_selection_change(-1)
            return
        self._icon_tree.setCurrentItem(item)

    def _current_row(self) -> int:
        item = self._icon_tree.currentItem()
        if item is None:
            return -1
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return -1
        try:
            return int(data)
        except (ValueError, TypeError):
            return -1

    def _add_icon(self) -> None:
        name = f"Icon {len(self._icons) + 1}"
        icon = IconDefinition(
            name=name,
            category="custom",
        )
        self._icons.append(icon)
        self._refresh_icon_list(len(self._icons) - 1)

    def _remove_icon(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        self._icons.pop(row)
        if self._icons:
            self._refresh_icon_list(min(row, len(self._icons) - 1))
        else:
            self._icon_tree.clear()
            self._row_to_item = []
            self._handle_selection_change(-1)

    # ------------------------------------------------------------------
    # Selection + preview
    def _handle_tree_selection(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:  # noqa: ARG002 - unused
        row = -1
        if current is not None:
            data = current.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, int):
                row = data
            else:
                try:
                    row = int(data)
                except (TypeError, ValueError):
                    row = -1
        self._handle_selection_change(row)

    def _handle_tree_double_click(self, item: QTreeWidgetItem | None, column: int) -> None:  # noqa: ARG002 - unused
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        try:
            row = int(data)
        except (TypeError, ValueError):
            return
        self._select_row(row)
        self._choose_icon_file()

    def _handle_selection_change(self, row: int) -> None:
        if row < 0 or row >= len(self._icons):
            self._preview_label.setText("Open or create a project, then select an icon to preview")
            self._preview_label.setPixmap(QPixmap())
            self._set_icon_form_enabled(False)
            return
        icon = self._icons[row]
        self._load_icon_into_form(icon)
        self._set_icon_form_enabled(True)
        pixmap = self._icon_pixmap(icon, 360)
        if pixmap is None:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("No artwork selected for this icon.")
            return
        self._preview_label.setText("")
        self._preview_label.setPixmap(pixmap)

    def _load_icon_into_form(self, icon: IconDefinition) -> None:
        self._suppress_form_updates = True
        self._icon_name_edit.setText(icon.name)
        self._icon_source_path_display.setText(str(icon.source_path) if icon.source_path else "")
        self._suppress_form_updates = False

    def _set_icon_form_enabled(self, enabled: bool) -> None:
        for widget in (
            self._icon_name_edit,
            self._icon_source_path_display,
            self._icon_choose_artwork_button,
            self._icon_apply_button,
        ):
            widget.setEnabled(enabled)

    def _set_metadata_form_enabled(self, enabled: bool) -> None:
        for widget in (
            self._pack_name_edit,
            self._pack_author_edit,
            self._pack_inherits_edit,
            self._pack_targets_edit,
        ):
            widget.setEnabled(enabled)

    def _update_metadata_panel(self) -> None:
        self._suppress_metadata_updates = True
        if self._project_loaded and self._settings is not None:
            self._pack_name_edit.setText(self._settings.name)
            self._pack_author_edit.setText(self._settings.author)
            self._pack_inherits_edit.setText(self._settings.inherits)
            self._pack_targets_edit.setText(
                ", ".join(self._settings.targets) if self._settings.targets else ""
            )
        else:
            for field in (
                self._pack_name_edit,
                self._pack_author_edit,
                self._pack_inherits_edit,
                self._pack_targets_edit,
            ):
                field.clear()
        self._suppress_metadata_updates = False

    def _handle_metadata_field_commit(self) -> None:
        if self._suppress_metadata_updates or not self._project_loaded or self._settings is None:
            return
        name = self._pack_name_edit.text().strip() or "Untitled Icon Pack"
        author = self._pack_author_edit.text().strip() or "Unknown"
        inherits = self._pack_inherits_edit.text().strip() or "hicolor"
        raw_targets = self._pack_targets_edit.text().replace(";", ",")
        targets = [part.strip() for part in raw_targets.split(",") if part.strip()]
        if not targets:
            targets = ["gnome", "kde"]
        self._settings.name = name
        self._settings.author = author
        self._settings.inherits = inherits
        self._settings.targets = targets
        self._metadata_confirmed = True
        self._update_metadata_panel()

    def _apply_icon_changes(self) -> None:
        self._commit_icon_name()

    def _choose_icon_file(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        icon = self._icons[row]
        start_dir = icon.source_path.parent if icon.source_path and icon.source_path.exists() else Path.home()
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select artwork",
            str(start_dir),
            "Images (*.png *.svg *.svgz)"
        )
        if not path_str:
            return
        path = Path(path_str)
        icon.source_path = path
        self._icon_source_path_display.setText(str(path))
        self._preview_label.setPixmap(self._icon_pixmap(icon, 360))
        self._refresh_icon_list(row)

    def _handle_name_commit(self) -> None:
        if self._suppress_form_updates:
            return
        self._commit_icon_name()

    def _commit_icon_name(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        name = self._icon_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Icon name is required.")
            self._suppress_form_updates = True
            self._icon_name_edit.setText(self._icons[row].name)
            self._suppress_form_updates = False
            return
        icon = self._icons[row]
        if icon.name == name:
            return
        icon.name = name
        self._refresh_icon_list(row)

    def _icon_pixmap(self, icon: IconDefinition, size: int) -> QPixmap | None:
        if icon.source_path and icon.source_path.exists():
            pixmap = QIcon(str(icon.source_path)).pixmap(size, size)
            if not pixmap.isNull():
                return pixmap
        return None

    # ------------------------------------------------------------------
    # Metadata + export
    def _edit_metadata(self) -> None:
        if not self._project_loaded:
            return
        updated = MetadataDialog.prompt(self, self._settings)
        if updated:
            self._settings = updated
            self._metadata_confirmed = True
            self._update_metadata_panel()

    def _ensure_metadata(self) -> bool:
        if self._settings is None:
            self._settings = PackSettings(name="Untitled Icon Pack", author="Unknown")
        if self._metadata_confirmed and self._settings.name and self._settings.author:
            return True
        updated = MetadataDialog.prompt(self, self._settings)
        if updated:
            self._settings = updated
            self._metadata_confirmed = True
            return True
        return False

    def _export_pack(self) -> None:
        if not self._project_loaded:
            return
        export_result = self._perform_export(prompt_for_directory=True)
        if export_result is None:
            return
        QMessageBox.information(
            self,
            "Export complete",
            f"Icon theme saved to {export_result.pack_root}"
        )

    def _install_pack_local(self) -> None:
        self._install_pack(
            title="Install for current user",
            install_roots=[
                Path.home() / ".local/share/icons",
                Path.home() / ".icons",
            ],
        )

    def _install_pack_system(self) -> None:
        self._install_pack(
            title="Install system-wide",
            install_roots=[
                Path("/usr/share/icons"),
                Path("/usr/local/share/icons"),
            ],
        )

    def _install_pack(self, title: str, install_roots: List[Path]) -> None:
        if not self._project_loaded:
            return
        export_result = self._perform_export(prompt_for_directory=False)
        if export_result is None:
            return
        installed, failures = install_icon_pack(export_result, install_roots)
        message: List[str] = []
        if installed:
            message.append("Installed to:")
            message.extend(f" • {path}" for path in installed)
        if failures:
            if message:
                message.append("")
            message.append("Install errors:")
            message.extend(f" • {path}: {error}" for path, error in failures)
        if not message:
            message = ["No destinations were available for installation."]
        QMessageBox.information(self, title, "\n".join(message))

    def _perform_export(self, *, prompt_for_directory: bool) -> ExportResult | None:
        if not self._ensure_metadata():
            return None
        if not self._icons:
            QMessageBox.information(self, "Add icons", "Create at least one icon first.")
            return None
        assert self._settings is not None  # satisfied by _ensure_metadata
        if prompt_for_directory:
            export_dir = self._prompt_export_directory()
            if export_dir is None:
                return None
            self._settings.output_dir = export_dir
        try:
            export_result = export_icon_pack(self._settings, self._icons)
        except Exception as exc:  # pragma: no cover - filesystem errors
            QMessageBox.critical(self, "Export failed", str(exc))
            return None
        self._record_recent_project(export_result.pack_root)
        self._last_export_result = export_result
        return export_result

    def _prompt_export_directory(self) -> Path | None:
        if self._settings is None:
            default = Path.home()
        else:
            default = self._settings.output_dir
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose export directory",
            str(default),
        )
        if not directory:
            return None
        return Path(directory)


class MetadataDialog(QDialog):
    """Dialog that captures pack metadata for a project."""

    def __init__(self, parent: QWidget | None, settings: PackSettings | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Project metadata")
        self._name_edit = QLineEdit(settings.name if settings else "")
        self._author_edit = QLineEdit(settings.author if settings else "")
        self._description_edit = QPlainTextEdit(settings.description if settings else "")
        self._inherits_combo = QComboBox()
        self._inherits_combo.addItems(["breeze", "papirus", "adwaita", "hicolor"])
        if settings:
            index = self._inherits_combo.findText(settings.inherits)
            if index >= 0:
                self._inherits_combo.setCurrentIndex(index)
        self._sizes_edit = QLineEdit(
            ",".join(str(size) for size in (settings.base_sizes if settings else [16, 24, 32, 48, 64, 128]))
        )
        self._output_dir_edit = QLineEdit(str(settings.output_dir if settings else Path("build")))
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._select_output_directory)

        self._gtk_checkbox = QCheckBox("GTK (GNOME, Cinnamon, Xfce)")
        self._qt_checkbox = QCheckBox("Qt / KDE Plasma")
        existing_targets = set(settings.targets if settings else ["gnome", "kde"])
        self._gtk_checkbox.setChecked("gnome" in existing_targets)
        self._qt_checkbox.setChecked("kde" in existing_targets)

        form = QFormLayout(self)
        form.addRow("Name", self._name_edit)
        form.addRow("Author", self._author_edit)
        form.addRow("Description", self._description_edit)
        form.addRow("Inherits", self._inherits_combo)
        form.addRow("Base sizes", self._sizes_edit)

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_dir_edit)
        output_row.addWidget(browse_button)
        form.addRow("Output", output_row)

        targets_widget = QWidget()
        targets_layout = QVBoxLayout(targets_widget)
        targets_layout.setContentsMargins(0, 0, 0, 0)
        targets_layout.addWidget(self._gtk_checkbox)
        targets_layout.addWidget(self._qt_checkbox)
        form.addRow("Targets", targets_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

        self._result: PackSettings | None = settings

    @staticmethod
    def prompt(parent: QWidget | None, settings: PackSettings | None) -> PackSettings | None:
        dialog = MetadataDialog(parent, settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog._result
        return None

    def _handle_accept(self) -> None:
        name = self._name_edit.text().strip()
        author = self._author_edit.text().strip()
        if not name or not author:
            QMessageBox.warning(self, "Missing fields", "Both name and author are required.")
            return
        sizes: List[int] = []
        for chunk in self._sizes_edit.text().split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                size = int(chunk)
            except ValueError:
                continue
            if size > 0:
                sizes.append(size)
        if not sizes:
            QMessageBox.warning(self, "Invalid sizes", "Provide at least one valid icon size.")
            return
        targets: List[str] = []
        if self._gtk_checkbox.isChecked():
            targets.append("gnome")
        if self._qt_checkbox.isChecked():
            targets.append("kde")
        if not targets:
            QMessageBox.warning(self, "Pick targets", "Select at least one target platform (GTK or Qt).")
            return
        self._result = PackSettings(
            name=name,
            author=author,
            description=self._description_edit.toPlainText().strip(),
            inherits=self._inherits_combo.currentText(),
            base_sizes=sorted(set(sizes)),
            output_dir=Path(self._output_dir_edit.text().strip() or "build"),
            targets=targets,
        )
        self.accept()

    def _select_output_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose output directory")
        if directory:
            self._output_dir_edit.setText(directory)


class BaseThemeDialog(QDialog):
    """Dialog that captures the base theme, inherits value, and target platforms."""

    def __init__(
        self,
        parent: QWidget | None = None,
        default_theme: str | None = None,
        extra_search_paths: Iterable[Path] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose base icon theme")
        self.resize(560, 520)

        self._themes: List[ThemeCandidate] = list_installed_themes(extra_search_paths)
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        for candidate in self._themes:
            item = QListWidgetItem(candidate.name)
            item.setData(Qt.ItemDataRole.UserRole, candidate.path)
            self._list.addItem(item)

        intro = QLabel("Select one of your installed icon packs (or browse to a folder) to inherit from.")
        intro.setWordWrap(True)

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse_for_theme)

        inherits_label = QLabel("Inherits")
        self._inherits_edit = QLineEdit(default_theme or "breeze")

        self._gtk_checkbox = QCheckBox("GTK (GNOME, Cinnamon, Xfce)")
        self._qt_checkbox = QCheckBox("Qt / KDE Plasma")
        self._gtk_checkbox.setChecked(True)
        self._qt_checkbox.setChecked(True)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._handle_accept)
        button_box.rejected.connect(self.reject)

        inherits_row = QHBoxLayout()
        inherits_row.addWidget(inherits_label)
        inherits_row.addWidget(self._inherits_edit)

        targets_widget = QWidget()
        targets_layout = QVBoxLayout(targets_widget)
        targets_layout.setContentsMargins(0, 0, 0, 0)
        targets_layout.addWidget(self._gtk_checkbox)
        targets_layout.addWidget(self._qt_checkbox)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._list)
        layout.addWidget(browse_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(inherits_row)
        layout.addWidget(targets_widget)
        layout.addWidget(button_box)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        if default_theme:
            self._select_theme_by_name(default_theme)

        self._selected_path: Path | None = None
        self._result: tuple[List[IconDefinition], str, str, List[str]] | None = None

    @staticmethod
    def prompt(parent: QWidget | None = None, default_theme: str | None = None) -> tuple[List[IconDefinition], str, str, List[str]] | None:
        dialog = BaseThemeDialog(parent, default_theme=default_theme)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog._result
        return None

    def _select_theme_by_name(self, name: str) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.text().split(" (")[0].lower() == name.lower():
                self._list.setCurrentRow(index)
                if not self._inherits_edit.text().strip():
                    self._inherits_edit.setText(name)
                return

    def _handle_accept(self) -> None:
        path = self._resolve_selection()
        if path is None:
            QMessageBox.warning(self, "Select a theme", "Choose a theme from the list or browse to one.")
            return
        inherits_value = self._inherits_edit.text().strip() or path.name
        targets: List[str] = []
        if self._gtk_checkbox.isChecked():
            targets.append("gnome")
        if self._qt_checkbox.isChecked():
            targets.append("kde")
        if not targets:
            QMessageBox.warning(self, "Pick targets", "Select at least one target platform (GTK or Qt).")
            return
        try:
            icons = load_icons_from_directory(path)
        except Exception as exc:
            QMessageBox.warning(self, "Unable to load theme", str(exc))
            return
        if not icons:
            QMessageBox.warning(
                self,
                "No icons found",
                "The selected folder does not contain any icon assets. Choose another theme.",
            )
            return

        self._result = (icons, path.name, inherits_value, targets)
        self.accept()

    def _resolve_selection(self) -> Path | None:
        item = self._list.currentItem()
        if item is not None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, Path):
                return data
            if data:
                return Path(str(data))
        return self._selected_path

    def _browse_for_theme(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select icon theme folder", str(Path.home()))
        if not directory:
            return
        path = Path(directory)
        label = f"{path.name} ({path})"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, path)
        self._list.addItem(item)
        self._list.setCurrentItem(item)
        self._selected_path = path
        if not self._inherits_edit.text().strip():
            self._inherits_edit.setText(path.name)

