import zlib
from construct import *

from .crypto import aes_sng, pad

def array(subcon):
    return PrefixedArray(Int32ul, subcon)

BEAT = Struct(
    'time' / Float32l,
    'measure' / Int16ul,
    'beat' / Int16ul,
    'phraseIteration' / Int32ul,
    'mask' / Int32ul,
)

PHRASE = Struct(
    'solo' / Int8sl,
    'disparity' / Int8sl,
    'ignore' / Int8sl,
    Padding(1),
    'maxDifficulty' / Int32ul,
    'phraseIterationLinks' / Int32ul,
    'name' / String(32, encoding='utf8')
)

CHORD_TEMPLATE = Struct(
    'mask' / Int32ul,
    'frets' / Int8sl[6],
    'fingers' / Int8sl[6],
    'notes' / Int32sl[6],
    'name' / String(32, encoding='utf8')
)

BEND = Struct(
    'time' / Float32l,
    'step' / Float32l,
    Padding(3),
    'UNK' / Int8sl
)

BEND_SEQUENCE = Struct(
    'bendValues' / BEND[32],
    'count' / Int32ul
)

CHORD_NOTE = Struct(
    'mask' / Int32ul[6],
    'bends' / BEND_SEQUENCE[6],
    'slideTo' / Int8sl[6],
    'slideUnpitchTo' / Int8sl[6],
    'vibrato' / Int16sl[6],
)

VOCAL = Struct(
    'time' / Float32l,
    'note' / Int32sl,
    'length' / Float32l,
    'lyrics' / String(48, encoding='utf8')
)

TEXTURE = Struct(
    'fontpath' / String(128, encoding='ascii'),
    'fontpathLength' / Int32ul,
    Padding(4),
    'width' / Int32ul,
    'height' / Int32ul
)

DEFINITION = Struct(
    'name' / String(12, encoding='utf8'),
    'rect1' / Float32l[4],
    'rect2' / Float32l[4],
)

SYMBOLS = Struct(
    'header' / array(Int32sl[8]),
    'texture' / array(TEXTURE),
    'definition' / array(DEFINITION)
)

PHRASE_ITERATION = Struct(
    'phraseId' / Int32ul,
    'time' / Float32l,
    'endTime' / Float32l,
    'difficulty' / Int32ul[3]
)

PHRASE_EXTRA_INFO_BY_LEVEL = Struct(
    'phraseId' / Int32ul,
    'difficulty' / Int32ul,
    'empty' / Int32ul,
    'levelJump' / Int8sl,
    'redundant' / Int16sl,
    Padding(1)
)

NEW_LINKED_DIFF = Struct(
    'levelBreak' / Int32sl,
    'nld_phrase' / array(Int32ul)
)

ACTION = Struct(
    'time' / Float32l,
    'name' / String(256, encoding='ascii')
)

EVENT = Struct(
    'time' / Float32l,
    'code' / String(256, encoding='ascii')
)

TONE = Struct(
    'time' / Float32l,
    'id' / Int32ul
)

DNA = Struct(
    'time' / Float32l,
    'id' / Int32ul
)

SECTION = Struct(
    'name' / String(32, encoding='utf8'),
    'number' / Int32ul,
    'startTime' / Float32l,
    'endTime' / Float32l,
    'startPhraseIterationId' / Int32ul,
    'endPhraseIterationId' / Int32ul,
    'stringMask' / Int8sl[36]
)

ANCHOR = Struct(
    'time' / Float32l,
    'endTime' / Float32l,
    'UNK_time' / Float32l,
    'UNK_time2' / Float32l,
    'fret' / Int32sl,
    'width' / Int32sl,
    'phraseIterationId' / Int32ul
)

ANCHOR_EXTENSION = Struct(
    'time' / Float32l,
    'fret' / Int8sl,
    Padding(7)
)

FINGERPRINT = Struct(
    'chordId' / Int32ul,
    'startTime' / Float32l,
    'endTime' / Float32l,
    'UNK_startTime' / Float32l,
    'UNK_endTime' / Float32l,
)

