#!/bin/zsh
# Plays every Zoya earcon candidate with its label printed, so you can pick a pack by ear.
# These are only the short UI sounds. Zoya's real voice (Nova 2 Sonic "kiara") arrives in Phase 2.
# Usage: ./audition.sh [zen|soft]   (default: both)
DIR="${0:A:h}/candidates"
EVENTS=(
  "wake:Listening"
  "release:Heard you"
  "processing:Working loop"
  "progress-step:Step done"
  "queued:Helper started"
  "complete:Helper finished"
  "warning:Needs confirmation"
  "success:Success"
  "purchase:Order placed"
  "mention:Needs your attention"
  "error:Error"
  "blocked:Blocked"
  "stop:Stopped"
  "cancel:Cancelled"
  "checkpoint:Memory saved"
  "send:Message sent"
  "add-to-cart:Added to cart"
)
for pack in ${1:-zen soft}; do
  echo "\n=== $pack pack ==="
  for entry in $EVENTS; do
    cue=${entry%%:*}; label=${entry#*:}
    echo "▶ $label"
    afplay "$DIR/$pack/$cue.mp3"
    sleep 0.6
  done
done
