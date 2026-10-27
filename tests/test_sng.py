from rocksmith.sng import Anchor, AnchorExtension, Bend, ChordTemplate, Song


def bend(**kw):
    b = dict(time=0.0, step=1.0, UNK=0)
    b.update(kw)
    return b


def note(**kw):
    n = dict(
        mask=1,
        flags=0,
        hash=0,
        time=10.0,
        string=1,
        fret=3,
        anchorFret=-1,
        anchorWidth=-1,
        chordId=-1,
        chordNoteId=-1,
        phraseId=0,
        phraseIterationId=0,
        fingerPrintId=[-1, -1],
        nextIterNote=-1,
        prevIterNote=-1,
        parentPrevNote=-1,
        slideTo=-1,
        slideUnpitchTo=-1,
        leftHand=0,
        tap=0,
        pickDirection=0,
        slap=0,
        pluck=0,
        vibrato=0,
        sustain=0.25,
        bend_time=0.0,
        bends=[bend()],
    )
    n.update(kw)
    return n


def minimal_song(vocals=False):
    song = dict(
        beats=[
            dict(time=10.0, measure=0, beat=0, phraseIteration=0, mask=1),
            dict(time=10.5, measure=1, beat=1, phraseIteration=0, mask=1),
        ],
        phrases=[
            dict(
                solo=0,
                disparity=0,
                ignore=0,
                maxDifficulty=2,
                phraseIterationLinks=0,
                name="P1",
            )
        ],
        chordTemplates=[
            dict(
                mask=3,
                frets=[3, 5, -1, -1, -1, -1],
                fingers=[1, 3, -1, -1, -1, -1],
                notes=[-1, -1, -1, -1, -1, -1],
                name="G",
            )
        ],
        chordNotes=[
            dict(
                mask=[0] * 6,
                bends=[dict(bendValues=[bend()] * 32, count=0) for _ in range(6)],
                slideTo=[-1] * 6,
                slideUnpitchTo=[-1] * 6,
                vibrato=[0] * 6,
            )
        ],
        vocals=[],
        symbols=None,
        phraseIterations=[
            dict(phraseId=0, time=10.0, endTime=20.0, difficulty=[1, 2, 3])
        ],
        phraseExtraInfos=[
            dict(phraseId=0, difficulty=2, empty=0, levelJump=1, redundant=0)
        ],
        newLinkedDiffs=[dict(levelBreak=1, nld_phrase=[0])],
        actions=[dict(time=10.0, name="start_solo")],
        events=[dict(time=10.0, name="solo")],
        tones=[dict(time=10.0, id=1)],
        dna=[dict(time=10.0, id=2)],
        sections=[
            dict(
                name="Section A",
                number=1,
                startTime=10.0,
                endTime=20.0,
                startPhraseIterationId=0,
                endPhraseIterationId=0,
                stringMask=[-1] * 36,
            )
        ],
        levels=[
            dict(
                difficulty=1,
                anchors=[
                    dict(
                        time=10.0,
                        endTime=10.5,
                        UNK_time=0.0,
                        UNK_time2=0.0,
                        fret=3,
                        width=1,
                        phraseIterationId=0,
                    )
                ],
                anchor_extensions=[dict(time=10.0, fret=3)],
                fingerprints=[
                    [
                        dict(
                            chordId=0,
                            startTime=10.0,
                            endTime=10.5,
                            UNK_startTime=0.0,
                            UNK_endTime=0.0,
                        )
                    ],
                    [],
                ],
                notes=[note()],
                averageNotesPerIter=[1.0],
                notesInIterCountNoIgnored=[1],
                notesInIterCount=[1],
            )
        ],
        metadata=dict(
            maxScores=100.0,
            maxNotes=10.0,
            maxNotesNoIgnored=10.0,
            pointsPerNote=1.0,
            firstBeatLength=0.5,
            startTime=10.0,
            capo=0,
            lastConversionDateTime="2024-01-01 00:00:00",
            part=0,
            songLength=60.0,
            tuning=[0, -5, -10, -15, -20, -25],
            firstNoteTime=10.0,
            firstNoteTime2=10.0,
            maxDifficulty=3,
        ),
    )
    if vocals:
        song["vocals"] = [dict(time=10.0, note=60, length=0.5, lyrics="little wing")]
        song["symbols"] = dict(
            header=[[0] * 8],
            texture=[
                dict(
                    fontpath="fonts/default.ttf",
                    fontpathLength=17,
                    width=256,
                    height=128,
                )
            ],
            definition=[
                dict(
                    name="A",
                    outerRect=dict(y0=0.0, x0=0.0, y1=1.0, x1=1.0),
                    innerRect=dict(y0=0.1, x0=0.1, y1=0.9, x1=0.9),
                )
            ],
        )
    return song


def test_sizes_match_wire():
    assert Bend.sizeof() == 12
    assert Anchor.sizeof() == 28
    assert AnchorExtension.sizeof() == 12
    assert ChordTemplate.sizeof() == 72


def test_roundtrip_minimal():
    raw = Song.build(minimal_song())
    parsed = Song.parse(raw)
    assert Song.build(parsed) == raw


def test_roundtrip_vocals():
    raw = Song.build(minimal_song(vocals=True))
    parsed = Song.parse(raw)
    assert parsed.symbols.definition[0].name == "A"
    assert Song.build(parsed) == raw


def test_none_sentinels_round_trip():
    # Note link/id fields carry -1 on real tracks; an unsigned schema
    # read them back as 65535 / 4294967295.
    parsed = Song.parse(Song.build(minimal_song()))
    n = parsed.levels[0].notes[0]
    assert n.chordId == -1
    assert n.chordNoteId == -1
    assert list(n.fingerPrintId) == [-1, -1]
    assert n.nextIterNote == -1
    assert n.prevIterNote == -1
    assert n.parentPrevNote == -1
