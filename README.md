# rocksmith

A python 3 package to deal with Rocksmith 2014 resources


## Usage

```sh
$ pyrocksmith -h
usage: pyrocksmith [-h] [--no-crypto] [--unpack FILE] [--pack DIRECTORY]
                   [--print-sng FILE] [--wwise FILE] [--gpa FILE] [--dds FILE]

Command line interface to the rocksmith python package.

optional arguments:
  -h, --help        show this help message and exit
  --no-crypto       do not perform encryption/decryption operations
  --unpack FILE     unpack a PSARC archive
  --pack DIRECTORY  pack a DIRECTORY into a PSARC archive
  --print-sng FILE  print a Rocksmith sng file as a JSON string
  --wwise FILE      generate soundbanks from a music file
  --gpa FILE        parse GoPlayAlong xml file for synchronization
  --dds FILE        generate DirectDraw Surface textures
```


## Installation

Requires Python 3

```sh
pip3 install git+https://github.com/0x0L/rocksmith.git
```

Soundbank generation requires a working Audiokinetic Wwise installation.

DDS generation requires ImageMagick.

## TODO

* SNG missing fields

* Package manager: RDF graph, manifest, ...

  1. Higher level view of the bunch of files
  2. How to do lessons, multiple songs, etc..


* Audio tools:

  Wwise bindings almost done, should handle bnk generation smoothly


* Tone extractor / manager


* Automatic conversion from GPX tab + sync info to rocksmith song:

  1. SngCompiler (half-finished rs-utils)
  2. Need conventional semantic in gpx files for sections and other RS only attributes


* Vocals / Fonts / Lessons / Showlights
