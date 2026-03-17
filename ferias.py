import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import hashlib
import base64
import os
import pytz
import configparser
import csv
import io
from config_reader import obter_headers_api, ler_token_config

def carregar_configuracoes():
    """
    Funcao para carregar configuracoes do arquivo .config
    (Adaptada do integracao_folha_ponto.py)
    """
    config = configparser.ConfigParser(interpolation=None)
    config.read('.config')
    
    # Verificar se existe secao APITARGET
    if not config.has_section('APITARGET'):
        print("Secao [APITARGET] nao encontrada no arquivo .config")
        return None
    
    return {
        'apitarget': {
            'url': config.get('APITARGET', 'url'),
            'integracao': config.get('APITARGET', 'integracao'),
            'token_base': config.get('APITARGET', 'token_base')
        }
    }

def gerar_token_target():
    """
    Gera o token para a API de destino usando a data atual
    (Adaptada do integracao_folha_ponto.py)
    """
    config = carregar_configuracoes()
    if not config:
        print("Erro ao carregar configuracoes")
        return None, None, None
    
    # Usar configuracoes da APITARGET
    url = config['apitarget']['url']
    integracao = config['apitarget']['integracao']
    token_base = config['apitarget']['token_base']
    
    # Configurar timezone para Sao Paulo
    tz_sao_paulo = pytz.timezone('America/Sao_Paulo')
    data_atual = datetime.now(tz_sao_paulo).strftime('%d/%m/%Y')
    
    # Gerar token final
    token_concatenado = token_base + data_atual
    token_final = hashlib.sha256(token_concatenado.encode('utf-8')).hexdigest()
    
    print(f"Data atual: {data_atual}")
    print(f"Token base: {token_base}")
    print(f"Token final gerado: {token_final[:32]}...")
    
    return url, integracao, token_final

def buscar_dados_empresa(funcionario_id, headers):
    """
    Busca informacoes da empresa do funcionario na API
    """
    try:
        url_empresa = f"https://dp.pack.alterdata.com.br/api/v1/funcionarios/{funcionario_id}/empresa"
        response = requests.get(url_empresa, headers=headers)
        
        if response.status_code == 200:
            empresa_data = response.json()
            empresa_info = empresa_data.get('data', {})
            if empresa_info:
                return empresa_info.get('id', '')
        else:
            print(f"    Erro {response.status_code} ao buscar empresa do funcionario {funcionario_id}")
    except Exception as e:
        print(f"    Erro ao buscar empresa do funcionario {funcionario_id}: {e}")
    
    return ''

def formatar_matricula_composta(cod_empresa, matricula_original):
    """
    Formata a matricula no padrao: cod_empresabmatricula_6_digitos
    Exemplo: cod_empresa=168, matricula=2 -> 168b000002
    """
    try:
        # Garantir que a matricula tenha 6 digitos com zeros a esquerda
        matricula_6_digitos = str(matricula_original).zfill(6)
        
        # Compor a matricula final
        matricula_composta = f"{cod_empresa}b{matricula_6_digitos}"
        
        print(f"    Matricula original: {matricula_original}")
        print(f"    Matricula 6 digitos: {matricula_6_digitos}")
        print(f"    Matricula FINAL: {matricula_composta}")
        
        return matricula_composta
        
    except Exception as e:
        print(f"    Erro ao formatar matricula: {e}")
        return f"{cod_empresa}b{str(matricula_original).zfill(6)}"

def converter_para_csv(dados, nome_arquivo="dados.csv"):
    """
    Funcao para converter dados em CSV com cabecalhos em lowercase
    (Adaptada do integracao_folha_ponto.py)
    """
    if not dados:
        print("Nao ha dados para converter em CSV")
        return None
    
    try:
        output = io.StringIO()
        
        # Obter cabecalhos das colunas e converter para lowercase
        fieldnames_originais = dados[0].keys()
        fieldnames_lowercase = [field.lower() for field in fieldnames_originais]
        
        # Criar mapeamento dos dados com chaves em lowercase
        dados_lowercase = []
        for linha in dados:
            linha_lowercase = {}
            for key, value in linha.items():
                linha_lowercase[key.lower()] = value
            dados_lowercase.append(linha_lowercase)
        
        # Criar writer CSV com fieldnames em lowercase
        writer = csv.DictWriter(output, fieldnames=fieldnames_lowercase, delimiter=';')
        
        writer.writeheader()
        for linha in dados_lowercase:
            writer.writerow(linha)
        
        csv_content = output.getvalue()
        output.close()
        
        with open(nome_arquivo, 'w', encoding='utf-8', newline='') as f:
            f.write(csv_content)
        
        print(f"CSV gerado com sucesso: {nome_arquivo}")
        print(f"Total de registros: {len(dados)}")
        print("Cabecalhos convertidos para lowercase!")
        
        return csv_content
        
    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None

