#!/usr/bin/env bash
# Descarga Piper Maider (euskera, HiTZ/Aholab, Apache-2.0) al dir del TTS.
# Uso: ./service/fetch-maider.sh [dir]     (default: /opt/emap-labs/tts)
set -euo pipefail
DIR="${1:-/opt/emap-labs/tts}"
REPO="https://huggingface.co/itzune/maider-tts/resolve/main"
mkdir -p "$DIR"
cd "$DIR"
if [[ ! -f eu-maider-medium.onnx ]]; then
  echo "→ eu-maider-medium.onnx"
  curl -fL -o eu-maider-medium.onnx "$REPO/eu-maider-medium.onnx"
fi
if [[ ! -f eu-maider-medium.onnx.json ]]; then
  echo "→ eu-maider-medium.onnx.json"
  curl -fL -o eu-maider-medium.onnx.json "$REPO/eu-maider-medium.onnx.json"
fi
ls -lh eu-maider-medium.onnx*
echo "listo: $DIR"
