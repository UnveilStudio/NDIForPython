# NDIForPython — Mappa mentale dell'architettura

> **Versione documento:** 2026-04-28
> **DLL target:** `Processing.NDI.Lib.x64.dll` 6.1.1.0 (NDI 6 Runtime, Vizrt)
> **DLL location (esempio):** `C:\Program Files\NDI\NDI 6 Runtime\v6\`
> **Verifica empirica:** `tests/test_api_audit.py`,
> `tests/test_e2e_loopback.py`, `tests/test_variants.py`

Tutto quello che e' scritto qui e' grounded su:
- il sorgente di `ndi/_lib.py`, `ndi/sender.py`, `ndi/receiver.py`,
  `ndi/finder.py`
- l'output dei test sopra (33 audit OK, 4 quadranti BGRA preservati
  byte-per-byte sul loopback, 5 variant test passati).

Non ci sono supposizioni: ogni claim ha un test corrispondente o cita un
file specifico.

---

## 1. Stack runtime

```
+--------------------------------------------------------+
|  Codice utente (script, app, modello inferenza, ecc.)  |
+----------------------+---------------------------------+
                       |
                       v
+--------------------------------------------------------+
|  ndi/sender.py    ndi/finder.py    ndi/receiver.py     |   <- API pubblica
|                                                        |
|  classi thin: 1 ctypes call -> 1 DLL function          |
+----------------------+---------------------------------+
                       |
                       v
+--------------------------------------------------------+
|  ndi/_lib.py                                           |   <- core ctypes
|   - DLL search (bundled / env / std install paths)     |
|   - ctypes.CDLL(_DLL_PATH)                             |
|   - struct definitions (5 ctypes.Structure)            |
|   - function bindings (13 NDIlib_*)                    |
|   - NDIlib_initialize() chiamato all'import            |
+----------------------+---------------------------------+
                       |
                       v
+--------------------------------------------------------+
|  Processing.NDI.Lib.x64.dll (6.1.1.0)                  |
|   - flat C API, niente vtable                          |
|   - mDNS discovery + RTP-like transport over UDP/TCP   |
|   - color conversion built-in (UYVY/BGRA/RGBA)         |
+----------------------+---------------------------------+
                       |
                       v
+--------------------------------------------------------+
|  Sistema operativo / rete                              |
|   - mDNS / Bonjour                                     |
|   - UDP/TCP IPv4 sulla LAN                             |
+--------------------------------------------------------+
```

Confronto con spout2-python: **niente vtable COM-style**, niente
`GetSpout()` factory, niente DX11/OpenGL. NDI e' una libreria
*network*, non *GPU*.

---

## 2. DLL search e licenza

`ndi/_lib.py` cerca la DLL in quest'ordine:

1. `ndi/Processing.NDI.Lib.x64.dll` (slot riservato — **mai** popolato dal
   nostro pacchetto: la licenza Vizrt vieta la redistribuzione)
2. `$NDI_RUNTIME_DIR_V6\Processing.NDI.Lib.x64.dll` (env var settata
   dall'installer ufficiale NDI 6)
3. `$NDI_RUNTIME_DIR_V5\...` (NDI 5)
4. `C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll`
5. `C:\Program Files\NDI\NDI 5 Runtime\v5\Processing.NDI.Lib.x64.dll`
6. `C:\Program Files\NDI\NDI 6 SDK\Lib\x64\Processing.NDI.Lib.x64.dll`
7. `C:\Program Files\NDI\NDI 5 SDK\Lib\x64\Processing.NDI.Lib.x64.dll`

Se nessuno di questi esiste, `_lib.py` solleva `OSError` con un messaggio
che punta a `https://ndi.video`.

`NDI_NOTICE.md` e `README.md` documentano il vincolo di licenza.

**Verificato (audit):** `_lib._dll_path` =
`C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll` su
questo sistema.

---

## 3. ABI ctypes — struct e funzioni

### 3.1 Struct (ctypes.Structure) — verificato in `test_api_audit.py`

| Struct | n. campi | sizeof (bytes) |
|--------|----------|----------------|
| `NDIlib_source_t` | 2 | 16 |
| `NDIlib_find_create_t` | 3 | 24 |
| `NDIlib_recv_create_v3_t` | 5 | 40 |
| `NDIlib_send_create_t` | 4 | 24 |
| `NDIlib_video_frame_v2_t` | 12 | 72 |

I size sono coerenti con un layout x64 con `c_char_p`/`c_void_p` allineati a
8 byte e `c_int`/`c_uint`/`c_float` a 4. Niente padding extra inserito da
ctypes su questi field set.

