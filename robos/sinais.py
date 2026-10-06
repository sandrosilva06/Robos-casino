"""Máquina de estados de um sinal: entrada -> gale 1 -> gale 2 -> green/red."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .estrategia import Analise, ConfigEstrategia, analisar
from .jogos import Cor, Jogo


@dataclass
class Placar:
    greens: dict[str, int] = field(default_factory=lambda: {"G0": 0, "G1": 0, "G2": 0, "PROTECAO": 0})
    reds: int = 0
    saldo: float = 0.0  # em unidades (aposta base = 1)

    @property
    def total_greens(self) -> int:
        return sum(self.greens.values())

    @property
    def taxa(self) -> float:
        total = self.total_greens + self.reds
        return self.total_greens / total if total else 0.0


@dataclass
class SinalAtivo:
    cor: Cor
    gale: int
    analise: Analise


@dataclass
class Evento:
    tipo: str  # ENTRADA, GALE, GREEN, RED
    jogo: Jogo
    cor: Cor
    gale: int = 0
    resultado: Cor | None = None
    analise: Analise | None = None
    placar: Placar | None = None
    lucro_ciclo: float = 0.0


@dataclass
class ConfigGestao:
    multiplicador_gale: float = 2.0
    # Aposta na proteção como fração da aposta na cor em cada ronda.
    fracao_protecao: float = 0.1
    # Rondas sem enviar sinais depois de um red.
    pausa_apos_red: int = 3


class GestorSinais:
    def __init__(self, jogo: Jogo, estrategia: ConfigEstrategia, gestao: ConfigGestao, ficheiro_placar: Path | None = None):
        self.jogo = jogo
        self.estrategia = estrategia
        self.gestao = gestao
        self.historico: list[Cor] = []
        self.sinal: SinalAtivo | None = None
        self.pausa = 0
        self.lucro_ciclo = 0.0
        self.ficheiro_placar = ficheiro_placar
        self.placar = self._carregar_placar()

    def _carregar_placar(self) -> Placar:
        if self.ficheiro_placar and self.ficheiro_placar.exists():
            d = json.loads(self.ficheiro_placar.read_text())
            return Placar(greens=d["greens"], reds=d["reds"], saldo=d["saldo"])
        return Placar()

    def _guardar_placar(self) -> None:
        if self.ficheiro_placar:
            self.ficheiro_placar.parent.mkdir(parents=True, exist_ok=True)
            self.ficheiro_placar.write_text(json.dumps(asdict(self.placar)))

    def carregar_historico(self, cores: list[Cor]) -> None:
        self.historico.extend(cores)
        self.historico = self.historico[-self.estrategia.historico_maximo:]

    def aposta(self, gale: int) -> float:
        return self.gestao.multiplicador_gale ** gale

    def _lucro_ronda(self, gale: int, cor_apostada: Cor, resultado: Cor) -> float:
        aposta = self.aposta(gale)
        protecao = aposta * self.gestao.fracao_protecao
        if resultado == cor_apostada:
            return aposta - protecao
        if resultado == self.jogo.protecao:
            return protecao * self.jogo.pagamento_protecao - aposta * self.jogo.perda_cor_na_protecao
        return -aposta - protecao

    def novo_resultado(self, resultado: Cor) -> list[Evento]:
        self.historico.append(resultado)
        self.historico = self.historico[-self.estrategia.historico_maximo:]
        eventos: list[Evento] = []

        if self.sinal:
            s = self.sinal
            self.lucro_ciclo += self._lucro_ronda(s.gale, s.cor, resultado)
            if resultado in (s.cor, self.jogo.protecao):
                chave = "PROTECAO" if resultado == self.jogo.protecao else f"G{s.gale}"
                self.placar.greens[chave] += 1
                eventos.append(self._fechar("GREEN", resultado))
            elif s.gale < self.estrategia.max_gales:
                s.gale += 1
                eventos.append(Evento("GALE", self.jogo, s.cor, s.gale, resultado, s.analise))
                return eventos
            else:
                self.placar.reds += 1
                self.pausa = self.gestao.pausa_apos_red
                eventos.append(self._fechar("RED", resultado))
                return eventos  # não entra logo a seguir a um red
        elif self.pausa > 0:
            self.pausa -= 1
            return eventos

        analise = analisar(self.historico, self.jogo, self.estrategia)
        if analise:
            self.sinal = SinalAtivo(analise.cor, 0, analise)
            self.lucro_ciclo = 0.0
            eventos.append(Evento("ENTRADA", self.jogo, analise.cor, 0, None, analise))
        return eventos

    def _fechar(self, tipo: str, resultado: Cor) -> Evento:
        s = self.sinal
        assert s is not None
        self.placar.saldo = round(self.placar.saldo + self.lucro_ciclo, 4)
        self._guardar_placar()
        ev = Evento(tipo, self.jogo, s.cor, s.gale, resultado, s.analise, copy.deepcopy(self.placar), round(self.lucro_ciclo, 2))
        self.sinal = None
        return ev
