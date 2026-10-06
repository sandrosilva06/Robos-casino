"""Fonte de resultados diretamente da mesa no casino (Playwright).

Faz login na conta, abre a mesa e escuta as mensagens WebSocket que o jogo da
Evolution recebe. `python main.py --diagnostico-casino fs` grava essas mensagens
durante uns minutos e mostra um resumo, para identificar o formato dos resultados.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

log = logging.getLogger(__name__)

PALAVRAS_RESULTADO = re.compile(r"result|winner|outcome|home|away|tie|draw|winspot|number", re.I)


@dataclass
class ConfigCasino:
    email: str
    senha: str
    url_login: str
    urls: dict[str, str]  # chave do jogo -> URL da mesa
    headless: bool = True
    ficheiro_sessao: Path = Path("dados/sessao_casino.json")


async def _visivel(pagina: Page, seletor: str):
    for loc in await pagina.locator(seletor).all():
        try:
            if await loc.is_visible():
                return loc
        except Exception:
            pass
    return None


async def fazer_login(pagina: Page, cfg: ConfigCasino) -> bool:
    """Login genérico: abre o formulário, preenche email e senha e envia."""
    await pagina.goto(cfg.url_login, wait_until="domcontentloaded")
    await pagina.wait_for_timeout(5000)
    senha = await _visivel(pagina, "input[type=password]")
    if senha is None:
        botao = await _visivel(pagina, "button:text-matches('entrar|login|iniciar sess', 'i'), "
                                       "a:text-matches('entrar|login|iniciar sess', 'i')")
        if botao is None:
            print("  Não encontrei botão de login nem campo de senha (talvez já tenhas sessão).")
            return True
        await botao.click()
        await pagina.wait_for_timeout(3000)
        senha = await _visivel(pagina, "input[type=password]")
        if senha is None:
            print("  Abri o login mas não apareceu o campo de senha.")
            return False
    email = await _visivel(pagina, "input[type=email], input[name*=mail i], input[name*=user i], "
                                   "input[name*=login i], input[type=text], input[type=tel]")
    if email is None:
        print("  Não encontrei o campo de email/utilizador.")
        return False
    await email.fill(cfg.email)
    await senha.fill(cfg.senha)
    await senha.press("Enter")
    await pagina.wait_for_timeout(3000)
    if await _visivel(pagina, "input[type=password]"):
        enviar = await _visivel(pagina, "button[type=submit], form button:text-matches('entrar|login|iniciar', 'i')")
        if enviar:
            await enviar.click()
    await pagina.wait_for_timeout(6000)
    if await _visivel(pagina, "input[type=password]"):
        texto = (await pagina.evaluate("document.body.innerText"))[:300].replace("\n", " | ")
        captcha = await pagina.locator("iframe[src*=captcha], iframe[title*=captcha i], [class*=captcha]").count()
        print(f"  O formulário de login continua visível. Captcha na página: {'sim' if captcha else 'não'}")
        print(f"  Texto: {texto}")
        return False
    return True


async def diagnostico(cfg: ConfigCasino, chave: str, segundos: int = 180, pasta: Path = Path("diagnostico")) -> None:
    pasta.mkdir(exist_ok=True)
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=cfg.headless, executable_path=os.getenv("CHROMIUM_PATH") or None)
    sessao = cfg.ficheiro_sessao
    ctx: BrowserContext = await browser.new_context(
        storage_state=str(sessao) if sessao.exists() else None,
        viewport={"width": 1366, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    )
    try:
        pagina = await ctx.new_page()
        print("\n== LOGIN")
        ok = await fazer_login(pagina, cfg)
        print(f"  URL: {pagina.url}\n  Login: {'OK' if ok else 'FALHOU'}")
        await pagina.screenshot(path=str(pasta / "casino_login.png"))
        if ok:
            sessao.parent.mkdir(parents=True, exist_ok=True)
            await ctx.storage_state(path=str(sessao))

        frames: list[tuple[str, str]] = []

        def ao_abrir_ws(ws):
            print(f"  WebSocket aberto: {ws.url[:110]}")
            ws.on("framereceived", lambda dados: frames.append(
                (ws.url, dados if isinstance(dados, str) else dados.decode("utf-8", "replace"))))

        pagina.on("websocket", ao_abrir_ws)
        print(f"\n== MESA ({chave})")
        await pagina.goto(cfg.urls[chave], wait_until="domcontentloaded")
        print(f"  URL: {pagina.url}")
        print(f"  A gravar mensagens durante {segundos}s...")
        for _ in range(segundos // 30):
            await asyncio.sleep(30)
            print(f"  ... {len(frames)} mensagens")
        await pagina.screenshot(path=str(pasta / f"casino_{chave}.png"))
        for f in pagina.frames[1:]:
            print(f"  iframe: {f.url[:110]}")

        with open(pasta / f"ws_{chave}.jsonl", "w") as fh:
            for url, dados in frames:
                fh.write(json.dumps({"ws": url, "dados": dados}) + "\n")

        print("\n== RESUMO")
        print("  Mensagens por WebSocket:")
        for url, n in Counter(u for u, _ in frames).most_common(5):
            print(f"    {n:>5}  {url[:90]}")
        tipos: Counter[str] = Counter()
        exemplos: dict[str, str] = {}
        for _, dados in frames:
            try:
                obj = json.loads(dados)
                tipo = str(obj.get("type") or obj.get("event") or obj.get("t") or "?") if isinstance(obj, dict) else "lista"
            except (ValueError, AttributeError):
                tipo = "não-JSON"
            tipos[tipo] += 1
            exemplos.setdefault(tipo, dados)
        print("  Tipos de mensagem (quantidade / exemplo):")
        for tipo, n in tipos.most_common(25):
            print(f"    {n:>5}  {tipo[:40]:<40} {exemplos[tipo][:110]}")
        print("  Mensagens com palavras de resultado:")
        vistos = set()
        for _, dados in frames:
            if PALAVRAS_RESULTADO.search(dados) and dados[:60] not in vistos:
                vistos.add(dados[:60])
                print(f"    {dados[:220]}")
                if len(vistos) >= 8:
                    break
        print(f"\n  Tudo gravado em {pasta.resolve()}/ws_{chave}.jsonl")
    finally:
        await browser.close()
        await pw.stop()
