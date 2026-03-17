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

def ler_campo_chave_config():
    """
    Lê o campo_chave da seção [FUNCIONARIOS] do arquivo .config
    """
    try:
        config = configparser.ConfigParser()
        config.read('.config', encoding='utf-8')
        
        if 'FUNCIONARIOS' in config and 'campo_chave' in config['FUNCIONARIOS']:
            campo_chave = config['FUNCIONARIOS']['campo_chave'].strip()
            print(f"Campo chave carregado do .config: {campo_chave}")
            return campo_chave
        else:
            print("Campo 'campo_chave' nao encontrado, usando padrao: 'matricula'")
            return 'matricula'
    except Exception as e:
        print(f"Erro ao ler campo_chave: {e}")
        return 'matricula'

def carregar_configuracoes_target():
    """
    Carrega configuracoes da secao [APITARGET] do arquivo .config
    """
    try:
        config = configparser.ConfigParser()
        config.read('.config', encoding='utf-8')
        
        if 'APITARGET' not in config:
            print("Secao [APITARGET] nao encontrada no arquivo .config")
            return None
        
        return {
            'url': config['APITARGET'].get('url', '').strip(),
            'integracao': config['APITARGET'].get('integracao', '').strip(),
            'token_base': config['APITARGET'].get('token_base', '').strip()
        }
    except Exception as e:
        print(f"Erro ao carregar configuracoes [APITARGET]: {e}")
        return None

def gerar_token_target():
    """
    Gera o token para a API de destino usando a data atual
    """
    config_target = carregar_configuracoes_target()
    if not config_target:
        return None, None
    
    # Configurar timezone para Sao Paulo
    tz_sao_paulo = pytz.timezone('America/Sao_Paulo')
    data_atual = datetime.now(tz_sao_paulo).strftime('%d/%m/%Y')
    
    # Gerar token final
    token_concatenado = config_target['token_base'] + data_atual
    token_final = hashlib.sha256(token_concatenado.encode('utf-8')).hexdigest()
    
    print(f"Data atual: {data_atual}")
    print(f"Token base: {config_target['token_base']}")
    print(f"Token final gerado: {token_final[:32]}...")
    
    return config_target, token_final

def formatar_cpf_11_digitos(cpf):
    """
    Formata CPF para garantir 11 digitos com zeros a esquerda
    """
    if not cpf:
        return ""
    
    # Converter para string e remover caracteres nao numericos
    cpf_str = str(cpf).replace('.', '').replace('-', '').replace('/', '').strip()
    
    # Se nao for numerico ou estiver vazio, retornar vazio
    if not cpf_str.isdigit():
        return ""
    
    # Completar com zeros a esquerda para 11 digitos
    cpf_formatado = cpf_str.zfill(11)
    
    # Validar se tem exatamente 11 digitos
    if len(cpf_formatado) == 11:
        return cpf_formatado
    
    return ""

def formatar_matricula_simples(matricula_original):
    """
    Formata a matricula com 6 digitos (zeros a esquerda)
    Exemplo: matricula=2 -> 000002
    """
    try:
        # Garantir que a matricula tenha 6 digitos com zeros a esquerda
        matricula_6_digitos = str(matricula_original).zfill(6)
        
        print(f"    Matricula original: {matricula_original}")
        print(f"    Matricula formatada: {matricula_6_digitos}")
        
        return matricula_6_digitos
        
    except Exception as e:
        print(f"    Erro ao formatar matricula: {e}")
        return str(matricula_original).zfill(6)

