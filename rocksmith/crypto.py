import zlib

from construct import Int32ub, Int32ul
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:  # cryptography moved the legacy CFB variant to "decrepit"
    from cryptography.hazmat.decrepit.ciphers.modes import CFB
except ImportError:
    from cryptography.hazmat.primitives.ciphers.modes import CFB

ARC_KEY = bytes.fromhex(
    "C53DB23870A1A2F71CAE64061FDD0E1157309DC85204D4C5BFDF25090DF2572C"
)
ARC_IV = bytes.fromhex("E915AA018FEF71FC508132E4BB4CEB42")
ARC_CIPHER = Cipher(algorithms.AES(ARC_KEY), CFB(ARC_IV))

MAC_KEY = bytes.fromhex(
    "9821330E34B91F70D0A48CBD625993126970CEA09192C0E6CDA676CC9838289D"
)

WIN_KEY = bytes.fromhex(
    "CB648DF3D12A16BF71701414E69619EC171CCA5D2A142E3E59DE7ADDA18A3A30"
)

PRF_KEY = bytes.fromhex(
    "728B369E24ED0134768511021812AFC0A3C25D02065F166B4BCC58CD2644F29E"
)

CONFIG_KEY = bytes.fromhex(
    "378B9026EE7DE70B8AF124C1E30978670F9EC8FD5E7285A86442DD73068C0473"
)

# sng container magic; console payloads keep it in the clear.
SNG_MAGIC = 0x4A


def decrypt_bom(data):
    decryptor = ARC_CIPHER.decryptor()
    return decryptor.update(data) + decryptor.finalize()


def encrypt_bom(data):
    encryptor = ARC_CIPHER.encryptor()
    return encryptor.update(data) + encryptor.finalize()


def aes_sng(key, iv):
    return Cipher(algorithms.AES(key), modes.CTR(iv))


def decrypt_sng(data, key):
    iv, data = data[8:24], data[24:]
    decryptor = aes_sng(key, iv).decryptor()
    decrypted = decryptor.update(data) + decryptor.finalize()
    length, payload = Int32ul.parse(decrypted[:4]), decrypted[4:]
    payload = zlib.decompress(payload)
    assert len(payload) == length
    return payload


def encrypt_sng(data, key):
    header = Int32ul.build(74) + Int32ul.build(3)
    iv = bytes(16)
    payload = Int32ul.build(len(data))
    payload += zlib.compress(data, zlib.Z_BEST_COMPRESSION)
    encryptor = aes_sng(key, iv).encryptor()
    encrypted = encryptor.update(payload) + encryptor.finalize()
    return header + iv + encrypted + bytes(56)


def wrap_sng_console(data, endian="<"):
    """Wrap a track payload in the plaintext '4a' container used by
    console (flags == 0) archives: u32 magic, u32 version, u32 size,
    then a zlib stream. X360/PS3 store the header big-endian."""
    def u32(value):
        return Int32ul.build(value) if endian == "<" else Int32ub.build(value)

    return u32(SNG_MAGIC) + u32(1) + u32(len(data)) + zlib.compress(
        data, zlib.Z_BEST_COMPRESSION
    )


def unwrap_sng_console(data):
    """Inverse of wrap_sng_console; the header endianness is read from
    the magic itself. Payloads without the container pass through."""
    if data[:4] not in (b"\x4a\x00\x00\x00", b"\x00\x00\x00\x4a"):
        return data

    endian = "<" if data[0] == SNG_MAGIC else ">"
    def u32(raw):
        return (Int32ul if endian == "<" else Int32ub).parse(raw)

    length = u32(data[8:12])
    payload = zlib.decompressobj().decompress(data[12:])
    assert len(payload) == length
    return payload


def decrypt_psarc(content, flags=4):
    """Unwrap sng payloads. flags != 0: PC/Mac AES-CTR containers.
    flags == 0: console plaintext containers, no keys involved.
    TODO: profile, config"""
    content = content.copy()
    for k in content:
        if flags == 0:
            if k.startswith("songs/bin/"):
                content[k] = unwrap_sng_console(content[k])
        elif "songs/bin/macos/" in k:
            content[k] = decrypt_sng(content[k], MAC_KEY)
        elif "songs/bin/generic/" in k:
            content[k] = decrypt_sng(content[k], WIN_KEY)
    return content


def encrypt_psarc(content, flags=4, endian="<"):
    """Wrap sng payloads for the target flags/endian; see
    decrypt_psarc for the container layouts.
    TODO: profile, config"""
    content = content.copy()
    for k in content:
        if flags == 0:
            if k.startswith("songs/bin/"):
                content[k] = wrap_sng_console(content[k], endian)
        elif "songs/bin/macos/" in k:
            content[k] = encrypt_sng(content[k], MAC_KEY)
        elif "songs/bin/generic/" in k:
            content[k] = encrypt_sng(content[k], WIN_KEY)
    return content
