"""
NDISourceFinder — discover NDI senders on the local network (mDNS).

Usage::

    from ndi import NDISourceFinder

    with NDISourceFinder() as finder:
        names = finder.wait(timeout_ms=2000)
        for n in names:
            print("found:", n)

Names look like ``"MACHINE-NAME (Source Name)"`` — that's what an NDI
receiver expects when connecting.
"""
import ctypes
import time
from typing import List, Optional

from . import _lib
from ._base import _NDIHandle


class NDISourceFinder(_NDIHandle):
    """
    Wraps NDIlib_find_* to enumerate NDI sources on the LAN.

    Parameters
    ----------
    show_local_sources : bool
        If True, sources running on the same machine are also returned.
        Default True (matches what most users expect when developing).
    groups : str | None
        Comma-separated list of NDI groups to search in. None = default group.
    extra_ips : str | None
        Comma-separated list of additional IP addresses to scan (for hosts
        outside the local mDNS scope). None = none.
    """

    _destroy_fn = staticmethod(_lib._dll.NDIlib_find_destroy)

    def __init__(
        self,
        show_local_sources: bool = True,
        groups: str | None = None,
        extra_ips: str | None = None,
    ):
        super().__init__()
        settings = _lib.NDIlib_find_create_t(
            show_local_sources=show_local_sources,
            p_groups=_lib._to_cstr(groups),
            p_extra_ips=_lib._to_cstr(extra_ips),
        )
        self._instance = _lib._dll.NDIlib_find_create_v2(ctypes.byref(settings))
        if not self._instance:
            raise RuntimeError("NDIlib_find_create_v2 returned NULL — failed to create finder")

    # ------------------------------------------------------------------ #

    def wait(self, timeout_ms: int = 2000) -> List[str]:
        """
        Block up to ``timeout_ms`` for the source list to change, then return
        the current list of source names.

        Calling this before any sources have been seen on the LAN gives mDNS
        time to settle. After the first call you can also use
        :meth:`get_sources` for non-blocking polling.
        """
        _lib._dll.NDIlib_find_wait_for_sources(self._instance, timeout_ms)
        return self.get_sources()

    def get_sources(self) -> List[str]:
        """
        Return the list of currently-known NDI source names. Non-blocking.
        Names look like ``"MACHINE-NAME (Source Name)"``.
        """
        names: List[str] = []
        for src in self._iter_current_sources():
            if src.p_ndi_name:
                names.append(src.p_ndi_name.decode("utf-8", errors="replace"))
        return names

    def find_source(
        self, source_name: str, timeout_ms: int = 5000
    ) -> Optional[_lib.NDIlib_source_t]:
        """
        Block up to ``timeout_ms`` waiting for a source whose name matches
        ``source_name`` exactly. Returns a copy of the matching
        :class:`NDIlib_source_t` (safe to keep), or ``None`` on timeout.

        The copy is necessary because the SDK's source list is invalidated
        on the next discovery call.
        """
        wanted = source_name.encode("utf-8")
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            # 200 ms slice keeps Ctrl+C latency tolerable.
            slice_ms = min(200, max(1, int((deadline - time.monotonic()) * 1000)))
            _lib._dll.NDIlib_find_wait_for_sources(self._instance, slice_ms)
            for src in self._iter_current_sources():
                if src.p_ndi_name == wanted:
                    return _lib.NDIlib_source_t(
                        p_ndi_name=src.p_ndi_name,
                        p_url_address=src.p_url_address,
                    )
        return None

    # ------------------------------------------------------------------ #

    def _iter_current_sources(self):
        """Iterate the SDK-owned source array. Pointer becomes invalid on the
        next find call — caller must consume eagerly."""
        count = ctypes.c_uint32(0)
        ptr = _lib._dll.NDIlib_find_get_current_sources(self._instance, ctypes.byref(count))
        if not ptr or count.value == 0:
            return
        for i in range(count.value):
            yield ptr[i]

    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return f"<NDISourceFinder instance={self._instance}>"
