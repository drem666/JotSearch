import sys
import os
import re
import json
import platform
import subprocess
import zipfile
import requests
import shutil
import stat
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QLabel, QPushButton, QFileDialog, QLineEdit, QCheckBox,
    QComboBox, QMessageBox, QStatusBar, QGroupBox, QGridLayout, QMenuBar,
    QMenu, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QRadioButton,
    QButtonGroup, QScrollArea, QFrame, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QSplitter, QToolButton
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QAction, QColor, QTextCharFormat, QSyntaxHighlighter, QIcon

# ── Pygments (optional, graceful fallback) ──────────────────────────────────
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer, get_all_lexers
    from pygments.formatters import HtmlFormatter
    PYGMENTS_OK = True
except ImportError:
    PYGMENTS_OK = False


# ════════════════════════════════════════════════════════════════════════════
#  SYNTAX HIGHLIGHTER  (Pygments → QSyntaxHighlighter bridge)
# ════════════════════════════════════════════════════════════════════════════
class PygmentsHighlighter(QSyntaxHighlighter):
    def __init__(self, document, lexer_name="markdown"):
        super().__init__(document)
        self._lexer_name = lexer_name
        self._update_lexer()

    def _update_lexer(self):
        try:
            from pygments.lexers import get_lexer_by_name
            from pygments.token import Token
            self._lexer = get_lexer_by_name(self._lexer_name, stripall=False)
            self._token_map = {
                Token.Keyword: ("#c678dd", True, False),
                Token.Keyword.Declaration: ("#c678dd", True, False),
                Token.Keyword.Namespace: ("#c678dd", True, False),
                Token.Name.Builtin: ("#e5c07b", False, False),
                Token.Name.Function: ("#61afef", False, False),
                Token.Name.Class: ("#e5c07b", True, False),
                Token.Name.Decorator: ("#e5c07b", False, False),
                Token.Literal.String: ("#98c379", False, False),
                Token.Literal.String.Doc: ("#98c379", False, True),
                Token.Literal.Number: ("#d19a66", False, False),
                Token.Comment: ("#5c6370", False, True),
                Token.Comment.Single: ("#5c6370", False, True),
                Token.Comment.Multiline: ("#5c6370", False, True),
                Token.Operator: ("#56b6c2", False, False),
                Token.Punctuation: ("#abb2bf", False, False),
                Token.Generic.Heading: ("#61afef", True, False),
                Token.Generic.Strong: (None, True, False),
                Token.Generic.Emph: (None, False, True),
            }
        except Exception:
            self._lexer = None

    def set_language(self, name):
        self._lexer_name = name
        self._update_lexer()
        self.rehighlight()

    def highlightBlock(self, text):
        if not PYGMENTS_OK or self._lexer is None:
            return
        try:
            from pygments.token import Token
            from pygments import lex
            col = 0
            for ttype, value in lex(text, self._lexer):
                length = len(value)
                fmt = QTextCharFormat()
                # Walk up the token hierarchy
                t = ttype
                while t:
                    if t in self._token_map:
                        color, bold, italic = self._token_map[t]
                        if color:
                            fmt.setForeground(QColor(color))
                        if bold:
                            fmt.setFontWeight(QFont.Bold)
                        if italic:
                            fmt.setFontItalic(True)
                        break
                    t = t.parent if hasattr(t, 'parent') and t.parent != t else None
                self.setFormat(col, length, fmt)
                col += length
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
#  FILE TREE PICKER DIALOG  (tristate checkbox propagation)
# ════════════════════════════════════════════════════════════════════════════
class FolderTreeDialog(QDialog):
    def __init__(self, parent=None, initial_paths=None):
        super().__init__(parent)
        self.setWindowTitle("Select Folders")
        self.resize(600, 500)
        self._building = False

        layout = QVBoxLayout(self)

        # Root chooser
        root_row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Root directory to browse…")
        browse_btn = QPushButton("Browse Root")
        browse_btn.clicked.connect(self._pick_root)
        root_row.addWidget(self.root_edit)
        root_row.addWidget(browse_btn)
        layout.addLayout(root_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Folders")
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if initial_paths:
            root = str(Path(initial_paths[0]).parent) if initial_paths else str(Path.home())
            self.root_edit.setText(root)
            self._populate(root)

    def _pick_root(self):
        d = QFileDialog.getExistingDirectory(self, "Select Root Directory")
        if d:
            self.root_edit.setText(d)
            self._populate(d)

    def _populate(self, root):
        self._building = True
        self.tree.clear()
        root_item = self._make_item(Path(root))
        self.tree.addTopLevelItem(root_item)
        self._add_children(root_item, Path(root), depth=0, max_depth=3)
        root_item.setExpanded(True)
        self._building = False

    def _make_item(self, path: Path):
        item = QTreeWidgetItem([path.name or str(path)])
        item.setData(0, Qt.UserRole, str(path))
        item.setCheckState(0, Qt.Unchecked)
        # NOTE: do NOT use Qt.ItemIsAutoTristate — it conflicts with manual propagation
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        return item

    def _add_children(self, parent_item, path: Path, depth, max_depth):
        if depth >= max_depth:
            return
        try:
            subdirs = sorted([p for p in path.iterdir() if p.is_dir() and not p.name.startswith('.')])
        except PermissionError:
            return
        for sub in subdirs:
            child = self._make_item(sub)
            parent_item.addChild(child)
            self._add_children(child, sub, depth + 1, max_depth)

    def _on_item_changed(self, item, column):
        if self._building:
            return
        self._building = True
        self.tree.blockSignals(True)
        try:
            state = item.checkState(0)
            # Only propagate down when the user explicitly checked/unchecked
            # (not when we set PartiallyChecked internally)
            if state in (Qt.Checked, Qt.Unchecked):
                self._propagate_down(item, state)
            self._propagate_up(item)
        finally:
            self.tree.blockSignals(False)
            self._building = False

    def _propagate_down(self, item, state):
        """Recursively set all descendants to the same binary state."""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._propagate_down(child, state)

    def _propagate_up(self, item):
        """Walk up the tree recalculating parent states from children."""
        parent = item.parent()
        if parent is None:
            return
        total = parent.childCount()
        checked = 0
        partial = 0
        for i in range(total):
            s = parent.child(i).checkState(0)
            if s == Qt.Checked:
                checked += 1
            elif s == Qt.PartiallyChecked:
                partial += 1
        if checked == total:
            parent.setCheckState(0, Qt.Checked)
        elif checked == 0 and partial == 0:
            parent.setCheckState(0, Qt.Unchecked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)
        # Continue walking up — but guard: don't recurse into the item we just changed
        self._propagate_up(parent)

    def get_selected_folders(self):
        result = []
        self._collect_checked(self.tree.invisibleRootItem(), result)
        return result

    def _collect_checked(self, item, result):
        for i in range(item.childCount()):
            child = item.child(i)
            if child.checkState(0) == Qt.Checked:
                result.append(child.data(0, Qt.UserRole))
            else:
                self._collect_checked(child, result)


# ════════════════════════════════════════════════════════════════════════════
#  SETTINGS DIALOG
# ════════════════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None, config_path=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self.config = config or {}
        self.config_path = config_path

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Default mode
        self.default_mode_combo = QComboBox()
        self.default_mode_combo.addItems(["Single File", "Multiple Files", "Single Folder (All Files)", "Multiple Folders"])
        self.default_mode_combo.setCurrentText(self.config.get("default_mode", "Single File"))
        form.addRow("Default Search Mode:", self.default_mode_combo)

        # Remember last mode
        self.remember_mode_chk = QCheckBox("Use last selected mode on startup")
        self.remember_mode_chk.setChecked(self.config.get("remember_last_mode", False))
        form.addRow("", self.remember_mode_chk)

        # Extension profiles
        ext_group = QGroupBox("Extension Profiles")
        ext_layout = QVBoxLayout()
        profiles = self.config.get("extension_profiles", {"default": "txt,md,py,js,html,css"})
        self.profile_combos = {}
        profile_form = QFormLayout()
        self.default_profile_combo = QComboBox()
        self.default_profile_combo.addItems(list(profiles.keys()))
        self.default_profile_combo.setCurrentText(self.config.get("active_profile", "default"))
        profile_form.addRow("Active Profile:", self.default_profile_combo)

        self.profiles_edit = QTextEdit()
        self.profiles_edit.setMaximumHeight(100)
        self.profiles_edit.setPlaceholderText('{"default": "txt,md,py", "web": "html,css,js"}')
        self.profiles_edit.setPlainText(json.dumps(profiles, indent=2))
        profile_form.addRow("Profiles (JSON):", self.profiles_edit)
        ext_layout.addLayout(profile_form)
        ext_group.setLayout(ext_layout)

        # Scratchpad directory
        scratch_row = QHBoxLayout()
        self.scratch_dir_edit = QLineEdit(self.config.get("scratchpad_dir", ""))
        self.scratch_dir_edit.setPlaceholderText("Default: script folder")
        scratch_browse = QPushButton("Browse")
        scratch_browse.clicked.connect(self._pick_scratch_dir)
        scratch_row.addWidget(self.scratch_dir_edit)
        scratch_row.addWidget(scratch_browse)
        form.addRow("Scratchpad Directory:", scratch_row)

        # Autosave
        autosave_group = QGroupBox("Autosave")
        as_layout = QFormLayout()
        self.autosave_mode_combo = QComboBox()
        self.autosave_mode_combo.addItems(["Timed", "On Change"])
        self.autosave_mode_combo.setCurrentText(self.config.get("autosave_mode", "Timed"))
        as_layout.addRow("Autosave Mode:", self.autosave_mode_combo)

        self.autosave_interval = QSpinBox()
        self.autosave_interval.setRange(1, 300)
        self.autosave_interval.setValue(self.config.get("autosave_interval_sec", 30))
        self.autosave_interval.setSuffix(" sec")
        as_layout.addRow("Timed Interval:", self.autosave_interval)
        autosave_group.setLayout(as_layout)

        layout.addLayout(form)
        layout.addWidget(ext_group)
        layout.addWidget(autosave_group)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_scratch_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Scratchpad Directory")
        if d:
            self.scratch_dir_edit.setText(d)

    def _save(self):
        try:
            profiles = json.loads(self.profiles_edit.toPlainText())
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Invalid JSON", "Extension profiles must be valid JSON.")
            return
        self.config["default_mode"] = self.default_mode_combo.currentText()
        self.config["remember_last_mode"] = self.remember_mode_chk.isChecked()
        self.config["extension_profiles"] = profiles
        self.config["active_profile"] = self.default_profile_combo.currentText()
        self.config["scratchpad_dir"] = self.scratch_dir_edit.text().strip()
        self.config["autosave_mode"] = self.autosave_mode_combo.currentText()
        self.config["autosave_interval_sec"] = self.autosave_interval.value()
        if self.config_path:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        self.accept()


# ════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ════════════════════════════════════════════════════════════════════════════
class JotSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JotSearch v2.0")
        self.resize(1200, 800)

        self.script_dir = Path(__file__).parent
        self.config_dir = self.script_dir / "config"
        self.config_dir.mkdir(exist_ok=True)
        self.settings_path = self.config_dir / "settings.json"
        self.themes_path = self.config_dir / "themes.qss"

        self.settings = self._load_settings()
        self.themes = self._parse_themes()
        self.current_theme = self.settings.get("last_theme", next(iter(self.themes), "Dark"))

        self.rg_path = self.setup_ripgrep()
        self.search_paths = []
        self.current_scratchpad_file = None
        self.autosave_enabled = False
        self.highlighter = None

        self.autosave_timer = QTimer()
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.autosave_now)

        self.init_ui()
        self.apply_theme(self.current_theme)
        self._apply_startup_settings()
        self._restore_geometry()

    # ── Settings ─────────────────────────────────────────────────────────
    def _load_settings(self):
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "default_mode": "Single File",
            "remember_last_mode": False,
            "last_mode": "Single File",
            "extension_profiles": {"default": "txt,md,py,js,html,css", "web": "html,css,js,ts", "docs": "txt,md,rst"},
            "active_profile": "default",
            "scratchpad_dir": "",
            "autosave_mode": "Timed",
            "autosave_interval_sec": 30,
            "last_theme": "Dark"
        }

    def _save_settings(self):
        self.config_dir.mkdir(exist_ok=True)
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2)

    def _apply_startup_settings(self):
        # Apply default or last mode
        if self.settings.get("remember_last_mode"):
            mode_name = self.settings.get("last_mode", self.settings.get("default_mode", "Single File"))
        else:
            mode_name = self.settings.get("default_mode", "Single File")
        modes = ["Single File", "Multiple Files", "Single Folder (All Files)", "Multiple Folders"]
        if mode_name in modes:
            self.mode_combo.setCurrentText(mode_name)

        # Apply active extension profile
        profiles = self.settings.get("extension_profiles", {})
        active = self.settings.get("active_profile", "default")
        if active in profiles:
            self.ext_entry.setText(profiles[active])

    # ── Theme parsing ─────────────────────────────────────────────────────
    def _parse_themes(self):
        themes = {}
        if not self.themes_path.exists():
            return themes
        try:
            content = self.themes_path.read_text(encoding='utf-8')
            pattern = re.compile(r'/\*Theme:\s*(.+?)\s*\*/(.*?)/\*Theme End\*/', re.DOTALL)
            for match in pattern.finditer(content):
                name = match.group(1).strip()
                qss = match.group(2).strip()
                themes[name] = qss
        except Exception:
            pass
        return themes

    # ── Ripgrep setup ─────────────────────────────────────────────────────
    def setup_ripgrep(self):
        system = platform.system()
        arch = platform.machine()
        platform_map = {
            "Windows": "x86_64-pc-windows-msvc",
            "Darwin": "aarch64-apple-darwin" if "arm" in arch.lower() else "x86_64-apple-darwin",
            "Linux": "x86_64-unknown-linux-musl"
        }
        bin_dir = self.script_dir / "bin"
        bin_dir.mkdir(exist_ok=True)
        exe_name = "rg.exe" if system == "Windows" else "rg"
        rg_path = bin_dir / exe_name
        if shutil.which("rg"):
            return "rg"
        if rg_path.exists():
            return str(rg_path)
        msg = QMessageBox()
        msg.setText("Ripgrep not found. Download portable version?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec() == QMessageBox.No:
            return None
        try:
            version = "14.1.0"
            platform_str = platform_map.get(system)
            url = f"https://github.com/BurntSushi/ripgrep/releases/download/{version}/ripgrep-{version}-{platform_str}.zip"
            zip_path = bin_dir / "rg.zip"
            with requests.get(url, stream=True) as r:
                with open(zip_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            with zipfile.ZipFile(zip_path, 'r') as z:
                for file in z.namelist():
                    if file.endswith(exe_name):
                        z.extract(file, bin_dir)
                        extracted = bin_dir / file
                        extracted.rename(rg_path)
                        break
            if system != "Windows":
                rg_path.chmod(rg_path.stat().st_mode | stat.S_IEXEC)
            zip_path.unlink()
            return str(rg_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Ripgrep install failed: {e}")
            return None

    # ── UI init ───────────────────────────────────────────────────────────
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._build_menubar()

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.search_tab = QWidget()
        self.scratch_tab = QWidget()
        self.tabs.addTab(self.search_tab, "🔍 Search")
        self.tabs.addTab(self.scratch_tab, "📝 Scratchpad")

        self.init_search_tab()
        self.init_scratchpad_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_menubar(self):
        from PySide6.QtWidgets import QToolBar, QWidgetAction
        mb = self.menuBar()

        # ── View menu (also has theme submenu for keyboard navigation) ──
        view_menu = mb.addMenu("View")
        for name in self.themes:
            act = QAction(name, self)
            act.triggered.connect(lambda checked=False, n=name: self.apply_theme(n))
            view_menu.addAction(act)

        # ── Theme combo + gear directly embedded in the menu bar ──
        # We use a QToolBar docked at the top so widgets sit right on the bar.
        self._top_toolbar = self.addToolBar("ThemeBar")
        self._top_toolbar.setMovable(False)
        self._top_toolbar.setFloatable(False)
        self._top_toolbar.setStyleSheet("QToolBar { spacing: 4px; padding: 2px 6px; border: none; }")

        lbl = QLabel("  Theme:")
        self._top_toolbar.addWidget(lbl)

        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(130)
        self.theme_combo.setToolTip("Switch UI theme instantly")
        if self.themes:
            self.theme_combo.addItems(list(self.themes.keys()))
            idx = self.theme_combo.findText(self.current_theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
        else:
            self.theme_combo.addItem("No themes found")
            self.theme_combo.setEnabled(False)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self._top_toolbar.addWidget(self.theme_combo)

        self._top_toolbar.addSeparator()

        gear_btn = QToolButton()
        gear_btn.setText("⚙")
        gear_btn.setToolTip("Settings")
        gear_btn.setMinimumWidth(32)
        gear_btn.clicked.connect(self.open_settings)
        self._top_toolbar.addWidget(gear_btn)

    def _on_theme_changed(self, name):
        if name and name in self.themes:
            self.apply_theme(name)

    # ── Search tab ────────────────────────────────────────────────────────
    def init_search_tab(self):
        layout = QVBoxLayout()

        # Search mode (Command / Regular)
        search_mode_box = QGroupBox("Search Mode")
        sm_layout = QHBoxLayout()
        self.cmd_mode_radio = QRadioButton("Command Mode")
        self.cmd_mode_radio.setToolTip("Search for command patterns (regex-aware, line-start anchored)")
        self.reg_mode_radio = QRadioButton("Regular Mode")
        self.reg_mode_radio.setToolTip("Search for any phrase in files (plain text)")
        self.cmd_mode_radio.setChecked(True)
        self.search_mode_group = QButtonGroup()
        self.search_mode_group.addButton(self.cmd_mode_radio)
        self.search_mode_group.addButton(self.reg_mode_radio)
        sm_layout.addWidget(self.cmd_mode_radio)
        sm_layout.addWidget(self.reg_mode_radio)
        sm_layout.addStretch()
        search_mode_box.setLayout(sm_layout)

        # File mode selector
        mode_box = QGroupBox("Select Target")
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Single File", "Multiple Files", "Single Folder (All Files)", "Multiple Folders"])
        self.mode_combo.currentIndexChanged.connect(self.update_selection_mode)
        mode_layout.addWidget(self.mode_combo)
        self.pick_btn = QPushButton("Select")
        self.pick_btn.clicked.connect(self.pick_target)
        mode_layout.addWidget(self.pick_btn)
        mode_box.setLayout(mode_layout)

        self.path_label = QLabel("No files/folders selected")
        self.path_label.setWordWrap(True)

        options_box = QGroupBox("Options")
        grid = QGridLayout()
        self.show_paths = QCheckBox("Show File Paths")
        self.show_paths.setChecked(True)
        self.unique_cmds = QCheckBox("Unique Results Only")
        self.recurse = QCheckBox("Recurse Subfolders")
        self.case_sensitive = QCheckBox("Case Sensitive")
        grid.addWidget(self.show_paths, 0, 0)
        grid.addWidget(self.unique_cmds, 0, 1)
        grid.addWidget(self.recurse, 1, 0)
        grid.addWidget(self.case_sensitive, 1, 1)
        grid.addWidget(QLabel("Extensions (comma-separated):"), 2, 0)
        self.ext_entry = QLineEdit("txt,md,py,js,html,css")
        grid.addWidget(self.ext_entry, 2, 1)
        options_box.setLayout(grid)

        search_row = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Enter search query…")
        self.search_entry.returnPressed.connect(self.run_search)
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("btn_search")
        self.search_btn.clicked.connect(self.run_search)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("btn_clear")
        self.clear_btn.clicked.connect(lambda: self.results_box.clear())
        search_row.addWidget(self.search_entry)
        search_row.addWidget(self.search_btn)
        search_row.addWidget(self.clear_btn)

        self.results_box = QTextEdit()
        self.results_box.setReadOnly(True)
        self.results_box.setFont(QFont("Consolas", 10))

        layout.addWidget(search_mode_box)
        layout.addWidget(mode_box)
        layout.addWidget(self.path_label)
        layout.addWidget(options_box)
        layout.addLayout(search_row)
        layout.addWidget(self.results_box)
        self.search_tab.setLayout(layout)

    # ── Scratchpad tab ────────────────────────────────────────────────────
    def init_scratchpad_tab(self):
        layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.new_btn.setObjectName("btn_new")
        self.open_btn = QPushButton("Open")
        self.open_btn.setObjectName("btn_open")
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("btn_save")
        self.saveas_btn = QPushButton("Save As")
        self.saveas_btn.setObjectName("btn_saveas")
        self.autosave_chk = QCheckBox("Autosave")

        for b in [self.new_btn, self.open_btn, self.save_btn, self.saveas_btn]:
            btn_row.addWidget(b)
        btn_row.addWidget(self.autosave_chk)

        # Language selector for syntax highlighting
        btn_row.addStretch()
        btn_row.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumWidth(120)
        self._populate_language_combo()
        self.lang_combo.currentTextChanged.connect(self._on_language_changed)
        btn_row.addWidget(self.lang_combo)

        self.new_btn.clicked.connect(self.new_scratchpad)
        self.open_btn.clicked.connect(self.open_scratchpad)
        self.save_btn.clicked.connect(self.save_scratchpad)
        self.saveas_btn.clicked.connect(self.save_scratchpad_as)
        self.autosave_chk.stateChanged.connect(self.toggle_autosave)

        self.notes_box = QTextEdit()
        self.notes_box.setFont(QFont("Cascadia Code, Consolas, Courier New", 11))
        self.notes_box.textChanged.connect(self.schedule_autosave)

        layout.addLayout(btn_row)
        layout.addWidget(self.notes_box)
        self.scratch_tab.setLayout(layout)

        # Init highlighter AFTER combo is populated so initial language is applied
        if PYGMENTS_OK:
            self.highlighter = PygmentsHighlighter(self.notes_box.document(), "markdown")
            # Trigger the combo signal now that highlighter exists
            self._on_language_changed(self.lang_combo.currentText())

    def _populate_language_combo(self):
        self.lang_combo.addItem("Plain Text", "text")
        if not PYGMENTS_OK:
            return
        common = [
            ("Markdown", "markdown"), ("Python", "python"), ("JavaScript", "javascript"),
            ("TypeScript", "typescript"), ("HTML", "html"), ("CSS", "css"),
            ("JSON", "json"), ("YAML", "yaml"), ("XML", "xml"),
            ("Bash/Shell", "bash"), ("SQL", "sql"), ("C", "c"),
            ("C++", "cpp"), ("C#", "csharp"), ("Java", "java"),
            ("Rust", "rust"), ("Go", "go"), ("Ruby", "ruby"),
            ("PHP", "php"), ("Kotlin", "kotlin"), ("Swift", "swift"),
            ("R", "r"), ("TOML", "toml"), ("Dockerfile", "docker"),
        ]
        for label, alias in common:
            self.lang_combo.addItem(label, alias)
        # Default to Markdown
        idx = self.lang_combo.findData("markdown")
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

    def _on_language_changed(self, text):
        """Called when user manually changes the dropdown OR auto-detect sets it.
        Always applies the chosen language to the highlighter."""
        if not PYGMENTS_OK or self.highlighter is None:
            return
        alias = self.lang_combo.currentData()
        if not alias or alias == "text":
            # Plain text — detach highlighter by setting a non-existent lexer gracefully
            self.highlighter.set_language("text")
        else:
            self.highlighter.set_language(alias)

    def _autodetect_language(self, filepath: str):
        """Set the language combo based on file extension. Called on file open.
        The user can override afterwards via the dropdown."""
        ext_map = {
            ".md": "markdown", ".markdown": "markdown",
            ".py": "python", ".pyw": "python",
            ".js": "javascript", ".mjs": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
            ".html": "html", ".htm": "html",
            ".css": "css", ".scss": "css",
            ".json": "json", ".jsonc": "json",
            ".yaml": "yaml", ".yml": "yaml",
            ".xml": "xml", ".svg": "xml",
            ".sh": "bash", ".bash": "bash", ".zsh": "bash",
            ".sql": "sql",
            ".c": "c", ".h": "c",
            ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
            ".cs": "csharp",
            ".java": "java",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".kt": "kotlin",
            ".swift": "swift",
            ".r": "r", ".R": "r",
            ".toml": "toml",
            ".txt": "text",
        }
        ext = Path(filepath).suffix.lower()
        alias = ext_map.get(ext)
        if not alias:
            return  # unknown extension — leave current selection
        idx = self.lang_combo.findData(alias)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

    # ── Target picking ────────────────────────────────────────────────────
    def pick_target(self):
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            f, _ = QFileDialog.getOpenFileName(self, "Select File")
            if f:
                self.search_paths = [f]
        elif mode == 1:
            files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
            if files:
                self.search_paths = files
        elif mode == 2:
            folder = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder:
                self.search_paths = [folder]
        elif mode == 3:
            dlg = FolderTreeDialog(self, self.search_paths or None)
            if dlg.exec() == QDialog.Accepted:
                selected = dlg.get_selected_folders()
                if selected:
                    self.search_paths = selected

        if self.search_paths:
            shown = " | ".join(self.search_paths[:3])
            if len(self.search_paths) > 3:
                shown += f" … (+{len(self.search_paths) - 3} more)"
            self.path_label.setText(f"<b>Selected:</b> {shown}")
        else:
            self.path_label.setText("No files/folders selected")
        self.status_bar.showMessage(f"Selected {len(self.search_paths)} path(s)")

    def update_selection_mode(self):
        self.search_paths.clear()
        self.path_label.setText("No files/folders selected")
        # Save last mode
        self.settings["last_mode"] = self.mode_combo.currentText()
        self._save_settings()

    # ── Search execution ──────────────────────────────────────────────────
    def run_search(self):
        query = self.search_entry.text().strip()
        if not query or not self.search_paths:
            self.status_bar.showMessage("Please enter a query and select paths.")
            return
        if not self.rg_path:
            self.status_bar.showMessage("Ripgrep not available.")
            return

        is_command_mode = self.cmd_mode_radio.isChecked()

        results = []
        seen = set()
        for path in self.search_paths:
            cmd = [self.rg_path, "--color=never", "--line-number"]

            if not self.case_sensitive.isChecked():
                cmd.append("--ignore-case")

            mode = self.mode_combo.currentIndex()
            if mode == 2:
                cmd += ["--max-depth", "1"]
            elif mode == 3 and self.recurse.isChecked():
                cmd.append("--hidden")

            exts = [e.strip() for e in self.ext_entry.text().split(',') if e.strip()]
            if exts:
                cmd += ["--type-add", f"custom:*.{{{','.join(exts)}}}", "--type", "custom"]

            if is_command_mode:
                # Command mode: regex search — matches query word anywhere on the line
                # e.g. "docker" matches "wsl -d docker-desktop" AND "docker run ..."
                # Users can still enter raw regex patterns like "docker\s+run"
                pattern = re.escape(query)
            else:
                # Regular mode: plain fixed-string, matches any text occurrence
                cmd += ["--fixed-strings"]
                pattern = query

            cmd += [pattern, path]

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
                out = proc.stdout.strip()
                if out:
                    for line in out.splitlines():
                        line = line.strip()
                        if not line or line.endswith(":"):
                            continue
                        if self.unique_cmds.isChecked() and line in seen:
                            continue
                        seen.add(line)

                        parts = line.split(":", 2)
                        if self.show_paths.isChecked() or mode == 0:
                            results.append(line)
                        else:
                            if len(parts) == 3:
                                results.append(parts[2].strip())
                            elif len(parts) == 2:
                                results.append(parts[1].strip())
                            else:
                                results.append(line)
            except Exception as e:
                results.append(f"[Error searching {path}]: {e}")

        mode_label = "Command" if is_command_mode else "Regular"
        output = "\n".join(results) if results else "No results found."
        self.results_box.setPlainText(output)
        self.status_bar.showMessage(
            f"[{mode_label} mode] Search done at {datetime.now().strftime('%H:%M:%S')} — {len(results)} result(s)"
        )

    # ── Scratchpad actions ────────────────────────────────────────────────
    def _scratch_default_dir(self):
        d = self.settings.get("scratchpad_dir", "").strip()
        return d if d and Path(d).is_dir() else str(self.script_dir)

    def new_scratchpad(self):
        self.notes_box.clear()
        self.current_scratchpad_file = None
        self.status_bar.showMessage("New scratchpad.")

    def open_scratchpad(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Open File", self._scratch_default_dir(),
            "Markdown (*.md);;Text Files (*.txt);;All Files (*)"
        )
        if f:
            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                self.notes_box.setPlainText(fh.read())
            self.current_scratchpad_file = f
            self.status_bar.showMessage(f"Loaded: {f}")
            if PYGMENTS_OK:
                self._autodetect_language(f)

    def save_scratchpad(self):
        if self.current_scratchpad_file:
            with open(self.current_scratchpad_file, 'w', encoding='utf-8') as fh:
                fh.write(self.notes_box.toPlainText())
            self.status_bar.showMessage(f"Saved: {self.current_scratchpad_file}")
        else:
            self.save_scratchpad_as()

    def save_scratchpad_as(self):
        f, _ = QFileDialog.getSaveFileName(
            self, "Save As", self._scratch_default_dir(),
            "Markdown (*.md);;Text Files (*.txt)"
        )
        if f:
            # Ensure proper extension
            if not (f.endswith(".md") or f.endswith(".txt")):
                f += ".md"
            self.current_scratchpad_file = f
            self.save_scratchpad()

    def toggle_autosave(self):
        self.autosave_enabled = self.autosave_chk.isChecked()
        self.status_bar.showMessage("Autosave " + ("ON" if self.autosave_enabled else "OFF"))

    def schedule_autosave(self):
        if not self.autosave_enabled or not self.current_scratchpad_file:
            return
        mode = self.settings.get("autosave_mode", "Timed")
        if mode == "On Change":
            self.autosave_now()
        else:
            interval_ms = self.settings.get("autosave_interval_sec", 30) * 1000
            self.autosave_timer.start(interval_ms)

    def autosave_now(self):
        if self.autosave_enabled and self.current_scratchpad_file:
            self.save_scratchpad()
            self.status_bar.showMessage(f"Autosaved at {datetime.now().strftime('%H:%M:%S')}")

    # ── Theme ─────────────────────────────────────────────────────────────
    def apply_theme(self, name):
        if name in self.themes:
            self.setStyleSheet(self.themes[name])
            self.current_theme = name
            self.settings["last_theme"] = name
            self._save_settings()
            # Sync toolbar combo without re-triggering apply_theme
            if hasattr(self, 'theme_combo'):
                self.theme_combo.blockSignals(True)
                idx = self.theme_combo.findText(name)
                if idx >= 0:
                    self.theme_combo.setCurrentIndex(idx)
                self.theme_combo.blockSignals(False)
            self.status_bar.showMessage(f"Theme: {name}", 2000)
        else:
            self.status_bar.showMessage(f"Theme '{name}' not found in themes.qss", 3000)

    def _restore_geometry(self):
        geom = self.settings.get("window_geometry")
        if geom:
            try:
                from PySide6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromBase64(geom.encode()))
                return
            except Exception:
                pass
        # Fallback: default size + centered on screen
        self.resize(1200, 800)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def closeEvent(self, event):
        from PySide6.QtCore import QByteArray
        self.settings["window_geometry"] = self.saveGeometry().toBase64().data().decode()
        self._save_settings()
        super().closeEvent(event)

    def open_settings(self):
        dlg = SettingsDialog(self, config=self.settings.copy(), config_path=self.settings_path)
        if dlg.exec() == QDialog.Accepted:
            self.settings = dlg.config
            self._save_settings()
            self._apply_startup_settings()
            self.status_bar.showMessage("Settings saved.", 2000)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = JotSearchApp()
    win.show()
    sys.exit(app.exec())