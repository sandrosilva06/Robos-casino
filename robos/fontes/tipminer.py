"""Fonte de resultados: tipminer.com, com login na tua conta (Playwright).

Os URLs e seletores CSS vêm do .env porque dependem do HTML atual do site.
Usa `python main.py --diagnostico` para gravar o HTML e screenshots das páginas
e acertar os seletores.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from ..jogos import Cor, Jogo
from .base import novos_itens

log = logging.getLogger(__name__)

# Junta texto e atributos de cada resultado para o jogo conseguir interpretar
# tanto "17" como class="result home" ou title="Empate".
JS_LER_ITENS = """
(seletor) => Array.from(document.querySelectorAll(seletor)).map(el => {
  const partes = [el.innerText, el.className, el.getAttribute('title'),
                  el.getAttribute('aria-label'), el.getAttribute('data-result'),
                  el.getAttribute('data-value')];
  el.querySelectorAll('img').forEach(i => partes.push(i.alt, i.src));
  el.querySelectorAll('[class]').forEach(c => partes.push(c.className));
  return partes.filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim();
})
"""


JS_CAMPOS = """
() => [
  ...Array.from(document.querySelectorAll('input')).map(i =>
    `input  type=${i.type} name=${i.name} id=${i.id} placeholder=${i.placeholder}`),
  ...Array.from(document.querySelectorAll('button, [type=submit], a[href*=login], a[href*=entrar]')).slice(0, 12).map(b =>
    `${b.tagName.toLowerCase()} type=${b.type || ''} id=${b.id} texto=${(b.innerText || '').trim().slice(0, 30)} href=${b.getAttribute('href') || ''}`),
]
"""

# Procura grupos de elementos repetidos com texto curto (números, letras, ícones):
# é assim que costumam aparecer os históricos de resultados.
JS_CANDIDATOS = """
() => {
  const grupos = {};
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length > 4) continue;
    const txt = (el.innerText || '').trim();
    if (txt.length > 10) continue;
    const tag = el.tagName.toLowerCase();
    const classes = Array.from(el.classList).map(c => '.' + CSS.escape(c));
    const chaves = classes.map(c => tag + c);
    if (classes.length > 1) chaves.push(tag + classes.join(''));
    for (const k of chaves) (grupos[k] = grupos[k] || []).push(el);
  }
  const amostra = e => {
    const img = e.querySelector('img');
    return [(e.innerText || '').trim(), e.getAttribute('title'), img && (img.alt || img.src.split('/').pop())]
      .filter(Boolean).join('/') || '(vazio)';
  };
  return Object.entries(grupos).filter(([, els]) => els.length >= 8)
    .sort((a, b) => b[1].length - a[1].length).slice(0, 20)
    .map(([sel, els]) => ({sel, n: els.length, ex: els.slice(0, 6).map(amostra)}));
}
"""


@dataclass
class ConfigTipminer:
    email: str
    senha: str
    url_login: str
    seletor_email: str
    seletor_senha: str
    seletor_entrar: str
    urls: dict[str, str]          # chave do jogo -> URL do histórico
    seletor_resultado: str
    recente_primeiro: bool = True
    intervalo: float = 4.0
    headless: bool = True
    ficheiro_sessao: Path = Path("dados/sessao_tipminer.json")


class FonteTipminer:
    def __init__(self, cfg: ConfigTipminer):
        self.cfg = cfg
        self._pw = None
        self._browser: Browser | None = None
        self._ctx: BrowserContext | None = None
        self._paginas: dict[str, Page] = {}
        self._lock = asyncio.Lock()
        self._conhecidos: dict[str, list[str]] = {}

    async def _contexto(self) -> BrowserContext:
        async with self._lock:
            if self._ctx:
                return self._ctx
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=self.cfg.headless, executable_path=os.getenv("CHROMIUM_PATH") or None)
            sessao = self.cfg.ficheiro_sessao
            self._ctx = await self._browser.new_context(
                storage_state=str(sessao) if sessao.exists() else None,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            )
            return self._ctx

    async def entrar(self) -> None:
        ctx = await self._contexto()
        pagina = await ctx.new_page()
        await pagina.goto(self.cfg.url_login, wait_until="domcontentloaded")
        if await pagina.locator(self.cfg.seletor_email).count() == 0:
            log.warning("Tipminer: campo de email não encontrado em %s (%s); "
                        "ou já tens sessão iniciada ou o URL/seletor de login está errado",
                        pagina.url, await pagina.title())
            await pagina.close()
            return
        await pagina.fill(self.cfg.seletor_email, self.cfg.email)
        await pagina.fill(self.cfg.seletor_senha, self.cfg.senha)
        await pagina.click(self.cfg.seletor_entrar)
        await pagina.wait_for_load_state("networkidle")
        self.cfg.ficheiro_sessao.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=str(self.cfg.ficheiro_sessao))
        log.info("Tipminer: login feito")
        await pagina.close()

    async def _pagina(self, jogo: Jogo) -> Page:
        if jogo.chave not in self._paginas:
            ctx = await self._contexto()
            p = await ctx.new_page()
            await p.goto(self.cfg.urls[jogo.chave], wait_until="domcontentloaded")
            self._paginas[jogo.chave] = p
        return self._paginas[jogo.chave]

    async def _janela(self, jogo: Jogo) -> list[str]:
        """Itens brutos da página, do mais antigo para o mais recente."""
        p = await self._pagina(jogo)
        await p.wait_for_selector(self.cfg.seletor_resultado, timeout=30000)
        itens = await p.evaluate(JS_LER_ITENS, self.cfg.seletor_resultado)
        itens = [i for i in itens if jogo.ler(i) is not None]
        return list(reversed(itens)) if self.cfg.recente_primeiro else itens

    async def historico(self, jogo: Jogo) -> list[Cor]:
        await self.entrar()
        janela = await self._janela(jogo)
        self._conhecidos[jogo.chave] = janela
        log.info("%s: %d resultados carregados do tipminer", jogo.nome, len(janela))
        return [jogo.ler(i) for i in janela]

    async def resultados(self, jogo: Jogo) -> AsyncIterator[Cor]:
        while True:
            await asyncio.sleep(self.cfg.intervalo)
            try:
                janela = await self._janela(jogo)
            except Exception as e:  # página caiu, sessão expirou, etc.
                log.warning("%s: erro a ler o tipminer (%s); a recarregar", jogo.nome, e)
                await self._recarregar(jogo)
                continue
            conhecidos = self._conhecidos[jogo.chave]
            novos = novos_itens(conhecidos, janela)
            if novos is None:
                log.warning("%s: perdi a sequência de resultados, a recomeçar", jogo.nome)
                self._conhecidos[jogo.chave] = janela
                continue
            self._conhecidos[jogo.chave] = (conhecidos + novos)[-500:]
            for item in novos:
                yield jogo.ler(item)

    async def _recarregar(self, jogo: Jogo) -> None:
        p = self._paginas.pop(jogo.chave, None)
        if p:
            await p.close()
        try:
            await self.entrar()
        except Exception as e:
            log.warning("Falha no login do tipminer: %s", e)

    async def diagnostico(self, jogos: list[Jogo], pasta: Path = Path("diagnostico")) -> None:
        pasta.mkdir(exist_ok=True)
        ctx = await self._contexto()

        print("\n== LOGIN")
        p = await ctx.new_page()
        r = await p.goto(self.cfg.url_login, wait_until="domcontentloaded")
        await p.wait_for_timeout(4000)
        print(f"  URL pedido : {self.cfg.url_login}")
        print(f"  URL final  : {p.url}  (HTTP {r.status if r else '?'})")
        print(f"  Título     : {await p.title()}")
        for campo in await p.evaluate(JS_CAMPOS):
            print(f"  {campo}")
        await p.screenshot(path=str(pasta / "login.png"), full_page=True)
        await p.close()

        try:
            await self.entrar()
        except Exception as e:
            print(f"  Falha no login: {e}")

        for jogo in jogos:
            p = await ctx.new_page()
            r = await p.goto(self.cfg.urls[jogo.chave], wait_until="domcontentloaded")
            self._paginas[jogo.chave] = p
            await p.wait_for_timeout(8000)
            await p.screenshot(path=str(pasta / f"{jogo.chave}.png"), full_page=True)
            (pasta / f"{jogo.chave}.html").write_text(await p.content())
            print(f"\n== {jogo.nome.upper()}")
            print(f"  URL final : {p.url}  (HTTP {r.status if r else '?'})")
            print(f"  Título    : {await p.title()}")
            texto = (await p.evaluate("document.body.innerText"))[:250].replace("\n", " | ")
            print(f"  Texto     : {texto}")
            itens = await p.evaluate(JS_LER_ITENS, self.cfg.seletor_resultado)
            print(f"  Seletor atual '{self.cfg.seletor_resultado}': {len(itens)} itens")
            print("  Candidatos (seletor / quantidade / exemplos):")
            for c in await p.evaluate(JS_CANDIDATOS):
                print(f"    {c['sel'][:60]:<60} {c['n']:>4}  {' · '.join(c['ex'])[:70]}")
        print(f"\nHTML e screenshots gravados em {pasta.resolve()}")

    async def fechar(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