### 3.2 Funzioni esposte (13)

Tutte hanno `restype` e `argtypes` configurati esplicitamente in
`_lib.py`. Verificato dal report di `test_api_audit.py`:

| Funzione | restype | argtypes |
|----------|---------|----------|
| `NDIlib_initialize` | bool | () |
| `NDIlib_destroy` | void | () |
| `NDIlib_send_create` | void* | (LP_NDIlib_send_create_t) |
| `NDIlib_send_destroy` | void | (void*) |
| `NDIlib_send_send_video_v2` | void | (void*, LP_video_frame) |
| `NDIlib_find_create_v2` | void* | (LP_find_create) |
| `NDIlib_find_destroy` | void | (void*) |
| `NDIlib_find_get_current_sources` | LP_source | (void*, LP_uint32) |
| `NDIlib_find_wait_for_sources` | bool | (void*, uint32) |
| `NDIlib_recv_create_v3` | void* | (LP_recv_create_v3) |
| `NDIlib_recv_destroy` | void | (void*) |
| `NDIlib_recv_capture_v2` | int (frame_type_e) | (void*, LP_video, void*, void*, uint32) |
| `NDIlib_recv_free_video_v2` | void | (void*, LP_video) |

`p_audio` e `p_metadata` sono dichiarati `c_void_p` per essere passati come
`None` (NULL) — il binding non espone audio o metadata.

### 3.3 FourCC (4-byte ASCII little-endian)

Verificato che ognuno corrisponde davvero al codice ASCII atteso:

| Costante | Valore esa | Bytes (LE) |
|----------|-----------|------------|
| `FOURCC_BGRA` | `0x41524742` | `b'BGRA'` |
| `FOURCC_BGRX` | `0x58524742` | `b'BGRX'` |
| `FOURCC_RGBA` | `0x41424752` | `b'RGBA'` |
| `FOURCC_RGBX` | `0x58424752` | `b'RGBX'` |

---

## 4. Lifecycle delle 3 classi pubbliche

### 4.1 `NDISender`

```
NDISender(name) ----> NDIlib_send_create_t { p_ndi_name=name, ...False... }
                  --> NDIlib_send_create  -> handle (void*)

send_frame(ptr, w, h, fourcc) -> NDIlib_video_frame_v2_t
                              -> NDIlib_send_send_video_v2(handle, &frame)
                              (non-blocking, NDI ha worker thread proprio)

release() -> NDIlib_send_destroy(handle); handle=None
__exit__/__del__ chiamano release()
```

### 4.2 `NDISourceFinder`

```
NDISourceFinder(show_local_sources) -> NDIlib_find_create_t
                                    -> NDIlib_find_create_v2 -> handle

wait(timeout_ms) -> NDIlib_find_wait_for_sources + get_sources()
get_sources()    -> NDIlib_find_get_current_sources -> array di NDIlib_source_t

release() -> NDIlib_find_destroy
```

**Nota importante (riga 80 di finder.py):** l'array ritornato da
`get_current_sources` e' di proprieta' della finder e **non va liberato**.
E' invalidato alla chiamata successiva.

### 4.3 `NDIReceiver`

```
NDIReceiver(source_name) :
  1. Discovery interno via NDISourceFinder(show_local_sources=True)
  2. Loop fino a connect_timeout_ms cercando match esatto p_ndi_name
  3. Copia NDIlib_source_t in struct propria (l'array della finder e'
     volatile)
  4. Chiama NDIlib_recv_create_v3 con color_format + bandwidth scelti

receive(timeout_ms) -> NDIlib_recv_capture_v2:
  ftype == VIDEO -> NDIVideoFrame(handle, video_struct) (con responsabilita'
                    di chiamare NDIlib_recv_free_video_v2 in release())
  altrimenti     -> _NO_FRAME (sentinel falsy + context-manager-safe)

release() -> NDIlib_recv_destroy
```

**Sottigliezza nel code path** (`receiver.py:225`): se `match is None`
solleva `TimeoutError`, **non** `RuntimeError`. Verificato in
`test_variants.py` Test 5.

---

## 5. Modello dati: `NDIVideoFrame`

