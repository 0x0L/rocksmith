# rocksmith

A python 3 package to deal with Rocksmith 2014 resources.

## Usage

```sh
$ pyrocksmith -h
usage: pyrocksmith [-h] [--no-crypto] [--extract PSARC] [--create DIRECTORY]

Command line interface to the rocksmith python package.

optional arguments:
  -h, --help          show this help message and exit
  --no-crypto         do NOT perform cryptographic operations
  --extract PSARC     unpack a PSARC archive
  --create DIRECTORY  create a PSARC archive
```

## Installation

```sh
pip3 install git+https://github.com/0x0L/rocksmith.git
```

## API

To load the content of a PSARC file into memory

```python
from rocksmith import *
content = PSARC.parse_stream(open('cherubrock_m.psarc', 'rb'))
```

`content` is a dictionary mapping from filenames to data. No cryptographic operation is performed by the `PSARC` object.

```python
sng = CryptoSNG(MAC_KEY).parse(content['songs/bin/macos/cherubrock_combo.sng'])
print(sng.metadata)
```

`sng` is a dict-like container for inspecting rocksmith binary song format.

By default the command line utility does perform cryptographic operations (unless `--no-crypto`). To read an already decrypted sng file, use the `SNG` object instead of `CryptoSNG`:

```python
sng = SNG.parse(open('./cherubrock_m/songs/bin/macos/cherubrock_combo.sng', 'rb'))
```

Repacking is equally easy:

```python
content['songs/bin/macos/cherubrock_combo.sng'] = CryptoSNG(MAC_KEY).build(sng)
PSARC.build_stream(content, open('cherubrock_repack_m.psarc', 'wb'))
```

`PSARC`, `SNG` and `CryptoSNG` can all operate both on buffers and streams.

## TODO

* Package manager: RDF graph, manifest, ...
* Audio tools: Wwise bindings, WAV converter, intro silence, preview
* Image tools: Convert, Manipulate DDS
* Tone extractor
* Automatic conversion Guitar pro tab + Time sync info (ie GoPlayAlong) to rocksmith song
