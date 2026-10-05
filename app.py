"""Transparência ES Inteligente - POC do CP2 (CPSI simulado).

Antes de abrir o painel, processe os dados:   python -m src.etl
Depois:                                       streamlit run app.py
"""

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pyarrow.parquet as pq
import streamlit as st

from src import analise
from src.analise import MESES, MESES_NOME
from src.esquema import MEDIDAS, TEXTOS

# dá para apontar outra pasta com a variável de ambiente DADOS_PROCESSADOS (os testes usam isso)
PASTA = Path(os.environ.get("DADOS_PROCESSADOS", Path(__file__).parent / "data_processed"))
AZUL, LARANJA, CINZA = "#2459C4", "#D9722B", "#9DB4E0"

st.set_page_config(page_title="Transparência ES Inteligente", layout="wide")


def brl(valor):
    if pd.isna(valor):
        return "-"
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def curto(valor):
    """1234567890 -> '1,23 bi' (para caber nos cartões)."""
    if pd.isna(valor):
        return "-"
    for limite, sufixo in [(1e9, "bi"), (1e6, "mi"), (1e3, "mil")]:
        if abs(valor) >= limite:
            return f"{valor / limite:.2f} {sufixo}".replace(".", ",")
    return f"{valor:.0f}"


def md(texto):
    """No Streamlit, dois '$' no mesmo texto viram fórmula. Isso mantém o 'R$' como texto."""
    return texto.replace("$", "\\$")


def milhar(n):
    return f"{int(n):,}".replace(",", ".")


def pct(x, casas=1):
    return f"{x:.{casas}f}%".replace(".", ",")


@st.cache_resource(show_spinner="Carregando os dados processados...")
def carregar(pasta, assinatura):
    # 'assinatura' (tamanho e data do arquivo) só serve para o cache notar quando o ETL rodou de novo.
    # cache_resource guarda uma cópia só na memória para todas as sessões; o painel nunca altera esta tabela.
    caminho = Path(pasta) / "registros.parquet"
    # textos que se repetem muito (unidade gestora, favorecido...) são lidos como categoria:
    # o nome fica guardado uma vez só, e a tabela inteira ocupa bem menos memória
    textos = (set(TEXTOS) | {"codigo_favorecido", "arquivo_origem"}) - {"id"}
    repetidos = [c for c in pq.read_schema(caminho).names if c in textos]
    registros = pq.read_table(caminho, read_dictionary=repetidos).to_pandas()
    qualidade = json.loads((Path(pasta) / "qualidade.json").read_text(encoding="utf-8"))
    return registros, qualidade


