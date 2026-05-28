import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import os

from config_reader import obter_headers_api, ler_token_config, ler_config
from funcionarios import (
    formatar_cpf_11_digitos,
    formatar_matricula_simples,
    ler_campo_chave_config,
    gerar_token_target,
)

# CPFs (11 digitos) ja incluidos no demissoes_api.csv neste ambiente; remova linha(s) manualmente para reprocessar.
ARQUIVO_HISTORICO_CPF_DEMISSOES = "demissoes_cpf_processados.txt"

# Ordem fixa ao gerar CSV vazio (somente cabecalho).
COLUNAS_CSV_DEMISSOES = [
    "campo_chave",
    "cpf",
    "matricula",
    "nome",
    "DATA_DEMISSAO",
    "obs",
    "data_aviso",
    "data_ultimo_dia_trabalhado",
    "data_acerto",
    "motivo",
    "local_exame",
    "opcao_empregado",
    "tipo_aviso",
    "devolveu_cracha",
    "dias_indenizados",
    "data_exame",
]


def carregar_cpfs_demissoes_processados():
    """CPFs ja exportados/registrados; comparacao sempre com 11 digitos."""
    if not os.path.exists(ARQUIVO_HISTORICO_CPF_DEMISSOES):
        return set()
    cpfs = set()
    try:
        with open(ARQUIVO_HISTORICO_CPF_DEMISSOES, "r", encoding="utf-8") as f:
            for linha in f:
                norm = formatar_cpf_11_digitos(linha.strip())
                if len(norm) == 11:
                    cpfs.add(norm)
    except OSError as e:
        print(f"AVISO: nao foi possivel ler {ARQUIVO_HISTORICO_CPF_DEMISSOES}: {e}")
    return cpfs


def registrar_cpfs_demissoes_processados(cpfs_novos):
    """
    Unifica novos CPFs no arquivo texto (uma linha por CPF, 11 digitos).
    Chamado apos gravar demissoes_api.csv com sucesso apenas para linhas efetivamente exportadas.
    """
    novos_limpos = []
    for c in cpfs_novos:
        norm = formatar_cpf_11_digitos(str(c))
        if len(norm) == 11:
            novos_limpos.append(norm)
    if not novos_limpos:
        return
    atual = carregar_cpfs_demissoes_processados()
    atual.update(novos_limpos)
    try:
        with open(ARQUIVO_HISTORICO_CPF_DEMISSOES, "w", encoding="utf-8") as f:
            for c in sorted(atual):
                f.write(c + "\n")
        print(
            f"\nHistorico de CPFs de demissao atualizado (+{len(novos_limpos)} CPF(s)): "
            f"{ARQUIVO_HISTORICO_CPF_DEMISSOES} ({len(atual)} CPF(s) no total)."
        )
    except OSError as e:
        print(f"ERRO ao gravar historico de CPFs: {e}")


def ler_pag_demissao_rest():
    """
    Le [APITARGET].pag_demissao (opcional). URL, integracao e token vêm da mesma secao via gerar_token_target().
    Padrao: funcionario_demissao.
    """
    cfg = ler_config()
    if not cfg or 'APITARGET' not in cfg:
        return 'funcionario_demissao'
    pag = (cfg['APITARGET'].get('pag_demissao') or '').strip().strip('"').strip("'")
    return pag if pag else 'funcionario_demissao'