def enviar_csv_para_api_target(nome_arquivo_csv):
    """
    Envia o CSV de funcionarios para a API da Hevi
    """
    import os
    
    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} nao encontrado!")
        return False
    
    print(f"Arquivo {nome_arquivo_csv} encontrado")
    
    # Obter configuracoes e token
    config_target, token_final = gerar_token_target()
    if not config_target or not token_final:
        print("Falha ao gerar token para API de destino")
        return False
    
    usuario_integracao = config_target['integracao']
    
    headers = {
        "user": usuario_integracao,
        "token": token_final
    }
    
    data = {
        "pag": "funcionario_cadastrar",
        "cmd": "importar_cad",
        "separador": ";"
    }
    
    try:
        print(f"Enviando POST para API da Hevi...")
        print(f"URL: {config_target['url']}")
        print(f"Usuario: {usuario_integracao}")
        print(f"Endpoint: funcionario_cadastrar")
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
                timeout=90
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
                    print(f"POST de funcionarios realizado com sucesso!")
                    print(f"Resposta da API:")
                    print(json.dumps(resultado, indent=2, ensure_ascii=False))
                    
                    cadastrados = resultado.get('ok', 0)
                    if cadastrados > 0:
                        print(f"{cadastrados} funcionario(s) cadastrado(s) com sucesso!")
                    
                    return True
                
            except json.JSONDecodeError:
                print(f"Resposta nao e JSON valido:")
                print(f"Resposta: {response.text[:500]}...")
                return False
                
        else:
            print(f"ERRO no POST - Status: {response.status_code}")
            print(f"Resposta: {response.text[:500]}...")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"ERRO na requisicao para API da Hevi: {e}")
        return False

def buscar_dados_empresa(funcionario_id, headers):
    """
    Busca informacoes da empresa do funcionario
    """
    try:
        url_empresa = f"https://dp.pack.alterdata.com.br/api/v1/funcionarios/{funcionario_id}/empresa"
        response = requests.get(url_empresa, headers=headers)
        
        if response.status_code == 200:
            empresa_data = response.json()
            empresa_info = empresa_data.get('data', {})
            if empresa_info:
                attributes = empresa_info.get('attributes', {})
                return {
                    'id': empresa_info.get('id', ''),
                    'codigo': attributes.get('codigo', ''),
                    'nome': attributes.get('nome', ''),
                    'cnpj': attributes.get('cnpj', '')
                }
    except Exception as e:
        pass
    
    return None

def extrair_codigo_departamento(externoid, nome, cei, id_departamento):
    """
    Para seguir o padrao da query SQL que funciona, usar o ID do departamento
    """
    # Na query SQL que funciona, eles usam: col.ID_CENTRO_CUSTO AS codigo_unidade
    # Entao vamos usar o ID do departamento diretamente
    if id_departamento:
        return str(id_departamento)
    
    # Estrategia alternativa: externoid valido
    if externoid and len(externoid) < 15 and not externoid.startswith('ZZZG7') and externoid != '':
        return externoid
    
    # Extrair codigo do nome se possivel
    if nome and ' - ' in nome:
        partes = nome.split(' - ', 1)
        if len(partes) >= 2:
            possivel_codigo = partes[0].strip()
            if possivel_codigo.isdigit() and len(possivel_codigo) <= 6:
                return possivel_codigo
    
    # Fallback
    return str(id_departamento) if id_departamento else "1"

def extrair_nome_limpo_departamento(nome):
    """
    Extrai apenas o nome do departamento, removendo codigos
    """
    if not nome:
        return ""
    
    if ' - ' in nome:
        partes = nome.split(' - ', 1)
        if len(partes) >= 2:
            return partes[1].strip()
    
    return nome.strip()

def extrair_nome_limpo_cargo(nome_funcao):
    """
    Extrai apenas o nome do cargo, removendo codigos
    """
    if not nome_funcao:
        return ""
    
    if ' - ' in nome_funcao:
        partes = nome_funcao.split(' - ', 1)
        if len(partes) >= 2:
            return partes[1].strip()
    
    return nome_funcao.strip()

