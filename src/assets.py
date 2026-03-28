import sys
import os

if getattr(sys, 'frozen', False):
    _BASE = os.path.join(sys._MEIPASS, 'assets')
else:
    _BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets'))


def asset(filename: str) -> str:
    return os.path.join(_BASE, filename)