NOTE = Struct(
    'mask' / Int32ul,
    'flags' / Int32ul,
    'hash' / Int32ul,
    'time' / Float32l,
    'string' / Int8sl,
    'fret' / Int8sl,
    'anchorFret' / Int8sl,
    'anchorWidth' / Int8sl,
    'chordId' / Int32ul,
    'chordNoteId' / Int32ul,
    'phraseId' / Int32ul,
    'phraseIterationId' / Int32ul,
    'fingerPrintId' / Int16ul[2],
    'nextIterNote' / Int16ul,
    'prevIterNote' / Int16ul,
    'parentPrevNote' / Int16ul,
    'slideTo' / Int8sl,
    'slideUnpitchTo' / Int8sl,
    'leftHand' / Int8sl,
    'tap' / Int8sl,
    'pickDirection' / Int8sl,
    'slap' / Int8sl,
    'pluck' / Int8sl,
    'vibrato' / Int16sl,
    'sustain' / Float32l,
    'bend_time' / Float32l,
    'bends' / array(BEND)
)

LEVEL = Struct(
    'difficulty' / Int32ul,
    'anchors' / array(ANCHOR),
    'anchor_extensions' / array(ANCHOR_EXTENSION),
    'fingerprints' / array(FINGERPRINT)[2],
    'notes' / array(NOTE),
    'averageNotesPerIter' / array(Float32l),
    'notesInIterCountNoIgnored' / array(Int32ul),
    'notesInIterCount' / array(Int32ul)
)

METADATA = Struct(
    'maxScores' / Float64l,
    'maxNotes' / Float64l,
    'maxNotesNoIgnored' / Float64l,
    'pointsPerNote' / Float64l,
    'firstBeatLength' / Float32l,
    'startTime' / Float32l,
    'capo' / Int8sl,
    'lastConversionDateTime' / String(32, encoding='ascii'),
    'part' / Int16sl,
    'songLength' / Float32l,
    'tuning' / array(Int16sl),
    'firstNoteTime' / Float32l,
    'firstNoteTime2' / Float32l,
    'maxDifficulty' / Int32sl
)

SNG = Struct(
    'beats' / array(BEAT),
    'phrases' / array(PHRASE),
    'chordTemplates' / array(CHORD_TEMPLATE),
    'chordNotes' / array(CHORD_NOTE),
    'vocals' / array(VOCAL),
    'symbols' / If(len_(this.vocals) > 0, SYMBOLS),
    'phraseIterations' / array(PHRASE_ITERATION),
    'phraseExtraInfos' / array(PHRASE_EXTRA_INFO_BY_LEVEL),
    'newLinkedDiffs' / array(NEW_LINKED_DIFF),
    'actions' / array(ACTION),
    'events' / array(EVENT),
    'tone' / array(TONE),
    'dna' / array(DNA),
    'sections' / array(SECTION),
    'levels' / array(LEVEL),
    'metadata' / METADATA
)

def decrypt_sng(data, key):
    iv, data = data[8:24], data[24:-56]
    decrypted = aes_sng(key, iv).decrypt(pad(data))
    length, payload = Int32ul.parse(decrypted[:4]), decrypted[4:len(data)]
    payload = zlib.decompress(payload)
    assert len(payload) == length
    return payload

def encrypt_sng(data, key):
    header = Int32ul.build(74) + Int32ul.build(3)
    iv = bytes(16)
    payload = Int32ul.build(len(data)) + zlib.compress(data, zlib.Z_BEST_COMPRESSION)
    encrypted = aes_sng(key, iv).encrypt(pad(payload))[:len(payload)]
    return header + iv + encrypted + bytes(56)

class CryptoSNG(Construct):
    def __init__(self, key):
        self.key = key
        super(CryptoSNG, self).__init__()

    def _parse(self, stream, context, path):
        return SNG.parse(decrypt_sng(stream.read(), self.key))

    def _build(self, obj, stream, context, path):
        stream.write(encrypt_sng(SNG.build(obj), self.key))
