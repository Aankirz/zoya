#!/bin/zsh
# Builds Zoya's earcons (D9, §7.3): UI SFX `zen` pack (CC0) OGG → loudness-normalised mono WAV.
# WAV avoids MP3 padding gaps in the loop. One-shots −20 LUFS, working loop −38 LUFS
# (loop TP −9: ffmpeg loudnorm rejects the −12 in §7.3, its range is [−9, 0]).
# Usage: ./scripts/build_sounds.sh   (needs ffmpeg: brew install ffmpeg)
set -euo pipefail
ROOT="${0:A:h:h}"
SRC="$ROOT/sounds/candidates/zen"
OUT="$ROOT/sounds"
RATE=48000  # zoya/audio.py mixes at this rate

for cue in wake release success error stop mention warning cancel \
    progress-step add-to-cart purchase checkpoint blocked; do
  ffmpeg -hide_banner -loglevel error -y -i "$SRC/$cue.ogg" \
    -af "loudnorm=I=-20:TP=-3,afade=t=in:d=0.005" -ac 1 -ar $RATE "$OUT/$cue.wav"
done
ffmpeg -hide_banner -loglevel error -y -i "$SRC/processing.ogg" \
  -af "loudnorm=I=-38:TP=-9" -ac 1 -ar $RATE "$OUT/processing.wav"
cp "$SRC/../LICENSE-AUDIO-uisfx.txt" "$OUT/LICENSE-AUDIO-uisfx.txt"
echo "built: $(ls "$OUT"/*.wav | wc -l | tr -d ' ') earcons in $OUT"
