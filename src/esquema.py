"""Nomes das colunas do conjunto oficial e como o projeto chama cada uma.

O cabeçalho dos CSVs é comparado sem acento, sem espaço e em minúsculas,
então "Unidade Gestora", "UnidadeGestora" e "UNIDADEGESTORA" dão no mesmo.
Se o arquivo vier com um nome diferente, basta acrescentar na lista certa.
"""

import re
import unicodedata

# as quatro etapas da despesa: ficam sempre separadas, nunca somadas entre si
MEDIDAS = {
    "valor_empenho": "Empenhado",
    "valor_liquidado": "Liquidado",
    "valor_pago": "Pago",
    "valor_rap": "Restos a pagar",
}

TEXTOS = {
    "unidade_gestora": "Unidade gestora",
    "grupo_despesa": "Grupo de despesa",
    "elemento_despesa": "Elemento de despesa",
    "acao": "Ação",
    "modalidade": "Modalidade",
    "tipo_licitacao": "Tipo de licitação",
    "favorecido": "Favorecido",
    "documento": "Documento",
    "id": "Id",
    "orgao": "Órgão",
    "funcao": "Função",
    "numero_processo": "Número do processo",
}

APELIDOS = {
    "data": ["data", "datadocumento", "datalancamento", "datamovimento", "datapagamento"],
    "valor_empenho": ["valorempenho", "valorempenhado", "empenhado"],
    "valor_liquidado": ["valorliquidado", "valorliquidacao", "liquidado"],
    "valor_pago": ["valorpago", "valorpagamento", "pago"],
    "valor_rap": ["valorrap", "rap", "valorrestosapagar", "restosapagar"],
    "unidade_gestora": ["unidadegestora", "nomeunidadegestora", "ug"],
    "grupo_despesa": ["grupodespesa", "grupodedespesa", "grupo"],
    "elemento_despesa": ["elementodespesa", "elementodedespesa", "elemento"],
    "acao": ["acao", "nomeacao"],
    "modalidade": ["modalidade", "modalidadeaplicacao"],
    "tipo_licitacao": ["tipolicitacao", "tipodelicitacao", "licitacao"],
    "favorecido": ["favorecido", "nomefavorecido", "credor"],
    "documento": ["documento", "numerodocumento", "nrdocumento"],
    "id": ["id", "idregistro"],
    "orgao": ["orgao", "nomeorgao"],
    "funcao": ["funcao", "nomefuncao"],
    "numero_processo": ["numeroprocesso", "processo", "nrprocesso"],
    "codigo_favorecido": ["cpfcnpjnis", "codigofavorecido", "cpfcnpj", "cnpjcpf", "cpfcnpjfavorecido", "documentofavorecido"],
}

OBRIGATORIAS = ["data", "valor_pago"]

# campos em que a busca textual procura
CAMPOS_BUSCA = ["favorecido", "unidade_gestora", "documento", "modalidade"]


def normalizar(texto):
    """'Unidade Gestora ' -> 'unidadegestora'"""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def sem_acento_minusculo(texto):
    """'São José' -> 'sao jose' (mantém os espaços, usado na busca)."""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()


def mapear_colunas(colunas):
    """Devolve {nome no projeto: nome no arquivo} para as colunas reconhecidas."""
    normalizadas = {normalizar(c): c for c in colunas}
    achadas = {}
    for interno, apelidos in APELIDOS.items():
        for apelido in apelidos:
            if apelido in normalizadas:
                achadas[interno] = normalizadas[apelido]
                break
    return achadas
