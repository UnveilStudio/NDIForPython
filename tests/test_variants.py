"""
Test variazioni: FOURCC_RGBA invece di BGRA, color_format diverso,
copy_to() invece di as_numpy(), rapid create/destroy.
"""
from __future__ import annotations
import ctypes, secrets, subprocess, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

W, H = 200, 150
SRC = f"NDIVar_{secrets.token_hex(2)}"


def spawn_sender(fourcc_name: str):
    """Spawn sender che invia con il fourcc dato (BGRA o RGBA).
       Pattern: 200 R + 100 G + 50 B + 255 A per ogni pixel.
    """
    code = f"""
import sys; sys.path.insert(0, r'{ROOT}')
import time, numpy as np
from ndi import NDISender, FOURCC_{fourcc_name}
W, H = {W}, {H}
# Buffer in formato {fourcc_name}: 4 byte per pixel nell'ordine indicato dal nome
arr = np.zeros((H, W, 4), dtype=np.uint8)
{"arr[..., 0] = 200; arr[..., 1] = 100; arr[..., 2] = 50; arr[..., 3] = 255  # B,G,R,A" if fourcc_name == "BGRA" else "arr[..., 0] = 200; arr[..., 1] = 100; arr[..., 2] = 50; arr[..., 3] = 255  # R,G,B,A"}
with NDISender('{SRC}', fps_n=30) as s:
    while True:
        s.send_frame(arr.ctypes.data, W, H, FOURCC_{fourcc_name})
        time.sleep(1/30)
"""
    return subprocess.Popen([sys.executable, "-u", "-c", code],
                            cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)


def discover_target(name_substring: str, timeout_ms: int = 4000):
    from ndi import NDISourceFinder
    with NDISourceFinder(show_local_sources=True) as f:
        f.wait(timeout_ms=timeout_ms)
        names = f.get_sources()
    return next((n for n in names if name_substring in n), None)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    failures = 0

    # ==== TEST 1: FOURCC_RGBA con receiver default (BGRX_BGRA) ====
    # NDI deve fare il color conversion sotto.
    print("=== TEST 1: sender RGBA -> receiver default (BGRX_BGRA) ===")
    proc = spawn_sender("RGBA")
    time.sleep(2.5)
    try:
        target = discover_target(SRC)
        assert target, f"sender '{SRC}' non trovato"
        from ndi import NDIReceiver
        with NDIReceiver(target, connect_timeout_ms=5000) as rx:
            for _ in range(20):
                with rx.receive(timeout_ms=200) as frame:
                    if not frame:
                        continue
                    arr = frame.as_numpy()[:, :frame.width, :3]
                    # Sender: R=200,G=100,B=50  -> in receiver default BGRA: B=50, G=100, R=200
                    bgr = arr.mean(axis=(0,1))
                    print(f"  fourcc ricevuto = {frame.fourcc.to_bytes(4,'little')}, "
                          f"BGR avg = {[int(c) for c in bgr]}")
                    expect = (50, 100, 200)
                    ok = all(abs(int(bgr[i]) - expect[i]) < 10 for i in range(3))
                    print(f"  match expected B=50 G=100 R=200 ? {'OK' if ok else 'FAIL'}")
                    if not ok:
                        failures += 1
                    break
            else:
                print("  FAIL: nessun frame ricevuto")
                failures += 1
    except Exception as e:
        print(f"  EXC: {e!r}")
        failures += 1
    finally:
        proc.terminate(); proc.wait(timeout=3)

    # ==== TEST 2: receiver con color_format=RGBX_RGBA ====
    # Sender BGRA -> receiver chiede RGBX_RGBA -> arrivati con R/G/B nell'ordine RGB
    print("\n=== TEST 2: sender BGRA -> receiver color_format=RGBX_RGBA ===")
    proc = spawn_sender("BGRA")
    time.sleep(2.5)
    try:
        target = discover_target(SRC)
        assert target, "sender not found"
        from ndi import NDIReceiver, RECV_COLOR_RGBX_RGBA
        with NDIReceiver(target, color_format=RECV_COLOR_RGBX_RGBA,
                         connect_timeout_ms=5000) as rx:
            for _ in range(20):
                with rx.receive(timeout_ms=200) as frame:
                    if not frame:
                        continue
                    arr = frame.as_numpy()[:, :frame.width, :3]
                    # Sender BGRA: B=200,G=100,R=50 -> receiver RGBA: R=50,G=100,B=200
                    rgb = arr.mean(axis=(0,1))
                    print(f"  fourcc ricevuto = {frame.fourcc.to_bytes(4,'little')}, "
                          f"RGB avg = {[int(c) for c in rgb]}")
                    expect = (50, 100, 200)
                    ok = all(abs(int(rgb[i]) - expect[i]) < 10 for i in range(3))
                    print(f"  match expected R=50 G=100 B=200 ? {'OK' if ok else 'FAIL'}")
                    if not ok:
                        failures += 1
                    break
            else:
                print("  FAIL: nessun frame ricevuto")
                failures += 1
    except Exception as e:
        print(f"  EXC: {e!r}")
        failures += 1
    finally:
        proc.terminate(); proc.wait(timeout=3)

    # ==== TEST 3: copy_to() invece di as_numpy() ====
    print("\n=== TEST 3: NDIVideoFrame.copy_to(bytearray) ===")
    proc = spawn_sender("BGRA")
    time.sleep(2.5)
    try:
        target = discover_target(SRC)
        assert target, "sender not found"
        from ndi import NDIReceiver
        with NDIReceiver(target, connect_timeout_ms=5000) as rx:
            for _ in range(20):
                with rx.receive(timeout_ms=200) as frame:
                    if not frame:
                        continue
                    size = frame.height * frame.line_stride
                    buf = bytearray(size)
                    frame.copy_to(buf)
                    nz = sum(1 for b in buf[::1024] if b != 0)
                    print(f"  copy_to {size} byte: non-zero campioni (su 1/1024) = {nz}")
                    if nz == 0:
                        print("  FAIL: copy_to ha prodotto buffer zero")
                        failures += 1
                    else:
                        print("  OK")
                    break
            else:
                failures += 1
    except Exception as e:
        print(f"  EXC: {e!r}")
        failures += 1
    finally:
        proc.terminate(); proc.wait(timeout=3)

    # ==== TEST 4: rapid create/destroy sender ====
    print("\n=== TEST 4: rapid create/destroy sender (no leak/segfault) ===")
    try:
        from ndi import NDISender
        for i in range(10):
            with NDISender(f"RapidSnd_{i}") as s:
                pass
        print("  10 cicli create/destroy: OK")
    except Exception as e:
        print(f"  EXC: {e!r}")
        failures += 1

    # ==== TEST 5: receive() timeout corto -> _NoFrame ====
    print("\n=== TEST 5: receive() su sender mai esistito -> TimeoutError ===")
    try:
        from ndi import NDIReceiver
        try:
            rx = NDIReceiver("NonExistent_xxx", connect_timeout_ms=1500)
            rx.release()
            print("  FAIL: doveva sollevare TimeoutError")
            failures += 1
        except TimeoutError as e:
            print(f"  OK: TimeoutError con messaggio: {e}")
    except Exception as e:
        print(f"  EXC inattesa: {e!r}")
        failures += 1

    print(f"\n=== TOTALI: failures = {failures} ===")
    return failures


if __name__ == "__main__":
    sys.exit(main())
