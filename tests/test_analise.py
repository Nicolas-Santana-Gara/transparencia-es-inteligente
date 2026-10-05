import math

import pytest

from src import analise
from src.esquema import mapear_colunas


def test_colunas_reconhecidas_com_acento_e_espaco():
    achadas = mapear_colunas(["Unidade Gestora", "VALORPAGO", "Ação", "Tipo Licitação", "Qualquer"])
    assert achadas == {"unidade_gestora": "Unidade Gestora", "valor_pago": "VALORPAGO",
                       "acao": "Ação", "tipo_licitacao": "Tipo Licitação"}


def test_serie_mensal_e_pico(processado):
    _, df, _ = processado
    mensal = analise.serie_mensal(df)
    pico = analise.resumo_do_pico(mensal)
    assert pico["mes_maior"] == 12
    assert pico["total_maior"] == pytest.approx(36999.99)   # 30.000 + 6.000 + 999,99 + 0
    assert pico["mes_menor"] == 6                           # só o estorno de -250
    assert mensal["total"].sum() == pytest.approx(48750.49)


def test_ic_da_media_conferido_na_mao():
    # n=5, média=30, s=15,811; t(0,975; 4 gl)=2,776 -> margem = 2,776 × 15,811 / √5 = 19,63
    ic = analise.ic_media([10, 20, 30, 40, 50])
    assert ic["media"] == pytest.approx(30)
    assert ic["ic_inf"] == pytest.approx(10.37, abs=0.01)
    assert ic["ic_sup"] == pytest.approx(49.63, abs=0.01)


def test_ic_com_um_valor_so_nao_inventa_intervalo():
    ic = analise.ic_media([100])
    assert ic["n"] == 1 and math.isnan(ic["ic_inf"])


def test_ic_da_proporcao_conferido_na_mao():
    # 413.609 de 586.208 -> 70,56%; margem = 1,96 × √(0,7056 × 0,2944 / 586.208) = 0,117 p.p.
    ic = analise.ic_proporcao(413609, 586208)
    assert ic["p"] == pytest.approx(70.557, abs=0.001)
    assert ic["ic_inf"] == pytest.approx(70.44, abs=0.005)
    assert ic["ic_sup"] == pytest.approx(70.67, abs=0.005)


def test_pagamento_medio_so_conta_valor_positivo(processado):
    _, df, _ = processado
    comp = analise.pagamento_medio_pico_x_resto(df, 12)
    assert comp["pico"]["n"] == 3      # a linha de dezembro com pago = 0 não entra
    assert comp["resto"]["n"] == 3     # zeros e o estorno ficam de fora


def test_concentracao_soma_cem_por_cento(processado):
    _, df, _ = processado
    dist = analise.concentracao(df, "unidade_gestora")
    assert dist["participacao"].sum() == pytest.approx(100)
    assert dist.iloc[0]["unidade_gestora"] == "FUNDO DE TESTE A"
    assert dist.iloc[-1]["acumulado"] == pytest.approx(100)


def test_filtro_por_mes_e_unidade(processado):
    _, df, _ = processado
    f = analise.filtrar(df, meses=(12, 12), unidades=["FUNDO DE TESTE A"])
    assert len(f) == 2 and set(f["mes"]) == {12}


def test_filtro_sem_resultado(processado):
    _, df, _ = processado
    assert analise.filtrar(df, meses=(8, 9)).empty


def test_busca_ignora_acento_e_maiuscula(processado):
    _, df, _ = processado
    assert len(analise.buscar(df, "jose da silva")) == 1
    assert len(analise.buscar(df, "FICTICIA")) == 3
    assert len(analise.buscar(df, "2025NE0009")) == 1          # por documento
    assert len(analise.buscar(df, "transferencia")) == 1       # por modalidade
    assert analise.buscar(df, "não existe").empty


def test_tabela_mantem_id_e_documento_e_mascara_cpf(processado):
    _, df, _ = processado
    tabela = analise.para_exibir(df)
    assert list(tabela.columns[:2]) == ["Id", "Documento"]
    assert "12345678901" not in tabela["CPF/CNPJ"].tolist()
    assert "***.456.789-**" in tabela["CPF/CNPJ"].tolist()
    assert "12345678000199" in tabela["CPF/CNPJ"].tolist()     # CNPJ é mantido


def test_busca_funciona_com_texto_lido_como_categoria(processado):
    # o painel lê os textos repetidos como categoria para gastar menos memória
    _, df, _ = processado
    categorico = df.astype({"favorecido": "category", "unidade_gestora": "category", "modalidade": "category"})
    assert len(analise.buscar(categorico, "ficticia")) == 3
    assert analise.concentracao(categorico[categorico["unidade_gestora"] == "FUNDO DE TESTE A"], "unidade_gestora").shape[0] == 1
