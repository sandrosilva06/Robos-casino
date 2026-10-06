from __future__ import annotations


def novos_itens(conhecidos: list[str], janela: list[str], sobreposicao_minima: int = 5) -> list[str] | None:
    """Compara a janela de resultados lida do site (do mais antigo para o mais
    recente) com o que já conhecemos e devolve só os itens novos.

    Procura a maior sobreposição entre o fim dos conhecidos e o início da janela.
    Devolve None se não houver sobreposição fiável (ex.: o bot esteve parado).
    """
    if not conhecidos:
        return janela
    maximo = min(len(conhecidos), len(janela))
    for n in range(maximo, 0, -1):
        if conhecidos[-n:] == janela[:n]:
            if n < min(sobreposicao_minima, maximo):
                break
            return janela[n:]
    return None