def importar_via_post_generico(nome_arquivo_csv, endpoint, nome_modulo):
    """
    Funcao para importar CSV via POST
    (Adaptada do integracao_folha_ponto.py)
    """
    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} NAO encontrado!")
        return None
    
    print(f"Arquivo {nome_arquivo_csv} encontrado")
    
    # Gerar token e configuracoes (mesma logica do integracao_folha_ponto.py)
    resultado_token = gerar_token_target()
    if not resultado_token or resultado_token[0] is None:
        print("Falha ao gerar token para API de destino")
        return None
    
    url, integracao, token_final = resultado_token
    
    headers = {
        "user": integracao,
        "token": token_final
    }
    
    data = {
        "pag": endpoint,
        "cmd": "importar_cad",
        "separador": ";"
    }
    
    try:
        print(f"Enviando POST para {endpoint.upper()}...")
        print(f"URL: {url}")
        print(f"User: {integracao}")
        print(f"Token: {token_final[:32]}...")
        
        with open(nome_arquivo_csv, 'rb') as arquivo:
            files = {
                'arquivo': (nome_arquivo_csv, arquivo, 'text/csv')
            }
            
            response = requests.post(
                url, 
                data=data, 
                files=files,
                headers=headers,
                timeout=30
            )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                resultado = response.json()
                
                if resultado.get('success') == False:
                    print(f"API retornou erro:")
                    print(f"Resposta: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
                    return None
                else:
                    print(f"POST de {nome_modulo} realizado!")
                    print(f"Resposta: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
                    
                    cadastrados = resultado.get('ok', 0)
                    if cadastrados > 0:
                        print(f"{cadastrados} {nome_modulo} cadastrado(s)!")
                    
                    return resultado
                    
            except json.JSONDecodeError:
                print(f"Resposta nao e JSON valido:")
                print(f"Resposta: {response.text[:500]}...")
                return None
        else:
            print(f"ERRO - Status: {response.status_code}")
            print(f"Resposta: {response.text[:500]}...")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"ERRO na requisicao: {e}")
        return None

def processar_modulo_ferias(dados_ferias, nome_arquivo_csv, nome_modulo):
    """
    Funcao generica para processar um modulo completo
    (Adaptada do integracao_folha_ponto.py para ferias)
    """
    print(f"\n" + "="*50)
    print(f"PROCESSANDO {nome_modulo.upper()}...")
    print("="*50)
    
    if dados_ferias:
        print(f"\n{len(dados_ferias)} {nome_modulo} encontrados!")
        
        print(f"\n2. Convertendo {nome_modulo} para CSV...")
        csv_content = converter_para_csv(dados_ferias, nome_arquivo_csv)
        
        if csv_content:
            print(f"\n3. Fazendo POST de {nome_modulo} na API...")
            resultado = importar_via_post_generico(nome_arquivo_csv, "ponto_afastamento", nome_modulo)
            
            if resultado:
                print(f"\nINTEGRACAO DE {nome_modulo.upper()} CONCLUIDA!")
                return True
            else:
                print(f"\nFALHA NO POST DE {nome_modulo.upper()}!")
                return False
        else:
            print(f"\nFalha ao gerar CSV de {nome_modulo}")
            return False
    else:
        print(f"\nNenhum dado de {nome_modulo} disponivel")
        return False

# =================== FUNCOES ESPECIFICAS DA API ALTERDATA ===================

def buscar_detalhes_funcionario_completo(funcionario_id, headers):
    """
    Busca detalhes completos de um funcionario especifico
    """
    try:
        url = f"https://dp.pack.alterdata.com.br/api/v1/funcionarios"
        params = {
            "filter[id]": funcionario_id,
            "include": "naturalidade,estado,foto,estadocivil,departamento,sexo,formadepagamento,nacionalidade,pais,tipoDeConta,tipoDeChavePix"
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            funcionarios = data.get('data', [])
            if funcionarios:
                return funcionarios[0]
        return None
    except Exception as e:
        print(f"  Erro ao buscar detalhes do funcionario {funcionario_id}: {e}")
        return None

def extrair_datas_de_retorno_admissao(funcionario_detalhado):
    """
    Tenta extrair datas relacionadas a afastamentos dos campos disponiveis
    """
    attributes = funcionario_detalhado.get('attributes', {})
    
    # Campos que podem conter informacoes de datas
    datas_disponiveis = {
        'admissao': attributes.get('admissao'),
        'retorno': attributes.get('retorno'),
        'demissao': attributes.get('demissao'),
        'datavencimentocontratoexperiencia': attributes.get('datavencimentocontratoexperiencia'),
        'dataprorrogacaocontratoexperiencia': attributes.get('dataprorrogacaocontratoexperiencia')
    }
    
    return datas_disponiveis

def consultar_funcionarios_com_ferias():
    """
    Coleta funcionarios que tem APENAS FERIAS registradas na API Alterdata
    """
    print("INICIANDO COLETA DE FERIAS DA API ALTERDATA...")
    
    # Obter headers do arquivo .config
    headers = obter_headers_api()
    if not headers:
        print("Nao foi possivel obter o token do arquivo .config")
        return [], None
    
    # Configuracoes da API
    base_url = "https://dp.pack.alterdata.com.br/api/v1/funcionarios"
    
    # Buscar funcionarios com campos de afastamento
    params = {
        "fields": "codigo,nome,afastamento,afastamentodescricao,status,admissao,retorno,demissao",
        "sort": "codigo"
    }
    
    funcionarios_com_ferias = []
    url_atual = base_url
    pagina = 1
    
    # Coletar funcionarios com paginacao
    while url_atual:
        try:
            print(f"  Coletando pagina {pagina}... ", end="")
            
            if pagina == 1:
                response = requests.get(url_atual, headers=headers, params=params)
            else:
                response = requests.get(url_atual, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                funcionarios_pagina = data.get('data', [])
                
                # Filtrar APENAS funcionarios com FERIAS
                for funcionario in funcionarios_pagina:
                    attributes = funcionario.get('attributes', {})
                    afastamento_desc_raw = attributes.get('afastamentodescricao', '')
                    afastamento_desc = afastamento_desc_raw.lower() if afastamento_desc_raw else ''
                    
                    # Verificar se e especificamente FERIAS
                    if afastamento_desc and 'ferias' in afastamento_desc:
                        # Buscar detalhes completos do funcionario
                        funcionario_detalhado = buscar_detalhes_funcionario_completo(funcionario.get('id'), headers)
                        if funcionario_detalhado:
                            funcionario['detalhes_completos'] = funcionario_detalhado
                        
                        funcionarios_com_ferias.append(funcionario)
                
                ferias_encontradas = len([f for f in funcionarios_pagina 
                                        if f.get('attributes', {}).get('afastamentodescricao') 
                                        and 'ferias' in (f.get('attributes', {}).get('afastamentodescricao') or '').lower()])
                print(f"{len(funcionarios_pagina)} funcionarios ({ferias_encontradas} em ferias)")
                
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
    
    print(f"\nTotal de funcionarios em FERIAS: {len(funcionarios_com_ferias)}")
    return funcionarios_com_ferias, headers

def estimar_datas_ferias(funcionario_api, afastamento_desc):
    """
    Estima datas de ferias (sempre 30 dias)
    """
    attributes = funcionario_api.get('attributes', {})
    
    # Tentar usar campo retorno se disponivel
    data_retorno = attributes.get('retorno')
    
    # Ferias: sempre 30 dias
    hoje = datetime.now()
    
    if data_retorno:
        try:
            dt_retorno = datetime.fromisoformat(data_retorno.replace('Z', '+00:00'))
            dt_inicio = dt_retorno - timedelta(days=30)
            return dt_inicio.strftime('%d/%m/%Y'), dt_retorno.strftime('%d/%m/%Y')
        except:
            pass
    
    # Estimativa padrao para ferias: 30 dias (15 dias atras + 15 dias a frente)
    dt_inicio = hoje - timedelta(days=15)
    dt_fim = hoje + timedelta(days=15)
    return dt_inicio.strftime('%d/%m/%Y'), dt_fim.strftime('%d/%m/%Y')

def mapear_ferias_para_csv(funcionario_api, headers):
    """
    Mapeia ferias do funcionario para o formato esperado no CSV com matricula composta
    """
    attributes = funcionario_api.get('attributes', {})
    funcionario_id = funcionario_api.get('id', '')
    
    # Dados das ferias
    afastamento_desc = attributes.get('afastamentodescricao', '')
    codigo_funcionario = attributes.get('codigo', funcionario_id)
    
    # BUSCAR CODIGO DA EMPRESA
    cod_empresa = buscar_dados_empresa(funcionario_id, headers)
    print(f"\nMapeando funcionario {codigo_funcionario} - Empresa: {cod_empresa}")
    
    # FORMATAR MATRICULA COMPOSTA
    matricula_composta = formatar_matricula_composta(cod_empresa, codigo_funcionario)
    
    # Para ferias, SEMPRE usar codigo 1011
    codigo_afastamento = '1011'
    
    # Tentar extrair datas dos detalhes completos se disponivel
    dtinicio = ''
    dtfim = ''
    
    if funcionario_api.get('detalhes_completos'):
        detalhes = funcionario_api['detalhes_completos']
        datas = extrair_datas_de_retorno_admissao(detalhes)
        
        # Se temos data de retorno, tentar calcular periodo
        if datas.get('retorno'):
            try:
                dtinicio_est, dtfim_est = estimar_datas_ferias(funcionario_api, afastamento_desc)
                dtinicio = dtinicio_est
                dtfim = dtfim_est
            except:
                pass
    
    # Se ainda nao temos datas, fazer estimativa baseada em ferias (30 dias)
    if not dtinicio and not dtfim:
        dtinicio, dtfim = estimar_datas_ferias(funcionario_api, afastamento_desc)
    
    # Mapeamento dos campos conforme formato esperado - USANDO MATRICULA COMPOSTA
    ferias_csv = {
        'ID-AFASTAMENTO': codigo_afastamento,  # SEMPRE 1011 para ferias
        'DTINICIO': dtinicio,      # Data estimada ou extraida (DD/MM/YYYY)
        'DTFIM': dtfim,           # Data estimada ou extraida (DD/MM/YYYY)
        'OBS': afastamento_desc or 'Ferias',  # Usar descricao ou padrao
        'CAMPO_CHAVE': 'matricula',  # Valor fixo
        'MATRICULA': matricula_composta  # matricula composta: cod_empresabmatricula
    }
    
    return ferias_csv

def gerar_csv_ferias():
    """
    Funcao principal para gerar o CSV das ferias com matricula composta
    (Adaptada para usar a logica do integracao_folha_ponto.py)
    """
    print("=" * 80)
    print("         GERACAO DE CSV DE FERIAS COM MATRICULA COMPOSTA - API eContador")
    print("=" * 80)
    
    # Verificar se token esta disponivel
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    print("\n1. Consultando ferias na API Alterdata...")
    # Coletar funcionarios com ferias da API
    funcionarios_ferias, headers = consultar_funcionarios_com_ferias()
    
    if not funcionarios_ferias:
        print("Nenhum funcionario em ferias foi encontrado na API")
        return None
    
    print(f"\n{len(funcionarios_ferias)} funcionarios em ferias encontrados!")
    
    # Converter para formato CSV
    ferias_csv = []
    erros = []
    funcionarios_com_datas = 0
    
    for i, funcionario_api in enumerate(funcionarios_ferias, 1):
        try:
            ferias_csv_item = mapear_ferias_para_csv(funcionario_api, headers)
            
            # Filtrar apenas registros com descricao de ferias valida
            obs_raw = ferias_csv_item['OBS']
            obs_lower = obs_raw.lower() if obs_raw else ''
            if ferias_csv_item['OBS'] and 'ferias' in obs_lower:
                ferias_csv.append(ferias_csv_item)
                
                # Contar funcionarios com datas preenchidas
                if ferias_csv_item['DTINICIO'] and ferias_csv_item['DTFIM']:
                    funcionarios_com_datas += 1
            
            if i % 10 == 0:
                print(f"  Processados {i}/{len(funcionarios_ferias)} funcionarios...")
                
        except Exception as e:
            erros.append({'id': funcionario_api.get('id', 'N/A'), 'erro': str(e)})
            print(f"  Erro ao processar funcionario {funcionario_api.get('id', 'N/A')}: {e}")
    
    if not ferias_csv:
        print("Nenhuma ferias foi convertida com sucesso")
        print("Nota: Pode ser que nao existam ferias ativas no momento")
        return None
    
    print(f"\n{len(ferias_csv)} ferias processadas!")
    print(f"   Todas com ID-AFASTAMENTO: 1011 (Ferias)")
    print(f"   Funcionarios com datas: {funcionarios_com_datas}")
    
    return ferias_csv

def validar_dados_ferias_csv(nome_arquivo):
    """
    Valida os dados do CSV de ferias gerado
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
        campos_obrigatorios = ['matricula', 'obs', 'dtinicio', 'dtfim', 'id-afastamento']
        
        for campo in campos_obrigatorios:
            if campo in df.columns:
                vazios = df[campo].isna().sum() + (df[campo] == '').sum()
                if vazios > 0:
                    print(f"  Campo '{campo}': {vazios} registros vazios")
                else:
                    print(f"  Campo '{campo}': todos preenchidos")
            else:
                print(f"  Campo obrigatorio '{campo}' nao encontrado")
        
        # Verificar se todos os registros sao codigo 1011 (ferias)
        if 'id-afastamento' in df.columns:
            codigos_unicos = df['id-afastamento'].unique()
            print(f"  Codigos de afastamento encontrados: {codigos_unicos}")
            if len(codigos_unicos) == 1 and codigos_unicos[0] == '1011':
                print(f"  Todos os registros sao FERIAS (1011)")
            else:
                print(f"  Encontrados codigos diferentes de 1011!")
        
        print(f"  Validacao concluida")
        
    except Exception as e:
        print(f"  Erro na validacao: {e}")

def gerar_relatorio_ferias():
    """
    Gera relatorio especifico para ferias
    """
    relatorio = """
RELATORIO DE INTEGRACAO DE FERIAS - API ALTERDATA

ANALISE REALIZADA:
Este modulo foca especificamente na coleta e processamento de FERIAS dos funcionarios.

FILTROS APLICADOS:

1. SELECAO DE DADOS:
   - Filtro: afastamentodescricao contem 'ferias' (case-insensitive)
   - Codigo fixo: ID-AFASTAMENTO = 1011
   - Periodo padrao: 30 dias de ferias

2. MAPEAMENTO ESPECIFICO:
   - So processa registros que contenham 'ferias' na descricao
   - Ignora outros tipos de afastamento
   - Estimativa inteligente de 30 dias para ferias

DADOS GERADOS:

1. ESTRUTURA CSV:
   - id-afastamento: 1011 (fixo para ferias)
   - dtinicio: Data estimada de inicio
   - dtfim: Data estimada de fim (30 dias apos inicio)
   - obs: Descricao das ferias
   - campo_chave: matricula
   - matricula: Matricula composta (cod_empresabmatricula)

2. INTEGRACAO:
   - Endpoint: ponto_afastamento
   - Mesmo padrao do integracao_folha_ponto.py
   - Headers lowercase compativeis

Data do relatorio: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
"""
    
    with open('relatorio_ferias.txt', 'w', encoding='utf-8') as f:
        f.write(relatorio)
    
    print("Relatorio de ferias salvo em: relatorio_ferias.txt")

# =================== FUNCAO PRINCIPAL ===================

def processar_integracao_completa():
    """
    Funcao principal que executa todo o processo: coleta da API -> CSV -> POST para Hevi
    (Adaptada do integracao_folha_ponto.py)
    """
    print("INICIANDO INTEGRACAO DE FERIAS API ALTERDATA -> CSV -> POST API HEVI")
    print("="*70)
    
    # Gerar relatorio de ferias
    gerar_relatorio_ferias()
    
    # Etapa 1: Coletar dados da API Alterdata
    dados_ferias = gerar_csv_ferias()
    
    if not dados_ferias:
        print("Falha na coleta de dados da API Alterdata")
        return False
    
    # Etapa 2: Processar usando a logica do integracao_folha_ponto.py
    sucesso = processar_modulo_ferias(
        dados_ferias,
        'ferias_api.csv',
        'ferias'
    )
    
    if sucesso:
        # Validar dados gerados
        validar_dados_ferias_csv('ferias_api.csv')
        
        print(f"\nINTEGRACAO DE FERIAS FINALIZADA COM SUCESSO!")
        print(f"Ferias coletadas da API Alterdata")
        print(f"CSV gerado: ferias_api.csv")
        print(f"Dados enviados para sistema Hevi")
        print(f"Relatorio: relatorio_ferias.txt")
        print(f"IMPORTANTE: Todas as ferias receberam ID-AFASTAMENTO 1011!")
        
        # Mostrar todos os registros gerados
        try:
            df = pd.read_csv('ferias_api.csv', sep=';')
            print(f"\nREGISTROS GERADOS ({len(df)} total):")
            for i, row in df.iterrows():
                print(f"   {row['matricula']}: {row['dtinicio']} a {row['dtfim']} | {row['obs']}")
                
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
        
        return True
    else:
        print(f"\nFALHA NA INTEGRACAO!")
        print(f"CSV pode ter sido gerado: ferias_api.csv")
        print(f"Falha no envio para sistema Hevi")
        return False

# =================== EXECUCAO PRINCIPAL ===================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        comando = sys.argv[1].lower()
        
        if comando == "completo" or comando == "integracao":
            # Processo completo: API Alterdata → CSV → Hevi
            sucesso = processar_integracao_completa()
            
        elif comando == "csv":
            # Apenas gerar CSV
            gerar_relatorio_ferias()
            dados = gerar_csv_ferias()
            if dados:
                csv_content = converter_para_csv(dados, 'ferias_api.csv')
                if csv_content:
                    validar_dados_ferias_csv('ferias_api.csv')
                    print(f"\nCSV GERADO COM MATRICULA COMPOSTA!")
                    print(f"Arquivo: ferias_api.csv")
                    
                    # Mostrar todos os registros
                    try:
                        df = pd.read_csv('ferias_api.csv', sep=';')
                        print(f"\nTODOS OS REGISTROS ({len(df)}):")
                        for i, row in df.iterrows():
                            print(f"   {row['matricula']}: {row['dtinicio']} a {row['dtfim']} | {row['obs']}")
                            
                    except Exception as e:
                        print(f"Erro ao analisar CSV: {e}")
                    
        elif comando == "enviar":
            # Apenas enviar CSV existente
            nome_arquivo = sys.argv[2] if len(sys.argv) > 2 else "ferias_api.csv"
            if os.path.exists(nome_arquivo):
                resultado = importar_via_post_generico(nome_arquivo, "ponto_afastamento", "ferias")
                if resultado:
                    print(f"\nARQUIVO ENVIADO COM SUCESSO!")
                else:
                    print(f"\nFALHA NO ENVIO!")
            else:
                print(f"Arquivo {nome_arquivo} nao encontrado!")
        else:
            print("Comando invalido! Use: completo, csv, ou enviar")
            print("Exemplos:")
            print("  python ferias.py completo")
            print("  python ferias.py csv") 
            print("  python ferias.py enviar [nome_arquivo.csv]")
    else:
        # EXECUCAO: Executar integracao completa automaticamente (comportamento padrao)
        print("EXECUTANDO INTEGRACAO DE FERIAS (modo automatico)")
        print("Para ver opcoes use: python ferias.py --help")
        sucesso = processar_integracao_completa()
        if sucesso:
            print(f"\nINTEGRACAO DE FERIAS FINALIZADA COM SUCESSO!")
        else:
            print(f"\nINTEGRACAO DE FERIAS FALHOU - Verifique os logs acima")