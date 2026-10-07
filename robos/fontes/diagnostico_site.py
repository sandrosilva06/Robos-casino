"""Diagnóstico de uma página pública de histórico (sem login).

    python main.py --diagnostico-site https://signals-house.com/cataloguer/27

Abre a página e durante uns minutos regista: pedidos de dados (XHR/fetch),
mensagens WebSocket e os grupos de elementos que parecem ser o histórico, com
a cor de cada bola e onde aparecem os resultados novos.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path

from playwright.async_api import async_playwright

from .tipminer import JS_CANDIDATOS

JS_ITENS = """
(sel) => Array.from(document.querySelectorAll(sel)).map(e => {
  const st = getComputedStyle(e);
  let cor = st.backgroundColor;
  if (cor === 'rgba(0, 0, 0, 0)' || cor === 'transparent') cor = st.backgroundImage.slice(0, 40);
  return `${(e.innerText || '').trim()}|${cor}|${e.className}`.slice(0, 90);
})
"""


JS_BOLAS = """
() => Array.from(document.querySelectorAll('body *'))
  .filter(e => e.children.length === 0 && /^([2-9]|1[0-4])$/.test((e.innerText || '').trim()))
  .map(e => {
    const alvo = e.closest('[class*=rounded]') || e;
    return `${e.innerText.trim()}|${getComputedStyle(alvo).backgroundColor}|${e.tagName.toLowerCase()}.${e.className}|pai: ${alvo.className}`.slice(0, 140);
  })
"""


async def diagnostico(url: str, segundos: int = 120, pasta: Path = Path("diagnostico")) -> None:
    pasta.mkdir(exist_ok=True)
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
    ctx = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    )
    pedidos: list[tuple[str, int, str]] = []
    todos: list[tuple[str, str]] = []
    falhas: list[str] = []
    consola: list[str] = []
    frames: list[tuple[str, str]] = []

    async def ao_responder(resp):
        if resp.request.resource_type not in ("xhr", "fetch"):
            return
        try:
            corpo = await resp.text()
        except Exception:
            corpo = ""
        pedidos.append((resp.url, resp.status, corpo))

    def ao_abrir_ws(ws):
        print(f"  WebSocket aberto: {ws.url[:110]}")
        ws.on("framereceived", lambda d: frames.append(
            (ws.url, d if isinstance(d, str) else d.decode("utf-8", "replace"))))

    try:
        p = await ctx.new_page()
        p.on("response", lambda r: asyncio.ensure_future(ao_responder(r)))
        p.on("websocket", ao_abrir_ws)
        p.on("request", lambda rq: todos.append((rq.resource_type, rq.url)))
        p.on("requestfailed", lambda rq: falhas.append(f"{rq.resource_type} {rq.url[:100]} {rq.failure}"))
        p.on("console", lambda m: consola.append(f"{m.type}: {m.text[:150]}") if m.type in ("error", "warning") else None)
        print("\n== PÁGINA")
        r = await p.goto(url, wait_until="domcontentloaded")
        await p.wait_for_timeout(10000)
        print(f"  URL final : {p.url}  (HTTP {r.status if r else '?'})")
        print(f"  Título    : {await p.title()}")
        texto = (await p.evaluate("document.body.innerText"))[:200].replace("\n", " | ")
        print(f"  Texto     : {texto}")
        # Faz scroll até ao fundo, para carregar gráficos que só aparecem quando ficam visíveis.
        for _ in range(10):
            await p.mouse.wheel(0, 900)
            await p.wait_for_timeout(700)
        await p.wait_for_timeout(5000)
        await p.screenshot(path=str(pasta / "site_inicio.png"), full_page=True)
        bolas = await p.evaluate(JS_BOLAS)
        print(f"\n== BOLAS COM NÚMERO 2-14: {len(bolas)} encontradas")
        for b in bolas[:8]:
            print(f"  {b}")

        candidatos = await p.evaluate(JS_CANDIDATOS)
        print("\n== CANDIDATOS A HISTÓRICO (seletor / quantidade / exemplos)")
        for c in candidatos[:12]:
            print(f"  {c['sel'][:55]:<55} {c['n']:>4}  {' · '.join(c['ex'])[:60]}")
        principais = [c["sel"] for c in candidatos[:3]]
        antes = {s: await p.evaluate(JS_ITENS, s) for s in principais}

        print(f"\n== A OBSERVAR DURANTE {segundos}s")
        for i in range(segundos // 30):
            await asyncio.sleep(30)
            print(f"  ... {(i + 1) * 30}s: {len(pedidos)} pedidos de dados, {len(frames)} mensagens WebSocket")
        await p.screenshot(path=str(pasta / "site_fim.png"), full_page=True)

        print("\n== O QUE MUDOU NOS CANDIDATOS (texto|cor|classe)")
        for s in principais:
            depois = await p.evaluate(JS_ITENS, s)
            print(f"  [{s[:60]}] antes {len(antes[s])} itens, depois {len(depois)}")
            print(f"    primeiros antes : {' ; '.join(antes[s][:3])}")
            print(f"    primeiros depois: {' ; '.join(depois[:3])}")
            print(f"    últimos antes   : {' ; '.join(antes[s][-3:])}")
            print(f"    últimos depois  : {' ; '.join(depois[-3:])}")

        print("\n== PEDIDOS DE DADOS (quantidade / estado / URL / início da resposta)")
        por_url = Counter(u.split("?")[0] for u, _, _ in pedidos)
        exemplo = {u.split("?")[0]: (s, c) for u, s, c in pedidos}
        for u, n in por_url.most_common(10):
            s, c = exemplo[u]
            print(f"  {n:>4}  {s}  {u[:90]}")
            print(f"        {c[:200]!r}")

        print("\n== TODOS OS PEDIDOS QUE NÃO SÃO IMAGENS/ESTILOS (tipo / URL)")
        vistos = set()
        for tipo, u in todos:
            chave = (tipo, u.split("?")[0])
            if tipo in ("image", "stylesheet", "font", "media") or chave in vistos:
                continue
            vistos.add(chave)
            print(f"  {tipo:<11} {u[:110]}")
        if falhas:
            print("\n== PEDIDOS QUE FALHARAM")
            for f in falhas[:10]:
                print(f"  {f}")
        if consola:
            print("\n== ERROS NA CONSOLA DA PÁGINA")
            for c in consola[:10]:
                print(f"  {c}")
        api = [(u, c) for u, _, c in pedidos if "signals-house.com/games" in u]
        if api:
            print("\n== RESPOSTAS DA API DE JOGOS")
            for u, c in api[:4]:
                print(f"  {u[:100]}\n    {c[:600]}")

        if frames:
            print("\n== WEBSOCKET (quantidade / exemplo)")
            tipos: Counter[str] = Counter()
            ex: dict[str, str] = {}
            for _, d in frames:
                try:
                    o = json.loads(d)
                    t = str(o.get("type") or o.get("event") or "?") if isinstance(o, dict) else "lista"
                except ValueError:
                    t = d[:20]
                tipos[t] += 1
                ex.setdefault(t, d)
            for t, n in tipos.most_common(12):
                print(f"  {n:>4}  {t[:30]:<30} {ex[t][:150]}")

        with open(pasta / "site_pedidos.jsonl", "w") as fh:
            for u, s, c in pedidos:
                fh.write(json.dumps({"url": u, "estado": s, "corpo": c[:5000]}) + "\n")
        print(f"\n  Gravado em {pasta.resolve()}")
    finally:
        await browser.close()
        await pw.stop()
