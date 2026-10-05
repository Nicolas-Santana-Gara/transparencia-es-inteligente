"""Contas do painel: filtros, as duas perguntas, intervalos de confiança e busca."""

import math

import pandas as pd
from scipy import stats

from .esquema import CAMPOS_BUSCA, sem_acento_minusculo

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
              "agosto", "setembro", "outubro", "novembro", "dezembro"]
Z_95 = 1.96
N_MINIMO = 30


def filtrar(df, meses=None, unidades=None, grupos=None):
    """Filtros da barra lateral. None ou lista vazia = não filtra."""
    f = df
    if meses:
        f = f[f["mes"].between(meses[0], meses[1])]
    if unidades and "unidade_gestora" in f.columns:
        f = f[f["unidade_gestora"].isin(unidades)]
    if grupos and "grupo_despesa" in f.columns:
        f = f[f["grupo_despesa"].isin(grupos)]
    return f


# ---------------------------------------------------------------- pergunta 1

def serie_mensal(df, medida="valor_pago"):
    """Soma da medida em cada mês, com o número de registros que entraram."""
    g = df.dropna(subset=["mes"]).groupby("mes", observed=True)[medida].agg(total="sum", registros="count").reset_index()
    g["mes"] = g["mes"].astype(int)
    return g.sort_values("mes").reset_index(drop=True)


def resumo_do_pico(mensal):
    """Maior e menor mês e a variação do maior sobre o mês anterior."""
    if mensal.empty:
        return None
    maior = mensal.loc[mensal["total"].idxmax()]
    menor = mensal.loc[mensal["total"].idxmin()]
    anterior = mensal[mensal["mes"] == maior["mes"] - 1]
    variacao = None
    if not anterior.empty and anterior["total"].iloc[0] > 0:
        variacao = (maior["total"] / anterior["total"].iloc[0] - 1) * 100
    return {"mes_maior": int(maior["mes"]), "total_maior": float(maior["total"]),
            "mes_menor": int(menor["mes"]), "total_menor": float(menor["total"]),
            "variacao_sobre_anterior": variacao, "media_mensal": float(mensal["total"].mean())}


def ic_media(valores, confianca=0.95):
    """IC da média pela t de Student: média ± t × s / √n."""
    v = pd.Series(valores).dropna()
    n = len(v)
    if n < 2:
        return {"n": n, "media": float(v.mean()) if n else math.nan, "mediana": float(v.median()) if n else math.nan,
                "desvio": math.nan, "ic_inf": math.nan, "ic_sup": math.nan}
    media, desvio = float(v.mean()), float(v.std(ddof=1))
    margem = stats.t.ppf((1 + confianca) / 2, df=n - 1) * desvio / math.sqrt(n)
    return {"n": n, "media": media, "mediana": float(v.median()), "desvio": desvio,
            "ic_inf": media - margem, "ic_sup": media + margem}


def pagamento_medio_pico_x_resto(df, mes_pico):
    """Valor médio por pagamento (ValorPago > 0) no mês de pico e nos demais meses."""
    pagos = df[(df["valor_pago"] > 0) & df["mes"].notna()]
    return {"pico": ic_media(pagos.loc[pagos["mes"] == mes_pico, "valor_pago"]),
            "resto": ic_media(pagos.loc[pagos["mes"] != mes_pico, "valor_pago"])}


def intervalos_se_sobrepoem(a, b):
    return not (a["ic_sup"] < b["ic_inf"] or b["ic_sup"] < a["ic_inf"])


# ---------------------------------------------------------------- pergunta 2

def concentracao(df, por, medida="valor_pago"):
    """Total, participação e acumulado por unidade gestora, grupo etc."""
    g = df.groupby(por, dropna=False, observed=True)[medida].agg(total="sum", registros="count").reset_index()
    g = g.sort_values("total", ascending=False).reset_index(drop=True)
    soma = g["total"].sum()
    g["participacao"] = g["total"] / soma * 100 if soma else 0.0
    g["acumulado"] = g["participacao"].cumsum()
    return g


# ---------------------------------------------------------------- qualidade

def ic_proporcao(k, n):
    """IC de 95% de uma proporção: p ± 1,96 × √(p(1 − p)/n). Devolve em %."""
    if not n:
        return {"p": math.nan, "ic_inf": math.nan, "ic_sup": math.nan}
    p = k / n
    margem = Z_95 * math.sqrt(p * (1 - p) / n)
    return {"p": p * 100, "ic_inf": max(0.0, p - margem) * 100, "ic_sup": min(1.0, p + margem) * 100}


# ---------------------------------------------------------------- busca e exibição

def buscar(df, termo):
    """Procura o termo em favorecido, unidade gestora, documento e modalidade, sem ligar para acento ou maiúscula.

    Compara com os valores distintos de cada campo (são poucos perto do total de linhas) e depois
    pega as linhas que têm esses valores. Assim não é preciso guardar uma coluna extra só para a busca.
    """
    termo = sem_acento_minusculo(termo).strip()
    if not termo:
        return df
    achou = pd.Series(False, index=df.index)
    for campo in CAMPOS_BUSCA:
        if campo in df.columns:
            valores = [v for v in df[campo].unique() if termo in sem_acento_minusculo(v)]
            if valores:
                achou |= df[campo].isin(valores)
    return df[achou]


def mascarar_documento(valor):
    """CPF (11 dígitos) vira ***.456.789-**. CNPJ é de empresa e fica como está."""
    digitos = "".join(ch for ch in str(valor) if ch.isdigit())
    if len(digitos) == 11:
        return f"***.{digitos[3:6]}.{digitos[6:9]}-**"
    return valor


COLUNAS_TABELA = ["id", "documento", "data", "unidade_gestora", "favorecido", "grupo_despesa", "modalidade",
                  "valor_empenho", "valor_liquidado", "valor_pago", "valor_rap", "arquivo_origem", "linha_origem"]


ROTULOS = {"id": "Id", "documento": "Documento", "data": "Data", "unidade_gestora": "Unidade gestora",
           "favorecido": "Favorecido", "codigo_favorecido": "CPF/CNPJ", "grupo_despesa": "Grupo de despesa",
           "modalidade": "Modalidade", "valor_empenho": "Empenhado (R$)", "valor_liquidado": "Liquidado (R$)",
           "valor_pago": "Pago (R$)", "valor_rap": "Restos a pagar (R$)",
           "arquivo_origem": "Arquivo de origem", "linha_origem": "Linha no arquivo"}


def para_exibir(df):
    """Tabela de rastreabilidade: Id e Documento sempre na frente, CPF mascarado."""
    visivel = df[[c for c in COLUNAS_TABELA if c in df.columns]].copy()
    if "codigo_favorecido" in df.columns:
        visivel.insert(min(5, len(visivel.columns)), "codigo_favorecido", df["codigo_favorecido"].map(mascarar_documento))
    return visivel.rename(columns=ROTULOS)
