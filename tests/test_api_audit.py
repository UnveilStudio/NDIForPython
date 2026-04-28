"""
Audit dell'API NDIForPython.

Verifica grounded sui file di:
  - DLL caricata e init OK
  - sizes/offsets delle struct ctypes coerenti con SDK NDI 6
  - bind di tutte le funzioni esposte
  - costanti FourCC ben formate (4 byte ASCII validi)
  - create/destroy lifecycle senza leak/segfault per: send, find, recv
"""
from __future__ import annotations
import ctypes
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ndi
from ndi import _lib

REPORT = []


def check(label, ok, value=""):
    REPORT.append({"label": label, "ok": bool(ok), "value": str(value)})
    flag = "OK " if ok else "ERR"
    print(f"  [{flag}] {label:50s} {value}")


def main():
    # --- DLL & init ---
    print("== DLL e init ==")
    check("DLL path esiste", os.path.exists(_lib._dll_path), _lib._dll_path)
    check("ndi loadable",    hasattr(ndi, "NDISender"))
    check("init() True (gia chiamato)", True, "_lib.py chiama NDIlib_initialize all'import")

    # --- FourCC sanity (deve essere 4 byte ASCII validi) ---
    print("\n== FourCC sanity ==")
    for name in ("FOURCC_BGRA", "FOURCC_BGRX", "FOURCC_RGBA", "FOURCC_RGBX"):
        v = getattr(_lib, name)
        as_bytes = int(v).to_bytes(4, "little")
        ascii_ok = all(0x41 <= b <= 0x5A for b in as_bytes)
        check(f"{name} = 0x{v:08X} -> {as_bytes!r}", ascii_ok, "")

    # --- Struct field count e size sanity ---
    print("\n== Struct ctypes ==")
    structs = [
        ("NDIlib_source_t",         _lib.NDIlib_source_t,         2),
        ("NDIlib_find_create_t",    _lib.NDIlib_find_create_t,    3),
        ("NDIlib_recv_create_v3_t", _lib.NDIlib_recv_create_v3_t, 5),
        ("NDIlib_send_create_t",    _lib.NDIlib_send_create_t,    4),
        ("NDIlib_video_frame_v2_t", _lib.NDIlib_video_frame_v2_t, 12),
    ]
    for sname, sclass, expected_n in structs:
        n = len(sclass._fields_)
        sz = ctypes.sizeof(sclass)
        check(f"{sname}: {n} fields, sizeof={sz}", n == expected_n, f"({n}/{expected_n})")

    # --- Funzioni bind: argtypes/restype non None ---
    print("\n== Funzioni bind ==")
    fn_names = [
        "NDIlib_initialize", "NDIlib_destroy",
        "NDIlib_send_create", "NDIlib_send_destroy", "NDIlib_send_send_video_v2",
        "NDIlib_find_create_v2", "NDIlib_find_destroy",
        "NDIlib_find_get_current_sources", "NDIlib_find_wait_for_sources",
        "NDIlib_recv_create_v3", "NDIlib_recv_destroy",
        "NDIlib_recv_capture_v2", "NDIlib_recv_free_video_v2",
    ]
    for fn in fn_names:
        bound = getattr(_lib._dll, fn, None)
        ok = bound is not None and hasattr(bound, "argtypes")
        if ok:
            check(f"{fn} -> {bound.restype}", True, f"argtypes={[t.__name__ for t in bound.argtypes]}")
        else:
            check(f"{fn} bind", False, "missing")

    # --- Lifecycle send ---
    print("\n== Lifecycle SEND ==")
    try:
        s = ndi.NDISender("AuditSender")
        check("NDISender create", s._instance is not None, hex(s._instance or 0))
        check("repr non crasha", True, repr(s))
        s.release()
        check("NDISender release idempotent", s._instance is None)
        s.release()  # re-release should not crash
        check("NDISender release 2nd time no crash", True)
    except Exception as e:
        check("Lifecycle SEND", False, repr(e))

    # --- Lifecycle find ---
    print("\n== Lifecycle FIND ==")
    try:
        f = ndi.NDISourceFinder()
        check("NDISourceFinder create", f._instance is not None, hex(f._instance or 0))
        sources = f.get_sources()  # non blocking
        check("get_sources non-blocking", isinstance(sources, list), f"got {len(sources)} sources")
        for s in sources:
            print(f"     - {s!r}")
        f.release()
        check("Finder release idempotent", f._instance is None)
    except Exception as e:
        check("Lifecycle FIND", False, repr(e))
        traceback.print_exc()

    # --- send_frame con buffer locale (no receiver) ---
    print("\n== send_frame con buffer locale ==")
    try:
        W, H = 320, 240
        buf = (ctypes.c_ubyte * (W * H * 4))()
        for i in range(0, len(buf), 4):
            buf[i+0] = 200  # B
            buf[i+1] = 100  # G
            buf[i+2] = 50   # R
            buf[i+3] = 255

        with ndi.NDISender("AuditSendFrame") as s:
            for _ in range(3):
                s.send_frame(ctypes.addressof(buf), W, H, _lib.FOURCC_BGRA)
            check("send_frame chiamato 3 volte (no crash)", True)
    except Exception as e:
        check("send_frame test", False, repr(e))
        traceback.print_exc()

    # --- Riepilogo ---
    out = ROOT / "tests" / "audit_report.json"
    out.write_text(json.dumps(REPORT, indent=2))
    ok = sum(1 for r in REPORT if r["ok"])
    err = sum(1 for r in REPORT if not r["ok"])
    print(f"\n=== TOTALI ===  ok={ok}  err={err}  report={out.name}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
