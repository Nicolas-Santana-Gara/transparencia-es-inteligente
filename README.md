# Transparência ES Inteligente

POC do CP2 (CPSI simulado) - Engenharia de Software, FIAP, 2º semestre de 2026.

Painel para explorar as despesas do Governo do Espírito Santo em 2025. Mostra quando os
pagamentos se concentram, quais unidades gestoras e grupos de despesa recebem mais, e
permite chegar de qualquer número até o Documento e o Id do registro que o formou.

**Painel no ar (modo demonstração):** https://transparencia-es-inteligente.vercel.app

**Empresa fictícia:** DataCidadã Tech · **Turma:** 2ESPK

| Integrante | RM |
|---|---|
| Gustavo Garcia Silva | RM562078 |
| Nicolas Gara | RM561461 |
| João Vitor Reis Silva | RM563115 |
| João Marcelo Diniz Vespa | RM564038 |
| Thiago Luza Alves | RM562219 |
| Matheus Antunes | RM561292 |

## O que funciona hoje

| ID | Funcionalidade | Onde ver |
|---|---|---|
| F01 | Carregar os resultados processados de 2025 | O painel abre sem reprocessar os ZIPs |
| F02 | Evolução mensal do valor pago, com o pico marcado | Aba "Quando se paga" |
| F03 | Ranking das 10 maiores unidades gestoras | Aba "Onde se concentra" |
| F04 | Distribuição por grupo de despesa | Aba "Onde se concentra" |
| F05 | Busca por favorecido, unidade, documento e modalidade | Aba "Busca e rastreabilidade" |
| F06 | Rastreabilidade por Documento e Id | Toda tabela de registros |
| F07 | Painel de qualidade dos dados | Aba "Qualidade dos dados" |
| F08 | Reprocessamento dos ZIPs por linha de comando | `python -m src.etl` |

Além disso: filtros por mês, unidade gestora e grupo de despesa, que valem para todas as
abas; intervalo de confiança de 95% do pagamento médio (mês de pico x demais meses) e das
proporções de registros com valor zero e negativo; download dos registros em CSV.

Ainda não existe: dados de 2024, API de consulta, banco de dados, alertas e login.

A proposta técnica e os slides estão em `docs/`.

## Como rodar

Precisa de Python 3.10 ou mais novo.

```bash
git clone <link do repositório>
cd transparencia-es-inteligente
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / Mac
pip install -r requirements.txt
```

Para abrir o painel:

```bash
streamlit run app.py
```

O painel abre em http://localhost:8501.

### Com os dados oficiais

1. Coloque os quatro arquivos ZIP de despesas de 2025 na pasta `data_raw/`.
2. Processe os dados (leva alguns segundos) e atualize a página do painel:

```bash
python -m src.etl
```

### Modo demonstração

O repositório já vem com um conjunto **simulado** em `data_processed/`, para o painel abrir
logo depois de clonar. São 40.000 registros inventados, com nomes claramente fictícios
("UNIDADE GESTORA DEMO 01"), e o painel mostra um aviso em todas as telas enquanto
estiver nesse modo. Esses números não são resultado de análise e não devem ser citados.
Rodar o ETL com os ZIPs oficiais substitui o conjunto simulado. Para gerá-lo de novo:

```bash
python -m src.etl --demo
```

## Dados

- **Fonte:** Governo do Estado do Espírito Santo (Portal da Transparência), com o
  Dicionário de Dados v1.0. Usamos os quatro arquivos ZIP de despesas de 2025 fornecidos
  na disciplina.
- **Formato:** CSV com separador ponto e vírgula, UTF-8 com BOM e vírgula decimal.
- **Campos usados:** Id, Documento, Data, UnidadeGestora, GrupoDespesa, Modalidade,
  Favorecido, ValorEmpenho, ValorLiquidado, ValorPago e ValorRap.

Os ZIPs não ficam no repositório. O material fornecido é um recorte sistemático: os
totais que aparecem no painel valem para esse conjunto e não para o Estado inteiro.

### O que o ETL faz

