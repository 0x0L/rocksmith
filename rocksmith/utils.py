import os

from .crypto import decrypt_sng, encrypt_sng, MAC_KEY, WIN_KEY

def path2dict(path):
    """Reads a path into a dictionary"""
    n = len(path) + 1
    d = {}
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            with open(fullpath, 'rb') as fh:
                d[fullpath[n:]] = fh.read()
    return d

def dict2path(d, dest='.'):
    """Writes a dict into a path"""
    for filepath, data in d.items():
        filename = os.path.join(dest, filepath)
        path = os.path.dirname(filename)
        if not os.path.exists(path):
            os.makedirs(path)
        with open(filename, 'wb') as fh:
            fh.write(data)

def encrypt_psarc(content):
    ## TODO profile, config
    for k in content:
        if 'songs/bin/macos/' in k:
            content[k] = encrypt_sng(content[k], MAC_KEY)
        elif 'songs/bin/generic/' in k:
            content[k] = encrypt_sng(content[k], WIN_KEY)

def decrypt_psarc(content):
    ## TODO profile, config
    for k in content:
        if 'songs/bin/macos/' in k:
            content[k] = decrypt_sng(content[k], MAC_KEY)
        elif 'songs/bin/generic/' in k:
            content[k] = decrypt_sng(content[k], WIN_KEY)
