# JotSearch - Portable Text Search Tool

![JotSearch Screenshot](screenshot.png)

JotSearch is a portable desktop application that provides powerful text search capabilities. It includes a self-contained version of ripgrep (rg) for searching through files.

## Features

- 📦 **100% Portable** - No installation required
- 🔍 Built-in ripgrep search engine
- 📁 Recursive directory searching
- 🧩 Filter by multiple file extensions
- 🔤 Case sensitivity toggle
- 💬 Exact phrase search using double quotes
- 📝 Integrated scratchpad with file operations
- ⚡ Autosave functionality for notes

## Getting Started

### Windows Users
1. Download the `JotSearch.zip` package
2. Extract to any folder
3. Run `JotSearch.exe`

### macOS/Linux Users
1. Ensure you have Python 3.6+ installed
2. Download the `JotSearch.py` file
3. Run: `python3 JotSearch.py`

## First Run Setup

On first launch:
1. The application will detect if ripgrep is installed
2. If not found, it will offer to download a portable version
3. Approve the download to install ripgrep in the application folder

![Ripgrep Installation Prompt](install-prompt.png)

## Usage

### Search Features
1. Click "Choose Folder" to select a directory to search
2. Enter your search query
3. (Optional) Specify file extensions (comma-separated)
4. (Optional) Check "Case Sensitive" for exact case matching
5. Press Enter or click "Search"

### Scratchpad Features
- **New**: Create a new scratchpad
- **Open**: Load a text file
- **Save**: Save to current file
- **Save As**: Save to a new file
- **Autosave**: Automatically save changes to current file

## Portable Operation

- The application stores all data in its own directory
- Ripgrep is installed in the `bin` subfolder
- You can move the entire folder to different computers
- All settings and scratchpad files are self-contained

## Manual Installation (Advanced)

If automatic download fails:
1. Download the appropriate ripgrep version:
   - Windows: [ripgrep-x86_64-pc-windows-msvc.zip](https://github.com/BurntSushi/ripgrep/releases)
   - macOS: [ripgrep-x86_64-apple-darwin.tar.gz](https://github.com/BurntSushi/ripgrep/releases)
   - Linux: [ripgrep-x86_64-unknown-linux-musl.tar.gz](https://github.com/BurntSushi/ripgrep/releases)
2. Extract the zip file
3. Place the `rg` (or `rg.exe` on Windows) in the `bin` folder

## Troubleshooting

### Common Issues
1. **Download fails**:
   - Check your internet connection
   - Download manually (see instructions above)
   - Place the executable in the `bin` folder

2. **Permission errors** (macOS/Linux): 
```bash
   chmod +x bin/rg
```
3. **Search not working**:
Ensure the bin folder contains the ripgrep executable
Verify the folder selection is correct
Try simple queries first

## Distribution Packages
# Pre-built packages include:
Windows: JotSearch.exe (PyInstaller build)
macOS: JotSearch.app (PyInstaller build)
Linux: JotSearch executable

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Key Features of the Portable Solution

1. **Automatic Ripgrep Installation**:
   - Detects missing ripgrep on first run
   - Downloads the appropriate version for the OS
   - Installs it in the `bin` subdirectory

2. **Self-Contained Operation**:
   - All files stay within the application directory
   - No system-wide installation required
   - Easy to move between computers

3. **Cross-Platform Support**:
   - Handles Windows, macOS, and Linux
   - Automatically selects correct architecture
   - Sets executable permissions appropriately

4. **Graceful Fallback**:
   - Uses system ripgrep if available
   - Offers manual installation instructions
   - Provides clear error messages

5. **User-Friendly Experience**:
   - Simple yes/no installation prompt
   - Progress updates during download
   - Status bar notifications

This implementation makes JotSearch truly portable - users can run it from a USB drive or cloud storage without any system dependencies. The automatic download feature ensures a smooth first-run experience for non-technical users.