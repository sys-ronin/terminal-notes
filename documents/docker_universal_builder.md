# Universal Docker Build Script

## A Technical Overview

---

## 1. Purpose

This script builds cross‑platform executables for Terminal Notes using Docker. It runs on Linux, macOS, or Windows and produces binaries for all target platforms without requiring native build environments.

The script automates:
- Downloading and bundling optional editors (micro, nvim)
- Running PyInstaller in isolated Docker containers
- Cleaning build artifacts between runs
- Providing a consistent build environment regardless of host OS

---

## 2. Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 20.10+ | Required for Linux/Windows builds; optional for macOS |
| Python | 3.6+ | Only for running the script itself |
| Internet | Yes | Downloads editors and Docker images |
| Disk space | ~2 GB | For Docker images and build artifacts |

The script detects missing requirements and exits with a clear message.

---

## 3. Supported Outputs

| Platform | Architecture | Output File | Build Method |
|----------|--------------|-------------|--------------|
| Linux | x86_64 | `terminal-notes-linux` | Docker (python:3.13-slim) |
| Windows | x86_64 | `terminal-notes-windows.exe` | Docker (python:3.13-slim) |
| macOS | x86_64 | `terminal-notes-macos` | Native PyInstaller (fallback to Docker) |

ARM64 builds are not supported in this version.

---

## 4. How It Works

### 4.1 Platform Detection

The script identifies the host OS using `platform.system()`:
- `Linux` → Docker‑based builds for all targets
- `Darwin` (macOS) → Native build for macOS, Docker for others
- `Windows` → Docker‑based builds for all targets

### 4.2 Editor Download

When the user selects editor bundling, the script downloads:

| Editor | Linux | Windows | macOS |
|--------|-------|---------|-------|
| micro | `micro-2.0.15-linux64-static.tar.gz` | `micro-2.0.15-win64.zip` | `micro-2.0.15-osx.tar.gz` |
| nvim | `nvim-linux64.tar.gz` | `nvim-win64.zip` | `nvim-macos-x86_64.tar.gz` |

Downloads use `urllib.request` with progress indication. Extracted binaries are moved to `assets/editors/`.

### 4.3 Docker Build

For each target platform, the script runs:

```bash
docker run --rm -v $(pwd):/src -w /src python:3.13-slim bash -c "
    apt-get update -qq && \
    apt-get install -y -qq git binutils file && \
    pip install -q pyinstaller requests ... && \
    pyinstaller --clean --onefile ... terminal_notes_ui.py
"
```

All output is suppressed except errors. Build timeouts are set to 600 seconds.

### 4.4 Native macOS Build

When running on macOS, the script uses the system PyInstaller instead of Docker:

```bash
python -m PyInstaller --clean --onefile ...
```

This avoids Docker performance penalties on macOS and produces a native binary.

### 4.5 Cleanup

After each build, the script removes:
- `dist/` and `build/` directories
- `*.spec` files
- `__pycache__` directories
- Temporary editor downloads

---

## 5. Menu Structure

```
MAIN MENU
├── 1) Linux (x86_64)
├── 2) Windows (x86_64)
├── 3) macOS (x86_64)
├── 4) All platforms
└── 0) Exit

EDITOR MENU
├── 1) Bundle both micro and nvim
├── 2) Bundle micro only
├── 3) Bundle nvim only
├── 4) Bundle neither
└── 0) Back

CONFIRMATION
├── Shows selected options
├── 1) Proceed
└── 0) Back
```

The interface uses numbered options, left alignment, and clear cancellation paths.

---

## 6. Error Handling

| Error | Handling |
|-------|----------|
| Docker not installed | Exit with installation instructions |
| Download fails | Retry with clear error message |
| Build timeout (600s) | Report timeout and continue |
| Missing output file | Report failure and continue to next build |

The script does not stop on individual build failures; it attempts all requested builds and reports results.

---

## 7. File Structure After Build

```
dist/
├── terminal-notes-linux          (Linux executable)
├── terminal-notes-windows.exe    (Windows executable)
└── terminal-notes-macos          (macOS executable)

assets/editors/                   (temporary, removed after build)
├── micro-linux / micro-windows.exe / micro-macos
└── nvim-linux / nvim-windows.exe / nvim-macos
```

---

## 8. Usage

```bash
python build.py
```

Follow the menu prompts. The script handles the rest.

---

## 9. Limitations

- ARM64 builds not supported (x86_64 only)
- macOS build requires native PyInstaller for best results
- Docker Desktop required on macOS and Windows
- Large download size (~2 GB for Docker images on first run)

---

## 10. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Docker for Linux/Windows | Consistent environment, no host dependencies |
| Native for macOS | Docker on macOS has performance overhead |
| Single script, no config | Zero setup, works immediately |
| Suppressed build output | Clean terminal experience |
| 600 second timeout | Accommodates slow networks or large builds |
| Editor bundling optional | Users choose size vs. functionality |

---

## 11. Dependencies

The script uses only Python standard library modules:
- `os`, `sys`, `platform` – system interaction
- `subprocess` – running Docker and PyInstaller
- `shutil`, `pathlib` – file operations
- `urllib.request` – downloading editors
- `tarfile`, `zipfile` – extracting archives

No external Python packages are required to run the script.

---

## 12. Source Code

The script is part of the Terminal Notes repository:

- **Location:** `build.py` or `_docker_universal_builder.py`
- **License:** Same as Terminal Notes (Eternal License)

---

*Documented April 2026*
