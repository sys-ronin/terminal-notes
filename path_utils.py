#!/usr/bin/env python3
import os
import sys

def get_app_dir():
    """Get the correct application directory (works for script and PyInstaller)"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        return os.path.dirname(sys.executable)
    else:
        # Running as Python script
        return os.path.dirname(os.path.abspath(__file__))

def get_assets_dir():
    """Get the assets directory (where crypto files are)"""
    if getattr(sys, 'frozen', False):
        # In PyInstaller, assets are in the temp directory
        return os.path.join(os.path.dirname(__file__), 'assets')
    else:
        # In development, assets are next to this file
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')