def grafico_mensal(mensal, pico):
    cores = [LARANJA if m == pico["mes_maior"] else CINZA if m == pico["mes_menor"] else AZUL for m in mensal["mes"]]
    fig = go.Figure(go.Bar(x=[MESES[m - 1] for m in mensal["mes"]], y=mensal["total"], marker_color=cores,
                           hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>"))
    fig.add_hline(y=pico["media_mensal"], line_dash="dot", line_color="#5B6680",
                  annotation_text="média mensal", annotation_position="top left")
    fig.update_layout(yaxis_title="Valor pago (R$)", xaxis_title="Mês", height=400, margin=dict(t=30))
    return fig


def frase_do_pico(pico):
    vezes = f"{pico['total_maior'] / pico['media_mensal']:.1f}".replace(".", ",")
    texto = (f"O maior mês foi **{MESES_NOME[pico['mes_maior'] - 1]}**, com {brl(pico['total_maior'])}, "
             f"o equivalente a {vezes} vezes a média mensal de {brl(pico['media_mensal'])}.")
    if pico["variacao_sobre_anterior"] is not None:
        texto += f" Ficou {pct(pico['variacao_sobre_anterior'])} acima do mês anterior."
    return texto + f" O menor foi **{MESES_NOME[pico['mes_menor'] - 1]}**, com {brl(pico['total_menor'])}."


st.title("Transparência ES Inteligente")
st.caption("Despesas do Governo do Espírito Santo: do indicador ao registro de origem.")

# ---------------------------------------------------------------- dados

arquivo = PASTA / "registros.parquet"
if not arquivo.exists() or not (PASTA / "qualidade.json").exists():
    st.error(
        "Os dados ainda não foram processados.\n\n"
        "1. Coloque os arquivos ZIP de despesas na pasta `data_raw/`.\n"
        "2. Rode `python -m src.etl` no terminal.\n"
        "3. Atualize esta página."
    )
    st.stop()

try:
    df, q = carregar(str(PASTA), (arquivo.stat().st_size, arquivo.stat().st_mtime))
except Exception as erro:  # arquivo corrompido ou gerado por outra versão do ETL
    st.error(f"Não consegui abrir os dados processados ({erro}). Rode `python -m src.etl` de novo.")
    st.stop()

medidas = q["medidas"]
simulado = q.get("simulado", False)
FONTE = "dados simulados para demonstração" if simulado else "Governo do Estado do Espírito Santo"

if simulado:
    st.warning(
        "**Modo demonstração: estes dados são SIMULADOS.** Não são os dados oficiais do Espírito Santo e os números "
        "não devem ser usados como resultado. Para usar os dados reais, coloque os ZIPs em `data_raw/` e rode "
        "`python -m src.etl`."
    )

# ---------------------------------------------------------------- filtros

with st.sidebar:
    st.header("Filtros")
    meses = st.slider("Meses", 1, 12, (1, 12))
    unidades = []
    if "unidade_gestora" in df.columns:
        unidades = st.multiselect("Unidade gestora", sorted(df["unidade_gestora"].unique()), placeholder="Todas")
    grupos = []
    if "grupo_despesa" in df.columns:
        grupos = st.multiselect("Grupo de despesa", sorted(df["grupo_despesa"].unique()), placeholder="Todos")
    st.divider()
    st.caption(f"{milhar(q['registros'])} registros, de {q['periodo'][0]} a {q['periodo'][1]}. "
               f"Processado em {q['gerado_em']}.")
    if simulado:
        st.caption("Dados simulados, só para demonstração.")
    else:
        st.caption("O conjunto é um recorte: os totais valem para ele, não para o Estado inteiro.")

recorte = analise.filtrar(df, meses, unidades, grupos)


def filtros_em_texto():
    partes = [f"Meses: {MESES[meses[0] - 1]} a {MESES[meses[1] - 1]}"]
    partes.append("Unidade gestora: " + (", ".join(unidades) if unidades else "todas"))
    partes.append("Grupo: " + (", ".join(grupos) if grupos else "todos"))
    return " | ".join(partes)


def rodape(n, medida="ValorPago (R$)"):
    st.caption(f"Medida: {medida} | {filtros_em_texto()} | {milhar(n)} registros | Fonte: {FONTE}")


if recorte.empty:
    st.warning("Nenhum registro para os filtros escolhidos. Tire algum filtro ou amplie o período.")
    st.stop()

aba_geral, aba_quando, aba_onde, aba_busca, aba_qualidade = st.tabs(
    ["Visão geral", "Quando se paga", "Onde se concentra", "Busca e rastreabilidade", "Qualidade dos dados"]
)

# ---------------------------------------------------------------- visão geral

with aba_geral:
    pagos = recorte[recorte["valor_pago"] > 0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valor pago (R$)", curto(recorte["valor_pago"].sum()), help=brl(recorte["valor_pago"].sum()))
    c2.metric("Registros", milhar(len(recorte)), help="Todas as linhas do recorte, com ou sem pagamento")
    if "favorecido" in recorte.columns:
        c3.metric("Favorecidos pagos", milhar(pagos["favorecido"].nunique()))
    if "unidade_gestora" in recorte.columns:
        c4.metric("Unidades gestoras", milhar(recorte["unidade_gestora"].nunique()))

    st.write("**As etapas da despesa, uma de cada vez**")
    colunas = st.columns(len(medidas))
    for coluna, m in zip(colunas, medidas):
        coluna.metric(f"{MEDIDAS[m]} (R$)", curto(recorte[m].sum()), help=brl(recorte[m].sum()))
    st.caption("Empenhado, liquidado, pago e restos a pagar são etapas diferentes da mesma despesa. "
               "Por isso aparecem separados e nunca são somados entre si.")

    mensal_geral = analise.serie_mensal(recorte)
    pico_geral = analise.resumo_do_pico(mensal_geral)
    if pico_geral is not None:
        st.write("**Valor pago por mês**")
        st.plotly_chart(grafico_mensal(mensal_geral, pico_geral), width="stretch", key="mensal_geral")
        st.write(md(frase_do_pico(pico_geral)))

    st.info(f"De cada 10 registros, cerca de {round(q['pago_zero'] / q['registros'] * 10)} têm valor pago igual a zero: "
            "representam outra etapa da despesa. O painel não conta registro como pagamento.")
    rodape(len(recorte))

# ---------------------------------------------------------------- pergunta 1

with aba_quando:
    st.subheader("Em quais meses o valor pago se concentra?")
    mensal = analise.serie_mensal(recorte)
    pico = analise.resumo_do_pico(mensal)

    if pico is None:
        st.warning("Não há registros com data neste recorte.")
    else:
        st.plotly_chart(grafico_mensal(mensal, pico), width="stretch", key="mensal_quando")
        st.write(md(frase_do_pico(pico)))
        rodape(int(mensal["registros"].sum()))

        st.divider()
        st.write(f"**O pico vem de pagamentos maiores? Valor médio por pagamento em "
                 f"{MESES_NOME[pico['mes_maior'] - 1]} e nos outros meses**")
        comp = analise.pagamento_medio_pico_x_resto(recorte, pico["mes_maior"])
        linhas = []
        for rotulo, r in [(MESES_NOME[pico["mes_maior"] - 1].capitalize(), comp["pico"]), ("Demais meses", comp["resto"])]:
            linhas.append({"Período": rotulo, "Pagamentos (n)": milhar(r["n"]), "Média": brl(r["media"]),
                           "IC 95% - de": brl(r["ic_inf"]), "IC 95% - até": brl(r["ic_sup"]),
                           "Mediana": brl(r["mediana"]), "Desvio padrão": brl(r["desvio"])})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

        a, b = comp["pico"], comp["resto"]
        if min(a["n"], b["n"]) < analise.N_MINIMO:
            st.warning(f"Há menos de {analise.N_MINIMO} pagamentos em um dos períodos. "
                       "Com tão poucos, o intervalo fica largo e pouco confiável.")
        elif analise.intervalos_se_sobrepoem(a, b):
            st.info("Os intervalos se sobrepõem: não dá para afirmar que o pagamento médio do mês de pico é diferente. "
                    "O pico vem principalmente de mais pagamentos, não de pagamentos maiores.")
        else:
            sentido = "maior" if a["media"] > b["media"] else "menor"
            st.info(f"Os intervalos não se sobrepõem: o pagamento médio do mês de pico é {sentido} que o dos outros meses.")
        st.caption("Entram só registros com ValorPago maior que zero. IC de 95% da média pela t de Student "
                   "(média ± t × desvio / √n). O conjunto é um recorte sistemático, então o intervalo é uma referência.")

        with st.expander("O que um pico pode indicar, e o que ele não prova"):
            st.markdown(
                "- **Pode indicar:** encerramento do exercício, folha de pagamento, transferências programadas "
                "ou registros contábeis agrupados.\n"
                "- **Não prova:** desperdício, fraude ou irregularidade. O pico é só um ponto de partida, e todo valor "
                "pode ser conferido na aba de busca até o Documento e o Id do registro."
            )

# ---------------------------------------------------------------- pergunta 2

with aba_onde:
    st.subheader("Quais unidades gestoras e grupos de despesa concentram o valor pago?")
    if "unidade_gestora" not in recorte.columns:
        st.warning("O arquivo não tem a coluna de unidade gestora.")
    else:
        dist = analise.concentracao(recorte, "unidade_gestora")
        topo = dist.head(10)
        esquerda, direita = st.columns([3, 2])
        with esquerda:
            fig = px.bar(topo.iloc[::-1], x="total", y="unidade_gestora", orientation="h",
                         labels={"total": "Valor pago (R$)", "unidade_gestora": ""}, color_discrete_sequence=[AZUL])
            fig.update_layout(height=max(320, 36 * len(topo)), margin=dict(t=10))
            st.plotly_chart(fig, width="stretch")
        with direita:
            st.metric("A maior unidade", pct(dist["participacao"].iloc[0]), help=str(dist["unidade_gestora"].iloc[0]))
            st.metric("As 5 maiores", pct(dist["participacao"].head(5).sum()))
            st.metric("As 10 maiores", pct(dist["participacao"].head(10).sum()))
            st.caption(f"Participação no valor pago, entre {milhar(len(dist))} unidades gestoras.")

        tabela = pd.DataFrame({"Unidade gestora": topo["unidade_gestora"], "Valor pago": topo["total"].map(brl),
                               "Participação": topo["participacao"].map(pct), "Acumulado": topo["acumulado"].map(pct),
                               "Registros": topo["registros"].map(milhar)})
        st.dataframe(tabela, hide_index=True, width="stretch")
        rodape(len(recorte))

    if "grupo_despesa" in recorte.columns:
        st.divider()
        st.write("**Distribuição por grupo de despesa**")
        g = analise.concentracao(recorte, "grupo_despesa")
        fig = px.bar(g.iloc[::-1], x="total", y="grupo_despesa", orientation="h",
                     labels={"total": "Valor pago (R$)", "grupo_despesa": ""}, color_discrete_sequence=[LARANJA])
        fig.update_layout(height=max(260, 40 * len(g)), margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(pd.DataFrame({"Grupo de despesa": g["grupo_despesa"], "Valor pago": g["total"].map(brl),
                                   "Participação": g["participacao"].map(pct), "Registros": g["registros"].map(milhar)}),
                     hide_index=True, width="stretch")
        rodape(len(recorte))

    if "unidade_gestora" in recorte.columns:
        st.divider()
        st.write("**De onde veio esse número**")
        escolhida = st.selectbox("Ver os registros de qual unidade gestora?", dist["unidade_gestora"])
        linhas = recorte[recorte["unidade_gestora"] == escolhida]
        st.write(md(f"{milhar(len(linhas))} registros somam {brl(linhas['valor_pago'].sum())} em valor pago. "
                    "Abaixo, os 200 de maior valor, com Documento e Id."))
        st.dataframe(analise.para_exibir(linhas.nlargest(200, "valor_pago")), hide_index=True, width="stretch",
                     column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")})

# ---------------------------------------------------------------- busca

with aba_busca:
    st.subheader("Buscar registros e conferir a origem")
    termo = st.text_input("Buscar por favorecido, unidade gestora, documento ou modalidade",
                          placeholder="Ex.: FUNDO FINANCEIRO")
    achados = analise.buscar(recorte, termo)
    if achados.empty:
        st.warning(f"Nenhum registro encontrado para \"{termo}\" com os filtros atuais.")
    else:
        st.write(md(f"**{milhar(len(achados))} registros**, somando {brl(achados['valor_pago'].sum())} em valor pago."))
        ordenados = achados.nlargest(500, "valor_pago")
        st.dataframe(analise.para_exibir(ordenados), hide_index=True, width="stretch",
                     column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")})
        st.caption("Mostrando até 500 registros, do maior valor pago para o menor. Id e Documento identificam "
                   "o registro no conjunto oficial; as duas últimas colunas dizem em que arquivo e linha ele está.")
        st.download_button("Baixar estes registros (CSV)",
                           analise.para_exibir(ordenados).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name="registros_transparencia_es.csv", mime="text/csv")
        rodape(len(achados))

# ---------------------------------------------------------------- qualidade

with aba_qualidade:
    st.subheader("O que foi encontrado nos dados e o que foi feito")
    c1, c2, c3 = st.columns(3)
    c1.metric("Linhas lidas", milhar(q["linhas_lidas"]))
    c2.metric("Registros usados", milhar(q["registros"]))
    c3.metric("Arquivos", len(q["arquivos"]))

    n = q["registros"]
    situacoes = [
        ("Datas inválidas", q["datas_invalidas"], "Registro mantido, sem data"),
        ("Linhas integralmente duplicadas", q["linhas_duplicadas"], "Removida a repetida"),
        ("ValorPago negativo", q["pago_negativo"], "Mantidos: possíveis estornos ou ajustes"),
        ("ValorPago igual a zero", q["pago_zero"], "Mantidos: outra etapa da despesa"),
    ]
    for m, k in q["valores_invalidos"].items():
        if k:
            situacoes.append((f"{MEDIDAS[m]}: valor que não é número", k, "Mantido, valor em branco"))
    st.dataframe(pd.DataFrame([{"Verificação": s, "Registros": milhar(k), "Do total": pct(k / n * 100, 2),
                                "Decisão": d} for s, k, d in situacoes]), hide_index=True, width="stretch")

    vazios = q["campos_totalmente_em_branco"]
    if vazios:
        st.warning("Campos que vêm 100% em branco neste conjunto: " + ", ".join(TEXTOS[c] for c in vazios)
                   + ". O painel não preenche esses campos por dedução; por isso não há análise por eles.")

    st.write("**Intervalo de confiança das proporções**")
    linhas = []
    for rotulo, k in [("ValorPago igual a zero", q["pago_zero"]), ("ValorPago negativo", q["pago_negativo"])]:
        ic = analise.ic_proporcao(k, n)
        linhas.append({"Proporção de registros": rotulo, "Registros": milhar(k), "Estimativa": pct(ic["p"], 2),
                       "IC 95% - de": pct(ic["ic_inf"], 2), "IC 95% - até": pct(ic["ic_sup"], 2)})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.caption(f"p ± 1,96 × √(p(1 − p)/n), com n = {milhar(n)}. O conjunto é um recorte sistemático e não uma amostra "
               "aleatória, então o intervalo vale como referência.")

    st.write("**Arquivos processados**")
    st.dataframe(df.groupby("arquivo_origem", observed=True).size().rename("registros").reset_index(), hide_index=True)
