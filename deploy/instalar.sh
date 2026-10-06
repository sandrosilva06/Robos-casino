#!/usr/bin/env bash
# Instala/atualiza os robôs num VPS Ubuntu/Debian e deixa-os a correr como serviço.
#   curl -fsSL https://raw.githubusercontent.com/sandrosilva06/Robos-casino/claude/robos-sinais-telegram/deploy/instalar.sh | sudo bash
set -euo pipefail

REPO="https://github.com/sandrosilva06/Robos-casino.git"
RAMO="${RAMO:-claude/robos-sinais-telegram}"
PASTA="/opt/robos-casino"
UTILIZADOR="robos"

if [ "$(id -u)" -ne 0 ]; then echo "Corre com sudo."; exit 1; fi

echo "==> Pacotes do sistema"
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip >/dev/null

id "$UTILIZADOR" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$UTILIZADOR"

echo "==> Código ($RAMO)"
if [ -d "$PASTA/.git" ]; then
  git -C "$PASTA" fetch -q origin "$RAMO"
  git -C "$PASTA" checkout -q -B "$RAMO" "origin/$RAMO"
else
  git clone -q --branch "$RAMO" "$REPO" "$PASTA"
fi

echo "==> Python e browser (pode demorar uns minutos)"
python3 -m venv "$PASTA/.venv"
"$PASTA/.venv/bin/pip" install -q --upgrade pip
"$PASTA/.venv/bin/pip" install -q -r "$PASTA/requirements.txt"
export PLAYWRIGHT_BROWSERS_PATH="$PASTA/.browsers"
"$PASTA/.venv/bin/playwright" install --with-deps chromium >/dev/null

[ -f "$PASTA/.env" ] || cp "$PASTA/.env.example" "$PASTA/.env"
chmod 600 "$PASTA/.env"
chown -R "$UTILIZADOR:$UTILIZADOR" "$PASTA"

echo "==> Serviço"
cat > /etc/systemd/system/robos-casino.service <<SERVICO
[Unit]
Description=Robos de sinais (Telegram)
After=network-online.target
Wants=network-online.target

[Service]
User=$UTILIZADOR
WorkingDirectory=$PASTA
Environment=PLAYWRIGHT_BROWSERS_PATH=$PASTA/.browsers
ExecStart=$PASTA/.venv/bin/python main.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
SERVICO
systemctl daemon-reload
systemctl enable -q robos-casino

cat <<FIM

Instalação concluída.
1) Preenche o .env:        sudo nano $PASTA/.env
2) Arranca/reinicia:       sudo systemctl restart robos-casino
3) Ver o que está a fazer: sudo journalctl -u robos-casino -f
Diagnóstico do tipminer:   cd $PASTA && sudo -u $UTILIZADOR PLAYWRIGHT_BROWSERS_PATH=$PASTA/.browsers .venv/bin/python main.py --diagnostico
Para atualizar o robô:     volta a correr este mesmo comando de instalação.
FIM
