"""Ancla una ventana al escritorio de Windows (como el modo "En el escritorio" de Rainmeter).

La ventana pasa a ser *propiedad* de Progman (la ventana del escritorio). Por eso:
- queda siempre justo encima del fondo/íconos y debajo de cualquier otra app;
- Win + D ("Mostrar escritorio") no la minimiza, porque es parte del escritorio.
No usa hooks ni inyecta nada en Explorer: solo cambia el dueño y el orden Z.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL

GWLP_HWNDPARENT = -8
GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
HWND_BOTTOM = wintypes.HWND(1) if _IS_WINDOWS else None
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010


def _progman() -> int | None:
    return user32.FindWindowW("Progman", None) or None


def pin(hwnd: int) -> None:
    """Hace a Progman dueño de la ventana y la manda al fondo."""
    if not _IS_WINDOWS:
        return
    progman = _progman()
    if not progman:
        return
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, progman)
    to_bottom(hwnd)


def to_bottom(hwnd: int) -> None:
    if _IS_WINDOWS:
        user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)


def keep_pinned(hwnd: int) -> None:
    """Llamar cada tanto: si Explorer se reinició (Progman nuevo), vuelve a anclar."""
    if not _IS_WINDOWS:
        return
    progman = _progman()
    if progman and user32.GetWindow(hwnd, GW_OWNER) != progman:
        pin(hwnd)
    else:
        to_bottom(hwnd)
