#!/bin/bash
set -e
cd "$(dirname "$0")"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
LOG_DIR="$(pwd)"
if [ ! -f venv/bin/activate ]; then
  echo "$(date "+%Y-%m-%d %H:%M:%S") ERRO: venv/bin/activate nao encontrado em $(pwd)" >&2
  exit 1
fi
if [ ! -f .config ]; then
  echo "$(date "+%Y-%m-%d %H:%M:%S") ERRO: arquivo .config nao encontrado em $(pwd)" >&2
  exit 1
fi
source venv/bin/activate
exec python -u main.py
