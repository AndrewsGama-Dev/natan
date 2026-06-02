#!/bin/bash
set -e
BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

if [ ! -f venv/bin/activate ]; then
  echo "$(date "+%Y-%m-%d %H:%M:%S") ERRO: venv/bin/activate nao encontrado" >&2
  exit 1
fi
if [ ! -f .config ]; then
  echo "$(date "+%Y-%m-%d %H:%M:%S") ERRO: .config nao encontrado" >&2
  exit 1
fi

LOG_DIR="$BASE/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/integrador_$(date +%Y%m%d_%H%M%S).log"
ln -sfn "$LOG_FILE" "$BASE/integrador.log"

# Mantem apenas os 10 logs mais recentes
ls -1t "$LOG_DIR"/integrador_*.log 2>/dev/null | tail -n +11 | xargs -r rm -f --

echo "========== INICIO $(date "+%Y-%m-%d %H:%M:%S") ==========" >> "$LOG_FILE"
source venv/bin/activate
python -u main.py >> "$LOG_FILE" 2>&1
RET=$?
echo "========== FIM $(date "+%Y-%m-%d %H:%M:%S") exit=$RET ==========" >> "$LOG_FILE"
ls -1t "$LOG_DIR"/integrador_*.log 2>/dev/null | tail -n +11 | xargs -r rm -f --
exit $RET
