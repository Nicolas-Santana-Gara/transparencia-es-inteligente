"""Dados de teste: 12 linhas inventadas, no mesmo formato dos arquivos oficiais.

Não são dados reais. Têm erros colocados de propósito (linha duplicada, data
impossível, valor negativo, campos em branco) para os testes conferirem o tratamento.
"""

import zipfile

import pytest

from src import etl

CABECALHO = ("Id;Data;Orgao;Funcao;NumeroProcesso;UnidadeGestora;GrupoDespesa;Modalidade;Favorecido;"
             "CodigoFavorecido;Documento;ValorEmpenho;ValorLiquidado;ValorPago;ValorRap")
LINHAS = [
    "1;15/01/2025;;;;FUNDO DE TESTE A;PESSOAL;DIRETA;EMPRESA FICTÍCIA LTDA;12345678000199;2025NE0001;10.000,00;10.000,00;10.000,00;0,00",
    "1;15/01/2025;;;;FUNDO DE TESTE A;PESSOAL;DIRETA;EMPRESA FICTÍCIA LTDA;12345678000199;2025NE0001;10.000,00;10.000,00;10.000,00;0,00",
    "2;20/02/2025;;;;FUNDO DE TESTE A;PESSOAL;DIRETA;FULANO DE EXEMPLO;12345678901;2025NE0002;1.500,50;1.500,50;1.500,50;0,00",
    "3;31/02/2025;;;;SECRETARIA DE TESTE B;CORRENTES;DIRETA;JOSÉ DA SILVA ME;98765432000155;2025NE0003;2.000,00;2.000,00;0,00;0,00",
    "4;10/03/2025;;;;SECRETARIA DE TESTE B;CORRENTES;TRANSFERÊNCIA;OUTRA EMPRESA SA;98765432000155;2025NE0004;500,00;500,00;500,00;0,00",
    "5;12/03/2025;;;;SECRETARIA DE TESTE B;CORRENTES;DIRETA;OUTRA EMPRESA SA;98765432000155;2025NE0005;800,00;0,00;0,00;0,00",
    "6;05/06/2025;;;;SECRETARIA DE TESTE B;CORRENTES;DIRETA;OUTRA EMPRESA SA;98765432000155;2025NE0006;250,00;250,00;-250,00;0,00",
    "7;18/07/2025;;;;FUNDO DE TESTE A;PESSOAL;DIRETA;EMPRESA FICTÍCIA LTDA;12345678000199;2025NE0007;300,00;0,00;0,00;0,00",
    "8;02/12/2025;;;;FUNDO DE TESTE A;PESSOAL;DIRETA;EMPRESA FICTÍCIA LTDA;12345678000199;2025NE0008;30.000,00;30.000,00;30.000,00;0,00",
    "9;15/12/2025;;;;FUNDO DE TESTE A;PESSOAL;DIRETA;FULANO DE EXEMPLO;12345678901;2025NE0009;6.000,00;6.000,00;6.000,00;150,00",
    "10;20/12/2025;;;;SECRETARIA DE TESTE B;CORRENTES;DIRETA;OUTRA EMPRESA SA;98765432000155;2025NE0010;999,99;999,99;999,99;0,00",
    "11;21/12/2025;;;;SECRETARIA DE TESTE B;CORRENTES;DIRETA;OUTRA EMPRESA SA;98765432000155;2025NE0011;70,00;0,00;0,00;0,00",
]


def gravar_zip(pasta, nome="Despesas_2025_ficticio.zip", linhas=LINHAS, cabecalho=CABECALHO):
    pasta.mkdir(parents=True, exist_ok=True)
    conteudo = ("﻿" + "\n".join([cabecalho] + linhas) + "\n").encode("utf-8")
    with zipfile.ZipFile(pasta / nome, "w") as z:
        z.writestr("despesas.csv", conteudo)
    return pasta


@pytest.fixture
def entrada(tmp_path):
    return gravar_zip(tmp_path / "data_raw")


@pytest.fixture
def processado(entrada, tmp_path):
    saida = tmp_path / "data_processed"
    df, q = etl.executar(entrada, saida)
    return saida, df, q
