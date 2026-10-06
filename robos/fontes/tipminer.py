"""Fonte de resultados: tipminer.com, com login na tua conta (Playwright).

Os URLs e seletores CSS vêm do .env porque dependem do HTML atual do site.
Usa `python main.py --diagnostico` para gravar o HTML e screenshots das páginas
e acertar os seletores.
"""
from __future__ import annotations

import asyncio
import logging
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
            self._browser = await self._pw.chromium.launch(headless=self.cfg.headless)
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
            log.info("Tipminer: sessão já iniciada")
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
        await self.entrar()
        for jogo in jogos:
            p = await self._pagina(jogo)
            await p.wait_for_timeout(5000)
            await p.screenshot(path=str(pasta / f"{jogo.chave}.png"), full_page=True)
            (pasta / f"{jogo.chave}.html").write_text(await p.content())
            itens = await p.evaluate(JS_LER_ITENS, self.cfg.seletor_resultado)
            print(f"\n== {jogo.nome}: {len(itens)} itens com o seletor '{self.cfg.seletor_resultado}'")
            for i in itens[:15]:
                print(f"  {jogo.ler(i)!s:<14} <- {i[:100]}")
        print(f"\nHTML e screenshots gravados em {pasta.resolve()}")

    async def fechar(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
