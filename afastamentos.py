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
from funcionarios import (
    formatar_cpf_11_digitos,
    ler_campo_chave_config,
)

def _rotulo_registro_afastamento(row):
    """Identificador exibido no resumo final (CSV sem coluna matricula)."""
    cpf = row.get('cpf', '')
    if cpf is not None and str(cpf).strip() and str(cpf).lower() != 'nan':
        return str(cpf).strip()
    return str(row.get('id-afastamento', '?'))

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

def _parse_data_iso(valor):
    """Converte string ISO da API Alterdata em datetime."""
    return datetime.fromisoformat(str(valor).replace('Z', '+00:00'))

def extrair_datas_dos_campos_corretos(attributes):
    """
    Extrai datas dos campos da API Alterdata:
    - attributes['afastamento'] = data de inicio
    - attributes['retorno'] = data de fim
    Se houver apenas inicio, retorno = inicio + 20 anos.
    """
    print(f"  Extraindo datas dos CAMPOS CORRETOS...")
    
    campo_inicio = attributes.get('afastamento')
    campo_fim = attributes.get('retorno')
    
    print(f"    Campo 'afastamento' (INICIO): {campo_inicio}")
    print(f"    Campo 'retorno' (FIM): {campo_fim}")
    
    if campo_inicio and campo_fim:
        try:
            dt_inicio = _parse_data_iso(campo_inicio)
            dt_fim = _parse_data_iso(campo_fim)
            
            data_inicio_fmt = dt_inicio.strftime('%d/%m/%Y')
            data_fim_fmt = dt_fim.strftime('%d/%m/%Y')
            
            print(f"    DATAS EXTRAIDAS: {data_inicio_fmt} ate {data_fim_fmt}")
            return data_inicio_fmt, data_fim_fmt, "CAMPOS_CORRETOS_API"
            
        except Exception as e:
            print(f"    Erro ao converter datas: {e}")
    
    elif campo_inicio and not campo_fim:
        try:
            dt_inicio = _parse_data_iso(campo_inicio)
            try:
                dt_fim = dt_inicio.replace(year=dt_inicio.year + 20)
            except ValueError:
                dt_fim = dt_inicio.replace(year=dt_inicio.year + 20, day=28)
            
            data_inicio_fmt = dt_inicio.strftime('%d/%m/%Y')
            data_fim_fmt = dt_fim.strftime('%d/%m/%Y')
            
            print(
                f"    Retorno ausente na API — usando inicio + 20 anos: "
                f"{data_inicio_fmt} ate {data_fim_fmt}"
            )
            return data_inicio_fmt, data_fim_fmt, "INICIO_MAIS_20_ANOS"
            
        except Exception as e:
            print(f"    Erro ao calcular retorno (inicio + 20 anos): {e}")
    
    elif campo_fim:
        try:
            dt_fim = _parse_data_iso(campo_fim)
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
        "fields": "codigo,nome,cpf,afastamento,afastamentodescricao,status,retorno",
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

def mapear_afastamento_para_csv(funcionario_api, campo_chave):
    """
    Coluna CAMPO_CHAVE no CSV: mesmo texto da secao [FUNCIONARIOS] do .config
    que funcionarios.py usa em ler_campo_chave_config.
    Coluna CPF: 11 digitos (sem mascara).
    """
    attributes = funcionario_api.get('attributes', {})
    funcionario_id = funcionario_api.get('id', '')
    
    afastamento_desc = attributes.get('afastamentodescricao', '')
    codigo_funcionario = attributes.get('codigo', '')
    if not codigo_funcionario:
        codigo_funcionario = str(funcionario_id)
    
    # Valor exibido no CSV = igual funcionarios_api (preserva grafia do .config)
    campo_chave_csv = (campo_chave or "").strip() or 'matricula'
    campo_ck_norm = campo_chave_csv.lower()
    
    cpf_fmt = formatar_cpf_11_digitos(attributes.get('cpf', ''))
    print(
        f"\nMapeando funcionario {codigo_funcionario} — cpf: {cpf_fmt or '(vazio)'} | "
        f"campo_chave CSV ({campo_chave_csv})"
    )
    if campo_ck_norm == 'cpf' and not cpf_fmt:
        print("    AVISO: CPF vazio na API — verificar cadastro no destino se a chave for cpf.")
    
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
    
    if not dtinicio or not dtfim:
        print(
            f"    PULANDO registro — sem datas na API "
            f"(cpf: {cpf_fmt or 'N/A'}, obs: {afastamento_desc or 'N/A'})"
        )
        return None
    
    afastamento_csv = {
        'ID-AFASTAMENTO': codigo_afastamento,
        'DTINICIO': dtinicio,
        'DTFIM': dtfim,
        'OBS': afastamento_desc if afastamento_desc else 'Afastamento',
        'CAMPO_CHAVE': campo_chave_csv,
        'CPF': cpf_fmt or '',
        
    }
    
    return afastamento_csv

