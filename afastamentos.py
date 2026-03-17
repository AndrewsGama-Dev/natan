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
import sys
from config_reader import obter_headers_api, ler_token_config

def carregar_configuracoes():
    """Funcao para carregar configuracoes do arquivo .config"""
    config = configparser.ConfigParser(interpolation=None)
    config.read('.config')
    
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
    """Gera o token para a API de destino usando a data atual"""
    config = carregar_configuracoes()
    if not config:
        print("Erro ao carregar configuracoes")
        return None, None, None
    
    url = config['apitarget']['url']
    integracao = config['apitarget']['integracao']
    token_base = config['apitarget']['token_base']
    
    tz_sao_paulo = pytz.timezone('America/Sao_Paulo')
    data_atual = datetime.now(tz_sao_paulo).strftime('%d/%m/%Y')
    
    token_concatenado = token_base + data_atual
    token_final = hashlib.sha256(token_concatenado.encode('utf-8')).hexdigest()
    
    return url, integracao, token_final

def buscar_dados_empresa(funcionario_id, headers):
    """
    Busca informaçoes da empresa do funcionario na API
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
    """Funcao para converter dados em CSV com cabecalhos em lowercase"""
    if not dados:
        print("Nao ha dados para converter em CSV")
        return None
    
    try:
        output = io.StringIO()
        
        fieldnames_originais = dados[0].keys()
        fieldnames_lowercase = [field.lower() for field in fieldnames_originais]
        
        dados_lowercase = []
        for linha in dados:
            linha_lowercase = {}
            for key, value in linha.items():
                linha_lowercase[key.lower()] = value
            dados_lowercase.append(linha_lowercase)
        
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
        
        return csv_content
        
    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None

def importar_via_post_generico(nome_arquivo_csv, endpoint, nome_modulo):
    """Funcao para importar CSV via POST"""
    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} NAO encontrado!")
        return None
    
    resultado_token = gerar_token_target()
    if not resultado_token or resultado_token[0] is None:
        print("Falha ao gerar token para API de destino")
        return None
    
    url, integracao, token_final = resultado_token
    
    headers = {"user": integracao, "token": token_final}
    data = {"pag": endpoint, "cmd": "importar_cad", "separador": ";"}
    
    try:
        with open(nome_arquivo_csv, 'rb') as arquivo:
            files = {'arquivo': (nome_arquivo_csv, arquivo, 'text/csv')}
            response = requests.post(url, data=data, files=files, headers=headers, timeout=30)
        
        if response.status_code == 200:
            try:
                resultado = response.json()
                if resultado.get('success') == False:
                    print(f"API retornou erro: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
                    return None
                else:
                    print(f"POST de {nome_modulo} realizado!")
                    cadastrados = resultado.get('ok', 0)
                    if cadastrados > 0:
                        print(f"{cadastrados} {nome_modulo} cadastrado(s)!")
                    return resultado
            except json.JSONDecodeError:
                print(f"Resposta nao eh JSON valido: {response.text[:500]}...")
                return None
        else:
            print(f"ERRO - Status: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"ERRO na requisicao: {e}")
        return None

def processar_modulo_afastamentos(dados_afastamentos, nome_arquivo_csv, nome_modulo):
    """Funcao generica para processar um modulo completo"""
    print(f"\n" + "="*50)
    print(f"PROCESSANDO {nome_modulo.upper()}...")
    print("="*50)
    
    if dados_afastamentos:
        print(f"\n{len(dados_afastamentos)} {nome_modulo} encontrados!")
        
        csv_content = converter_para_csv(dados_afastamentos, nome_arquivo_csv)
        
        if csv_content:
            resultado = importar_via_post_generico(nome_arquivo_csv, "ponto_afastamento", nome_modulo)
            
            if resultado:
                print(f"\nINTEGRACAO DE {nome_modulo.upper()} CONCLUIDA!")
                return True
            else:
                print(f"\nFALHA NO POST DE {nome_modulo.upper()}!")
                return False
        else:
            return False
    else:
        print(f"\nNenhum dado de {nome_modulo} disponivel")
        return False

def extrair_datas_dos_campos_corretos(attributes):
    """
    FUNCAO CORRIGIDA: Extrai datas dos campos corretos identificados
    
    CAMPOS CORRETOS IDENTIFICADOS:
    - attributes['afastamento'] = Data de INICIO (2025-07-16T03:00:00Z)
    - attributes['retorno'] = Data de FIM (2025-07-18T03:00:00Z)
    """
    print(f"  Extraindo datas dos CAMPOS CORRETOS...")
    
    # BUSCAR CAMPOS CORRETOS
    campo_inicio = attributes.get('afastamento')  # Data de INICIO
    campo_fim = attributes.get('retorno')         # Data de FIM
    
    print(f"    Campo 'afastamento' (INICIO): {campo_inicio}")
    print(f"    Campo 'retorno' (FIM): {campo_fim}")
    
    # Verificar se temos ambos os campos
    if campo_inicio and campo_fim:
        try:
            # Converter datas ISO para formato DD/MM/YYYY
            dt_inicio = datetime.fromisoformat(campo_inicio.replace('Z', '+00:00'))
            dt_fim = datetime.fromisoformat(campo_fim.replace('Z', '+00:00'))
            
            data_inicio_fmt = dt_inicio.strftime('%d/%m/%Y')
            data_fim_fmt = dt_fim.strftime('%d/%m/%Y')
            
            print(f"    DATAS EXTRAIDAS: {data_inicio_fmt} ate {data_fim_fmt}")
            return data_inicio_fmt, data_fim_fmt, "CAMPOS_CORRETOS_API"
            
        except Exception as e:
            print(f"    Erro ao converter datas: {e}")
    
    # Se nao temos ambos, tentar pelo menos o retorno
    elif campo_fim:
        try:
            dt_fim = datetime.fromisoformat(campo_fim.replace('Z', '+00:00'))
            data_fim_fmt = dt_fim.strftime('%d/%m/%Y')
            
            print(f"    Apenas data FIM: {data_fim_fmt}")
            return None, data_fim_fmt, "APENAS_RETORNO"
            
        except Exception as e:
            print(f"    Erro ao converter data de retorno: {e}")
    
    print(f"    Campos de data nao encontrados")
    return None, None, "SEM_DATAS_API"

def consultar_funcionarios_com_afastamentos():
    """Coleta funcionarios que tem afastamentos registrados na API Alterdata"""
    print("INICIANDO COLETA - VERSAO CORRIGIDA")
    
    headers = obter_headers_api()
    if not headers:
        print("Nao foi possivel obter o token do arquivo .config")
        return [], None
    
    base_url = "https://dp.pack.alterdata.com.br/api/v1/funcionarios"
    
    params = {
        "fields": "codigo,nome,afastamento,afastamentodescricao,status,retorno",
        "sort": "codigo"
    }
    
    funcionarios_com_afastamento = []
    url_atual = base_url
    pagina = 1
    
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
                
                for funcionario in funcionarios_pagina:
                    attributes = funcionario.get('attributes', {})
                    afastamento = attributes.get('afastamento')
                    afastamento_desc_raw = attributes.get('afastamentodescricao', '')
                    afastamento_desc = afastamento_desc_raw.lower() if afastamento_desc_raw else ''
                    
                    # Se tem afastamento ativo ou descricao de afastamento, MAS NAO EH FERIAS
                    if (afastamento is not None or (afastamento_desc and afastamento_desc.strip())) and 'ferias' not in afastamento_desc:
                        
                        print(f"\n  Funcionario {attributes.get('codigo', 'N/A')} - {afastamento_desc_raw}")
                        funcionarios_com_afastamento.append(funcionario)
                
                afastamentos_nao_ferias = len([f for f in funcionarios_pagina 
                                             if f.get('attributes', {}).get('afastamentodescricao') 
                                             and 'ferias' not in (f.get('attributes', {}).get('afastamentodescricao') or '').lower()
                                             and (f.get('attributes', {}).get('afastamentodescricao') or '').strip()])
                
                print(f"{len(funcionarios_pagina)} funcionarios ({afastamentos_nao_ferias} com afastamento nao-ferias)")
                
                url_atual = data.get('links', {}).get('next')
                pagina += 1
                
                time.sleep(0.5)
            else:
                print(f"Erro {response.status_code}: {response.text}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Erro na conexao: {e}")
            break
    
    print(f"\nTotal de funcionarios com afastamento: {len(funcionarios_com_afastamento)}")
    return funcionarios_com_afastamento, headers

def mapear_afastamento_para_csv(funcionario_api, headers):
    """
    FUNCAO PRINCIPAL ATUALIZADA: Usar matricula composta sem campo COD_EMPRESA separado
    """
    attributes = funcionario_api.get('attributes', {})
    funcionario_id = funcionario_api.get('id', '')
    
    afastamento_desc = attributes.get('afastamentodescricao', '')
    codigo_funcionario = attributes.get('codigo', funcionario_id)
    
    # BUSCAR CODIGO DA EMPRESA
    cod_empresa = buscar_dados_empresa(funcionario_id, headers)
    print(f"\nMapeando funcionario {codigo_funcionario} - Empresa: {cod_empresa}")
    
    # FORMATAR MATRICULA COMPOSTA
    matricula_composta = formatar_matricula_composta(cod_empresa, codigo_funcionario)
    
    # DEFINIR ID-AFASTAMENTO BASEADO NO CONTEUDO DO OBS
    obs_normalizada = afastamento_desc.lower().strip() if afastamento_desc else ''
    
    print(f"    Descricao original: '{afastamento_desc}'")
    print(f"    Descricao normalizada: '{obs_normalizada}'")
    
    if 'ferias' in obs_normalizada or 'férias' in obs_normalizada:
        codigo_afastamento = '1011'  # Ferias
        print(f"    >>> DETECTADO: Ferias -> ID 1011")
    elif 'atestado' in obs_normalizada:
        codigo_afastamento = '1012'  # Atestado
        print(f"    >>> DETECTADO: Atestado -> ID 1012")
    else:
        codigo_afastamento = '1012'  # Default para outros tipos de afastamento
        print(f"    >>> DEFAULT: Outro tipo -> ID 1012")
    
    print(f"    ID-Afastamento FINAL: {codigo_afastamento}")
    
    # USAR CAMPOS CORRETOS DIRETAMENTE
    dtinicio, dtfim, origem_data = extrair_datas_dos_campos_corretos(attributes)
    
    # Se nao conseguimos extrair
    if not dtinicio or not dtfim:
        print(f"    ERRO: Nao foi possivel obter datas dos campos")
        dtinicio = dtinicio or 'SEM_DATA_API'
        dtfim = dtfim or 'SEM_DATA_API'
        origem_data = 'ERRO_API'
    
    # Mapeamento final - USANDO MATRICULA COMPOSTA (sem COD_EMPRESA separado)
    afastamento_csv = {
        'ID-AFASTAMENTO': codigo_afastamento,
        'DTINICIO': dtinicio,
        'DTFIM': dtfim,
        'OBS': afastamento_desc if afastamento_desc else 'Afastamento',
        'CAMPO_CHAVE': 'matricula',
        'MATRICULA': matricula_composta
    }
    
    return afastamento_csv

def gerar_csv_afastamentos():
    """FUNCAO PRINCIPAL: Gerar CSV usando matricula composta"""
    print("=" * 80)
    print("     GERACAO DE CSV COM MATRICULA COMPOSTA - PADRAO: cod_empresabmatricula")
    print("=" * 80)
    
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    print("\n1. Consultando afastamentos na API Alterdata...")
    funcionarios_afastamento, headers = consultar_funcionarios_com_afastamentos()
    
    if not funcionarios_afastamento:
        print("Nenhum funcionario com afastamento foi encontrado")
        return None
    
    # Converter para formato CSV
    afastamentos_csv = []
    funcionarios_com_datas_reais = 0
    funcionarios_sem_datas = 0
    
    for funcionario_api in funcionarios_afastamento:
        try:
            afastamento_csv = mapear_afastamento_para_csv(funcionario_api, headers)
            
            obs = afastamento_csv['OBS'].lower()
            if 'ferias' not in obs:
                afastamentos_csv.append(afastamento_csv)
                
                # Contar sucessos
                if afastamento_csv['DTINICIO'] != 'SEM_DATA_API' and afastamento_csv['DTFIM'] != 'SEM_DATA_API':
                    funcionarios_com_datas_reais += 1
                else:
                    funcionarios_sem_datas += 1
                    
        except Exception as e:
            print(f"Erro ao processar funcionario: {e}")
            funcionarios_sem_datas += 1
    
    print(f"\nRESULTADO:")
    print(f"   Funcionarios com datas CORRETAS: {funcionarios_com_datas_reais}")
    print(f"   Funcionarios sem datas: {funcionarios_sem_datas}")
    print(f"   Total de registros: {len(afastamentos_csv)}")
    
    return afastamentos_csv

def processar_integracao_completa():
    """FUNCAO PRINCIPAL ATUALIZADA"""
    print("INICIANDO INTEGRACAO COM MATRICULA COMPOSTA")
    print("="*50)
    
    dados_afastamentos = gerar_csv_afastamentos()
    
    if not dados_afastamentos:
        print("Falha na coleta de dados")
        return False
    
    sucesso = processar_modulo_afastamentos(
        dados_afastamentos,
        'afastamentos_api.csv',
        'afastamentos'
    )
    
    if sucesso:
        print(f"\nINTEGRACAO CONCLUIDA!")
        print(f"CSV gerado: afastamentos_api.csv")
        
        # Mostrar todos os registros gerados
        try:
            df = pd.read_csv('afastamentos_api.csv', sep=';')
            print(f"\nREGISTROS GERADOS ({len(df)} total):")
            for i, row in df.iterrows():
                print(f"   {row['matricula']}: {row['dtinicio']} a {row['dtfim']} | {row['obs']}")
                
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
        
        return True
    else:
        print(f"\nFALHA NA INTEGRACAO!")
        return False

# =================== EXECUCAO PRINCIPAL ===================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        comando = sys.argv[1].lower()
        
        if comando == "completo" or comando == "integracao":
            sucesso = processar_integracao_completa()
            
        elif comando == "csv":
            dados = gerar_csv_afastamentos()
            if dados:
                csv_content = converter_para_csv(dados, 'afastamentos_api.csv')
                if csv_content:
                    print(f"\nCSV FINAL GERADO COM MATRICULA COMPOSTA!")
                    print(f"Arquivo: afastamentos_api.csv")
                    
                    # Mostrar todos os registros
                    try:
                        df = pd.read_csv('afastamentos_api.csv', sep=';')
                        print(f"\nTODOS OS REGISTROS ({len(df)}):")
                        for i, row in df.iterrows():
                            print(f"   {row['matricula']}: {row['dtinicio']} a {row['dtfim']} | {row['obs']}")
                            
                    except Exception as e:
                        print(f"Erro ao analisar CSV: {e}")
                    
        elif comando == "enviar":
            nome_arquivo = sys.argv[2] if len(sys.argv) > 2 else "afastamentos_api.csv"
            if os.path.exists(nome_arquivo):
                resultado = importar_via_post_generico(nome_arquivo, "ponto_afastamento", "afastamentos")
                if resultado:
                    print(f"\nARQUIVO ENVIADO COM SUCESSO!")
                else:
                    print(f"\nFALHA NO ENVIO!")
            else:
                print(f"Arquivo {nome_arquivo} nao encontrado!")
                
        else:
            print("Comando invalido! Use:")
            print("  python afastamentos.py completo   # Integracao completa")
            print("  python afastamentos.py csv        # Apenas gerar CSV")
            print("  python afastamentos.py enviar [arquivo.csv]")
    else:
        print("EXECUTANDO INTEGRACAO COM MATRICULA COMPOSTA")
        sucesso = processar_integracao_completa()
        if sucesso:
            print(f"\nINTEGRACAO CONCLUIDA COM MATRICULA COMPOSTA!")
        else:
            print(f"\nINTEGRACAO FALHOU")