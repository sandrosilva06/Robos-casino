"""Cliente mínimo da Bot API do Telegram."""
from __future__ import annotations

import asyncio
import logging

import httpx

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.cliente = httpx.AsyncClient(timeout=20)

    async def enviar(self, texto: str) -> None:
        dados = {"chat_id": self.chat_id, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
        for tentativa in range(5):
            try:
                r = await self.cliente.post(f"{self.url}/sendMessage", json=dados)
                if r.status_code == 429:
                    espera = r.json().get("parameters", {}).get("retry_after", 5)
                    await asyncio.sleep(espera)
                    continue
                r.raise_for_status()
                return
            except httpx.HTTPError as e:
                log.warning("Falha ao enviar para o Telegram (%s), tentativa %d", e, tentativa + 1)
                await asyncio.sleep(2 ** tentativa)
        log.error("Mensagem não enviada: %s", texto[:80])