def buscar_dados_departamento(funcionario_id, headers):
    """
    Busca informacoes do departamento do funcionario
    """
    try:
        # Primeira tentativa: buscar funcionario com include do departamento
        url_funcionario = f"https://dp.pack.alterdata.com.br/api/v1/funcionarios/{funcionario_id}?include=departamento"
        response = requests.get(url_funcionario, headers=headers)
        
        if response.status_code == 200:
            funcionario_data = response.json()
            
            # Verificar se ha dados included (departamento)
            included = funcionario_data.get('included', [])
            for item in included:
                if item.get('type') == 'departamentos':
                    attributes = item.get('attributes', {})
                    externoid = attributes.get('externoid', '')
                    nome = attributes.get('nome', '')
                    cei = attributes.get('cei', '')
                    
                    codigo_final = extrair_codigo_departamento(externoid, nome, cei, item.get('id', ''))
                    
                    return {
                        'id': item.get('id', ''),
                        'codigo': codigo_final,
                        'nome': extrair_nome_limpo_departamento(nome),
                        'cei': cei
                    }
            
            # Se nao encontrou nos included, verificar relationships
            data_list = funcionario_data.get('data', [])
            if isinstance(data_list, list) and data_list:
                relationships = data_list[0].get('relationships', {})
            elif isinstance(data_list, dict):
                relationships = data_list.get('relationships', {})
            else:
                relationships = {}
                
            departamento_rel = relationships.get('departamento', {})
            departamento_data = departamento_rel.get('data')
            
            if departamento_data:
                departamento_id = departamento_data.get('id')
                if departamento_id:
                    # Buscar departamento diretamente
                    url_departamento = f"https://dp.pack.alterdata.com.br/api/v1/departamentos/{departamento_id}"
                    dept_response = requests.get(url_departamento, headers=headers)
                    
                    if dept_response.status_code == 200:
                        dept_data = dept_response.json()
                        dept_attributes = dept_data.get('data', {}).get('attributes', {})
                        
                        externoid = dept_attributes.get('externoid', '')
                        nome = dept_attributes.get('nome', '')
                        cei = dept_attributes.get('cei', '')
                        
                        codigo_final = extrair_codigo_departamento(externoid, nome, cei, departamento_id)
                        
                        return {
                            'id': departamento_id,
                            'codigo': codigo_final,
                            'nome': extrair_nome_limpo_departamento(nome),
                            'cei': cei
                        }
        
        # Segunda tentativa: buscar departamento atraves do endpoint direto
        url_departamento_funcionario = f"https://dp.pack.alterdata.com.br/api/v1/funcionarios/{funcionario_id}/departamento"
        dept_response = requests.get(url_departamento_funcionario, headers=headers)
        
        if dept_response.status_code == 200:
            dept_data = dept_response.json()
            dept_info = dept_data.get('data', {})
            if dept_info:
                attributes = dept_info.get('attributes', {})
                
                externoid = attributes.get('externoid', '')
                nome = attributes.get('nome', '')
                cei = attributes.get('cei', '')
                
                codigo_final = extrair_codigo_departamento(externoid, nome, cei, dept_info.get('id', ''))
                
                return {
                    'id': dept_info.get('id', ''),
                    'codigo': codigo_final,
                    'nome': extrair_nome_limpo_departamento(nome),
                    'cei': cei
                }
                        
    except Exception as e:
        print(f"Erro ao buscar departamento do funcionario {funcionario_id}: {e}")
    
    return None

