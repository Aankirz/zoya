#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ARCHIVE="${1:?usage: packaging/local_feed.sh dist/Zoya-<version>.zip}"
PORT=8765
FEED="dist/feed"
KEYCHAIN="$HOME/Library/Keychains/zoya-signing.keychain-db"
BUNDLE_ID="app.zoya.Zoya"
TOOLS="$(ls -d dist/cache/sparkle-*/bin | tail -1)"

rm -rf "$FEED"
mkdir -p "$FEED"
cp "$ARCHIVE" "$FEED/"
security unlock-keychain -p "$(security find-generic-password -s 'Zoya signing keychain' -w)" "$KEYCHAIN"
printf "%s" "$(security find-generic-password -s 'Zoya Sparkle EdDSA key' -w "$KEYCHAIN")" |
  "$TOOLS/generate_appcast" --ed-key-file - --download-url-prefix "http://127.0.0.1:$PORT/" "$FEED"
defaults write "$BUNDLE_ID" SUFeedURL "http://127.0.0.1:$PORT/appcast.xml"
trap 'defaults delete "$BUNDLE_ID" SUFeedURL' EXIT
echo "Serving $FEED on http://127.0.0.1:$PORT. Quit Zoya and open her again; she'll ask about the update."
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$FEED"
