"""
Shared base class for NDI handle wrappers.

Holds the opaque DLL instance pointer, the context-manager protocol, and a
``release()`` template that calls a subclass-provided destroy function.
"""


class _NDIHandle:
    """Common lifecycle for objects that wrap an NDIlib_*_create handle."""

    # Subclasses set this to the appropriate _dll.NDIlib_*_destroy callable.
    _destroy_fn = staticmethod(lambda _: None)

    def __init__(self):
        # Set first so __del__ is safe even if a subclass raises before
        # populating the real instance pointer.
        self._instance = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()

    def __del__(self):
        if getattr(self, "_instance", None) is None:
            return
        try:
            self.release()
        except Exception:
            pass

    def release(self):
        """Destroy the underlying NDI resource and free its handle."""
        if self._instance:
            type(self)._destroy_fn(self._instance)
            self._instance = None