def gerar_csv_afastamentos():
    """CSV de afastamentos: campo_chave + cpf (sem coluna matricula)."""
    print("=" * 80)
    print("     GERACAO DE CSV DE AFASTAMENTOS - chave por cpf/campo_chave do .config")
    print("=" * 80)
    
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    campo_chave_cfg = ler_campo_chave_config()
    print(f"\n[Afastamentos] CAMPO_CHAVE no CSV igual ao .config [FUNCIONARIOS]: {campo_chave_cfg.strip() if campo_chave_cfg else campo_chave_cfg}")
    
    print("\n1. Consultando afastamentos na API Alterdata...")
    funcionarios_afastamento, _ = consultar_funcionarios_com_afastamentos()
    
    if not funcionarios_afastamento:
        print("Nenhum funcionario com afastamento foi encontrado")
        return None
    
    # Converter para formato CSV
    afastamentos_csv = []
    funcionarios_com_datas_reais = 0
    funcionarios_sem_datas = 0
    
    for funcionario_api in funcionarios_afastamento:
        try:
            afastamento_csv = mapear_afastamento_para_csv(funcionario_api, campo_chave_cfg)
            if not afastamento_csv:
                funcionarios_sem_datas += 1
                continue
            
            obs = afastamento_csv['OBS'].lower()
            if 'ferias' not in obs:
                afastamentos_csv.append(afastamento_csv)
                funcionarios_com_datas_reais += 1
                    
        except Exception as e:
            print(f"Erro ao processar funcionario: {e}")
            funcionarios_sem_datas += 1
    
    print(f"\nRESULTADO:")
    print(f"   Registros exportados com datas: {funcionarios_com_datas_reais}")
    print(f"   Registros pulados (sem datas na API): {funcionarios_sem_datas}")
    print(f"   Total de registros: {len(afastamentos_csv)}")
    
    return afastamentos_csv

def processar_integracao_completa():
    """Integracao afastamentos (identificador alinhado a funcionarios.py)."""
    print("INICIANDO INTEGRACAO DE AFASTAMENTOS")
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
                rotulo = _rotulo_registro_afastamento(row)
                print(f"   {rotulo}: {row['dtinicio']} a {row['dtfim']} | {row['obs']}")
                
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
                    print(f"\nCSV FINAL GERADO (cpf + campo_chave conforme .config)")
                    print(f"Arquivo: afastamentos_api.csv")
                    
                    # Mostrar todos os registros
                    try:
                        df = pd.read_csv('afastamentos_api.csv', sep=';')
                        print(f"\nTODOS OS REGISTROS ({len(df)}):")
                        for i, row in df.iterrows():
                            rotulo = _rotulo_registro_afastamento(row)
                            print(f"   {rotulo}: {row['dtinicio']} a {row['dtfim']} | {row['obs']}")
                            
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
        print("EXECUTANDO INTEGRACAO DE AFASTAMENTOS")
        sucesso = processar_integracao_completa()
        if sucesso:
            print(f"\nINTEGRACAO CONCLUIDA!")
        else:
            print(f"\nINTEGRACAO FALHOU")