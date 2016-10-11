# rocksmith

A python 3 package to deal with Rocksmith 2014 resources


## Usage

```sh
$ pyrocksmith -h
usage: pyrocksmith [-h] [--no-crypto] [--unpack FILE] [--pack DIRECTORY]
                   [--print-sng FILE]

Command line interface to the rocksmith python package.

optional arguments:
  -h, --help        show this help message and exit
  --no-crypto       do not perform encryption/decryption operations
  --unpack FILE     unpack a PSARC archive
  --pack DIRECTORY  pack a DIRECTORY into a PSARC archive
  --print-sng FILE  print a Rocksmith sng file as a JSON string
```


## Installation

Requires Python 3

```sh
pip3 install git+https://github.com/0x0L/rocksmith.git
```


## API

`PSARC`, `SNG` can operate on buffers (`parse` / `build`) or streams (`parse_stream` / `build_stream`)

### PSARC

To unpack the content of a PSARC file in memory

```python
from rocksmith import PSARC
content = PSARC().parse_stream(open('cherubrock_m.psarc', 'rb'))
```

`content` is a plain python dict from file names to data. To pack a dictionary into a PSARC

```python
PSARC().build_stream(content, open('cherubrock_repack_m.psarc', 'wb'))
```

The `PSARC` object takes an optional `crypto` argument which defaults to `True`. If `crypto` is set to `False` no encryption/decryption is applied.

### SNG

Rocksmith songs are easily readable

```python
from rocksmith import SNG
sng = SNG.parse(content['songs/bin/macos/cherubrock_combo.sng'])
```

`sng` is a dict-like container for inspecting rocksmith binary song format

```python
print(sng['metadata'])  # or simply, print(sng.metadata)
```

Repacking `sng` is similar to repacking PSARC

```python
repacked = SNG.build(sng)
```


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
