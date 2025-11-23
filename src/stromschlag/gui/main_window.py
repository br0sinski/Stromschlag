"""Main window for the Stromschlag GUI."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
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

from ..core.exporters import export_icon_pack
from ..core.models import IconDefinition, PackSettings
from ..core.project_io import load_project, save_project
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
        self._project_path: Path | None = None
        self._settings: PackSettings | None = None
        self._metadata_confirmed = False
        self._project_loaded = False

        # Project UI widgets created up front
        self._icon_tree = QTreeWidget()
        self._icon_tree.setHeaderHidden(True)
        self._icon_tree.setAnimated(True)
        self._category_nodes: dict[str, QTreeWidgetItem] = {}
        self._row_to_item: List[QTreeWidgetItem | None] = []
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

        self._stack = QStackedWidget()
        self._placeholder_view = self._build_placeholder_view()
        self._project_view = self._build_project_view()
        self._stack.addWidget(self._placeholder_view)
        self._stack.addWidget(self._project_view)
        self.setCentralWidget(self._stack)

        self._create_actions()
        self._create_menus()
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
        open_button = QPushButton("Open project…")
        open_button.clicked.connect(self._open_project)
        button_row.addStretch()
        button_row.addWidget(new_button)
        button_row.addWidget(open_button)
        button_row.addStretch()
        layout.addLayout(button_row)
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
        panel = QGroupBox("Icon options")
        form = QFormLayout(panel)
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

        self._set_icon_form_enabled(False)
        return panel

    def _create_actions(self) -> None:
        self._new_action = QAction("New Project", self)
        self._new_action.triggered.connect(self._new_project)

        self._open_action = QAction("Open Project…", self)
        self._open_action.triggered.connect(self._open_project)

        self._save_action = QAction("Save Project", self)
        self._save_action.triggered.connect(self._save_project)

        self._save_as_action = QAction("Save Project As…", self)
        self._save_as_action.triggered.connect(self._save_project_as)

        self._metadata_action = QAction("Edit Metadata…", self)
        self._metadata_action.triggered.connect(self._edit_metadata)

        self._export_action = QAction("Export Icon Theme…", self)
        self._export_action.triggered.connect(self._export_pack)

    def _create_menus(self) -> None:
        menubar: QMenuBar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self._new_action)
        file_menu.addAction(self._open_action)
        file_menu.addSeparator()
        file_menu.addAction(self._save_action)
        file_menu.addAction(self._save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self._export_action)

        options_menu = menubar.addMenu("&Options")
        options_menu.addAction(self._metadata_action)
        self._update_action_states()

    # ------------------------------------------------------------------
    # Project lifecycle
    def _show_placeholder(self) -> None:
        self._project_loaded = False
        self._stack.setCurrentWidget(self._placeholder_view)
        self._update_action_states()
        self._icon_tree.clear()
        self._category_nodes.clear()
        self._row_to_item = []
        self._preview_label.clear()
        self._set_icon_form_enabled(False)

    def _show_project_view(self) -> None:
        self._project_loaded = True
        self._stack.setCurrentWidget(self._project_view)
        self._update_action_states()
        self._refresh_icon_list()

    def _update_action_states(self) -> None:
        state = self._project_loaded
        for action in (self._save_action, self._save_as_action, self._metadata_action, self._export_action):
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

        self._project_path = None
        self._settings = PackSettings(
            name="Untitled Icon Pack",
            author="Unknown",
            inherits=inherits or (source_theme or "breeze"),
            targets=targets,
        )
        self._metadata_confirmed = False
        self._icons = icons
        self._show_project_view()
        self._announce_theme_source(source_theme)

    def _open_project(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Stromschlag project",
            str(Path.home()),
            "Stromschlag Projects (*.yaml *.yml)"
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            settings, icons = load_project(path)
        except Exception as exc:  # pragma: no cover - filesystem errors
            QMessageBox.critical(self, "Unable to open project", str(exc))
            return
        self._project_path = path
        self._settings = settings
        self._metadata_confirmed = True
        self._icons = icons
        self._show_project_view()

    def _announce_theme_source(self, theme_name: str | None) -> None:
        if theme_name:
            self.statusBar().showMessage(
                f"Loaded icons from '{theme_name}'.",
                5000,
            )

    def _save_project(self) -> None:
        if not self._project_loaded or not self._settings:
            return
        if not self._project_path:
            self._save_project_as()
            return
        try:
            save_project(self._project_path, self._settings, self._icons)
        except Exception as exc:  # pragma: no cover - filesystem errors
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        QMessageBox.information(self, "Project saved", f"Saved to {self._project_path}")

    def _save_project_as(self) -> None:
        if not self._settings:
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stromschlag project",
            str(self._project_path or Path.home()),
            "Stromschlag Projects (*.yaml)"
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() not in {".yaml", ".yml"}:
            path = path.with_suffix(".yaml")
        try:
            save_project(path, self._settings, self._icons)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._project_path = path
        QMessageBox.information(self, "Project saved", f"Saved to {path}")

    # ------------------------------------------------------------------
    # Icon manipulation
    def _refresh_icon_list(self, select_index: int | None = None) -> None:
        self._icon_tree.blockSignals(True)
        self._icon_tree.clear()
        self._category_nodes.clear()
        self._row_to_item = [None] * len(self._icons)

        for idx, icon in enumerate(self._icons):
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

        self._icon_tree.expandAll()
        self._icon_tree.blockSignals(False)

        if not self._icons:
            self._handle_selection_change(-1)
            return

        target = select_index if select_index is not None else 0
        target = max(0, min(target, len(self._icons) - 1))
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
        if not self._ensure_metadata():
            return
        if not self._icons:
            QMessageBox.information(self, "Add icons", "Create at least one icon first.")
            return
        export_dir = self._prompt_export_directory()
        if export_dir is None:
            return
        assert self._settings is not None  # satisfied by _ensure_metadata
        self._settings.output_dir = export_dir
        try:
            target = export_icon_pack(self._settings, self._icons)
        except Exception as exc:  # pragma: no cover - filesystem errors
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Export complete",
            f"Icon theme saved to {target}"
        )

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

