#!/usr/bin/env bash
set -euo pipefail
NAME="Zoya Self-Signed Code Signing"
KEYCHAIN="$HOME/Library/Keychains/zoya-signing.keychain-db"
PASSWORD_SERVICE="Zoya signing keychain"
DAYS=7300

if [[ -e "$KEYCHAIN" ]]; then
  echo "$KEYCHAIN already exists. Never make a second certificate: every user would lose their permissions."
  exit 1
fi
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
keychain_password="$(openssl rand -hex 24)"
p12_password="$(openssl rand -hex 24)"

openssl req -x509 -newkey rsa:2048 -nodes -days "$DAYS" -subj "/CN=$NAME" \
  -addext "basicConstraints=critical,CA:false" \
  -addext "keyUsage=critical,digitalSignature" \
  -addext "extendedKeyUsage=critical,codeSigning" \
  -keyout "$work/key.pem" -out "$work/cert.pem" 2>/dev/null
openssl pkcs12 -export -legacy -inkey "$work/key.pem" -in "$work/cert.pem" -name "$NAME" \
  -out "$work/identity.p12" -passout "pass:$p12_password"

security add-generic-password -a "$USER" -s "$PASSWORD_SERVICE" -w "$keychain_password" \
  -T /usr/bin/security
security create-keychain -p "$keychain_password" "$KEYCHAIN"
security set-keychain-settings "$KEYCHAIN"
security unlock-keychain -p "$keychain_password" "$KEYCHAIN"
security import "$work/identity.p12" -k "$KEYCHAIN" -P "$p12_password" -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple: -s -k "$keychain_password" "$KEYCHAIN" >/dev/null
echo "Created \"$NAME\" in $KEYCHAIN. Back it up now: docs/phases/prod-3b-report.md, Signing."
