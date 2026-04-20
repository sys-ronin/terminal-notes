#!/usr/bin/env python3
"""
Terminal Notes Universal Build Script
Simplified - No ARM support, builds x86_64 only for all platforms
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

# =============================================================================
# TERMINAL UI HELPERS
# =============================================================================

def get_terminal_size():
    try:
        columns, rows = shutil.get_terminal_size()
        return max(60, columns), rows
    except:
        return 80, 24


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title, width=None):
    if width is None:
        width, _ = get_terminal_size()
    separator = "-" * width
    print(separator)
    print(f"{title:^{width}}")
    print(separator)


def get_input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def format_option(number, description):
    return f"  [{number}] {description}"


# =============================================================================
# BUILD CONFIGURATION
# =============================================================================

class BuildConfig:
    def __init__(self):
        self.platform = None
        self.bundle_micro = False
        self.bundle_nvim = False
        self.build_linux = False
        self.build_windows = False
        self.build_macos = False


# =============================================================================
# MENU SYSTEM
# =============================================================================

def show_main_menu(config):
    while True:
        clear_screen()
        width, _ = get_terminal_size()
        
        print_header("TERMINAL NOTES BUILD SCRIPT", width)
        print()
        print("  Select target platform:")
        print()
        print(format_option("1", "Linux (x86_64)"))
        print(format_option("2", "Windows (x86_64)"))
        print(format_option("3", "macOS (x86_64)"))
        print(format_option("4", "All platforms"))
        print(format_option("0", "Exit"))
        print()
        
        choice = get_input("  Choose [0-4]: ")
        
        if choice == "0":
            print("\n  Exiting...")
            return False
        elif choice in ["1", "2", "3", "4"]:
            config.platform = int(choice)
            return True


def show_editor_menu(config):
    while True:
        clear_screen()
        width, _ = get_terminal_size()
        
        print_header("EDITOR BUNDLING OPTIONS", width)
        print()
        print("  Bundle editors for offline use (increases size):")
        print()
        print(format_option("1", "Bundle both micro and nvim (recommended)"))
        print(format_option("2", "Bundle micro only (lightweight)"))
        print(format_option("3", "Bundle nvim only (powerful)"))
        print(format_option("4", "Bundle neither (use system editors)"))
        print(format_option("0", "Back"))
        print()
        
        choice = get_input("  Choose [0-4]: ")
        
        if choice == "0":
            return False
        elif choice == "1":
            config.bundle_micro = True
            config.bundle_nvim = True
            return True
        elif choice == "2":
            config.bundle_micro = True
            config.bundle_nvim = False
            return True
        elif choice == "3":
            config.bundle_micro = False
            config.bundle_nvim = True
            return True
        elif choice == "4":
            config.bundle_micro = False
            config.bundle_nvim = False
            return True


def show_confirmation(config):
    while True:
        clear_screen()
        width, _ = get_terminal_size()
        
        print_header("BUILD CONFIRMATION", width)
        print()
        
        platform_names = {1: "Linux", 2: "Windows", 3: "macOS", 4: "All platforms"}
        print(f"  Platform: {platform_names.get(config.platform, 'Unknown')}")
        print()
        
        editor_msg = "none"
        if config.bundle_micro and config.bundle_nvim:
            editor_msg = "both micro and nvim"
        elif config.bundle_micro:
            editor_msg = "micro only"
        elif config.bundle_nvim:
            editor_msg = "nvim only"
        print(f"  Editors: {editor_msg}")
        print()
        print("  Architectures: x86_64 only")
        print()
        print(format_option("1", "Proceed with build"))
        print(format_option("0", "Back"))
        print()
        
        choice = get_input("  Choose [0-1]: ")
        
        if choice == "0":
            return False
        elif choice == "1":
            return True


# =============================================================================
# DOWNLOAD FUNCTIONS
# =============================================================================

def check_docker():
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def download_file(url, dest):
    import urllib.request
    
    class ProgressHook:
        def __init__(self):
            self.last_percent = -1
        
        def __call__(self, count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                if percent != self.last_percent and percent % 10 == 0:
                    print(f"\r    Downloading... {percent}%", end="", flush=True)
                    self.last_percent = percent
    
    try:
        urllib.request.urlretrieve(url, dest, ProgressHook())
        print("\r    Downloading... 100%")
        return True
    except Exception as e:
        print(f"\r    Download failed: {e}")
        return False


def download_editors(config, target_platform):
    if not config.bundle_micro and not config.bundle_nvim:
        return True
    
    print(f"  Downloading editors for {target_platform}...")
    
    try:
        import urllib.request
        import zipfile
        import tarfile
        
        if config.bundle_micro:
            print("    Downloading micro...")
            if target_platform == "linux":
                url = "https://github.com/zyedidia/micro/releases/download/v2.0.14/micro-2.0.14-linux64-static.tar.gz"
                local_file = "/tmp/micro.tar.gz"
                if not download_file(url, local_file):
                    return False
                with tarfile.open(local_file, "r:gz", errorlevel=0) as tar:
                    tar.extractall("/tmp", filter='data')
                shutil.move("/tmp/micro-2.0.14/micro", "assets/editors/micro-linux")
                os.chmod("assets/editors/micro-linux", 0o755)
                
            elif target_platform == "windows":
                url = "https://github.com/zyedidia/micro/releases/download/v2.0.14/micro-2.0.14-win64.zip"
                local_file = "/tmp/micro.zip"
                if not download_file(url, local_file):
                    return False
                extract_dir = "/tmp/micro_extract"
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(local_file, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
                for root, dirs, files in os.walk(extract_dir):
                    if "micro.exe" in files:
                        shutil.move(os.path.join(root, "micro.exe"), "assets/editors/micro-windows.exe")
                        break
                shutil.rmtree(extract_dir, ignore_errors=True)
                
            elif target_platform == "macos":
                url = "https://github.com/micro-editor/micro/releases/download/v2.0.15/micro-2.0.15-osx.tar.gz"
                local_file = "/tmp/micro.tar.gz"
                if not download_file(url, local_file):
                    return False
                with tarfile.open(local_file, "r:gz", errorlevel=0) as tar:
                    tar.extractall("/tmp", filter='data')
                
                # Search for the micro binary anywhere in /tmp
                micro_path = None
                for root, dirs, files in os.walk("/tmp"):
                    if "micro" in files:
                        # Check if it's the executable (not a text file)
                        full_path = os.path.join(root, "micro")
                        if os.path.isfile(full_path) and not full_path.endswith('.sha'):
                            micro_path = full_path
                            break
                
                if micro_path:
                    shutil.move(micro_path, "assets/editors/micro-macos")
                    os.chmod("assets/editors/micro-macos", 0o755)
                else:
                    print(f"    Could not find micro binary in extracted files")
                    return False
        
        if config.bundle_nvim:
            print("    Downloading nvim...")
            if target_platform == "linux":
                url = "https://github.com/neovim/neovim/releases/download/v0.12.0/nvim-linux-x86_64.tar.gz"
                local_file = "/tmp/nvim.tar.gz"
                if not download_file(url, local_file):
                    return False
                with tarfile.open(local_file, "r:gz", errorlevel=0) as tar:
                    tar.extractall("/tmp", filter='data')
                shutil.move("/tmp/nvim-linux-x86_64/bin/nvim", "assets/editors/nvim-linux")
                os.chmod("assets/editors/nvim-linux", 0o755)
                
            elif target_platform == "windows":
                url = "https://github.com/neovim/neovim/releases/download/v0.10.4/nvim-win64.zip"
                local_file = "/tmp/nvim.zip"
                if not download_file(url, local_file):
                    return False
                extract_dir = "/tmp/nvim_extract"
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(local_file, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
                for root, dirs, files in os.walk(extract_dir):
                    if "nvim.exe" in files:
                        shutil.move(os.path.join(root, "nvim.exe"), "assets/editors/nvim-windows.exe")
                        break
                shutil.rmtree(extract_dir, ignore_errors=True)
                
            elif target_platform == "macos":
                url = "https://github.com/neovim/neovim/releases/download/v0.10.4/nvim-macos-x86_64.tar.gz"
                local_file = "/tmp/nvim.tar.gz"
                if not download_file(url, local_file):
                    return False
                with tarfile.open(local_file, "r:gz", errorlevel=0) as tar:
                    tar.extractall("/tmp", filter='data')
                shutil.move("/tmp/nvim-macos-x86_64/bin/nvim", "assets/editors/nvim-macos")
                os.chmod("assets/editors/nvim-macos", 0o755)
            print("    nvim downloaded")
        
        print(f"  \033[32m✓ Editors downloaded\033[0m")
        return True
        
    except Exception as e:
        print(f"  \033[31m✗ Failed: {e}\033[0m")
        return False


# =============================================================================
# BUILD FUNCTIONS
# =============================================================================

def build_pyinstaller(name, docker_image, build_desc, config):
    print(f"  Building {build_desc}... ", end="", flush=True)
    
    args = [
        "docker", "run", "--rm",
        "-v", f"{os.getcwd()}:/src",
        "-w", "/src",
        docker_image,
        "bash", "-c",
        "apt-get update -qq && "
        "apt-get install -y -qq git binutils file > /dev/null 2>&1 && "
        "pip install -q pyinstaller requests urllib3 charset-normalizer idna certifi 2>/dev/null && "
        f"pyinstaller --clean --onefile --name {name} "
        "--add-data 'assets:assets' "
        "--add-data 'git_filter_repo.py:.' "
        "--hidden-import cryptography "
        "--hidden-import cffi "
        "--hidden-import requests "
        "--hidden-import urllib3 "
        "--hidden-import charset_normalizer "
        "--hidden-import idna "
        "--hidden-import certifi "
        "--exclude-module dev_dashboard "
        f"terminal_notes_ui.py > /dev/null 2>&1"
    ]
    
    # Add editor binaries
    if config.bundle_micro:
        if "linux" in name:
            args[-1] += " --add-data 'assets/editors/micro-linux:./editors'"
        elif "windows" in name:
            args[-1] += " --add-data 'assets/editors/micro-windows.exe:./editors'"
        elif "macos" in name:
            args[-1] += " --add-data 'assets/editors/micro-macos:./editors'"
    
    if config.bundle_nvim:
        if "linux" in name:
            args[-1] += " --add-data 'assets/editors/nvim-linux:./editors'"
        elif "windows" in name:
            args[-1] += " --add-data 'assets/editors/nvim-windows.exe:./editors'"
        elif "macos" in name:
            args[-1] += " --add-data 'assets/editors/nvim-macos:./editors'"
    
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and (os.path.exists(f"dist/{name}") or os.path.exists(f"dist/{name}.exe")):
            print("\033[32m✓ done\033[0m")
            return True
        else:
            print("\033[31m✗ failed\033[0m")
            return False
    except subprocess.TimeoutExpired:
        print("\033[31m✗ timeout\033[0m")
        return False
    except Exception as e:
        print(f"\033[31m✗ {e}\033[0m")
        return False


def build_macos_native(name, build_desc, config):
    """Build natively on macOS (without Docker)"""
    print(f"  Building {build_desc} natively... ", end="", flush=True)
    
    if platform.system() != "Darwin":
        print("\033[33m⚠ skipping (not on macOS)\033[0m")
        return False
    
    # Ensure PyInstaller is installed
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pyinstaller"], capture_output=True)
    
    args = [
        sys.executable, "-m", "PyInstaller", "--clean", "--onefile",
        f"--name={name}",
        "--add-data=assets:assets",
        "--add-data=git_filter_repo.py:.",
        "--hidden-import=cryptography",
        "--hidden-import=cffi",
        "--hidden-import=requests",
        "--hidden-import=urllib3",
        "--hidden-import=charset_normalizer",
        "--hidden-import=idna",
        "--hidden-import=certifi",
        "--exclude-module=dev_dashboard",
        "terminal_notes_ui.py"
    ]
    
    if config.bundle_micro:
        args.append("--add-data=assets/editors/micro-macos:./editors")
    if config.bundle_nvim:
        args.append("--add-data=assets/editors/nvim-macos:./editors")
    
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            print(f"\n  Error: {result.stderr[:200] if result.stderr else 'Unknown'}")
            return False
        
        if os.path.exists(f"dist/{name}"):
            print("\033[32m✓ done\033[0m")
            return True
        else:
            print("\n  Output not found")
            return False
    except Exception as e:
        print(f"\033[31m✗ {e}\033[0m")
        return False


# =============================================================================
# PLATFORM BUILD FUNCTIONS
# =============================================================================

def build_linux(config):
    if not download_editors(config, "linux"):
        return False
    return build_pyinstaller("terminal-notes-linux", "python:3.13-slim", "Linux x86_64", config)


def build_windows(config):
    if not download_editors(config, "windows"):
        return False
    return build_pyinstaller("terminal-notes-windows.exe", "python:3.13-slim", "Windows x86_64", config)


def build_macos(config):
    if not download_editors(config, "macos"):
        return False
    # Use native build on macOS, Docker fallback otherwise
    if platform.system() == "Darwin":
        return build_macos_native("terminal-notes-macos", "macOS x86_64", config)
    else:
        return build_pyinstaller("terminal-notes-macos", "python:3.13-slim", "macOS x86_64", config)


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Check Docker for non-macOS builds
    if platform.system() != "Darwin" and not check_docker():
        clear_screen()
        width, _ = get_terminal_size()
        print_header("DOCKER REQUIRED", width)
        print()
        print("  This build script requires Docker to be installed.")
        print("  For macOS, Docker is optional (native build available).")
        print()
        print("  Install Docker from: https://docker.com")
        print()
        input("  Press Enter to exit...")
        return 1
    
    config = BuildConfig()
    
    while True:
        if not show_main_menu(config):
            break
        
        if not show_editor_menu(config):
            continue
        
        # Initialize build flags
        config.build_linux = False
        config.build_windows = False
        config.build_macos = False
        
        if config.platform == 1 or config.platform == 4:
            config.build_linux = True
        if config.platform == 2 or config.platform == 4:
            config.build_windows = True
        if config.platform == 3 or config.platform == 4:
            config.build_macos = True
        
        if not show_confirmation(config):
            continue
        
        # Start build
        clear_screen()
        width, _ = get_terminal_size()
        print_header("BUILDING", width)
        print()
        
        # Clean
        print("  Cleaning build artifacts...", end=" ", flush=True)
        shutil.rmtree("dist", ignore_errors=True)
        shutil.rmtree("build", ignore_errors=True)
        for f in Path(".").glob("*.spec"):
            f.unlink()
        print("\033[32m✓ done\033[0m")
        
        os.makedirs("assets/editors", exist_ok=True)
        os.makedirs("dist", exist_ok=True)
        
        # Build
        if config.build_linux:
            build_linux(config)
        if config.build_windows:
            build_windows(config)
        if config.build_macos:
            build_macos(config)
        
        # Cleanup
        shutil.rmtree("assets/editors", ignore_errors=True)
        
        # Summary
        print()
        print_header("BUILD COMPLETE!", width)
        print()
        print("  Output directory: dist/")
        print()
        
        if os.path.exists("dist"):
            for f in os.listdir("dist"):
                fpath = os.path.join("dist", f)
                size = os.path.getsize(fpath)
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.0f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.0f} MB"
                print(f"    {f} ({size_str})")
        
        print()
        input("  Press Enter to return to main menu...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())