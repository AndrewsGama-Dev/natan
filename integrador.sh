#!/bin/bash
set -e
BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Dias de retencao dos logs em logs/ (sobrescreva com INTEGRADOR_LOG_DIAS=7 no cron, se quiser)
LOG_RETENTION_DAYS="${INTEGRADOR_LOG_DIAS:-5}"

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

_limpar_logs_antigos() {
  # Apaga integrador_*.log com mais de N dias (mtime); mantem os dos ultimos N dias
  find "$LOG_DIR" -maxdepth 1 -type f -name 'integrador_*.log' -mtime +"$LOG_RETENTION_DAYS" -delete 2>/dev/null || true
}

_limpar_logs_antigos

LOG_FILE="$LOG_DIR/integrador_$(date +%Y%m%d_%H%M%S).log"
ln -sfn "$LOG_FILE" "$BASE/integrador.log"

echo "========== INICIO $(date "+%Y-%m-%d %H:%M:%S") ==========" >> "$LOG_FILE"
source venv/bin/activate
python -u main.py >> "$LOG_FILE" 2>&1
RET=$?
echo "========== FIM $(date "+%Y-%m-%d %H:%M:%S") exit=$RET ==========" >> "$LOG_FILE"

_limpar_logs_antigos
exit $RET
