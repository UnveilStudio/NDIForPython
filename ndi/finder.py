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
from typing import List

from . import _lib


class NDISourceFinder:
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

    def __init__(
        self,
        show_local_sources: bool = True,
        groups: str | None = None,
        extra_ips: str | None = None,
    ):
        settings = _lib.NDIlib_find_create_t(
            show_local_sources=show_local_sources,
            p_groups=groups.encode() if groups else None,
            p_extra_ips=extra_ips.encode() if extra_ips else None,
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
        # wait_for_sources returns True if the list changed during the wait.
        # We don't care about the return — we always read whatever's current.
        _lib._dll.NDIlib_find_wait_for_sources(self._instance, ctypes.c_uint32(timeout_ms))
        return self.get_sources()

    def get_sources(self) -> List[str]:
        """
        Return the list of currently-known NDI source names. Non-blocking.
        Names look like ``"MACHINE-NAME (Source Name)"``.
        """
        count = ctypes.c_uint32(0)
        ptr = _lib._dll.NDIlib_find_get_current_sources(self._instance, ctypes.byref(count))
        if not ptr or count.value == 0:
            return []
        # The returned array is owned by the finder; we just read names out of it.
        names: List[str] = []
        for i in range(count.value):
            raw = ptr[i].p_ndi_name
            if raw:
                names.append(raw.decode("utf-8", errors="replace"))
        return names

    # ------------------------------------------------------------------ #

    def release(self) -> None:
        if self._instance:
            _lib._dll.NDIlib_find_destroy(self._instance)
            self._instance = None

    def __enter__(self) -> "NDISourceFinder":
        return self

    def __exit__(self, *_) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()

    def __repr__(self) -> str:
        return f"<NDISourceFinder instance={self._instance}>"