| Situação | Decisão |
|---|---|
| Linha idêntica a outra em todas as colunas | Remove a repetida e conta |
| Data impossível ou em formato desconhecido | Mantém o registro, sem data, e conta |
| Valor que não é número | Mantém o registro, com o valor em branco, e conta |
| ValorPago igual a zero | Mantém: é outra etapa da despesa |
| ValorPago negativo | Mantém e sinaliza como possível estorno ou ajuste |
| Campo de texto em branco (Órgão, Função, Processo) | Mantém em branco, sem preencher por dedução |

As quantidades de cada caso ficam em `data_processed/qualidade.json` e aparecem na aba
"Qualidade dos dados". Empenhado, liquidado, pago e restos a pagar ficam em colunas
separadas e nunca são somados entre si.

## Arquitetura

```
ZIPs oficiais ──> ETL (src/etl.py) ──> data_processed/ ──> painel (app.py) ──> usuário
 data_raw/         lê, converte,        registros.parquet    Streamlit + Plotly
                   audita e grava       qualidade.json
```

```
app.py              telas, filtros e gráficos
src/etl.py          leitura dos ZIPs, tratamento e relatório de qualidade
src/analise.py      contas: série mensal, concentração, intervalos de confiança, busca
src/esquema.py      nomes de coluna aceitos
src/demo.py         gerador do conjunto simulado do modo demonstração
tests/              testes automáticos
data_raw/           onde ficam os ZIPs (não versionados)
data_processed/     saída do ETL, lida pelo painel
```

O processamento fica separado da tela: o painel abre rápido porque só lê o que o ETL já
preparou, e qualquer pessoa com os ZIPs consegue refazer o processamento.

Se um arquivo vier com nome de coluna diferente, basta acrescentar o nome na lista
`APELIDOS` de `src/esquema.py`.

## Testes

```bash
pytest
```

São 31 testes: conversão de valores e datas, leitura do ZIP, contagem dos achados de
qualidade, totais e intervalos de confiança conferidos à mão, busca sem acento, máscara de
CPF, o modo demonstração e o painel inteiro em sete situações (dados normais, sem dados
processados, filtro sem resultado, busca sem resultado, troca de filtro e com e sem o
aviso de dados simulados). Os testes usam 12 linhas inventadas
no formato dos arquivos oficiais; não são dados reais.

## Situações de erro tratadas

- Sem ZIP em `data_raw/`: o ETL para e diz o que falta, sem gerar saída vazia.
- ZIP corrompido, CSV com separador errado ou sem as colunas obrigatórias: mensagem
  dizendo qual é o problema.
- Painel aberto antes de rodar o ETL: a tela explica os passos.
- Filtro ou busca sem resultado: aviso na tela.

## Como reproduzir um número do painel

1. Escolha os filtros na barra lateral.
2. Na aba "Onde se concentra", selecione a unidade gestora em "De onde veio esse número".
   A tabela lista os registros que foram somados, com Id e Documento.
3. As colunas "Arquivo de origem" e "Linha no arquivo" dizem onde cada registro está no
   CSV oficial.
4. Na aba "Busca e rastreabilidade", o botão de download exporta os registros para
   conferir fora do painel.

## Limitações conhecidas

- Só há dados de 2025; não dá para comparar com outros anos.
- Órgão, Função e Número do processo vêm em branco, então não há análise por esses campos.
- Os intervalos de confiança supõem amostra aleatória. O conjunto é um recorte
  sistemático, por isso eles valem como referência.
- Valores de despesa são muito assimétricos; a média por pagamento é puxada por poucos
  pagamentos grandes. A mediana aparece ao lado.
- Um pico ou um registro atípico não é prova de irregularidade.
- Os dados ficam em memória; com volumes muito maiores seria preciso um banco de dados.
- CPF de favorecido aparece mascarado; CNPJ, que é dado de empresa, é mantido.

## Uso de IA

Usamos um assistente de IA (Claude) como apoio na escrita do código, na revisão dos
textos e na montagem dos slides. A verificação foi feita com os testes automáticos, que
comparam as contas com valores calculados à mão.

A solução em si não usa IA para classificar despesas nem para apontar fraude.
