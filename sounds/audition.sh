#!/bin/zsh
# Plays every Zoya earcon candidate, announced by voice, so you can pick a pack by ear.
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
  say "$pack pack"
  for entry in $EVENTS; do
    cue=${entry%%:*}; label=${entry#*:}
    say "$label"
    afplay "$DIR/$pack/$cue.mp3"
    sleep 0.6
  done
done
