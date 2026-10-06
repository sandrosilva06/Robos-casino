"""Definição dos jogos: cores, proteção, pagamentos e leitura dos resultados."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Cor(str, Enum):
    VERMELHO = "V"
    AZUL = "A"
    PRETO = "P"
    EMPATE = "E"
    ZERO = "Z"


EMOJI = {
    Cor.VERMELHO: "🔴",
    Cor.AZUL: "🔵",
    Cor.PRETO: "⚫",
    Cor.EMPATE: "🟡",
    Cor.ZERO: "🟢",
}

VERMELHOS_ROLETA = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


@dataclass(frozen=True)
class Jogo:
    chave: str
    nome: str
    cores_aposta: tuple[Cor, Cor]
    protecao: Cor
    nomes: dict[Cor, str]
    # Quanto paga a aposta de proteção (x:1).
    pagamento_protecao: float
    # Fração da aposta na cor que se perde quando sai a proteção.
    perda_cor_na_protecao: float
    # Probabilidades reais por ronda (usadas pelo simulador).
    probabilidades: dict[Cor, float]

    def rotulo(self, cor: Cor) -> str:
        return f"{EMOJI[cor]} {self.nomes[cor]}"

    def ler(self, texto: str) -> Cor | None:
        """Converte o texto/atributos de um resultado do site numa Cor."""
        raise NotImplementedError


class FootballStudio(Jogo):
    def ler(self, texto: str) -> Cor | None:
        t = texto.lower()
        if re.search(r"empate|tie|draw|\bt\b|\be\b|yellow|amarel|gold", t):
            return Cor.EMPATE
        if re.search(r"casa|home|vermelh|red|\bh\b|\bc\b", t):
            return Cor.VERMELHO
        if re.search(r"visitante|away|azul|blue|\ba\b|\bv\b", t):
            return Cor.AZUL
        return None


class LightningRoulette(Jogo):
    def ler(self, texto: str) -> Cor | None:
        m = re.search(r"\b([0-9]|[12][0-9]|3[0-6])\b", texto)
        if not m:
            return None
        return numero_para_cor(int(m.group(1)))


def numero_para_cor(n: int) -> Cor:
    if n == 0:
        return Cor.ZERO
    return Cor.VERMELHO if n in VERMELHOS_ROLETA else Cor.PRETO


FOOTBALL_STUDIO = FootballStudio(
    chave="football_studio",
    nome="Football Studio",
    cores_aposta=(Cor.VERMELHO, Cor.AZUL),
    protecao=Cor.EMPATE,
    nomes={Cor.VERMELHO: "CASA", Cor.AZUL: "VISITANTE", Cor.EMPATE: "EMPATE"},
    pagamento_protecao=11,
    perda_cor_na_protecao=0.5,
    probabilidades={Cor.VERMELHO: 0.4626, Cor.AZUL: 0.4626, Cor.EMPATE: 0.0748},
)

LIGHTNING_ROULETTE = LightningRoulette(
    chave="lightning_roulette",
    nome="Lightning Roulette",
    cores_aposta=(Cor.VERMELHO, Cor.PRETO),
    protecao=Cor.ZERO,
    nomes={Cor.VERMELHO: "VERMELHO", Cor.PRETO: "PRETO", Cor.ZERO: "ZERO"},
    pagamento_protecao=29,
    perda_cor_na_protecao=1.0,
    probabilidades={Cor.VERMELHO: 18 / 37, Cor.PRETO: 18 / 37, Cor.ZERO: 1 / 37},
)

JOGOS = {j.chave: j for j in (FOOTBALL_STUDIO, LIGHTNING_ROULETTE)}
