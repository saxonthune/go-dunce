#!/usr/bin/env bash
# Downloads a KataGo binary and network into engines/ (gitignored).
# Override BACKEND=eigenavx2 for a CPU-only build.
set -euo pipefail

VERSION="v1.18.1"
BACKEND="${BACKEND:-opencl}"
NETWORK="kata1-b18c384nbt-s8341979392-d3881113763.bin.gz"

root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$root/engines"
mkdir -p "$dest"

zip="katago-${VERSION}-${BACKEND}-linux-x64.zip"
if [ ! -x "$dest/katago" ]; then
  curl -fL -o "$dest/$zip" "https://github.com/lightvector/KataGo/releases/download/${VERSION}/${zip}"
  unzip -o -q "$dest/$zip" -d "$dest"
  rm "$dest/$zip"
  chmod +x "$dest/katago"
fi

if [ ! -f "$dest/$NETWORK" ]; then
  curl -fL -o "$dest/$NETWORK" "https://media.katagotraining.org/uploaded/networks/models/kata1/${NETWORK}"
fi
ln -sf "$NETWORK" "$dest/model.bin.gz"

echo "KataGo ready in $dest"
