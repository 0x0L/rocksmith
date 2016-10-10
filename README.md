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

`content` is a python dict from filenames to data

```python
print(content['appid.appid'])
```

The `PSARC` object does not handle the encryption/decryption of any file. To open a `sng` file in memory

```python
sng = CryptoSNG(MAC_KEY).parse(content['songs/bin/macos/cherubrock_combo.sng'])
```

`sng` is a dict-like container for inspecting rocksmith binary song format.

```python
print(sng['metadata'])  # or simply, print(sng.metadata)
```

By default the command line utility does perform cryptographic operations (unless `--no-crypto`). To read an already decrypted sng file, use the `SNG` object instead of `CryptoSNG`

```python
sng = SNG.parse(open('./cherubrock_m/songs/bin/macos/cherubrock_combo.sng', 'rb'))
```

Repacking a PSARC file is equally easy

```python
content['songs/bin/macos/cherubrock_combo.sng'] = CryptoSNG(MAC_KEY).build(sng)
PSARC.build_stream(content, open('cherubrock_repack_m.psarc', 'wb'))
```

`PSARC`, `SNG` and `CryptoSNG` can all operate on buffers or streams.

## TODO

* SNG missing fields

* Package manager: RDF graph, manifest, ...

  1. Higher level view of the bunch of files
  2. How to do lessons, multiple songs, etc..


* Audio tools:

  1. Wwise bindings (ideally should also handle .bnk generation)
  2. Audio converter, add intro silence, make preview: ffmpeg or similar


* Image tools: ImageMagick

* Tone extractor / manager

* Automatic conversion Guitar pro tab + Time sync info (ie GoPlayAlong) to rocksmith song:

  1. GPX reader (done rs-utils)
  2. GoPlayAlong reader (done rs-utils)
  3. SngCompiler (half-finished rs-utils)
  4. Need conventional semantic in gpx files for sections and other RS only attributes
