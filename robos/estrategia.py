"""Análise do histórico para escolher a entrada.

Para cada tamanho de padrão (as últimas N cores), procura no histórico todas as
vezes em que esse mesmo padrão apareceu e simula a entrada completa (cor +
proteção + gales) que teria sido feita a seguir. A entrada só é enviada quando
o melhor padrão tem amostras e taxa de acerto acima dos mínimos configurados.
"""
from __future__ import annotations

from dataclasses import dataclass

from .jogos import Cor, Jogo


@dataclass(frozen=True)
class Analise:
    cor: Cor
    padrao: tuple[Cor, ...]
    amostras: int
    taxa: float          # % de ciclos ganhos (até ao último gale)
    taxa_sem_gale: float  # % de ciclos ganhos logo na entrada


@dataclass
class ConfigEstrategia:
    tamanhos_padrao: tuple[int, ...] = (3, 4, 5)
    min_amostras: int = 20
    taxa_minima: float = 0.88
    taxa_maxima: float = 0.98
    max_gales: int = 2
    historico_maximo: int = 2000


def resultado_ciclo(seq: list[Cor], inicio: int, cor: Cor, jogo: Jogo, max_gales: int) -> tuple[bool, int] | None:
    """Simula um ciclo a partir de seq[inicio]. Devolve (ganhou, gale) ou None se faltam dados."""
    for gale in range(max_gales + 1):
        i = inicio + gale
        if i >= len(seq):
            return None
        if seq[i] == cor or seq[i] == jogo.protecao:
            return True, gale
    return False, max_gales


def analisar(historico: list[Cor], jogo: Jogo, cfg: ConfigEstrategia) -> Analise | None:
    seq = historico[-cfg.historico_maximo:]
    melhor: Analise | None = None
    for n in cfg.tamanhos_padrao:
        if len(seq) < n + 1:
            continue
        padrao = tuple(seq[-n:])
        # Não entra com a proteção dentro do padrão atual: o padrão fica sem sentido.
        if jogo.protecao in padrao:
            continue
        for cor in jogo.cores_aposta:
            ganhos = ganhos_g0 = total = 0
            for fim in range(n, len(seq)):
                if tuple(seq[fim - n:fim]) != padrao:
                    continue
                r = resultado_ciclo(seq, fim, cor, jogo, cfg.max_gales)
                if r is None:
                    continue
                total += 1
                if r[0]:
                    ganhos += 1
                    ganhos_g0 += r[1] == 0
            if total < cfg.min_amostras:
                continue
            a = Analise(cor, padrao, total, ganhos / total, ganhos_g0 / total)
            if not cfg.taxa_minima <= a.taxa <= cfg.taxa_maxima:
                continue
            chave = (a.taxa, a.taxa_sem_gale, a.amostras)
            if melhor is None or chave > (melhor.taxa, melhor.taxa_sem_gale, melhor.amostras):
                melhor = a
    return melhor
