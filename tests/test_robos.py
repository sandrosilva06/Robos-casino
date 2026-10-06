from robos.estrategia import ConfigEstrategia, analisar
from robos.fontes.base import novos_itens
from robos.jogos import FOOTBALL_STUDIO as FS, LIGHTNING_ROULETTE as LR, Cor
from robos.mensagens import formatar
from robos.sinais import ConfigGestao, GestorSinais

V, A, E, P, Z = Cor.VERMELHO, Cor.AZUL, Cor.EMPATE, Cor.PRETO, Cor.ZERO


def gestor(jogo=FS, **kw):
    cfg = ConfigEstrategia(tamanhos_padrao=(2,), min_amostras=3, taxa_minima=0.5)
    return GestorSinais(jogo, cfg, ConfigGestao(pausa_apos_red=kw.get("pausa", 0)))


def com_sinal(g, cor=V):
    """Força um sinal ativo sem depender da análise."""
    from robos.estrategia import Analise
    from robos.sinais import SinalAtivo
    g.sinal = SinalAtivo(cor, 0, Analise(cor, (V, V), 10, 0.9, 0.5))
    g.lucro_ciclo = 0.0


def test_green_sem_gale():
    g = gestor()
    com_sinal(g)
    ev = g.novo_resultado(V)[0]
    assert ev.tipo == "GREEN" and ev.gale == 0
    assert g.placar.greens["G0"] == 1
    assert ev.lucro_ciclo == 0.9  # +1 na cor, -0.1 na proteção


def test_dois_gales_e_red():
    g = gestor()
    com_sinal(g)
    assert [e.tipo for e in g.novo_resultado(A)] == ["GALE"]
    assert [e.tipo for e in g.novo_resultado(A)] == ["GALE"]
    ev = g.novo_resultado(A)[0]
    assert ev.tipo == "RED"
    assert g.placar.reds == 1
    assert ev.lucro_ciclo == -7.7  # -(1+2+4) na cor, -(0.1+0.2+0.4) na proteção


def test_green_no_gale_2():
    g = gestor()
    com_sinal(g)
    g.novo_resultado(A)
    g.novo_resultado(A)
    ev = g.novo_resultado(V)[0]
    assert ev.tipo == "GREEN" and ev.gale == 2
    assert ev.lucro_ciclo == round(-1.1 - 2.2 + 3.6, 2)


def test_empate_protegido_football_studio():
    g = gestor()
    com_sinal(g)
    ev = g.novo_resultado(E)[0]
    assert ev.tipo == "GREEN" and g.placar.greens["PROTECAO"] == 1
    assert ev.lucro_ciclo == round(0.1 * 11 - 0.5, 2)


def test_zero_protegido_roleta():
    g = gestor(LR)
    com_sinal(g, P)
    ev = g.novo_resultado(Z)[0]
    assert ev.tipo == "GREEN"
    assert ev.lucro_ciclo == round(0.1 * 29 - 1, 2)


def test_pausa_apos_red():
    g = gestor(pausa=2)
    g.carregar_historico([V, A] * 20)
    com_sinal(g)
    for _ in range(3):
        g.novo_resultado(A)
    assert g.sinal is None
    assert g.novo_resultado(V) == [] and g.novo_resultado(A) == []


def test_analise_encontra_padrao():
    # Depois de V,V vem sempre A neste histórico.
    hist = [V, V, A, A] * 15 + [V, V]
    a = analisar(hist, FS, ConfigEstrategia(tamanhos_padrao=(2,), min_amostras=5, taxa_minima=0.9, taxa_maxima=1.0))
    assert a is not None and a.cor == A and a.taxa_sem_gale == 1.0


def test_analise_ignora_padrao_com_protecao():
    hist = [V, A] * 30 + [E, V]
    assert analisar(hist, FS, ConfigEstrategia(tamanhos_padrao=(2,), min_amostras=5, taxa_minima=0.0)) is None


def test_ler_resultados():
    assert FS.ler("result home") == V
    assert FS.ler("Visitante") == A
    assert FS.ler("tie") == E
    assert LR.ler("17") == P and LR.ler("32 x500") == V and LR.ler("0") == Z
    assert LR.ler("sem numero") is None


def test_novos_itens():
    conhecidos = list("abcdefgh")
    assert novos_itens(conhecidos, list("cdefghij")) == ["i", "j"]
    assert novos_itens(conhecidos, list("cdefgh")) == []
    assert novos_itens(conhecidos, list("xyzwqk")) is None


def test_mensagens():
    g = gestor()
    com_sinal(g)
    for r in (A, A, V):
        for ev in g.novo_resultado(r):
            assert formatar(ev)


def test_analise_respeita_taxa_maxima():
    hist = [V, V, A, A] * 15 + [V, V]  # padrão com 100%
    cfg = ConfigEstrategia(tamanhos_padrao=(2,), min_amostras=5, taxa_minima=0.88, taxa_maxima=0.98)
    assert analisar(hist, FS, cfg) is None


def test_mensagem_entrada():
    from robos.estrategia import Analise
    from robos.sinais import Evento
    ev = Evento("ENTRADA", FS, A, analise=Analise(A, (V, V), 50, 0.912, 0.5))
    texto = formatar(ev, "https://betnjet.click/WFcUQ")
    assert "🔵 VISITANTE" in texto and "🟡 EMPATE" in texto
    assert "Assertividade: <b>91%</b>" in texto and "https://betnjet.click/WFcUQ" in texto