def consultar_todos_funcionarios_para_csv():
    """
    Coleta APENAS funcionarios ATIVOS da API
    """
    print("INICIANDO COLETA DE FUNCIONARIOS ATIVOS PARA CSV...")
    
    headers = obter_headers_api()
    if not headers:
        print("Nao foi possivel obter o token do arquivo .config")
        return [], None
    
    base_url = "https://dp.pack.alterdata.com.br/api/v1/funcionarios"
    
    params = {
        "filter[status]": "ativo",
        "sort": "codigo",
        "page[limit]": "100"
    }
    
    todos_funcionarios = []
    url_atual = base_url
    pagina = 1
    tentativas_sem_dados = 0
    max_tentativas_sem_dados = 3
    
    while url_atual and tentativas_sem_dados < max_tentativas_sem_dados:
        try:
            print(f"  Coletando pagina {pagina}... ", end="")
            
            if pagina == 1:
                response = requests.get(url_atual, headers=headers, params=params, timeout=30)
            else:
                response = requests.get(url_atual, headers=headers, timeout=30)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                funcionarios_pagina = data.get('data', [])
                
                if funcionarios_pagina:
                    todos_funcionarios.extend(funcionarios_pagina)
                    print(f"    {len(funcionarios_pagina)} funcionarios ATIVOS coletados (Total: {len(todos_funcionarios)})")
                    tentativas_sem_dados = 0
                    
                    links = data.get('links', {})
                    url_atual = links.get('next')
                    
                    if url_atual:
                        print(f"    Proxima pagina: {url_atual[:80]}...")
                    else:
                        print(f"    Ultima pagina alcancada")
                        break
                        
                    pagina += 1
                    time.sleep(0.2)
                else:
                    print(f"    Pagina sem dados")
                    tentativas_sem_dados += 1
                    break
                    
            elif response.status_code == 429:
                print(f"    Rate limit - aguardando 10 segundos...")
                time.sleep(10)
                continue
            else:
                print(f"    Erro {response.status_code}: {response.text[:100]}")
                tentativas_sem_dados += 1
                break
                
        except requests.exceptions.RequestException as e:
            print(f"    Erro na conexao: {e}")
            tentativas_sem_dados += 1
            time.sleep(2)
    
    print(f"\nCOLETA FINALIZADA:")
    print(f"  Total de funcionarios ATIVOS coletados: {len(todos_funcionarios)}")
    print(f"  Paginas processadas: {pagina - 1}")
    
    return todos_funcionarios, headers

def formatar_data_brasileira(data_iso):
    """
    Converte data ISO para formato brasileiro DD/MM/AAAA
    """
    if not data_iso:
        return ""
    
    try:
        data_str = data_iso.replace('Z', '').split('T')[0]
        data_obj = datetime.strptime(data_str, '%Y-%m-%d')
        return data_obj.strftime('%d/%m/%Y')
    except Exception as e:
        return ""

