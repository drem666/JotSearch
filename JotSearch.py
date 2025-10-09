# Updated JotSearch.py with Embedded Ripgrep Support
import os
import subprocess
import tkinter as tk
import platform
import zipfile
import requests
import shutil
import stat
from tkinter import filedialog, ttk, messagebox
from datetime import datetime
from pathlib import Path

class JotSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JotSearch v0.5")
        self.root.geometry("1200x960")
        self.root.configure(bg="#f0f0f0")

        self.search_folder = ""
        self.current_scratchpad_file = None
        self.autosave_enabled = False
        self.autosave_id = None
        self.rg_path = self.setup_ripgrep()
        self.setup_ui()
        self.setup_menu()

    def setup_ripgrep(self):
        """Set up ripgrep executable in the application directory"""
        # Determine platform and architecture
        system = platform.system()
        arch = platform.machine()
        
        # Map platform to ripgrep naming convention
        platform_map = {
            "Windows": "x86_64-pc-windows-msvc",
            "Darwin": "aarch64-apple-darwin" if "arm" in arch.lower() else "x86_64-apple-darwin",
            "Linux": "x86_64-unknown-linux-musl"
        }
        
        # Create bin directory if it doesn't exist
        bin_dir = Path(__file__).parent / "bin"
        bin_dir.mkdir(exist_ok=True)
        
        # Set executable name and path
        exe_name = "rg.exe" if system == "Windows" else "rg"
        rg_path = bin_dir / exe_name
        
        # Return system rg if found
        if shutil.which("rg"):
            return "rg"
        
        # Return local rg if already exists
        if rg_path.exists():
            return str(rg_path)
        
        # If ripgrep not found, offer to download it
        if not messagebox.askyesno(
            "Ripgrep Required",
            "Ripgrep not found. Download portable version to application folder?",
            icon='question'
        ):
            return None
        
        try:
            # Determine download URL
            platform_str = platform_map.get(system)
            if not platform_str:
                messagebox.showerror(
                    "Unsupported Platform",
                    f"Portable ripgrep not available for {system}. Please install manually."
                )
                return None
            
            version = "14.1.0"  # Latest stable version
            url = f"https://github.com/BurntSushi/ripgrep/releases/download/{version}/ripgrep-{version}-{platform_str}.zip"
            
            # Download the zip file
            self.status_var.set("Downloading ripgrep...")
            self.root.update()
            
            zip_path = bin_dir / "rg.zip"
            response = requests.get(url, stream=True)
            with open(zip_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            # Extract the zip file
            self.status_var.set("Extracting ripgrep...")
            self.root.update()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Find the executable in the zip file
                for file in zip_ref.namelist():
                    if file.endswith(exe_name):
                        zip_ref.extract(file, bin_dir)
                        break
            
            # Move executable to bin directory
            extracted_path = bin_dir / file
            if extracted_path != rg_path:
                extracted_path.rename(rg_path)
            
            # Set executable permissions on macOS/Linux
            if system != "Windows":
                rg_path.chmod(rg_path.stat().st_mode | stat.S_IEXEC)
            
            # Clean up
            zip_path.unlink()
            shutil.rmtree(bin_dir / file.split('/')[0], ignore_errors=True)
            
            self.status_var.set("Ripgrep installed successfully!")
            return str(rg_path)
            
        except Exception as e:
            messagebox.showerror(
                "Installation Failed",
                f"Failed to install ripgrep: {str(e)}\nPlease install manually."
            )
            return None

    # ... (rest of the code remains the same until on_search method)
    def setup_menu(self):
        menu_bar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="New Scratchpad", command=self.new_scratchpad)
        file_menu.add_command(label="Open Scratchpad", command=self.open_scratchpad)
        file_menu.add_command(label="Save Scratchpad", command=self.save_scratchpad)
        file_menu.add_command(label="Save Scratchpad As", command=self.save_scratchpad_as)
        file_menu.add_separator()
        file_menu.add_checkbutton(label="Autosave", command=self.toggle_autosave)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        
        self.root.config(menu=menu_bar)

    def setup_ui(self):
        # --- Folder Picker ---
        folder_frame = tk.Frame(self.root, bg="#f0f0f0")
        folder_frame.pack(pady=10, padx=10, fill=tk.X)

        self.folder_label = tk.Label(folder_frame, text="No folder selected", bg="#f0f0f0", anchor="w")
        self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        pick_btn = ttk.Button(folder_frame, text="Choose Folder", command=self.choose_folder)
        pick_btn.pack(side=tk.RIGHT)

        # --- Search Options ---
        options_frame = tk.Frame(self.root, bg="#f0f0f0")
        options_frame.pack(pady=5, padx=10, fill=tk.X)

        # Extensions input
        tk.Label(options_frame, text="Extensions:", bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 5))
        self.extensions_entry = ttk.Entry(options_frame, width=30)
        self.extensions_entry.pack(side=tk.LEFT)
        self.extensions_entry.insert(0, "txt,md,py,js,html,css")  # Default extensions

        # Case sensitivity checkbox
        self.case_sensitive_var = tk.BooleanVar()
        case_check = ttk.Checkbutton(options_frame, text="Case Sensitive", variable=self.case_sensitive_var)
        case_check.pack(side=tk.LEFT, padx=(10, 0))

        # --- Search Bar ---
        search_frame = tk.Frame(self.root, bg="#f0f0f0")
        search_frame.pack(pady=5, padx=10, fill=tk.X)

        self.search_entry = ttk.Entry(search_frame, font=("Segoe UI", 12))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", self.on_search)

        search_btn = ttk.Button(search_frame, text="Search", command=self.on_search)
        search_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # --- Results Summary ---
        self.summary_var = tk.StringVar()
        self.summary_var.set("Enter search query and select folder")
        summary_label = tk.Label(self.root, textvariable=self.summary_var, bg="#f0f0f0", anchor="w", padx=10)
        summary_label.pack(fill=tk.X, pady=(10, 0))

        # --- Results Area ---
        results_frame = tk.Frame(self.root)
        results_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # Add scrollbar to results
        scrollbar = tk.Scrollbar(results_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_box = tk.Text(results_frame, height=15, bg="#ffffff", font=("Consolas", 10), yscrollcommand=scrollbar.set)
        self.results_box.pack(fill=tk.BOTH, expand=True)
        self.results_box.insert("end", "Search results will appear here...\n")
        self.results_box.config(state=tk.DISABLED)  # Make read-only
        
        scrollbar.config(command=self.results_box.yview)

        # --- Notes Section ---
        notes_frame = tk.Frame(self.root)
        notes_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=False)

        # Notes header with buttons and checkbox
        notes_header = tk.Frame(notes_frame, bg="#f0f0f0")
        notes_header.pack(fill=tk.X)
        
        tk.Label(notes_header, text="Scratchpad", bg="#f0f0f0", 
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        
        # Button container
        btn_frame = tk.Frame(notes_header, bg="#f0f0f0")
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="New", width=6, 
                  command=self.new_scratchpad).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Open", width=6, 
                  command=self.open_scratchpad).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Save", width=6, 
                  command=self.save_scratchpad).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Save As", width=6, 
                  command=self.save_scratchpad_as).pack(side=tk.LEFT, padx=2)
        
        # Autosave checkbox
        self.autosave_var = tk.BooleanVar()
        autosave_check = ttk.Checkbutton(
            notes_header, 
            text="Autosave", 
            variable=self.autosave_var,
            command=self.toggle_autosave
        )
        autosave_check.pack(side=tk.RIGHT, padx=(10, 0))

        # Add scrollbar to notes
        notes_scroll = tk.Scrollbar(notes_frame)
        notes_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.notes_box = tk.Text(notes_frame, height=8, bg="#fcfcfc", 
                                font=("Segoe UI", 11), yscrollcommand=notes_scroll.set)
        self.notes_box.pack(fill=tk.BOTH, expand=True)
        self.notes_box.insert("end", "Type your notes here...")
        
        # Bind text change event for autosave
        self.notes_box.bind("<KeyRelease>", self.schedule_autosave)
        notes_scroll.config(command=self.notes_box.yview)

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.search_folder = folder
            self.folder_label.config(text=folder)
            self.status_var.set(f"Selected folder: {folder}")

    def on_search(self, event=None):
        query = self.search_entry.get().strip()
        if not self.search_folder:
            self.status_var.set("Please select a folder first")
            return
        if not query:
            self.status_var.set("Please enter a search query")
            return
        
        # Check if ripgrep is available
        if not self.rg_path:
            self.status_var.set("Error: ripgrep not available. Searches disabled.")
            return
            
        # Prepare ripgrep command
        cmd = [self.rg_path, "--color=never", "--line-number", "--encoding", "auto"]
        
        # Handle case sensitivity
        if not self.case_sensitive_var.get():
            cmd.append("--ignore-case")
            
        # Handle exact phrase (double quotes)
        if query.startswith('"') and query.endswith('"'):
            cmd.append("--fixed-strings")
            query = query[1:-1]  # Remove quotes
            
        # Handle file extensions
        exts = [ext.strip() for ext in self.extensions_entry.get().split(",") if ext.strip()]
        if exts:
            cmd.append("--type-add")
            cmd.append(f"custom:*.{{{','.join(exts)}}}")
            cmd.append("--type")
            cmd.append("custom")
        
        cmd.extend([query, self.search_folder])
        
        # Execute search
        try:
            self.status_var.set("Searching...")
            self.root.update_idletasks()  # Update UI
            
            # Use universal_newlines=True to handle text properly
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
            output = result.stdout
            
            # Update results
            self.results_box.config(state=tk.NORMAL)
            self.results_box.delete("1.0", "end")
            
            if output:
                self.results_box.insert("end", output)
                result_count = len(output.splitlines())
                self.summary_var.set(f"Found {result_count} results for: '{query}'")
            else:
                self.results_box.insert("end", "No results found")
                self.summary_var.set(f"No results found for: '{query}'")
                
            self.results_box.config(state=tk.DISABLED)
            self.status_var.set(f"Search completed at {datetime.now().strftime('%H:%M:%S')}")
            
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # No matches found
                self.results_box.config(state=tk.NORMAL)
                self.results_box.delete("1.0", "end")
                self.results_box.insert("end", "No results found")
                self.results_box.config(state=tk.DISABLED)
                self.summary_var.set(f"No results found for: '{query}'")
                self.status_var.set("Search completed with no results")
            else:
                # Try to get error output with proper encoding handling
                error_output = e.stderr
                if not error_output:
                    try:
                        error_output = e.stderr.decode('utf-8', 'replace')
                    except:
                        error_output = "Unknown error (could not decode stderr)"
                
                self.status_var.set(f"Search error: {error_output.strip()}")
                self.results_box.config(state=tk.NORMAL)
                self.results_box.delete("1.0", "end")
                self.results_box.insert("end", f"Search error:\n{error_output}")
                self.results_box.config(state=tk.DISABLED)
                self.summary_var.set(f"Error searching for: '{query}'")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            self.results_box.config(state=tk.NORMAL)
            self.results_box.delete("1.0", "end")
            self.results_box.insert("end", f"Error: {str(e)}")
            self.results_box.config(state=tk.DISABLED)
            self.summary_var.set(f"Error occurred during search")

    def new_scratchpad(self):
        if self.notes_box.get("1.0", "end-1c").strip() and not self.current_scratchpad_file:
            if not messagebox.askyesno(
                "Unsaved Changes", 
                "You have unsaved changes. Create new scratchpad anyway?",
                icon='warning'
            ):
                return
                
        self.notes_box.delete("1.0", "end")
        self.current_scratchpad_file = None
        self.status_var.set("Created new scratchpad")

    def open_scratchpad(self):
        if self.notes_box.get("1.0", "end-1c").strip() and not self.current_scratchpad_file:
            if not messagebox.askyesno(
                "Unsaved Changes", 
                "You have unsaved changes. Open new file anyway?",
                icon='warning'
            ):
                return
                
        file_path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                # Try multiple encodings to handle different file types
                for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        with open(file_path, "r", encoding=encoding) as file:
                            content = file.read()
                        self.notes_box.delete("1.0", "end")
                        self.notes_box.insert("end", content)
                        self.current_scratchpad_file = file_path
                        self.status_var.set(f"Loaded scratchpad: {file_path} ({encoding})")
                        return
                    except UnicodeDecodeError:
                        continue
                
                # If all encodings fail, try with errors='replace'
                with open(file_path, "r", encoding='utf-8', errors='replace') as file:
                    content = file.read()
                self.notes_box.delete("1.0", "end")
                self.notes_box.insert("end", content)
                self.current_scratchpad_file = file_path
                self.status_var.set(f"Loaded scratchpad (with replacement chars): {file_path}")
                
            except Exception as e:
                self.status_var.set(f"Error loading file: {str(e)}")

    def save_scratchpad(self):
        if self.current_scratchpad_file:
            self._save_to_file(self.current_scratchpad_file)
        else:
            self.save_scratchpad_as()

    def save_scratchpad_as(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.current_scratchpad_file = file_path
            self._save_to_file(file_path)

    def _save_to_file(self, file_path):
        try:
            content = self.notes_box.get("1.0", "end-1c")
            with open(file_path, "w", encoding='utf-8') as file:
                file.write(content)
            self.status_var.set(f"Scratchpad saved: {file_path}")
            return True
        except Exception as e:
            self.status_var.set(f"Error saving file: {str(e)}")
            return False

    def toggle_autosave(self):
        self.autosave_enabled = self.autosave_var.get()
        status = "ON" if self.autosave_enabled else "OFF"
        self.status_var.set(f"Autosave {status} - Changes will be saved automatically")
        
        # If enabling autosave and we have a current file, save immediately
        if self.autosave_enabled and self.current_scratchpad_file:
            self.autosave_now()

    def schedule_autosave(self, event=None):
        if self.autosave_enabled and self.current_scratchpad_file:
            # Cancel previous scheduled save if any
            if self.autosave_id:
                self.root.after_cancel(self.autosave_id)
                
            # Schedule new save
            self.autosave_id = self.root.after(2000, self.autosave_now)

    def autosave_now(self):
        if self.autosave_enabled and self.current_scratchpad_file:
            if self._save_to_file(self.current_scratchpad_file):
                self.status_var.set(f"Autosaved scratchpad at {datetime.now().strftime('%H:%M:%S')}")
                
    def on_closing(self):
        # Check for unsaved changes
        if self.notes_box.get("1.0", "end-1c").strip() and not self.current_scratchpad_file:
            if messagebox.askyesno(
                "Unsaved Changes", 
                "You have unsaved changes. Exit anyway?",
                icon='warning'
            ):
                self.root.destroy()
        else:
            self.root.destroy()

# --- Run the app ---
if __name__ == "__main__":
    root = tk.Tk()
    app = JotSearchApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()