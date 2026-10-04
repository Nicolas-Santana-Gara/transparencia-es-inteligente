"""Testa o painel inteiro, como o usuário usa, sem abrir navegador."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).parent.parent


def abrir(pasta, monkeypatch):
    monkeypatch.setenv("DADOS_PROCESSADOS", str(pasta))
    return AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()


def test_painel_abre_com_dados_processados(processado, monkeypatch):
    app = abrir(processado[0], monkeypatch)
    assert not app.exception
    assert len(app.tabs) == 5
    assert app.metric[0].label == "Valor pago (R$)"


def test_sem_dados_processados_o_painel_explica_o_que_fazer(tmp_path, monkeypatch):
    app = abrir(tmp_path, monkeypatch)
    assert not app.exception
    assert "python -m src.etl" in app.error[0].value
    assert len(app.tabs) == 0


def test_filtro_sem_resultado_avisa_o_usuario(processado, monkeypatch):
    app = abrir(processado[0], monkeypatch)
    app.slider[0].set_value((8, 9)).run()
    assert not app.exception
    assert "Nenhum registro para os filtros" in app.warning[0].value


def test_busca_que_nao_acha_nada_avisa(processado, monkeypatch):
    app = abrir(processado[0], monkeypatch)
    app.text_input[0].set_value("termo que não existe").run()
    assert not app.exception
    assert any("Nenhum registro encontrado" in w.value for w in app.warning)


def test_filtrar_por_unidade_muda_o_total(processado, monkeypatch):
    app = abrir(processado[0], monkeypatch)
    antes = app.metric[1].value
    app.multiselect[0].set_value(["FUNDO DE TESTE A"]).run()
    assert not app.exception
    assert app.metric[1].value != antes


def test_modo_demo_avisa_em_destaque_que_os_dados_sao_simulados(tmp_path, monkeypatch):
    from src import etl
    etl.executar(None, tmp_path, demo=True)
    app = abrir(tmp_path, monkeypatch)
    assert not app.exception
    assert "SIMULADOS" in app.warning[0].value
    assert any("dados simulados" in c.value for c in app.caption)


def test_dados_reais_nao_mostram_aviso_de_simulacao(processado, monkeypatch):
    app = abrir(processado[0], monkeypatch)
    assert not any("SIMULADOS" in w.value for w in app.warning)
