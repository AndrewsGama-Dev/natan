import requests
import json
import pandas as pd
from datetime import datetime
import time
import hashlib
import pytz
import configparser
import sys
from config_reader import obter_headers_api, ler_token_config

def carregar_configuracoes_target():
    """
    Carrega configurações da seção [APITARGET] do arquivo .config
    """
    try:
        config = configparser.ConfigParser()
        config.read('.config', encoding='utf-8')
        
        if 'APITARGET' not in config:
            print("Seção [APITARGET] não encontrada no arquivo .config")
            return None
        
        return {
            'url': config['APITARGET'].get('url', '').strip(),
            'integracao': config['APITARGET'].get('integracao', '').strip(),
            'token_base': config['APITARGET'].get('token_base', '').strip()
        }
    except Exception as e:
        print(f"Erro ao carregar configurações [APITARGET]: {e}")
        return None

def gerar_token_target():
    """
    Gera o token para a API de destino usando a data atual
    """
    config_target = carregar_configuracoes_target()
    if not config_target:
        return None, None
    
    # Configurar timezone para São Paulo
    tz_sao_paulo = pytz.timezone('America/Sao_Paulo')
    data_atual = datetime.now(tz_sao_paulo).strftime('%d/%m/%Y')
    
    # Gerar token final
    token_concatenado = config_target['token_base'] + data_atual
    token_final = hashlib.sha256(token_concatenado.encode('utf-8')).hexdigest()
    
    print(f"\nGERAÇÃO DO TOKEN:")
    print(f"Data atual: {data_atual}")
    print(f"Token concatenado: {token_concatenado}")
    print(f"Token final: {token_final}")
    print("=" * 50)
    
    return config_target, token_final

def carregar_lista_empresas():
    """
    Carrega a lista de empresas do arquivo lista_empresas.csv
    """
    try:
        print("Carregando lista de empresas do arquivo lista_empresas.csv...")
        
        # Ler o CSV
        df = pd.read_csv('lista_empresas.csv', encoding='utf-8')
        
        print(f"Lista carregada: {len(df)} empresas encontradas")
        
        # Converter para lista de dicionários
        lista_empresas = []
        
        for _, row in df.iterrows():
            # Limpar CNPJ removendo caracteres especiais
            cnpj_original = str(row['cnpj'])
            cnpj_limpo = cnpj_original.replace('.', '').replace('-', '').replace('/', '')
            
            empresa_info = {
                'codigo_legado': int(row['codigo_legado']),
                'nome_lista': str(row['nome']),
                'cnpj_original': cnpj_original,
                'cnpj_limpo': cnpj_limpo
            }
            lista_empresas.append(empresa_info)
        
        return lista_empresas
        
    except FileNotFoundError:
        print("Arquivo 'lista_empresas.csv' não encontrado!")
        return []
    except Exception as e:
        print(f"Erro ao carregar lista de empresas: {e}")
        return []

