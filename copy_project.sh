#!/usr/bin/env bash
set -e

SRC="$(dirname "$(realpath "$0")")/qsequoia2"
DEST="$HOME/.local/share/QGIS/QGIS3/profiles/default/python/plugins"

cp -r "$SRC" "$DEST/"
echo "qsequoia2 copié dans $DEST"