def enviar_csv_demissoes_rest(nome_arquivo_csv='demissoes_api.csv'):
    """
    POST na mesma [APITARGET] do .config que funcionarios/afastamentos (url, integracao, token_base).
    Apenas o campo "pag" é específico da demissão (funcionario_demissao por padrao).
    Multipart: pag, cmd=importar_cad, separador=; + arquivo CSV.
    """
    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} nao encontrado!")
        return False

    print(f"Arquivo {nome_arquivo_csv} encontrado")

    config_target, token_final = gerar_token_target()
    if not config_target or not token_final:
        print("Falha ao gerar token para API de destino")
        return False

    pag = ler_pag_demissao_rest()
    usuario = config_target['integracao']

    headers = {
        'user': usuario,
        'token': token_final,
    }

    data = {
        'pag': pag,
        'cmd': 'importar_cad',
        'separador': ';',
    }

    try:
        print(f"Enviando POST (demissoes) — [APITARGET] url/token/user iguais aos demais modulos REST")
        print(f"URL: {config_target['url']}")
        print(f"Usuario: {usuario}")
        print(f"pag: {pag}")
        print(f"Token: {token_final[:32]}...")

        with open(nome_arquivo_csv, 'rb') as arquivo:
            files = {'arquivo': (nome_arquivo_csv, arquivo, 'text/csv')}
            response = requests.post(
                config_target['url'],
                data=data,
                files=files,
                headers=headers,
                timeout=90,
            )

        print(f"Status da resposta: {response.status_code}")

        if response.status_code == 200:
            try:
                resultado = response.json()

                if resultado.get('success') is False:
                    print('API retornou erro:')
                    print(json.dumps(resultado, indent=2, ensure_ascii=False))
                    return False

                print('POST de demissoes realizado com sucesso!')
                print(json.dumps(resultado, indent=2, ensure_ascii=False))

                cadastrados = resultado.get('ok', 0)
                if cadastrados and cadastrados > 0:
                    print(f"{cadastrados} registro(s) processado(s) conforme retorno da API.")

                return True

            except json.JSONDecodeError:
                print(f"Resposta nao e JSON valido: {response.text[:500]}...")
                return False

        print(f"ERRO no POST - Status: {response.status_code}")
        print(f"Resposta: {response.text[:500]}...")
        return False

    except requests.exceptions.RequestException as e:
        print(f"ERRO na requisicao: {e}")
        return False


