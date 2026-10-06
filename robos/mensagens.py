"""Texto das mensagens enviadas para o Telegram (HTML)."""
from __future__ import annotations

from .jogos import EMOJI
from .sinais import Evento, Placar


def _placar(p: Placar) -> str:
    g = p.greens
    return (
        f"📈 <b>Placar:</b> {p.total_greens} ✅ | {p.reds} ❌ — {p.taxa:.1%}\n"
        f"SG {g['G0']} · G1 {g['G1']} · G2 {g['G2']} · Proteção {g['PROTECAO']}"
    )


def formatar(ev: Evento, link: str = "") -> str:
    j = ev.jogo
    if ev.tipo == "ENTRADA":
        texto = (
            f"🚨 <b>ENTRADA CONFIRMADA — {j.nome}</b>\n\n"
            f"🎯 Apostar: <b>{j.rotulo(ev.cor)}</b>\n"
            f"🛡️ Proteger: <b>{j.rotulo(j.protecao)}</b>\n"
            f"🔁 Até 2 gales\n\n"
            f"📊 Assertividade: <b>{ev.analise.taxa:.0%}</b>"
        )
        if link:
            texto += f"\n\n🎰 Jogar aqui: {link}"
        return texto
    if ev.tipo == "GALE":
        return (
            f"🔁 <b>GALE {ev.gale}</b> — saiu {EMOJI[ev.resultado]}\n"
            f"Dobrar no <b>{j.rotulo(ev.cor)}</b> + proteção {EMOJI[j.protecao]}"
        )
    if ev.tipo == "GREEN":
        etapa = "PROTEÇÃO" if ev.resultado == j.protecao else ("SEM GALE" if ev.gale == 0 else f"GALE {ev.gale}")
        return (
            f"✅✅ <b>GREEN — {etapa}</b> {EMOJI[ev.resultado]}\n"
            f"\n{_placar(ev.placar)}"
        )
    return (
        f"❌ <b>RED</b> — saiu {EMOJI[ev.resultado]}\n"
        f"\n{_placar(ev.placar)}"
    )
