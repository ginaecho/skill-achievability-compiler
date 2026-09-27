---
name: sheet-music-transposer
description: Transpose a MusicXML lead sheet to a new key for a singer, keeping chord symbols consistent.
---
# Lead sheet transposer

1. Load `song.musicxml` with `music21`.
2. Transpose notes and chord symbols by the interval from the current key to the requested key.
3. Write `song_transposed.musicxml` and report the old and new key signatures.
