"""
Low-level ctypes interface to Processing.NDI.Lib.x64.dll (NDI SDK 5 / 6).

The NDI C API is a flat set of exported functions (no vtable), so binding is
straightforward. We initialize the library once at import time and expose the
relevant structs and function handles.
"""
import ctypes
import os
import sys

if sys.platform != "win32":
    raise OSError("NDI is only supported on Windows (Processing.NDI.Lib.x64.dll)")

# --------------------------------------------------------------------------- #
# DLL search
# --------------------------------------------------------------------------- #

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_DLL_NAME = "Processing.NDI.Lib.x64.dll"

# Search order: bundled in this package → env vars → standard install paths.
_search = [os.path.join(_PKG_DIR, _DLL_NAME)]

for _env_key in ("NDI_RUNTIME_DIR_V6", "NDI_RUNTIME_DIR_V5"):
    _env_val = os.environ.get(_env_key)
    if _env_val:
        _search.append(os.path.join(_env_val, _DLL_NAME))

_search += [
    r"C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll",
    r"C:\Program Files\NDI\NDI 5 Runtime\v5\Processing.NDI.Lib.x64.dll",
    r"C:\Program Files\NDI\NDI 6 SDK\Lib\x64\Processing.NDI.Lib.x64.dll",
    r"C:\Program Files\NDI\NDI 5 SDK\Lib\x64\Processing.NDI.Lib.x64.dll",
]

_dll = None
_dll_path = None
for _p in _search:
    if os.path.exists(_p):
        try:
            _dll = ctypes.CDLL(_p)
            _dll_path = _p
            break
        except OSError:
            pass

if _dll is None:
    raise OSError(
        f"{_DLL_NAME} not found. Install NDI Runtime from https://ndi.video "
        f"or place the DLL next to this file: {_search[0]}"
    )

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# FourCC pixel formats
FOURCC_BGRA = 0x41524742   # b'BGRA' little-endian
FOURCC_RGBA = 0x41424752   # b'RGBA' little-endian
FOURCC_BGRX = 0x58524742   # b'BGRX' (alpha ignored)

# Frame format
FRAME_FORMAT_PROGRESSIVE = 1

# Pass 0 for timecode/timestamp → NDI synthesizes them automatically.

# --------------------------------------------------------------------------- #
# Structs
# --------------------------------------------------------------------------- #

class NDIlib_send_create_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name",  ctypes.c_char_p),   # sender name shown to receivers
        ("p_groups",    ctypes.c_char_p),   # NULL = default group
        ("clock_video", ctypes.c_bool),     # False: don't throttle to video clock
        ("clock_audio", ctypes.c_bool),
    ]


class NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("xres",                 ctypes.c_int),
        ("yres",                 ctypes.c_int),
        ("FourCC",               ctypes.c_uint),
        ("frame_rate_N",         ctypes.c_int),    # numerator   (e.g. 60)
        ("frame_rate_D",         ctypes.c_int),    # denominator (e.g. 1)
        ("picture_aspect_ratio", ctypes.c_float),  # 0.0 = xres/yres
        ("frame_format_type",    ctypes.c_int),
        ("timecode",             ctypes.c_int64),  # 0 = synthesize
        ("p_data",               ctypes.c_void_p),
        ("line_stride_in_bytes", ctypes.c_int),    # width * 4 for BGRA/RGBA
        ("p_metadata",           ctypes.c_char_p), # NULL = none
        ("timestamp",            ctypes.c_int64),  # 0 = synthesize
    ]

# --------------------------------------------------------------------------- #
# Function bindings
# --------------------------------------------------------------------------- #

_dll.NDIlib_initialize.restype  = ctypes.c_bool
_dll.NDIlib_initialize.argtypes = []

_dll.NDIlib_destroy.restype  = None
_dll.NDIlib_destroy.argtypes = []

_dll.NDIlib_send_create.restype  = ctypes.c_void_p
_dll.NDIlib_send_create.argtypes = [ctypes.POINTER(NDIlib_send_create_t)]

_dll.NDIlib_send_destroy.restype  = None
_dll.NDIlib_send_destroy.argtypes = [ctypes.c_void_p]

_dll.NDIlib_send_send_video_v2.restype  = None
_dll.NDIlib_send_send_video_v2.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(NDIlib_video_frame_v2_t),
]

# --------------------------------------------------------------------------- #
# One-time library initialisation
# --------------------------------------------------------------------------- #

if not _dll.NDIlib_initialize():
    raise RuntimeError("NDIlib_initialize() returned False — NDI library failed to start")
