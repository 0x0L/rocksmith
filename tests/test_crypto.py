import builtins
import importlib

# CFB moved to cryptography.hazmat.decrepit in 43; rocksmith.crypto's
# fallback import covers older releases. Take the real class from
# wherever this release keeps it.
try:
    from cryptography.hazmat.decrepit.ciphers.modes import CFB as REAL_CFB
except ImportError:
    from cryptography.hazmat.primitives.ciphers.modes import CFB as REAL_CFB

from cryptography.hazmat.primitives.ciphers import modes as prim_modes

_MISSING = object()


def test_legacy_cfb_import_path():
    import rocksmith.crypto as crypto

    real_import = builtins.__import__

    def no_decrepit(name, *args, **kwargs):
        if name == "cryptography.hazmat.decrepit.ciphers.modes":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    # bind CFB in the module dict so the fallback sees an old-style
    # primitives.modes without its lazy decrepit getattr firing
    old = prim_modes.__dict__.get("CFB", _MISSING)
    prim_modes.__dict__["CFB"] = REAL_CFB
    builtins.__import__ = no_decrepit
    try:
        importlib.reload(crypto)
    finally:
        builtins.__import__ = real_import
        if old is _MISSING:
            del prim_modes.__dict__["CFB"]
        else:
            prim_modes.__dict__["CFB"] = old
    data = b"a chart worth compressing" * 20
    assert crypto.decrypt_sng(crypto.encrypt_sng(data, b"0" * 16), b"0" * 16) == data
