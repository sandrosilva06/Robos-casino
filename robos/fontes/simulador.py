"""Fonte de teste: gera resultados com as probabilidades reais de cada jogo."""
from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator

from ..jogos import Cor, Jogo


class FonteSimulador:
    def __init__(self, intervalo: float = 5.0, semente: int | None = None):
        self.intervalo = intervalo
        self.rng = random.Random(semente)

    def _sortear(self, jogo: Jogo) -> Cor:
        cores, pesos = zip(*jogo.probabilidades.items())
        return self.rng.choices(cores, pesos)[0]

    async def historico(self, jogo: Jogo) -> list[Cor]:
        return [self._sortear(jogo) for _ in range(500)]

    async def resultados(self, jogo: Jogo) -> AsyncIterator[Cor]:
        while True:
            await asyncio.sleep(self.intervalo)
            yield self._sortear(jogo)

    async def fechar(self) -> None:
        pass
