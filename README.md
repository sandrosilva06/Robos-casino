# Robôs de sinais — Football Studio e Lightning Roulette

Dois robôs de Telegram que leem os resultados do tipminer.com (com login na tua conta),
analisam o histórico e enviam entradas no formato **cor + proteção + 2 gales**.

- **Football Studio:** aposta em 🔴 Casa ou 🔵 Visitante, proteção 🟡 Empate (paga 11:1).
- **Lightning Roulette:** aposta em 🔴 Vermelho ou ⚫ Preto, proteção 🟢 Zero (paga 29:1).

Fluxo: entrada → se perder, gale 1 → se perder, gale 2 → se perder, **RED**.
Se sair a cor ou a proteção em qualquer etapa, **GREEN**. Cada mensagem de fecho
mostra o placar (SG/G1/G2/proteção), a taxa e o saldo em unidades.

## Como escolhe as entradas

A cada resultado, pega nas últimas 3, 4 e 5 cores e procura todas as vezes que esse
padrão apareceu no histórico (até 2000 rondas). Para cada cor simula o ciclo completo
com gales e proteção, e só envia se o melhor padrão tiver pelo menos `MIN_AMOSTRAS`
casos e taxa entre `TAXA_MINIMA` e `TAXA_MAXIMA`. Depois de um red faz uma pausa de `PAUSA_APOS_RED` rondas.
Tudo é configurável no `.env`.

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # preenche tokens do Telegram e login do tipminer
```

## 1. Acertar o tipminer (uma vez)

```bash
python main.py --diagnostico
```

Faz login, abre as páginas dos dois jogos e grava `diagnostico/*.html` e `*.png`,
mostrando o que leu com o seletor atual. Se aparecerem `None` ou 0 itens, ajusta
`TIPMINER_URL_*` e `TIPMINER_SELETOR_*` no `.env` (ou envia-me os ficheiros do
diagnóstico). `TIPMINER_HEADLESS=false` mostra o browser.

## 2. Testar o Telegram sem o tipminer

`FONTE=simulador` gera resultados com as probabilidades reais dos jogos a cada
`SIMULADOR_INTERVALO` segundos.

## 3. Correr

```bash
python main.py
```

O placar fica em `dados/placar_*.json` (sobrevive a reinícios). Testes: `pytest`.
