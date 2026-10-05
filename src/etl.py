"""ETL: lê os ZIPs oficiais, trata e grava os dados que o painel usa.

Uso:
    python -m src.etl                       # lê data_raw/ e grava em data_processed/
    python -m src.etl --entrada PASTA --saida PASTA
    python -m src.etl --demo                # sem os ZIPs: gera dados SIMULADOS para demonstração

Saídas:
    registros.parquet   um registro por linha, já com valores e datas convertidos
    qualidade.json      o que foi lido, o que foi encontrado e o que foi feito
"""

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from .esquema import MEDIDAS, OBRIGATORIAS, TEXTOS, mapear_colunas

RAIZ = Path(__file__).resolve().parent.parent


class ErroDeDados(Exception):
    """Problema nos arquivos de entrada que o usuário consegue resolver."""


# ------------------------------------------------------------------ leitura

def _ler_csv(arquivo, nome):
    """CSV do portal: ';' como separador, UTF-8 com BOM, tudo lido como texto."""
    try:
        df = pd.read_csv(arquivo, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        raise ErroDeDados(f"{nome} está vazio.")
    except UnicodeDecodeError:
        raise ErroDeDados(f"{nome} não está em UTF-8. Use o arquivo original, sem abrir e salvar no Excel.")
    if df.shape[1] <= 1:
        raise ErroDeDados(f"{nome} veio com uma coluna só. O separador esperado é ponto e vírgula (;).")
    df.columns = [c.strip() for c in df.columns]
    df["arquivo_origem"] = nome
    df["linha_origem"] = range(2, len(df) + 2)  # a linha 1 é o cabeçalho
    return df


def ler_entrada(pasta):
    """Lê todos os .zip (e .csv soltos) da pasta e empilha."""
    pasta = Path(pasta)
    if not pasta.exists():
        raise ErroDeDados(f"A pasta {pasta} não existe.")
    partes = []
    for caminho in sorted(pasta.iterdir()):
        if caminho.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(caminho) as z:
                    internos = [n for n in z.namelist() if n.lower().endswith(".csv")]
                    if not internos:
                        raise ErroDeDados(f"{caminho.name} não tem nenhum CSV dentro.")
                    for interno in internos:
                        with z.open(interno) as f:
                            partes.append(_ler_csv(f, f"{caminho.name}/{Path(interno).name}"))
            except zipfile.BadZipFile:
                raise ErroDeDados(f"{caminho.name} está corrompido ou incompleto. Baixe de novo.")
        elif caminho.suffix.lower() == ".csv":
            partes.append(_ler_csv(caminho, caminho.name))
    if not partes:
        raise ErroDeDados(
            f"Nenhum arquivo ZIP encontrado em {pasta}. "
            "Coloque ali os arquivos de despesas fornecidos na disciplina e rode de novo."
        )
    return pd.concat(partes, ignore_index=True)


# ------------------------------------------------------------------ tratamento

def converter_valor(serie):
    """'1.234,56' -> 1234.56. Aceita 'R$', espaços e negativo entre parênteses."""
    s = serie.astype(str).str.strip()
    negativo = s.str.startswith("(") & s.str.endswith(")")
    s = s.str.replace(r"[R$\s()]", "", regex=True)
    ja_decimal = s.str.fullmatch(r"-?\d+\.\d{1,2}")  # "1234.56" já usa ponto decimal
    convertido = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    valores = pd.to_numeric(convertido.where(~ja_decimal, s), errors="coerce")
    return valores.where(~negativo, -valores)


def converter_data(serie):
    """Aceita 31/12/2025 e 2025-12-31 (com ou sem hora). O resto vira ausente."""
    s = serie.astype(str).str.strip().str.slice(0, 10)
    br = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return br.fillna(pd.to_datetime(s, format="%Y-%m-%d", errors="coerce"))


def tratar(bruto):
    """Devolve (registros tratados, relatório de qualidade)."""
    colunas = mapear_colunas(bruto.columns)
    faltando = [c for c in OBRIGATORIAS if c not in colunas]
    if faltando:
        originais = [c for c in bruto.columns if not c.endswith("_origem")]
        raise ErroDeDados(
            "O arquivo não tem as colunas obrigatórias (" + ", ".join(faltando) + "). "
            "Colunas encontradas: " + ", ".join(originais)
        )

    q = {"linhas_lidas": int(len(bruto)), "colunas": colunas}

    # duplicidade: linha idêntica em todas as colunas originais
    originais = [c for c in bruto.columns if c not in ("arquivo_origem", "linha_origem")]
    duplicada = bruto.duplicated(subset=originais, keep="first")
    q["linhas_duplicadas"] = int(duplicada.sum())
    # daqui em diante ficam só as colunas que o painel usa (o arquivo oficial tem dezenas de outras,
    # inclusive dados bancários, que não entram no painel)
    manter = list(colunas.values()) + ["arquivo_origem", "linha_origem"]
    df = bruto.loc[~duplicada, manter].rename(columns={orig: interno for interno, orig in colunas.items()}).copy()
    q["colunas_no_arquivo"] = len(originais)

    # valores: as quatro etapas ficam em colunas separadas
    medidas = [m for m in MEDIDAS if m in df.columns]
    q["valores_invalidos"] = {}
    for m in medidas:
        texto = df[m].astype(str).str.strip()
        df[m] = converter_valor(df[m])
        q["valores_invalidos"][m] = int((df[m].isna() & (texto != "")).sum())

    # datas
    texto = df["data"].astype(str).str.strip()
    df["data"] = converter_data(df["data"])
    q["datas_invalidas"] = int((df["data"].isna() & (texto != "")).sum())
    q["datas_em_branco"] = int((texto == "").sum())
    df["ano"] = df["data"].dt.year.astype("Int64")
    df["mes"] = df["data"].dt.month.astype("Int64")

    # textos: campo vazio continua vazio, não é preenchido por dedução
    textos = [t for t in TEXTOS if t in df.columns]
    q["em_branco"] = {}
    for t in textos:
        df[t] = df[t].astype(str).str.strip()
        q["em_branco"][t] = int((df[t] == "").sum())
    n = len(df)
    q["campos_totalmente_em_branco"] = [t for t in textos if n and q["em_branco"][t] == n]
    q["campos_ausentes_no_arquivo"] = [t for t in ("orgao", "funcao", "numero_processo") if t not in df.columns]

    # o que cada registro traz em valor pago
    q["pago_zero"] = int((df["valor_pago"] == 0).sum())
    q["pago_negativo"] = int((df["valor_pago"] < 0).sum())
    q["pago_positivo"] = int((df["valor_pago"] > 0).sum())
    q["pago_em_branco"] = int(df["valor_pago"].isna().sum())

    q["registros"] = int(n)
    q["periodo"] = [
        df["data"].min().strftime("%d/%m/%Y") if df["data"].notna().any() else None,
        df["data"].max().strftime("%d/%m/%Y") if df["data"].notna().any() else None,
    ]
    q["arquivos"] = sorted(df["arquivo_origem"].unique().tolist())
    q["medidas"] = medidas
    return df.reset_index(drop=True), q


# ------------------------------------------------------------------ gravação

def executar(entrada, saida, demo=False):
    if demo:
        from .demo import gerar_bruto
        bruto = gerar_bruto()
    else:
        bruto = ler_entrada(entrada)
    df, q = tratar(bruto)
    q["simulado"] = bool(demo)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    # compressão forte: o arquivo de 2025 inteiro fica com menos de 10 MB
    df.to_parquet(saida / "registros.parquet", index=False, compression="zstd", compression_level=19)
    q["gerado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    (saida / "qualidade.json").write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
    return df, q


def main(argumentos=None):
    p = argparse.ArgumentParser(description="Processa os ZIPs de despesas do ES para o painel.")
    p.add_argument("--entrada", default=RAIZ / "data_raw", help="pasta com os ZIPs (padrão: data_raw)")
    p.add_argument("--saida", default=RAIZ / "data_processed", help="pasta de saída (padrão: data_processed)")
    p.add_argument("--demo", action="store_true", help="gera dados SIMULADOS em vez de ler os ZIPs (só para demonstração)")
    args = p.parse_args(argumentos)
    try:
        _, q = executar(args.entrada, args.saida, demo=args.demo)
    except ErroDeDados as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    if q["simulado"]:
        print("ATENÇÃO: dados SIMULADOS, gerados só para demonstração. Não são os dados oficiais.")
    print(f"Arquivos lidos: {len(q['arquivos'])}")
    print(f"Registros: {q['registros']:,}".replace(",", "."))
    print(f"Período: {q['periodo'][0]} a {q['periodo'][1]}")
    print(f"Linhas duplicadas removidas: {q['linhas_duplicadas']}")
    print(f"Datas inválidas: {q['datas_invalidas']}")
    print(f"ValorPago zero: {q['pago_zero']:,} | negativo: {q['pago_negativo']:,} | positivo: {q['pago_positivo']:,}".replace(",", "."))
    if q["campos_totalmente_em_branco"]:
        print("Campos 100% em branco: " + ", ".join(q["campos_totalmente_em_branco"]))
    print(f"Gravado em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
