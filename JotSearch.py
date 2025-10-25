import sys
import os
import platform
import subprocess
import zipfile
import requests
import shutil
import stat
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit, QLabel, QPushButton,
    QFileDialog, QLineEdit, QCheckBox, QComboBox, QMessageBox, QStatusBar, QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

class JotSearchApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JotSearch v1.0 (PySide6 Edition)")
        self.resize(1200, 800)
        self.dark_theme = True
        self.rg_path = self.setup_ripgrep()

        self.search_paths = []
        self.current_scratchpad_file = None
        self.autosave_enabled = False
        self.autosave_timer = QTimer()
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.autosave_now)

        self.init_ui()
        self.apply_theme()

    def setup_ripgrep(self):
        system = platform.system()
        arch = platform.machine()
        platform_map = {
            "Windows": "x86_64-pc-windows-msvc",
            "Darwin": "aarch64-apple-darwin" if "arm" in arch.lower() else "x86_64-apple-darwin",
            "Linux": "x86_64-unknown-linux-musl"
        }
        bin_dir = Path(__file__).parent / "bin"
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

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.search_tab = QWidget()
        self.scratch_tab = QWidget()

        self.tabs.addTab(self.search_tab, "Search")
        self.tabs.addTab(self.scratch_tab, "Scratchpad")

        self.init_search_tab()
        self.init_scratchpad_tab()

        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)

    def init_search_tab(self):
        layout = QVBoxLayout()

        mode_box = QGroupBox("Select Mode")
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
        layout.addWidget(self.path_label)

        options_box = QGroupBox("Options")
        grid = QGridLayout()
        self.show_paths = QCheckBox("Show File Paths")
        self.show_paths.setChecked(True)
        self.unique_cmds = QCheckBox("Unique Commands Only")
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
        self.search_entry.setPlaceholderText("Enter search query")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.run_search)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(lambda: self.results_box.clear())

        self.search_entry.returnPressed.connect(self.run_search)  # ENTER key trigger

        search_row.addWidget(self.search_entry)
        search_row.addWidget(self.search_btn)
        search_row.addWidget(self.clear_btn)

        self.results_box = QTextEdit()
        self.results_box.setReadOnly(True)
        self.results_box.setFont(QFont("Consolas", 10))

        self.theme_toggle = QPushButton("Toggle Theme")
        self.theme_toggle.clicked.connect(self.toggle_theme)

        layout.addWidget(mode_box)
        layout.addWidget(options_box)
        layout.addLayout(search_row)
        layout.addWidget(self.results_box)
        layout.addWidget(self.theme_toggle, alignment=Qt.AlignRight)
        self.search_tab.setLayout(layout)

    def init_scratchpad_tab(self):
        layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.open_btn = QPushButton("Open")
        self.save_btn = QPushButton("Save")
        self.saveas_btn = QPushButton("Save As")
        self.autosave_chk = QCheckBox("Autosave")
        for b in [self.new_btn, self.open_btn, self.save_btn, self.saveas_btn]:
            btn_row.addWidget(b)
        btn_row.addWidget(self.autosave_chk)
        self.new_btn.clicked.connect(self.new_scratchpad)
        self.open_btn.clicked.connect(self.open_scratchpad)
        self.save_btn.clicked.connect(self.save_scratchpad)
        self.saveas_btn.clicked.connect(self.save_scratchpad_as)
        self.autosave_chk.stateChanged.connect(self.toggle_autosave)

        self.notes_box = QTextEdit()
        self.notes_box.setFont(QFont("Segoe UI", 11))
        self.notes_box.textChanged.connect(self.schedule_autosave)

        layout.addLayout(btn_row)
        layout.addWidget(self.notes_box)
        self.scratch_tab.setLayout(layout)

    def pick_target(self):
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            f, _ = QFileDialog.getOpenFileName(self, "Select File")
            if f:
                self.search_paths = [f]
        elif mode == 1:
            files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
            self.search_paths = files
        elif mode == 2:
            folder = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder:
                self.search_paths = [folder]
        elif mode == 3:
            folders = QFileDialog.getExistingDirectory(self, "Select First Folder")
            if folders:
                self.search_paths.append(folders)
        if self.search_paths:
            shown = " | ".join(self.search_paths[:3])
            if len(self.search_paths) > 3:
                shown += f" ... (+{len(self.search_paths) - 3} more)"
            self.path_label.setText(f"<b>Selected:</b> {shown}")
        else:
            self.path_label.setText("No files/folders selected")
        self.status_bar.showMessage(f"Selected {len(self.search_paths)} paths")

    def update_selection_mode(self):
        self.search_paths.clear()

    def run_search(self):
        query = self.search_entry.text().strip()
        if not query or not self.search_paths:
            self.status_bar.showMessage("Please enter query and select paths.")
            return
        if not self.rg_path:
            self.status_bar.showMessage("Ripgrep not available.")
            return

        results = []
        seen_cmds = set()
        for path in self.search_paths:
            cmd = [self.rg_path, "--color=never", "--line-number"]
            if not self.case_sensitive.isChecked():
                cmd.append("--ignore-case")
            # Handle recursion depending on mode
            mode = self.mode_combo.currentIndex()
            if mode == 2:  # Single Folder - no recursion
                cmd += ["--max-depth", "1"]
            elif mode == 3 and self.recurse.isChecked():
                cmd.append("--hidden")  # allow recursion

            exts = [e.strip() for e in self.ext_entry.text().split(',') if e.strip()]
            if exts:
                cmd += ["--type-add", f"custom:*.{{{','.join(exts)}}}", "--type", "custom"]
            cmd += [query, path]

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
                out = proc.stdout.strip()
                if out:
                    blocks = out.splitlines()
                    for line in blocks:
                        cmd_line = line.strip()
                        if self.unique_cmds.isChecked() and cmd_line in seen_cmds:
                            continue
                        seen_cmds.add(cmd_line)
                        # Skip folder-only headers like "Y:/folder:"
                        if cmd_line.endswith(":") or cmd_line.strip().endswith(":"):
                            continue

                        parts = cmd_line.split(":", 2)

                        if self.show_paths.isChecked():
                            # Show full path:line:command in folder mode
                            results.append(f"{cmd_line}\n")
                        else:
                            # Hide file path — only show the command text
                            if len(parts) == 3:
                                # folder mode: drop file + line number
                                cmd_text = parts[2]
                            elif len(parts) == 2:
                                # file mode: drop line number
                                cmd_text = parts[1]
                            else:
                                cmd_text = cmd_line
                            results.append(f"{cmd_text.strip()}\n")

            except Exception as e:
                results.append(f"Error searching {path}: {e}\n")

        output = "\n".join(results) if results else "No results found."
        self.results_box.setPlainText(output)
        self.status_bar.showMessage(f"Search completed at {datetime.now().strftime('%H:%M:%S')}")

    def new_scratchpad(self):
        self.notes_box.clear()
        self.current_scratchpad_file = None
        self.status_bar.showMessage("New scratchpad.")

    def open_scratchpad(self):
        f, _ = QFileDialog.getOpenFileName(self, "Open Scratchpad", filter="Text Files (*.txt);;All Files (*)")
        if f:
            with open(f, 'r', encoding='utf-8', errors='replace') as file:
                self.notes_box.setPlainText(file.read())
            self.current_scratchpad_file = f
            self.status_bar.showMessage(f"Loaded {f}")

    def save_scratchpad(self):
        if self.current_scratchpad_file:
            with open(self.current_scratchpad_file, 'w', encoding='utf-8') as file:
                file.write(self.notes_box.toPlainText())
            self.status_bar.showMessage(f"Saved {self.current_scratchpad_file}")
        else:
            self.save_scratchpad_as()

    def save_scratchpad_as(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save Scratchpad As", filter="Text Files (*.txt);;All Files (*)")
        if f:
            self.current_scratchpad_file = f
            self.save_scratchpad()

    def toggle_autosave(self):
        self.autosave_enabled = self.autosave_chk.isChecked()
        if self.autosave_enabled:
            self.status_bar.showMessage("Autosave ON")
        else:
            self.status_bar.showMessage("Autosave OFF")

    def schedule_autosave(self):
        if self.autosave_enabled and self.current_scratchpad_file:
            self.autosave_timer.start(2000)

    def autosave_now(self):
        if self.autosave_enabled and self.current_scratchpad_file:
            self.save_scratchpad()
            self.status_bar.showMessage(f"Autosaved at {datetime.now().strftime('%H:%M:%S')}")

    def toggle_theme(self):
        self.dark_theme = not self.dark_theme
        self.apply_theme()

    def apply_theme(self):
        if self.dark_theme:
            bg, text = "#1e1e1e", "#f0f0f0"
        else:
            bg, text = "#f7f7f7", "#202020"
        self.setStyleSheet(f"""
            QWidget {{background-color:{bg}; color:{text};}}
            QPushButton {{border-radius:6px; padding:6px 12px; color:#fff;}}
            QPushButton[text='Search'] {{background-color:#3498db;}}
            QPushButton[text='New'] {{background-color:#2ecc71;}}
            QPushButton[text='Open'] {{background-color:#3498db;}}
            QPushButton[text='Save'] {{background-color:#f1c40f;}}
            QPushButton[text='Save As'] {{background-color:#e67e22;}}
            QPushButton[text='Toggle Theme'] {{background-color:#9b59b6;}}
        """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = JotSearchApp()
    win.show()
    sys.exit(app.exec())
