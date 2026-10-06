"""Robôs de sinais no Telegram: Football Studio e Lightning Roulette.

    python main.py                 # corre os dois robôs
    python main.py --diagnostico   # testa o login/seletores do tipminer
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from robos.estrategia import ConfigEstrategia
from robos.fontes.simulador import FonteSimulador
from robos.fontes.tipminer import ConfigTipminer, FonteTipminer
from robos.jogos import JOGOS, Jogo
from robos.mensagens import formatar
from robos.sinais import ConfigGestao, GestorSinais
from robos.telegram import Telegram

log = logging.getLogger("robos")


def env(nome: str, padrao: str | None = None) -> str:
    valor = os.getenv(nome, padrao)
    if valor is None or valor == "":
        raise SystemExit(f"Falta a variável {nome} no .env")
    return valor


def criar_fonte():
    if env("FONTE", "tipminer") == "simulador":
        return FonteSimulador(intervalo=float(env("SIMULADOR_INTERVALO", "5")))
    return FonteTipminer(ConfigTipminer(
        email=env("TIPMINER_EMAIL"),
        senha=env("TIPMINER_SENHA"),
        url_login=env("TIPMINER_URL_LOGIN"),
        seletor_email=env("TIPMINER_SELETOR_EMAIL"),
        seletor_senha=env("TIPMINER_SELETOR_SENHA"),
        seletor_entrar=env("TIPMINER_SELETOR_ENTRAR"),
        urls={
            "football_studio": env("TIPMINER_URL_FOOTBALL_STUDIO"),
            "lightning_roulette": env("TIPMINER_URL_LIGHTNING_ROULETTE"),
        },
        seletor_resultado=env("TIPMINER_SELETOR_RESULTADO"),
        recente_primeiro=env("TIPMINER_RECENTE_PRIMEIRO", "true").lower() == "true",
        intervalo=float(env("TIPMINER_INTERVALO", "4")),
        headless=env("TIPMINER_HEADLESS", "true").lower() == "true",
    ))


def config_estrategia() -> ConfigEstrategia:
    return ConfigEstrategia(
        tamanhos_padrao=tuple(int(x) for x in env("PADRAO_TAMANHOS", "3,4,5").split(",")),
        min_amostras=int(env("MIN_AMOSTRAS", "20")),
        taxa_minima=float(env("TAXA_MINIMA", "0.88")),
        max_gales=int(env("MAX_GALES", "2")),
    )


def config_gestao() -> ConfigGestao:
    return ConfigGestao(
        multiplicador_gale=float(env("MULTIPLICADOR_GALE", "2")),
        fracao_protecao=float(env("FRACAO_PROTECAO", "0.1")),
        pausa_apos_red=int(env("PAUSA_APOS_RED", "3")),
    )


async def correr_robo(jogo: Jogo, fonte, sufixo: str) -> None:
    telegram = Telegram(env(f"TELEGRAM_TOKEN_{sufixo}"), env(f"TELEGRAM_CHAT_{sufixo}"))
    link = os.getenv(f"LINK_MESA_{sufixo}", "")
    gestor = GestorSinais(jogo, config_estrategia(), config_gestao(), Path(f"dados/placar_{jogo.chave}.json"))
    gestor.carregar_historico(await fonte.historico(jogo))
    log.info("%s: robô ativo com %d resultados de histórico", jogo.nome, len(gestor.historico))
    async for resultado in fonte.resultados(jogo):
        log.info("%s: saiu %s", jogo.nome, resultado.name)
        for evento in gestor.novo_resultado(resultado):
            await telegram.enviar(formatar(evento, link))


async def principal(diagnostico: bool) -> None:
    fonte = criar_fonte()
    try:
        if diagnostico:
            if not isinstance(fonte, FonteTipminer):
                raise SystemExit("O diagnóstico só se aplica com FONTE=tipminer")
            await fonte.diagnostico(list(JOGOS.values()))
            return
        robos = []
        if env("ATIVAR_FOOTBALL_STUDIO", "true").lower() == "true":
            robos.append(correr_robo(JOGOS["football_studio"], fonte, "FS"))
        if env("ATIVAR_LIGHTNING_ROULETTE", "true").lower() == "true":
            robos.append(correr_robo(JOGOS["lightning_roulette"], fonte, "LR"))
        await asyncio.gather(*robos)
    finally:
        await fonte.fechar()


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostico", action="store_true")
    asyncio.run(principal(parser.parse_args().diagnostico))
