# NDI® Trademark and Runtime Notice

This project is an **unofficial, third-party Python binding** built on top of
the **NDI® SDK**. It is not affiliated with, endorsed by, or sponsored by
Vizrt Group or NewTek.

## Trademark

> NDI® is a registered trademark of Vizrt Group.

The "NDI" name and logo are used here strictly for descriptive interoperability
purposes (i.e. to indicate that this Python package speaks the NDI protocol).

## NDI Runtime / SDK is NOT bundled

This package does **not** ship `Processing.NDI.Lib.x64.dll` or any other NDI
binary, because the NDI SDK has its own licence (the NDI SDK Licence Agreement)
which governs redistribution and is **not** compatible with simply attaching
the DLL to a public Python package.

End users must obtain the NDI runtime themselves, free of charge, from the
official source:

- **NDI Runtime**: https://ndi.video/download-ndi-sdk/
- **NDI SDK** (developers): same page

By installing the NDI Runtime, users accept the NDI SDK Licence Agreement
directly with Vizrt — this project is not a party to that agreement.

## What this Python package gives you

A thin `ctypes` wrapper that:

1. Searches well-known install paths (`C:\Program Files\NDI\NDI 6 Runtime\...`,
   `NDI 5`, the `NDI_RUNTIME_DIR_V6` / `NDI_RUNTIME_DIR_V5` env vars) for the
   already-installed Runtime DLL.
2. Loads it and exposes a Pythonic `NDISender` class.

If the Runtime is not installed, `import ndi` raises a clear `OSError` pointing
the user to https://ndi.video.

## Attribution

If you publish work that uses this package, we'd appreciate a mention of:

- The official NDI website: https://ndi.video
- This repository: https://github.com/UnveilStudio/NDIForPython

Required by Vizrt for any product that uses NDI: the on-screen / documentation
attribution of the NDI® trademark with the registered-mark symbol on first
significant use, exactly as written above.