def mapear_funcionario_para_csv(funcionario_api, headers=None):
    """
    Mapeia um funcionario da API para o formato esperado no CSV com matricula simples (6 digitos)
    """
    attributes = funcionario_api.get('attributes', {})
    funcionario_id = funcionario_api.get('id', '')
    
    # Ler campo_chave do .config
    campo_chave = ler_campo_chave_config()
    
    # PRIMEIRO: Formatar CPF com 11 digitos (zeros a esquerda)
    cpf_formatado = formatar_cpf_11_digitos(attributes.get('cpf', ''))
    
    # SEGUNDO: Usar o campo 'codigo' dos atributos
    codigo_funcionario = attributes.get('codigo', '')
    if not codigo_funcionario:
        # Fallback para o ID se nao tiver codigo
        codigo_funcionario = str(funcionario_id)
    
    # TERCEIRO: Buscar dados do departamento
    departamento_info = None
    
    if headers and funcionario_id:
        departamento_info = buscar_dados_departamento(funcionario_id, headers)
    
    print(f"\nMapeando funcionario {codigo_funcionario}")
    
    # QUARTO: FORMATAR MATRICULA SIMPLES (6 digitos)
    matricula_simples = formatar_matricula_simples(codigo_funcionario)
    
    # QUINTO: Por enquanto sempre usar senha padrao
    senha_padrao = 'Ponto123'
    
    # SEXTO: Mapeamento dos campos do CSV
    funcionario_csv = {
        'campo_chave': campo_chave,  # Valor lido do .config
        'nome': attributes.get('nome', ''),
        'cpf': cpf_formatado,  # CPF formatado com 11 digitos
        'matricula': matricula_simples,  # Matricula simples: 6 digitos
        'rg': attributes.get('identidade', ''),
        'pis': attributes.get('pis', '') or cpf_formatado,  # CPF como fallback
        'dtadmissao': formatar_data_brasileira(attributes.get('admissao')),
        'cnh': '',
        'email': attributes.get('email', ''),
        'nome_tipo_pessoa': '',
        'telefone': '',
        'ramal': '',
        'endereco': attributes.get('rua', ''),
        'bairro': '',
        'cidade': attributes.get('cidade', ''),
        'uf': '',
        'cep': attributes.get('cep', ''),
        'login': cpf_formatado,  # CPF formatado
        'dtdemissao': '',
        'regime_juridico': '',
        'tipo_salario': '',
        'salario': str(attributes.get('salarioBase', '')),
        'dtnascimento': formatar_data_brasileira(attributes.get('nascimento')),
        'nome_mae': '',
        'nome_pai': '',
        'escolaridade': '',
        'estado_civil': '',
        'qtd_filho': '',
        'sexo': '',
        'nacionalidade': '',
        'naturalidade': '',
        'complemento': '',
        'codigo_unidade': departamento_info.get('id', '') if departamento_info else '',
        'nome_unidade': extrair_nome_limpo_departamento(departamento_info.get('nome', '')) if departamento_info else '',
        'codigo_cargo': '',  # Sera preenchido abaixo
        'nome_cargo': extrair_nome_limpo_cargo(attributes.get('nomefuncao', '')),
        'senha': senha_padrao,
        'cracha': cpf_formatado,  # CPF formatado
        'nome_nivel': '',
        'cod_escala_padrao': '',
        'codigo_escala': '',
        'dtinicio_escala': '',
        'empresa': '',
        'nome_funcao': extrair_nome_limpo_cargo(attributes.get('nomefuncao', '')),
        'codigo_legado_funcao': '',  # Sera preenchido abaixo
        'nro_centro_custo': departamento_info.get('id', '') if departamento_info else '',
        'codigo_legado_centro_custo': departamento_info.get('id', '') if departamento_info else '',
        'nome_centro_custo': extrair_nome_limpo_departamento(departamento_info.get('nome', '')) if departamento_info else '',
        'cod_sindicato': '',
        'nome_sindicato': '',
        'timezone': 'America/Manaus'
    }
    
    # Extrair codigo do cargo do campo nomefuncao
    nome_funcao = attributes.get('nomefuncao', '')
    if nome_funcao and ' - ' in nome_funcao:
        try:
            partes = nome_funcao.split(' - ', 1)
            if len(partes) >= 2:
                codigo_funcao = partes[0].strip()
                if codigo_funcao:
                    funcionario_csv['codigo_cargo'] = codigo_funcao
                    funcionario_csv['codigo_legado_funcao'] = codigo_funcao
        except Exception as e:
            pass
    
    return funcionario_csv

def gerar_csv_funcionarios():
    """
    Funcao principal para gerar o CSV dos funcionarios ATIVOS com matricula simples (6 digitos)
    """
    print("=" * 80)
    print("         GERACAO DE CSV DE FUNCIONARIOS ATIVOS - API eContador")
    print("=" * 80)
    
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    funcionarios_api, headers = consultar_todos_funcionarios_para_csv()
    
    if not funcionarios_api:
        print("Nenhum funcionario ATIVO foi coletado da API")
        return
    
    print(f"\nConvertendo {len(funcionarios_api)} funcionarios ATIVOS para formato CSV...")
    
    funcionarios_csv = []
    erros = []
    
    for i, funcionario_api in enumerate(funcionarios_api, 1):
        try:
            funcionario_csv = mapear_funcionario_para_csv(funcionario_api, headers)
            funcionarios_csv.append(funcionario_csv)
            
            if i % 10 == 0:
                print(f"  Processados {i}/{len(funcionarios_api)} funcionarios...")
                time.sleep(0.5)
                
        except Exception as e:
            erros.append({'id': funcionario_api.get('id', 'N/A'), 'erro': str(e)})
            print(f"  Erro ao processar funcionario {funcionario_api.get('id', 'N/A')}: {e}")
    
    if not funcionarios_csv:
        print("Nenhum funcionario foi convertido com sucesso")
        return
    
    print(f"\nCriando DataFrame com {len(funcionarios_csv)} funcionarios...")
    df = pd.DataFrame(funcionarios_csv)
    
    nome_arquivo = "funcionarios_api.csv"
    
    try:
        df.to_csv(nome_arquivo, index=False, encoding='utf-8-sig', sep=';')
        print(f"CSV gerado com sucesso: {nome_arquivo}")
        
        print(f"\nESTATISTICAS:")
        print(f"  Total de funcionarios processados: {len(funcionarios_csv)}")
        print(f"  Erros de conversao: {len(erros)}")
        print(f"  Colunas no CSV: {len(df.columns)}")
        
        print(f"\nPREVIEW DOS DADOS (primeiras 3 linhas):")
        print(df.head(3).to_string())
        
        # Mostrar alguns registros
        try:
            print(f"\nREGISTROS GERADOS ({len(df)} total) - Primeiros 5:")
            for i, row in df.head(5).iterrows():
                print(f"   {row['nome']} - Matricula: {row['matricula']} - Campo Chave: {row['campo_chave']}")
        except Exception as e:
            print(f"Erro ao mostrar registros: {e}")
        
        return nome_arquivo
        
    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None