```
NDIVideoFrame __slots__:
   _recv (handle), _video (struct), 
   width, height, fourcc, line_stride, fps_n, fps_d, data_ptr

as_numpy() -> view zero-copy:
   ArrayType = c_ubyte * (rows * line_stride)
   raw = ArrayType.from_address(data_ptr)
   return np.frombuffer(raw, dtype=uint8).reshape(rows, line_stride // 4, 4)

   ATTENZIONE: width effettiva potrebbe essere < line_stride // 4 a causa
   di alignment — fare arr[:, :frame.width] per droppare padding columns.

copy_to(buffer):
   ctypes.memmove(buffer, data_ptr, height * line_stride)

release() -> NDIlib_recv_free_video_v2(_recv, &_video)
```

**Verificato empiricamente sul loopback locale:**
- `frame.fourcc` ricevuto = `b'BGRA'` (default color_format) o `b'RGBA'`
  quando si chiede `RECV_COLOR_RGBX_RGBA`
- `frame.line_stride == width * 4` (quindi 1280 byte per 320 px) — il
  padding e' assente sul loopback. Su hardware esterno potrebbe non
  esserlo. Il codice lo gestisce comunque correttamente.
- `as_numpy()[:, :width, :3]` → BGR utilizzabile direttamente con
  `cv2.imshow`.

---

## 6. Cosa funziona end-to-end (verificato)

| Caso | Test | Esito |
|------|------|-------|
| Audit DLL, struct, FourCC, function bindings | `test_api_audit.py` | 33/33 OK |
| Loopback Python sender -> Python receiver, BGRA, 4-quadrants pattern | `test_e2e_loopback.py` | 60/60 frame, BGR avg per quadrante esatto |
| Sender RGBA -> Receiver default BGRX_BGRA (color conversion) | `test_variants.py` Test 1 | drift max 2 byte (compressione NDI lossy chroma) |
| Sender BGRA -> Receiver RGBX_RGBA (color conversion) | `test_variants.py` Test 2 | RGB=[51,100,200] vs atteso [50,100,200] |
| `frame.copy_to(bytearray)` | Test 3 | 118 campioni non-zero (atteso 117) |
| 10 rapid create/destroy NDISender | Test 4 | nessun crash/leak |
| `NDIReceiver` con sender inesistente | Test 5 | `TimeoutError` con messaggio chiaro |

---

## 7. Differenze concettuali con spout2-python

| Aspetto | spout2-python | NDIForPython |
|---------|---------------|--------------|
| Trasporto | DX11 shared texture (GPU) | UDP/TCP RTP-like (LAN) |
| Scope | stesso PC, stessa GPU | stessa LAN, qualsiasi GPU/macchina |
| Latenza | submillisecond (texture handle) | qualche ms (pipeline rete) |
| Banda | infinita (GPU memory) | limitata da NIC (~Gbps) |
| Loopback Python<->Python | NON funziona (vedi spout ARCHITECTURE.md) | **funziona perfettamente** |
| Dipendenze esterne | DLL bundled (BSD) | DLL **non** bundled (NDI License) |
| ABI | COM vtable (172 slot) | flat C API (13 funzioni) |

---

## 8. Limitazioni note

1. **No audio, no metadata.** Il binding passa `NULL` per `p_audio` e
   `p_metadata` in `NDIlib_recv_capture_v2`. Aggiungere supporto richiede
   estendere `_lib.py` (struct `NDIlib_audio_frame_v3_t`,
   `NDIlib_metadata_frame_t`) e i wrapper.
2. **Pixel format limitati a 4-byte/pixel.** UYVY (subsampling 4:2:2)
   non e' esposto via `as_numpy()`/`copy_to()` — il codice assume
   `bytes_per_pixel = 4`. Se chiedi `RECV_COLOR_FASTEST` la receive puo'
   produrre UYVY e i wrapper fanno calcoli sbagliati.
3. **Stride non comunicato in `send_frame`.** Hard-coded a `width * 4`.
   Buffer NumPy con `stride > w*4` darebbero pixel sfasati.
4. **Cleartext sulla LAN.** NDI standard non e' criptato. NDI HX e
   varianti TLS-capable non sono esposte.
5. **`__del__` di `NDISender` non ha `try/except`.** Se l'oggetto e' in
   stato anomalo durante GC puo' generare warning. `NDIReceiver` invece
   ha gia' il try/except.

---

## 9. Reproduce / verify

```bash
# Audit struct + funzioni + FourCC + lifecycle
cd D:/Kit109/kit-app-template/NDIForPython
python tests/test_api_audit.py

# E2E loopback con verifica BGRA pattern (4 quadranti)
python tests/test_e2e_loopback.py

# Test variazioni FourCC, color_format, copy_to, timeouts
python tests/test_variants.py
```

Output salvati: `tests/audit_report.json`, `tests/e2e_received.png`.
