import pandas as pd
import pytest

from src import etl
from tests.conftest import gravar_zip


def test_valor_em_formato_brasileiro():
    v = etl.converter_valor(pd.Series(["1.234,56", "0,10", "R$ 2.000.000,00", "-250,00", "(100,00)", "1234.56"]))
    assert v.tolist() == [1234.56, 0.10, 2_000_000.00, -250.00, -100.00, 1234.56]


def test_valor_que_nao_e_numero_vira_ausente():
    assert etl.converter_valor(pd.Series(["abc", "", "  "])).isna().all()


def test_data_brasileira_e_iso():
    d = etl.converter_data(pd.Series(["15/01/2025", "2025-03-18", "2025-03-18 10:30:00"]))
    assert d.dt.strftime("%Y-%m-%d").tolist() == ["2025-01-15", "2025-03-18", "2025-03-18"]


def test_data_impossivel_vira_ausente():
    assert etl.converter_data(pd.Series(["31/02/2025", "ontem", ""])).isna().all()


def test_etl_le_o_zip_e_conta_o_que_encontrou(processado):
    saida, df, q = processado
    assert (saida / "registros.parquet").exists() and (saida / "qualidade.json").exists()
    assert q["linhas_lidas"] == 12
    assert q["linhas_duplicadas"] == 1
    assert q["registros"] == 11
    assert q["datas_invalidas"] == 1          # 31/02/2025
    assert q["pago_zero"] == 4
    assert q["pago_negativo"] == 1
    assert q["pago_positivo"] == 6
    assert q["campos_totalmente_em_branco"] == ["orgao", "funcao", "numero_processo"]
    assert q["periodo"] == ["15/01/2025", "21/12/2025"]


def test_as_etapas_ficam_em_colunas_separadas(processado):
    _, df, q = processado
    assert q["medidas"] == ["valor_empenho", "valor_liquidado", "valor_pago", "valor_rap"]
    # conta feita à mão: 10.000 + 1.500,50 + 500 - 250 + 30.000 + 6.000 + 999,99
    assert df["valor_pago"].sum() == pytest.approx(48750.49)
    assert df["valor_empenho"].sum() != df["valor_pago"].sum()


def test_cada_registro_guarda_de_onde_veio(processado):
    _, df, _ = processado
    linha = df[df["id"] == "2"].iloc[0]
    assert linha["arquivo_origem"] == "Despesas_2025_ficticio.zip/despesas.csv"
    assert linha["linha_origem"] == 4          # cabeçalho na 1, dois registros antes
    assert linha["documento"] == "2025NE0002"


def test_sem_zip_o_etl_para_com_mensagem_clara(tmp_path, capsys):
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    codigo = etl.main(["--entrada", str(vazia), "--saida", str(tmp_path / "saida")])
    assert codigo == 1
    assert "Nenhum arquivo ZIP encontrado" in capsys.readouterr().err
    assert not (tmp_path / "saida" / "registros.parquet").exists()


def test_zip_corrompido(tmp_path):
    (tmp_path / "quebrado.zip").write_bytes(b"isto nao e um zip")
    with pytest.raises(etl.ErroDeDados, match="corrompido"):
        etl.ler_entrada(tmp_path)


def test_arquivo_sem_coluna_obrigatoria(tmp_path):
    gravar_zip(tmp_path, linhas=["1;FUNDO X"], cabecalho="Id;UnidadeGestora")
    with pytest.raises(etl.ErroDeDados, match="colunas obrigatórias"):
        etl.tratar(etl.ler_entrada(tmp_path))


def test_separador_errado(tmp_path):
    gravar_zip(tmp_path, linhas=["1,15/01/2025,10"], cabecalho="Id,Data,ValorPago")
    with pytest.raises(etl.ErroDeDados, match="ponto e vírgula"):
        etl.ler_entrada(tmp_path)


def test_modo_demo_fica_marcado_como_simulado(tmp_path):
    df, q = etl.executar(None, tmp_path, demo=True)
    assert q["simulado"] is True
    assert len(df) == 40000
    assert df["unidade_gestora"].str.contains("DEMO").all()     # nomes claramente fictícios
    assert df["documento"].str.startswith("DEMO").all()


def test_dados_reais_nao_sao_marcados_como_simulados(processado):
    assert processado[2]["simulado"] is False