def buscar_empresa_na_api_por_cnpj(cnpj_limpo, headers):
    """
    Busca uma empresa específica na API usando o CNPJ
    """
    try:
        base_url = "https://dp.pack.alterdata.com.br/api/v1/empresas"
        
        # Filtro para buscar por CNPJ
        params = {
            "filter[empresas][cpfcnpj][EQ]": cnpj_limpo,
            "filter[empresas][ativa][EQ]": "true"
        }
        
        response = requests.get(base_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            empresas = data.get('data', [])
            
            if empresas:
                return empresas[0]
            else:
                return None
        else:
            print(f"    Erro {response.status_code} ao buscar CNPJ {cnpj_limpo}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"    Erro na conexão ao buscar CNPJ {cnpj_limpo}: {e}")
        return None

def consultar_empresas_da_lista():
    """
    Coleta apenas as empresas que estão na lista_empresas.csv
    """
    print("INICIANDO COLETA DE EMPRESAS DA LISTA...")
    
    # Carregar lista de empresas
    lista_empresas = carregar_lista_empresas()
    
    if not lista_empresas:
        print("Não foi possível carregar a lista de empresas")
        return [], None
    
    # Obter headers do arquivo .config
    headers = obter_headers_api()
    if not headers:
        print("Não foi possível obter o token do arquivo .config")
        return [], None
    
    empresas_encontradas = []
    empresas_nao_encontradas = []
    
    print(f"\nBuscando {len(lista_empresas)} empresas na API por CNPJ...")
    
    # Buscar cada empresa pelo CNPJ
    for i, empresa_lista in enumerate(lista_empresas, 1):
        cnpj_limpo = empresa_lista['cnpj_limpo']
        codigo_legado = empresa_lista['codigo_legado']
        
        try:
            print(f"  [{i:2d}/{len(lista_empresas)}] Código {codigo_legado} - CNPJ {empresa_lista['cnpj_original']}... ", end="")
            
            # Buscar empresa na API
            empresa_api = buscar_empresa_na_api_por_cnpj(cnpj_limpo, headers)
            
            if empresa_api:
                # Adicionar informações da lista à empresa encontrada
                empresa_api['_lista_info'] = empresa_lista
                empresas_encontradas.append(empresa_api)
                print(f"Encontrada")
            else:
                empresas_nao_encontradas.append(empresa_lista)
                print(f"Não encontrada")
            
            # Pausa para não sobrecarregar a API
            time.sleep(0.3)
            
        except Exception as e:
            print(f"Erro: {e}")
            empresas_nao_encontradas.append(empresa_lista)
    
    # Relatório final
    print(f"\nRELATÓRIO DA COLETA:")
    print(f"  Empresas encontradas: {len(empresas_encontradas)}")
    print(f"  Empresas não encontradas: {len(empresas_nao_encontradas)}")
    
    if empresas_nao_encontradas:
        print(f"\nEmpresas não encontradas na API:")
        for empresa in empresas_nao_encontradas:
            print(f"    Código {empresa['codigo_legado']} - {empresa['cnpj_original']}")
    
    print(f"\nTotal de empresas coletadas: {len(empresas_encontradas)}")
    return empresas_encontradas, headers

def mapear_empresa_para_csv(empresa_api):
    """
    Mapeia uma empresa da API para o formato esperado no CSV
    """
    attributes = empresa_api.get('attributes', {})
    lista_info = empresa_api.get('_lista_info', {})
    
    # Usar codigo_legado da lista_empresas.csv
    codigo_legado_lista = lista_info.get('codigo_legado', '')
    
    empresa_csv = {
        'codigo_legado': codigo_legado_lista,
        'campo_chave': 'codigo_legado',
        'nro': codigo_legado_lista,
        'nome': attributes.get('nome', ''),
        'cnpj': lista_info.get('cnpj_limpo', ''),
        'inscricao_estadual': '',
        'cep': '',
        'endereco': attributes.get('endereco', ''),
        'bairro': '',
        'cidade': 'Manaus',
        'uf': 'AM',
        'telefone': '',
        'email': '',
        'site': '',
        'nome_relatorio': None
    }
    
    return empresa_csv

def gerar_csv_empresas():
    """
    Função principal para gerar o CSV das empresas da lista
    """
    print("=" * 80)
    print("         GERAÇÃO DE CSV DE EMPRESAS DA LISTA - API eContador")
    print("=" * 80)
    
    # Verificar se token está disponível
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    # Coletar empresas da lista na API
    empresas_api, headers = consultar_empresas_da_lista()
    
    if not empresas_api:
        print("Nenhuma empresa foi coletada da API")
        return None
    
    print(f"\nConvertendo {len(empresas_api)} empresas para formato CSV...")
    
    # Converter para formato CSV
    empresas_csv = []
    
    for i, empresa_api in enumerate(empresas_api, 1):
        try:
            empresa_csv = mapear_empresa_para_csv(empresa_api)
            empresas_csv.append(empresa_csv)
            
            if i % 5 == 0:
                print(f"  Processadas {i}/{len(empresas_api)} empresas...")
                
        except Exception as e:
            lista_info = empresa_api.get('_lista_info', {})
            codigo_legado = lista_info.get('codigo_legado', 'N/A')
            print(f"  Erro ao processar empresa código {codigo_legado}: {e}")
    
    if not empresas_csv:
        print("Nenhuma empresa foi convertida com sucesso")
        return None
    
    # Criar DataFrame
    print(f"\nCriando DataFrame com {len(empresas_csv)} empresas...")
    df = pd.DataFrame(empresas_csv)
    
    # Ordenar por codigo_legado
    df = df.sort_values('codigo_legado')
    
    # Gerar arquivo CSV
    nome_arquivo = "empresas_api.csv"
    
    try:
        df.to_csv(nome_arquivo, index=False, encoding='utf-8-sig', sep=';')
        print(f"CSV gerado com sucesso: {nome_arquivo}")
        
        # Estatísticas
        print(f"\nESTATÍSTICAS:")
        print(f"  Total de empresas processadas: {len(empresas_csv)}")
        print(f"  Colunas no CSV: {len(df.columns)}")
        print(f"  Arquivo gerado: {nome_arquivo}")
        
        # Preview dos dados
        print(f"\nPREVIEW DOS DADOS (primeiras 3 linhas):")
        print(df.head(3).to_string())
        
        return nome_arquivo
        
    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None

def gerar_csv_empresas_original():
    """
    Função para gerar CSV usando códigos originais da API (IDs da API)
    """
    print("=" * 80)
    print("         GERAÇÃO DE CSV EMPRESAS - CÓDIGOS ORIGINAIS DA API")
    print("=" * 80)
    
    # Verificar se token está disponível
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    # Coletar empresas da lista na API
    empresas_api, headers = consultar_empresas_da_lista()
    
    if not empresas_api:
        print("Nenhuma empresa foi coletada da API")
        return None
    
    print(f"\nConvertendo {len(empresas_api)} empresas para formato CSV (códigos originais)...")
    
    # Converter para formato CSV usando códigos originais
    empresas_csv = []
    
    for i, empresa_api in enumerate(empresas_api, 1):
        try:
            attributes = empresa_api.get('attributes', {})
            lista_info = empresa_api.get('_lista_info', {})
            empresa_id = empresa_api.get('id', '')  # ID original da API
            
            # Usar ID original da API para codigo_legado e nro
            empresa_csv = {
                'codigo_legado': empresa_id,
                'campo_chave': 'codigo_legado',
                'nro': empresa_id,
                'nome': attributes.get('nome', ''),
                'cnpj': lista_info.get('cnpj_limpo', ''),
                'inscricao_estadual': '',
                'cep': '',
                'endereco': attributes.get('endereco', ''),
                'bairro': '',
                'cidade': 'Manaus',
                'uf': 'AM',
                'telefone': '',
                'email': '',
                'site': '',
                'nome_relatorio': None
            }
            
            empresas_csv.append(empresa_csv)
            
            if i % 5 == 0:
                print(f"  Processadas {i}/{len(empresas_api)} empresas...")
                
        except Exception as e:
            empresa_id = empresa_api.get('id', 'N/A')
            print(f"  Erro ao processar empresa ID {empresa_id}: {e}")
    
    if not empresas_csv:
        print("Nenhuma empresa foi convertida com sucesso")
        return None
    
    # Criar DataFrame
    print(f"\nCriando DataFrame com {len(empresas_csv)} empresas...")
    df = pd.DataFrame(empresas_csv)
    
    # Ordenar por codigo_legado
    df = df.sort_values('codigo_legado')
    
    # Gerar arquivo CSV
    nome_arquivo = "empresas_api.csv"
    
    try:
        df.to_csv(nome_arquivo, index=False, encoding='utf-8-sig', sep=';')
        print(f"CSV gerado com sucesso: {nome_arquivo}")
        
        # Estatísticas
        print(f"\nESTATÍSTICAS:")
        print(f"  Total de empresas processadas: {len(empresas_csv)}")
        print(f"  Colunas no CSV: {len(df.columns)}")
        print(f"  Arquivo gerado: {nome_arquivo}")
        print(f"  Nota: codigo_legado e nro usam IDs originais da API")
        
        # Preview dos dados
        print(f"\nPREVIEW DOS DADOS (primeiras 3 linhas):")
        print(df.head(3).to_string())
        
        return nome_arquivo
        
    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None

def enviar_csv_para_api_target(nome_arquivo_csv):
    """
    Envia o CSV de empresas para a API de destino via POST
    """
    import os
    
    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} não encontrado!")
        return False
    
    print(f"Arquivo {nome_arquivo_csv} encontrado")
    
    # Obter configurações e token
    config_target, token_final = gerar_token_target()
    if not config_target or not token_final:
        print("Falha ao gerar token para API de destino")
        return False
    
    # Obter usuário da configuração
    usuario = config_target.get('integracao', '')
    if not usuario:
        print("Usuário não encontrado na configuração [APITARGET]")
        return False
    
    # Preparar headers e dados
    headers = {
        "user": usuario,
        "token": token_final
    }
    
    data = {
        "pag": "configuracao_empresa",
        "cmd": "importar_cad",
        "separador": ";"
    }
    
    try:
        print(f"Enviando POST para API de destino...")
        print(f"URL: {config_target['url']}")
        print(f"Usuário: {usuario}")
        print(f"Token: {token_final[:32]}...")
        
        with open(nome_arquivo_csv, 'rb') as arquivo:
            files = {
                'arquivo': (nome_arquivo_csv, arquivo, 'text/csv')
            }
            
            response = requests.post(
                config_target['url'], 
                data=data, 
                files=files,
                headers=headers,
                timeout=30
            )
        
        print(f"Status da resposta: {response.status_code}")
        
        if response.status_code == 200:
            try:
                resultado = response.json()
                
                if resultado.get('success') == False:
                    print(f"API retornou erro:")
                    print(f"Resposta: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
                    return False
                else:
                    print(f"POST de empresas realizado com sucesso!")
                    print(f"Resposta da API:")
                    print(json.dumps(resultado, indent=2, ensure_ascii=False))
                    
                    cadastrados = resultado.get('ok', 0)
                    if cadastrados > 0:
                        print(f"{cadastrados} empresa(s) cadastrada(s) com sucesso!")
                    
                    return True
                
            except json.JSONDecodeError:
                print(f"Resposta não é JSON válido:")
                print(f"Resposta: {response.text[:500]}...")
                return False
                
        else:
            print(f"ERRO no POST - Status: {response.status_code}")
            print(f"Resposta: {response.text[:500]}...")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"ERRO na requisição para API de destino: {e}")
        return False

def processar_integracao_completa():
    """
    Função principal que executa todo o processo
    """
    print("=" * 80)
    print("    INTEGRAÇÃO COMPLETA BASEADA EM LISTA - eContador → Sistema Destino")
    print("=" * 80)
    
    # Etapa 1: Gerar CSV das empresas da lista
    print("\nETAPA 1: Coletando empresas da lista_empresas.csv na API eContador...")
    arquivo_csv = gerar_csv_empresas()
    
    if not arquivo_csv:
        print("Falha na geração do CSV. Processo interrompido.")
        return False
    
    # Etapa 2: Enviar para API de destino
    print("\nETAPA 2: Enviando CSV para API de destino...")
    sucesso_envio = enviar_csv_para_api_target(arquivo_csv)
    
    if sucesso_envio:
        print("\nINTEGRAÇÃO COMPLETA FINALIZADA COM SUCESSO!")
        print(f"Empresas da lista coletadas da API eContador")
        print(f"CSV gerado: {arquivo_csv}")
        print(f"Dados enviados para sistema de destino")
        return True
    else:
        print("\nFALHA NA INTEGRAÇÃO!")
        print(f"CSV gerado: {arquivo_csv}")
        print(f"Falha no envio para sistema de destino")
        return False

# Execução principal
if __name__ == "__main__":
    # Verificar argumentos de linha de comando
    if len(sys.argv) > 1:
        argumento = sys.argv[1].lower()
        
        if argumento == 'csv':
            # Gerar CSV com códigos da lista
            arquivo_csv = gerar_csv_empresas()
            
            if arquivo_csv:
                print(f"\nCSV gerado com sucesso: {arquivo_csv}")
                sys.exit(0)
            else:
                print("\nFalha na geração do CSV")
                sys.exit(1)
                
        elif argumento == 'original':
            # Gerar CSV com códigos originais da API
            arquivo_csv = gerar_csv_empresas_original()
            
            if arquivo_csv:
                print(f"\nCSV gerado com sucesso: {arquivo_csv}")
                print("Nota: codigo_legado e nro contêm IDs originais da API")
                sys.exit(0)
            else:
                print("\nFalha na geração do CSV")
                sys.exit(1)
        else:
            print("Argumentos disponíveis:")
            print("  python empresas.py csv      - Gerar CSV com códigos da lista")
            print("  python empresas.py original - Gerar CSV com códigos originais da API")
            sys.exit(1)
    else:
        # Sem argumentos - executar modo original por padrão E enviar para API TARGET
        arquivo_csv = gerar_csv_empresas_original()
        
        if arquivo_csv:
            print(f"\nCSV gerado com sucesso: {arquivo_csv}")
            print("Nota: codigo_legado e nro contêm IDs originais da API")
            
            # Enviar para API TARGET
            print("\nEnviando CSV para API TARGET...")
            sucesso_envio = enviar_csv_para_api_target(arquivo_csv)
            
            if sucesso_envio:
                print("\nSUCESSO: CSV gerado e enviado para API TARGET!")
                sys.exit(0)
            else:
                print("\nERRO: CSV gerado mas falha no envio para API TARGET")
                sys.exit(1)
        else:
            print("\nFalha na geração do CSV")
            sys.exit(1)