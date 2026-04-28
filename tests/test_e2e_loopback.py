"""
Test E2E: sender Python in un processo, receiver Python in un altro.

Verifica che il pixel transfer attraversi NDI sulla loopback locale e che
il frame ricevuto contenga i dati attesi (BGRA pattern noto).
"""
from __future__ import annotations
import ctypes
import secrets
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

W, H = 320, 240
SOURCE_NAME = f"NDIE2E_{secrets.token_hex(3)}"

# Pattern noto: 4 quadranti di colore — top-left B, top-right G, bottom-left R, bottom-right yellow
# (in BGRA: per cv2 lo otterremo come BGR)
def make_test_pattern(w: int, h: int) -> np.ndarray:
    bgra = np.zeros((h, w, 4), dtype=np.uint8)
    bgra[..., 3] = 255
    bgra[:h//2,  :w//2, 0] = 200          # B
    bgra[:h//2,  w//2:, 1] = 200          # G
    bgra[h//2:,  :w//2, 2] = 200          # R
    bgra[h//2:,  w//2:, :3] = (50, 200, 200)  # yellow (B=50,G=200,R=200)
    return bgra


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print(f"E2E test: source='{SOURCE_NAME}', {W}x{H}\n")

    # Lancio sender in subprocess
    sender_code = (
        f"import sys; sys.path.insert(0, r'{ROOT}')\n"
        "import time, ctypes, numpy as np\n"
        "from ndi import NDISender, FOURCC_BGRA\n"
        "import sys\n"
        f"W, H = {W}, {H}\n"
        # ricreo il pattern
        "bgra = np.zeros((H, W, 4), dtype=np.uint8)\n"
        "bgra[..., 3] = 255\n"
        "bgra[:H//2, :W//2, 0] = 200\n"
        "bgra[:H//2, W//2:, 1] = 200\n"
        "bgra[H//2:, :W//2, 2] = 200\n"
        "bgra[H//2:, W//2:, :3] = (50, 200, 200)\n"
        f"with NDISender('{SOURCE_NAME}', fps_n=30) as s:\n"
        "    while True:\n"
        "        s.send_frame(bgra.ctypes.data, W, H, FOURCC_BGRA)\n"
        "        time.sleep(1/30)\n"
    )

    print("Avvio sender in subprocess...")
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", sender_code],
        cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    # Lascio tempo per la registrazione mDNS
    time.sleep(2.5)

    try:
        from ndi import NDISourceFinder, NDIReceiver

        # 1) Discovery
        print("\n-- Discovery --")
        with NDISourceFinder(show_local_sources=True) as finder:
            sources = finder.wait(timeout_ms=3000)
        print(f"  sorgenti trovate: {len(sources)}")
        for s in sources:
            print(f"    - {s!r}")
        target = next((s for s in sources if SOURCE_NAME in s), None)
        if target is None:
            print(f"\n[FAIL] '{SOURCE_NAME}' non trovato sulla LAN")
            return 1
        print(f"  target = {target!r}")

        # 2) Receive
        print("\n-- Receive --")
        with NDIReceiver(target, connect_timeout_ms=5000) as rx:
            print("  receiver creato. raccolgo frame...")
            received = 0
            non_zero = 0
            saved = None
            samples = []
            for i in range(60):
                with rx.receive(timeout_ms=200) as frame:
                    if not frame:
                        continue
                    received += 1
                    arr = frame.as_numpy()  # (H, W_padded, 4) uint8
                    bgr = arr[:, :frame.width, :3]
                    if int(bgr.sum()) > 0:
                        non_zero += 1
                    if saved is None and bgr.size > 0:
                        # Salvo il primo frame non vuoto
                        saved = bgr.copy()
                        samples.append({
                            "fourcc": frame.fourcc.to_bytes(4,"little").decode("ascii", errors="replace"),
                            "size": (frame.width, frame.height),
                            "stride": frame.line_stride,
                            "fps": (frame.fps_n, frame.fps_d),
                        })

            print(f"  frame ricevuti  : {received}/60")
            print(f"  con pixel != 0  : {non_zero}")
            if samples:
                print(f"  primo frame info: {samples[0]}")

            if saved is not None:
                out = ROOT / "tests" / "e2e_received.png"
                cv2.imwrite(str(out), saved)
                print(f"  salvato: {out}")

                # Verifica pattern: 4 quadranti dominanti
                h, w = saved.shape[:2]
                tl = saved[:h//2, :w//2]
                tr = saved[:h//2, w//2:]
                bl = saved[h//2:, :w//2]
                br = saved[h//2:, w//2:]
                # Mean per canale per quadrante
                def avg(q): return [int(c) for c in q.mean(axis=(0,1))]
                print(f"  TL (atteso B>>R,G): BGR avg = {avg(tl)}")
                print(f"  TR (atteso G>>B,R): BGR avg = {avg(tr)}")
                print(f"  BL (atteso R>>B,G): BGR avg = {avg(bl)}")
                print(f"  BR (atteso giallo): BGR avg = {avg(br)}")

                ok = (
                    avg(tl)[0] > avg(tl)[1] and avg(tl)[0] > avg(tl)[2] and
                    avg(tr)[1] > avg(tr)[0] and avg(tr)[1] > avg(tr)[2] and
                    avg(bl)[2] > avg(bl)[0] and avg(bl)[2] > avg(bl)[1] and
                    avg(br)[1] > 100 and avg(br)[2] > 100  # G+R alti
                )
                if ok:
                    print("\n>>> SUCCESSO: pattern BGRA preservato attraverso NDI!")
                    rc = 0
                else:
                    print("\n>>> FAIL: pattern non corrisponde alle attese")
                    rc = 1
            else:
                print("\n>>> FAIL: nessun frame salvato")
                rc = 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    return rc


if __name__ == "__main__":
    sys.exit(main())