def consultar_funcionarios_demitidos():
    """
    Coleta funcionarios DEMITIDOS da API Alterdata (endpoint correto encontrado!)
    """
    print("INICIANDO COLETA DE FUNCIONARIOS DEMITIDOS...")
    
    # Obter headers do arquivo .config
    headers = obter_headers_api()
    if not headers:
        print("Nao foi possivel obter o token do arquivo .config")
        return [], None
    
    # Configuracoes da API - ENDPOINT CORRETO ENCONTRADO!
    base_url = "https://dp.pack.alterdata.com.br/api/v1/funcionarios"
    
    # FILTRO PARA FUNCIONARIOS DEMITIDOS (confirmado pelo diagnostico)
    params = {
        "filter[status]": "demitido",  # FUNCIONARIOS DEMITIDOS
        "fields": "codigo,nome,status,demissao,cpf,identidade,email,telefone",
        "sort": "codigo",
        "page[limit]": "100"
    }
    
    todos_demitidos = []
    url_atual = base_url
    pagina = 1
    
    # Coletar todos os funcionarios demitidos com paginacao
    while url_atual:
        try:
            print(f"  Coletando pagina {pagina}... ", end="")
            
            if pagina == 1:
                response = requests.get(url_atual, headers=headers, params=params)
            else:
                response = requests.get(url_atual, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                demitidos_pagina = data.get('data', [])
                todos_demitidos.extend(demitidos_pagina)
                
                print(f"{len(demitidos_pagina)} funcionarios demitidos")
                
                # Verificar se ha proxima pagina
                url_atual = data.get('links', {}).get('next')
                pagina += 1
                
                # Pausa para nao sobrecarregar a API
                time.sleep(0.5)
            else:
                print(f"Erro {response.status_code}: {response.text}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Erro na conexao: {e}")
            break
    
    print(f"\nTotal coletado: {len(todos_demitidos)} funcionarios demitidos")
    return todos_demitidos, headers

def formatar_data_brasileira(data_iso):
    """
    Converte data ISO para formato brasileiro DD/MM/AAAA
    """
    if not data_iso:
        return ""
    
    try:
        # Remove timezone e converte
        data_str = data_iso.replace('Z', '').split('T')[0]
        data_obj = datetime.strptime(data_str, '%Y-%m-%d')
        return data_obj.strftime('%d/%m/%Y')
    except:
        return ""

def calcular_datas_demissao(data_demissao_iso):
    """
    Calcula datas estimadas baseadas na data real de demissao da API
    """
    if not data_demissao_iso:
        # Se nao tem data, usar data atual como base
        hoje = datetime.now()
        data_demissao = hoje.strftime('%d/%m/%Y')
        data_aviso = (hoje - timedelta(days=30)).strftime('%d/%m/%Y')
        data_ultimo_dia = hoje.strftime('%d/%m/%Y')
        data_acerto = (hoje + timedelta(days=10)).strftime('%d/%m/%Y')
        return data_demissao, data_aviso, data_ultimo_dia, data_acerto
    
    try:
        # Converter data ISO para datetime
        data_obj = datetime.fromisoformat(data_demissao_iso.replace('Z', '+00:00'))
        
        # Usar a data real de demissao
        data_demissao = data_obj.strftime('%d/%m/%Y')
        data_aviso = (data_obj - timedelta(days=30)).strftime('%d/%m/%Y')  # 30 dias antes
        data_ultimo_dia = data_obj.strftime('%d/%m/%Y')  # Mesmo dia da demissao
        data_acerto = (data_obj + timedelta(days=10)).strftime('%d/%m/%Y')  # 10 dias apos
        
        return data_demissao, data_aviso, data_ultimo_dia, data_acerto
    except:
        # Fallback se der erro na conversao
        hoje = datetime.now()
        data_demissao = hoje.strftime('%d/%m/%Y')
        data_aviso = (hoje - timedelta(days=30)).strftime('%d/%m/%Y')
        data_ultimo_dia = hoje.strftime('%d/%m/%Y')
        data_acerto = (hoje + timedelta(days=10)).strftime('%d/%m/%Y')
        return data_demissao, data_aviso, data_ultimo_dia, data_acerto

def formatar_cpf_com_mascara_csv(cpf):
    """
    CPF para o CSV de demissoes no padrao brasileiro: XXX.XXX.XXX-XX
    Ex.: 03892225265 -> 038.922.252-65
    """
    digitos = formatar_cpf_11_digitos(cpf)
    if len(digitos) != 11:
        return ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"

def mapear_demissao_para_csv(funcionario_demitido, campo_chave):
    """
    Matricula no CSV: attributes.codigo da API Alterdata (6 digitos), como funcionarios.py.
    nome e cpf vindos de attributes na consulta de demitidos.
    Coluna cpf no CSV com pontos e traco (XXX.XXX.XXX-XX).
    """
    attributes = funcionario_demitido.get('attributes', {})
    funcionario_id = funcionario_demitido.get('id', '')
    
    codigo_funcionario = attributes.get('codigo', '')
    if not codigo_funcionario:
        codigo_funcionario = str(funcionario_id)
    
    data_demissao_iso = attributes.get('demissao', '')
    
    campo_chave_normalizado = (campo_chave or "").strip().lower()
    cpf_fmt = formatar_cpf_11_digitos(attributes.get('cpf', ''))
    cpf_para_csv = formatar_cpf_com_mascara_csv(attributes.get('cpf', ''))
    matricula_simples = formatar_matricula_simples(codigo_funcionario)
    print(
        f"\nMapeando funcionario {codigo_funcionario} — matricula (codigo API): {matricula_simples} | "
        f"campo_chave .config: {campo_chave_normalizado}"
    )
    if campo_chave_normalizado == 'cpf' and not cpf_fmt:
        print("    AVISO: CPF vazio na API — verificar cadastro no destino se a chave for CPF.")
    
    data_demissao, data_aviso, data_ultimo_dia, data_acerto = calcular_datas_demissao(data_demissao_iso)
    
    demissao_csv = {
        'campo_chave': campo_chave_normalizado or campo_chave,
        'cpf': cpf_para_csv,
        'matricula': matricula_simples,
        'nome': (attributes.get('nome') or '').strip(),
        'DATA_DEMISSAO': data_demissao,
        'obs': 'Demissao',
        'data_aviso': '',
        'data_ultimo_dia_trabalhado': data_ultimo_dia,
        'data_acerto': '',
        'motivo': 'Demissao',
        'local_exame': '',
        'opcao_empregado': '',
        'tipo_aviso': '',
        'devolveu_cracha': 'Sim',
        'dias_indenizados': 0,
        'data_exame': '',
    }
    
    return demissao_csv

def filtrar_demissoes_recentes(funcionarios_demitidos, data_limite='2025-01-01'):
    """
    Filtra demissoes a partir de uma data especifica
    ATUALIZADO: Agora trabalha com funcionarios demitidos diretamente
    """
    demissoes_filtradas = []
    data_limite_obj = datetime.strptime(data_limite, '%Y-%m-%d')
    
    for funcionario in funcionarios_demitidos:
        attributes = funcionario.get('attributes', {})
        data_demissao = attributes.get('demissao', '')
        
        if data_demissao:
            try:
                data_demissao_obj = datetime.fromisoformat(data_demissao.replace('Z', '+00:00'))
                data_demissao_sem_tz = data_demissao_obj.replace(tzinfo=None)
                
                if data_demissao_sem_tz >= data_limite_obj:
                    demissoes_filtradas.append(funcionario)
            except:
                # Se der erro na conversao, incluir mesmo assim
                demissoes_filtradas.append(funcionario)
    
    return demissoes_filtradas


# =================== FUNCAO PRINCIPAL ===================

def gerar_csv_demissoes():
    """
    Gera demissoes_api.csv apenas com demissoes cujo CPF ainda nao consta em
    demissoes_cpf_processados.txt (caso tipico aprendiz demitido e readmitido).

    Sem CPF valido na API: nao entra na deduplicacao por historico — linha vai para o CSV.
    Ao gravar CSV com sucesso: CPFs exportados novos passam para o arquivo de historico.
    Para reintegrar uma pessoa ao CSV, apague manualmente o CPF do arquivo de historico.

    Retorno None = falha; lista (possivelmente vazia) = sucesso gerando CSV (inclusive so cabecalho).
    """
    print("=" * 80)
    print("         GERACAO DE CSV DE DEMISSOES - matricula = codigo Alterdata (6 digitos)")
    print("=" * 80)

    nome_arquivo = "demissoes_api.csv"
    
    # Verificar se token esta disponivel
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    # Coletar funcionarios demitidos da API (ENDPOINT CORRETO)
    funcionarios_demitidos, _ = consultar_funcionarios_demitidos()
    
    if not funcionarios_demitidos:
        print("Nenhum funcionario demitido foi coletado da API")
        return None
    
    cpfs_ja_exportados = carregar_cpfs_demissoes_processados()
    print(
        f"\nHistorico de CPF ja processados ({ARQUIVO_HISTORICO_CPF_DEMISSOES}): "
        f"{len(cpfs_ja_exportados)} CPF(s). Para reprocessar, remova linha(s) desse arquivo."
    )
    
    # Filtrar demissoes recentes (desde janeiro de 2025)
    demissoes_filtradas = filtrar_demissoes_recentes(funcionarios_demitidos, '2025-01-01')
    print(f"Demissoes filtradas desde 01/01/2025: {len(demissoes_filtradas)}")
    
    if not demissoes_filtradas:
        print("Nenhuma demissao recente encontrada")
        print("Tentando processar todas as demissoes disponiveis...")
        demissoes_filtradas = funcionarios_demitidos
    
    print(f"\nConvertendo {len(demissoes_filtradas)} demissoes (depois sera aplicado filtro de historico)...")
    campo_chave_cfg = ler_campo_chave_config()
    print(f"   Matricula no CSV: codigo Alterdata (6 digitos) | campo_chave .config: {campo_chave_cfg}")
    
    # Converter para formato CSV
    demissoes_csv = []
    cpfs_para_registrar = []
    erros = []
    funcionarios_processados = set()
    ignorados_historico = 0
    sem_cpf_valido_para_historico = 0
    
    for i, funcionario_demitido in enumerate(demissoes_filtradas, 1):
        try:
            attrs = funcionario_demitido.get("attributes", {})
            cpf_digitos = formatar_cpf_11_digitos(attrs.get("cpf", ""))

            if len(cpf_digitos) == 11:
                if cpf_digitos in cpfs_ja_exportados:
                    ignorados_historico += 1
                    continue
            else:
                sem_cpf_valido_para_historico += 1

            demissao_csv = mapear_demissao_para_csv(funcionario_demitido, campo_chave_cfg)

            # Filtrar apenas registros com matricula valida
            if demissao_csv['matricula']:
                demissoes_csv.append(demissao_csv)
                funcionarios_processados.add(demissao_csv['matricula'])
                if len(cpf_digitos) == 11:
                    cpfs_para_registrar.append(cpf_digitos)
            
            if i % 10 == 0:
                print(f"  Processadas {i}/{len(demissoes_filtradas)}... (CSV novos ate agora: {len(demissoes_csv)})")
                
        except Exception as e:
            erros.append({'id': funcionario_demitido.get('id', 'N/A'), 'erro': str(e)})
            print(f"  Erro ao processar funcionario {funcionario_demitido.get('id', 'N/A')}: {e}")
    
    print(f"\nFiltro de historico: {ignorados_historico} ignorado(s) (CPF ja em {ARQUIVO_HISTORICO_CPF_DEMISSOES}).")
    if sem_cpf_valido_para_historico:
        print(f"   Registro(s) sem CPF de 11 digitos na API: {sem_cpf_valido_para_historico} (nao deduplicados pelo historico).")

    # Criar DataFrame (possivelmente vazio, so cabecalho)
    print(f"\nCriando DataFrame com {len(demissoes_csv)} rescisoes novas...")
    print(f"   Codigos/matriculas unicas no CSV: {len(funcionarios_processados)}")
    
    df = pd.DataFrame(demissoes_csv, columns=COLUNAS_CSV_DEMISSOES) if demissoes_csv else pd.DataFrame(columns=COLUNAS_CSV_DEMISSOES)

    try:
        df.to_csv(nome_arquivo, index=False, encoding='utf-8-sig', sep=';')
        print(f"CSV gerado com sucesso: {nome_arquivo}")
        
        # Estatisticas
        print(f"\nESTATISTICAS:")
        print(f"  Total de demissoes: {len(demissoes_csv)}")
        print(f"  Funcionarios unicos: {len(funcionarios_processados)}")
        print(f"  Erros de conversao: {len(erros)}")
        print(f"  Colunas no CSV: {len(df.columns)}")
        print(f"  Arquivo gerado: {nome_arquivo}")
        
        # Aviso sobre datas estimadas
        print(f"\nATENCAO:")
        print(f"  As datas foram ESTIMADAS baseadas na data de solicitacao")
        print(f"  Recomenda-se verificar e ajustar as datas conforme necessario")
        print(f"  Dados baseados apenas nas notificacoes de rescisao da API")
        
        # Mostrar preview dos dados
        print(f"\nPREVIEW DOS DADOS (primeiras 3 linhas):")
        print(df.head(3).to_string())
        
        # Salvar relatorio de erros se houver
        if erros:
            arquivo_erros = "erros_demissoes.json"
            with open(arquivo_erros, 'w', encoding='utf-8') as f:
                json.dump(erros, f, indent=2, ensure_ascii=False)
            print(f"\nRelatorio de erros salvo em: {arquivo_erros}")

        if cpfs_para_registrar:
            cpfs_para_registrar = list(dict.fromkeys(cpfs_para_registrar))
            registrar_cpfs_demissoes_processados(cpfs_para_registrar)
        elif ignorados_historico and len(demissoes_csv) == 0:
            print(f"\nNenhuma linha nova; historico intacto.")

        return demissoes_csv

    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None

def validar_dados_demissoes_csv(nome_arquivo):
    """
    Valida os dados do CSV de demissoes gerado
    """
    if not nome_arquivo:
        return
    
    try:
        print(f"\nVALIDANDO DADOS DO CSV: {nome_arquivo}")
        
        # Ler o CSV gerado
        df = pd.read_csv(nome_arquivo, sep=';', encoding='utf-8-sig')
        
        print(f"  Total de registros: {len(df)}")
        print(f"  Total de colunas: {len(df.columns)}")
        
        # Verificar campos obrigatorios
        campos_obrigatorios = ['matricula', 'DATA_DEMISSAO']
        
        for campo in campos_obrigatorios:
            if campo in df.columns:
                vazios = df[campo].isna().sum() + (df[campo] == '').sum()
                if vazios > 0:
                    print(f"  Campo '{campo}': {vazios} registros vazios")
                else:
                    print(f"  Campo '{campo}': todos preenchidos")
            else:
                print(f"  Campo obrigatorio '{campo}' nao encontrado")
        
        # Verificar consistencia de datas
        campos_data = ['DATA_DEMISSAO', 'data_aviso', 'data_ultimo_dia_trabalhado', 'data_acerto']
        for campo in campos_data:
            if campo in df.columns:
                registros_com_data = (df[campo] != '').sum()
                print(f"  {campo}: {registros_com_data} registros com data")
        
        if 'nome' in df.columns:
            nome_str = df['nome'].fillna('').astype(str).str.strip()
            vazios_nome = (nome_str == '').sum()
            if vazios_nome > 0:
                print(f"  Campo 'nome': {vazios_nome} registros vazios")
            else:
                print(f"  Campo 'nome': todos preenchidos")
        else:
            print(f"  Campo 'nome' nao encontrado no CSV")

        # Verificar funcionarios unicos
        if 'matricula' in df.columns:
            funcionarios_unicos = df['matricula'].nunique()
            print(f"  Funcionarios unicos demitidos: {funcionarios_unicos}")
        
        print(f"  Validacao concluida")
        
    except Exception as e:
        print(f"  Erro na validacao: {e}")

def processar_integracao_completa():
    """
    API Alterdata -> CSV demissoes_api.csv -> POST REST IFPonto (importar_cad).
    """
    print("=" * 80)
    print("    INTEGRACAO DE DEMISSOES - Alterdata -> CSV -> API REST (IFPonto)")
    print("=" * 80)
    
    # Etapa 1: Gerar CSV das demissoes
    print("\nETAPA 1: Coletando demissoes da API eContador...")
    demissoes_csv = gerar_csv_demissoes()

    if demissoes_csv is None:
        print("Falha na geracao dos dados. Processo interrompido.")
        return False

    # Etapa 2: Validar dados do CSV
    print("\nETAPA 2: Validando dados...")
    validar_dados_demissoes_csv("demissoes_api.csv")

    if len(demissoes_csv) == 0:
        print("\nNenhuma demissao nova no CSV; etapa de envio REST ignorada.")
        print(
            f"Todas ja constam em {ARQUIVO_HISTORICO_CPF_DEMISSOES} ou nao ha linhas validas. "
            "Remova CPF(s) do historico para gerar de novo."
        )
        return True

    # Etapa 3: Enviar via REST (mesmo padrao de funcionarios)
    print("\nETAPA 3: Enviando CSV de demissoes via API REST...")
    pag_atual = ler_pag_demissao_rest()
    print(f"   Parametro pag (configuravel [APITARGET] pag_demissao): {pag_atual}")
    sucesso_api = enviar_csv_demissoes_rest('demissoes_api.csv')
    
    if sucesso_api:
        print("\nINTEGRACAO COMPLETA FINALIZADA COM SUCESSO!")
        print(f"Demissoes coletadas da API Alterdata")
        print(f"CSV gerado: demissoes_api.csv")
        print(f"Arquivo enviado via REST (pag={pag_atual})")
        
        # Mostrar todos os registros gerados
        try:
            df = pd.read_csv('demissoes_api.csv', sep=';')
            print(f"\nREGISTROS GERADOS ({len(df)} total):")
            for i, row in df.iterrows():
                print(f"   {row['matricula']} | {row.get('nome', '')} | {row['DATA_DEMISSAO']}")
                
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
            
        return True
    else:
        print("\nFALHA NA INTEGRACAO!")
        print(f"CSV gerado: demissoes_api.csv")
        print(f"Falha no envio via API REST — confira pag_demissao em [APITARGET] conforme manual IFPonto")
        return False

# Exemplo de uso
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        comando = sys.argv[1].lower()
        
        if comando == "completo" or comando == "integracao":
            # API -> CSV -> REST
            sucesso = processar_integracao_completa()
            
        elif comando == "csv":
            # Apenas gerar CSV
            dados = gerar_csv_demissoes()
            if dados is None:
                print("\nFalha ao gerar CSV.")
            else:
                print(f"\nCSV atualizado — novas linhas: {len(dados)} | historico: {ARQUIVO_HISTORICO_CPF_DEMISSOES}")
                print(f"Arquivo: demissoes_api.csv")
                
                # Mostrar todos os registros
                try:
                    df = pd.read_csv('demissoes_api.csv', sep=';')
                    print(f"\nTODOS OS REGISTROS ({len(df)}):")
                    for i, row in df.iterrows():
                        print(f"   {row['matricula']} | {row.get('nome', '')} | {row['DATA_DEMISSAO']}")
                        
                except Exception as e:
                    print(f"Erro ao analisar CSV: {e}")
                    
        elif comando == "enviar":
            # Apenas enviar CSV gerado via REST
            nome_arquivo = sys.argv[2] if len(sys.argv) > 2 else "demissoes_api.csv"
            if os.path.exists(nome_arquivo):
                pag_atual = ler_pag_demissao_rest()
                print(f"Enviando {nome_arquivo} com pag={pag_atual}")
                resultado = enviar_csv_demissoes_rest(nome_arquivo)
                if resultado:
                    print(f"\nARQUIVO ENVIADO COM SUCESSO VIA REST!")
                else:
                    print(f"\nFALHA NO ENVIO REST!")
            else:
                print(f"Arquivo {nome_arquivo} nao encontrado!")
        else:
            print("Comando invalido! Use: completo, csv, ou enviar")
            print("Exemplos:")
            print("  python demissoes.py completo")
            print("  python demissoes.py csv") 
            print("  python demissoes.py enviar [nome_arquivo.csv]")
    else:
        # EXECUCAO: Executar integracao completa automaticamente (comportamento padrao)
        print("Executando integracao completa de demissoes...")
        sucesso = processar_integracao_completa()
        
        if sucesso:
            print("\nINTEGRACAO FINALIZADA COM SUCESSO!")
        else:
            print("\nINTEGRACAO FINALIZADA COM ERROS!")