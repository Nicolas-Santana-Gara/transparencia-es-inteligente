"""Gera um conjunto SIMULADO, no mesmo formato dos arquivos oficiais.

Serve só para o painel abrir e ser demonstrado quando os ZIPs oficiais não
estão na máquina. Os nomes são claramente fictícios e o painel avisa, em
todas as telas, que os dados não são reais.
"""

import numpy as np
import pandas as pd

GRUPOS = ["PESSOAL E ENCARGOS SOCIAIS (DEMO)", "OUTRAS DESPESAS CORRENTES (DEMO)", "INVESTIMENTOS (DEMO)",
          "JUROS E ENCARGOS DA DÍVIDA (DEMO)", "INVERSÕES FINANCEIRAS (DEMO)"]
MODALIDADES = ["APLICAÇÕES DIRETAS (DEMO)", "TRANSFERÊNCIAS A MUNICÍPIOS (DEMO)", "TRANSFERÊNCIAS A ENTIDADES (DEMO)"]


def _brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_bruto(n=40000, semente=2025):
    """Devolve um DataFrame de texto, como se tivesse acabado de sair do CSV."""
    rng = np.random.default_rng(semente)
    unidades = [f"UNIDADE GESTORA DEMO {i:02d}" for i in range(1, 41)]
    pesos = np.r_[0.17, 0.12, 0.09, 0.08, 0.07, [0.47 / 35] * 35]
    dias = rng.integers(1, 365, n)
    dias = np.where(rng.random(n) < 0.08, rng.integers(334, 365, n), dias)  # mais movimento em dezembro
    datas = pd.to_datetime("2025-01-01") + pd.to_timedelta(dias, unit="D")
    empenho = rng.lognormal(9, 1.7, n)
    tipo = rng.choice(["zero", "positivo", "negativo"], n, p=[0.70, 0.28, 0.02])
    pago = np.where(tipo == "positivo", empenho, np.where(tipo == "negativo", -empenho * 0.3, 0.0))
    ids = np.arange(1, n + 1)
    df = pd.DataFrame({
        "Id": ids.astype(str),
        "Data": datas.strftime("%d/%m/%Y"),
        "Orgao": "", "Funcao": "", "NumeroProcesso": "",
        "UnidadeGestora": rng.choice(unidades, n, p=pesos / pesos.sum()),
        "GrupoDespesa": rng.choice(GRUPOS, n, p=[0.45, 0.34, 0.12, 0.06, 0.03]),
        "Modalidade": rng.choice(MODALIDADES, n),
        "Favorecido": [f"FAVORECIDO DEMO {i:04d}" for i in rng.integers(1, 2500, n)],
        "Documento": [f"DEMO2025NE{i:06d}" for i in ids],
        "ValorEmpenho": [_brl(v) for v in empenho],
        "ValorLiquidado": [_brl(v) for v in np.abs(pago)],
        "ValorPago": [_brl(v) for v in pago],
        "ValorRap": "0,00",
    })
    df["arquivo_origem"] = "dados_simulados_demo.csv"
    df["linha_origem"] = range(2, n + 2)
    return df