def validar_dados_csv(nome_arquivo):
    """
    Valida os dados do CSV gerado
    """
    if not nome_arquivo:
        return
    
    try:
        print(f"\nVALIDANDO DADOS DO CSV: {nome_arquivo}")
        
        df = pd.read_csv(nome_arquivo, sep=';', encoding='utf-8-sig')
        
        print(f"  Total de registros: {len(df)}")
        print(f"  Total de colunas: {len(df.columns)}")
        
        campos_obrigatorios = ['nome', 'cpf', 'matricula', 'cod_empresa']
        
        for campo in campos_obrigatorios:
            if campo in df.columns:
                vazios = df[campo].isna().sum() + (df[campo] == '').sum()
                if vazios > 0:
                    print(f"  Campo '{campo}': {vazios} registros vazios")
                else:
                    print(f"  Campo '{campo}': todos preenchidos")
        
        print(f"  Validacao concluida")
        
    except Exception as e:
        print(f"  Erro na validacao: {e}")

def processar_integracao_completa():
    """
    Funcao principal que executa todo o processo
    """
    print("=" * 80)
    print("    INTEGRACAO COMPLETA DE FUNCIONARIOS ATIVOS - eContador -> Hevi")
    print("=" * 80)
    
    print("\nETAPA 1: Coletando funcionarios ATIVOS da API eContador...")
    arquivo_csv = gerar_csv_funcionarios()
    
    if not arquivo_csv:
        print("Falha na geracao do CSV. Processo interrompido.")
        return False
    
    print("\nETAPA 2: Validando dados do CSV...")
    validar_dados_csv(arquivo_csv)
    
    print("\nETAPA 3: Enviando CSV para API da Hevi...")
    sucesso_envio = enviar_csv_para_api_target(arquivo_csv)
    
    if sucesso_envio:
        print("\nINTEGRACAO COMPLETA FINALIZADA COM SUCESSO!")
        print(f"Funcionarios ATIVOS coletados da API eContador")
        print(f"CSV gerado: {arquivo_csv}")
        print(f"Dados enviados para sistema Hevi")
        print(f"IMPORTANTE: Matricula usa formato simples de 6 digitos")
        return True
    else:
        print("\nFALHA NA INTEGRACAO!")
        print(f"CSV gerado: {arquivo_csv}")
        print(f"Falha no envio para sistema Hevi")
        return False

# Exemplo de uso
if __name__ == "__main__":
    if len(sys.argv) > 1:
        comando = sys.argv[1].lower()
        
        if comando == "completo" or comando == "integracao":
            sucesso = processar_integracao_completa()
            
        elif comando == "csv":
            arquivo_csv = gerar_csv_funcionarios()
            if arquivo_csv:
                print(f"\nCSV GERADO COM MATRICULA SIMPLES (6 DIGITOS)!")
                print(f"Arquivo: {arquivo_csv}")
                
        else:
            print("Comando invalido! Use:")
            print("  python funcionarios.py completo   # Integracao completa")
            print("  python funcionarios.py csv        # Apenas gerar CSV")
    else:
        sucesso = processar_integracao_completa()
        sys.exit(0 if sucesso else 1)