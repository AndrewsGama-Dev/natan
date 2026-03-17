import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import configparser
import xml.etree.ElementTree as ET
import os
from config_reader import obter_headers_api, ler_token_config

def carregar_configuracoes_soap():
    """
    Funcao para carregar configuracoes SOAP do arquivo .config
    """
    config = configparser.ConfigParser(interpolation=None)
    config.read('.config')
    
    if not config.has_section('SOAP'):
        print("Secao [SOAP] nao encontrada no arquivo .config")
        return None
    
    return {
        'url': config.get('SOAP', 'url'),
        'client_id': config.get('SOAP', 'client_id'),
        'usuario': config.get('SOAP', 'usuario'),
        'senha': config.get('SOAP', 'senha')
    }

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

def buscar_funcionario_matricula(funcionario_id, headers):
    """
    Busca a matricula (codigo) do funcionario atraves do ID
    ATUALIZADO: Agora os dados ja vem completos da consulta principal
    """
    # Nao precisa mais buscar, os dados ja vem na consulta principal
    return str(funcionario_id).zfill(6)

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

def mapear_demissao_para_csv(funcionario_demitido, headers):
    """
    Mapeia funcionario demitido da API para o formato esperado no CSV com matricula composta
    ATUALIZADO: Agora usa dados diretos dos funcionarios demitidos e matricula composta
    """
    attributes = funcionario_demitido.get('attributes', {})
    funcionario_id = funcionario_demitido.get('id', '')
    
    # Dados ja disponiveis na consulta principal
    codigo = attributes.get('codigo', funcionario_id)
    data_demissao_iso = attributes.get('demissao', '')
    
    # BUSCAR CODIGO DA EMPRESA
    cod_empresa = buscar_dados_empresa(funcionario_id, headers)
    print(f"\nMapeando funcionario {codigo} - Empresa: {cod_empresa}")
    
    # FORMATAR MATRICULA COMPOSTA
    matricula_composta = formatar_matricula_composta(cod_empresa, codigo)
    
    # Calcular datas baseadas na data real de demissao
    data_demissao, data_aviso, data_ultimo_dia, data_acerto = calcular_datas_demissao(data_demissao_iso)
    
    # Mapeamento dos campos conforme a query original - USANDO MATRICULA COMPOSTA
    demissao_csv = {
        'matricula': matricula_composta,  # Matricula composta: cod_empresabmatricula
        'DATA_DEMISSAO': data_demissao,  # Data real de demissao
        'obs': 'Demissao',  # Valor fixo
        'data_aviso': data_aviso,  # 30 dias antes da demissao
        'data_ultimo_dia_trabalhado': data_ultimo_dia,  # Mesmo dia da demissao
        'data_acerto': data_acerto,  # 10 dias apos demissao
        'motivo': 'Demissao',  # Valor fixo
        'local_exame': '',  # Campo vazio conforme query
        'opcao_empregado': '',  # Campo vazio conforme query
        'tipo_aviso': 'Indenizado',  # Tipo padrao
        'devolveu_cracha': 'Sim',  # Valor padrao
        'dias_indenizados': 0,  # Valor padrao
        'data_exame': ''  # Campo vazio conforme query
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

# =================== FUNCOES SOAP ===================

def construir_xml_demissao(matricula, data_demissao, soap_config):
    """Constroi o XML de demissao no formato SOAP para um unico funcionario"""
    soap_xml = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:ifPonto">
    <soapenv:Header/>
    <soapenv:Body>
        <urn:demissao>
            <urn:pack>
                <urn:clientId>{soap_config['client_id']}</urn:clientId>
                <urn:user>{soap_config['usuario']}</urn:user>
                <urn:pass>{soap_config['senha']}</urn:pass>
                <urn:funcionario>
                    <urn:matricula>{matricula}</urn:matricula>
                    <urn:dtdemissao>{data_demissao}</urn:dtdemissao>
                </urn:funcionario>
            </urn:pack>
        </urn:demissao>
    </soapenv:Body>
</soapenv:Envelope>"""
    return soap_xml

def enviar_demissao_soap(xml_data, soap_url):
    """Envia o XML para o webservice SOAP"""
    headers = {'Content-Type': 'text/xml; charset=utf-8'}
    try:
        response = requests.post(
            soap_url,
            data=xml_data,
            headers=headers,
            timeout=10
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"Erro na comunicacao com o webservice SOAP: {str(e)}")
        return None

def salvar_xml_demissao(xml_data, matricula, tipo="request"):
    """Salva o XML de demissao localmente para registro"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"demissao_{tipo}_{matricula}_{timestamp}.xml"
    
    # Criar diretorio se nao existir
    os.makedirs('logs_demissao', exist_ok=True)
    filepath = os.path.join('logs_demissao', filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(xml_data)
    
    print(f"XML de demissao ({tipo}) salvo em: {filepath}")
    return filepath

def analisar_resposta_soap(resposta_xml):
    """
    Analisa a resposta XML do SOAP para determinar se foi bem-sucedida
    """
    try:
        # Parse do XML
        root = ET.fromstring(resposta_xml)
        
        # Namespaces baseados na resposta real
        namespaces = {
            'soap-env': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns1': 'urn:ifPonto'
        }
        
        # Procurar por SOAP Fault primeiro
        soap_fault = root.find('.//soap-env:Fault', namespaces) or root.find('.//Fault')
        if soap_fault is not None:
            fault_string = soap_fault.find('faultstring')
            fault_msg = fault_string.text if fault_string is not None else "Erro SOAP desconhecido"
            return False, f"SOAP Fault: {fault_msg}"
        
        # Procurar por ResultArray e result
        result_array = root.find('.//ns1:ResultArray', namespaces)
        if result_array is not None:
            results = result_array.findall('ns1:result', namespaces)
            
            if results:
                for result in results:
                    # Procurar por descricao
                    descricao_elem = result.find('ns1:descricao', namespaces)
                    if descricao_elem is not None:
                        descricao = descricao_elem.text
                        
                        if descricao:
                            descricao_lower = descricao.lower()
                            
                            # Indicadores de sucesso
                            sucessos = ['sucesso', 'ok', 'processado', 'realizado', 'concluido', 'gravado', 'salvo', 'demitido']
                            if any(palavra in descricao_lower for palavra in sucessos):
                                return True, descricao
                            
                            # Indicadores de erro
                            erros = ['erro', 'falha', 'invalido', 'negado', 'nao encontrado', 'ja existe']
                            if any(palavra in descricao_lower for palavra in erros):
                                return False, descricao
                    
                    # Procurar por outros campos
                    for campo in ['ns1:status', 'ns1:codigo', 'ns1:retorno']:
                        elem = result.find(campo, namespaces)
                        if elem is not None:
                            valor = elem.text
                            
                            if valor and valor.lower() in ['ok', 'sucesso', '1', 'true', 'sim']:
                                return True, valor
                            elif valor and valor.lower() in ['erro', 'falha', '0', 'false', 'nao', 'não']:
                                return False, valor
                
                return True, "Resposta processada sem erros aparentes"
        
        # Procurar qualquer elemento que possa indicar resultado
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if elem.text and any(campo in tag_name.lower() for campo in ['result', 'response', 'return']):
                
                if elem.text:
                    texto_lower = elem.text.lower()
                    if any(palavra in texto_lower for palavra in ['sucesso', 'ok', 'processado']):
                        return True, elem.text
                    elif any(palavra in texto_lower for palavra in ['erro', 'falha', 'invalido']):
                        return False, elem.text
        
        return True, "Status indeterminado - XML valido sem SOAP Fault"
            
    except ET.ParseError as e:
        return False, f"Erro de parse XML: {e}"
    except Exception as e:
        return False, f"Erro na analise: {e}"

def enviar_demissoes_via_soap(demissoes_csv):
    """
    Envia as demissoes via SOAP
    """
    print("\n" + "="*60)
    print("ENVIANDO DEMISSOES VIA SOAP")
    print("="*60)
    
    # Carregar configuracoes SOAP
    soap_config = carregar_configuracoes_soap()
    if not soap_config:
        print("Falha ao carregar configuracoes SOAP")
        return False
    
    print(f"Configuracoes SOAP:")
    print(f"   URL: {soap_config['url']}")
    print(f"   Client ID: {soap_config['client_id']}")
    print(f"   Usuario: {soap_config['usuario']}")
    
    sucessos = 0
    erros = 0
    
    print(f"\nProcessando {len(demissoes_csv)} demissoes via SOAP...")
    print("-" * 50)
    
    for i, demissao in enumerate(demissoes_csv, 1):
        matricula = demissao.get('matricula')
        data_demissao = demissao.get('DATA_DEMISSAO')
        
        if not matricula or not data_demissao:
            print(f"Demissao {i}: Dados incompletos - Matricula: {matricula}, Data: {data_demissao}")
            erros += 1
            continue
        
        print(f"\nProcessando demissao {i}/{len(demissoes_csv)}:")
        print(f"   Matricula: {matricula}")
        print(f"   Data: {data_demissao}")
        
        # Construir XML de requisicao
        xml_demissao = construir_xml_demissao(matricula, data_demissao, soap_config)
        
        # Salvar XML da requisicao
        salvar_xml_demissao(xml_demissao, matricula, "request")
        
        # Enviar via SOAP
        resposta = enviar_demissao_soap(xml_demissao, soap_config['url'])
        
        if resposta and resposta.status_code == 200:
            print(f"Requisicao enviada com sucesso!")
            print(f"Status HTTP: {resposta.status_code}")
            
            # Salvar XML da resposta
            salvar_xml_demissao(resposta.text, matricula, "response")
            
            # Analisar a resposta XML
            sucesso, mensagem = analisar_resposta_soap(resposta.text)
            
            if sucesso:
                sucessos += 1
                print(f"Demissao da matricula {matricula} processada com sucesso!")
                print(f"Mensagem: {mensagem}")
            else:
                print(f"Erro no processamento da matricula {matricula}")
                print(f"Mensagem: {mensagem}")
                erros += 1
                
        else:
            print(f"Erro ao enviar demissao {i}")
            if resposta:
                print(f"Status HTTP: {resposta.status_code}")
                print(f"Resposta: {resposta.text[:200]}...")
            erros += 1
        
        print("-" * 30)
        time.sleep(1)  # Pausa entre requisicoes
    
    # Resumo final
    print(f"\nRESUMO DO ENVIO SOAP:")
    print(f"Sucessos: {sucessos}")
    print(f"Erros: {erros}")
    print(f"Total processadas: {len(demissoes_csv)}")
    
    return sucessos > 0

# =================== FUNCAO PRINCIPAL ===================

def gerar_csv_demissoes():
    """
    Funcao principal para gerar o CSV das demissoes com matricula composta
    """
    print("=" * 80)
    print("         GERACAO DE CSV DE DEMISSOES COM MATRICULA COMPOSTA - API eContador")
    print("=" * 80)
    
    # Verificar se token esta disponivel
    token = ler_token_config()
    if not token:
        print("Falha ao carregar token do arquivo .config")
        return None
    
    # Coletar funcionarios demitidos da API (ENDPOINT CORRETO)
    funcionarios_demitidos, headers = consultar_funcionarios_demitidos()
    
    if not funcionarios_demitidos:
        print("Nenhum funcionario demitido foi coletado da API")
        return None
    
    # Filtrar demissoes recentes (desde janeiro de 2025)
    demissoes_filtradas = filtrar_demissoes_recentes(funcionarios_demitidos, '2025-01-01')
    print(f"Demissoes filtradas desde 01/01/2025: {len(demissoes_filtradas)}")
    
    if not demissoes_filtradas:
        print("Nenhuma demissao recente encontrada")
        print("Tentando processar todas as demissoes disponiveis...")
        demissoes_filtradas = funcionarios_demitidos
    
    print(f"\nConvertendo {len(demissoes_filtradas)} demissoes para formato CSV...")
    print("   (Usando dados reais de demissao da API)")
    
    # Converter para formato CSV
    demissoes_csv = []
    erros = []
    funcionarios_processados = set()
    
    for i, funcionario_demitido in enumerate(demissoes_filtradas, 1):
        try:
            demissao_csv = mapear_demissao_para_csv(funcionario_demitido, headers)
            
            # Filtrar apenas registros com matricula valida
            if demissao_csv['matricula']:
                demissoes_csv.append(demissao_csv)
                funcionarios_processados.add(demissao_csv['matricula'])
            
            if i % 10 == 0:
                print(f"  Processadas {i}/{len(demissoes_filtradas)} demissoes... (Funcionarios: {len(funcionarios_processados)})")
                
        except Exception as e:
            erros.append({'id': funcionario_demitido.get('id', 'N/A'), 'erro': str(e)})
            print(f"  Erro ao processar funcionario {funcionario_demitido.get('id', 'N/A')}: {e}")
    
    if not demissoes_csv:
        print("Nenhuma rescisao foi convertida com sucesso")
        return None
    
    # Criar DataFrame
    print(f"\nCriando DataFrame com {len(demissoes_csv)} demissoes...")
    print(f"   Funcionarios unicos demitidos: {len(funcionarios_processados)}")
    
    df = pd.DataFrame(demissoes_csv)
    
    # Gerar arquivo CSV
    nome_arquivo = "demissoes_api.csv"
    
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
        
        return demissoes_csv  # Retornar dados para uso no SOAP
        
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
        
        # Verificar funcionarios unicos
        if 'matricula' in df.columns:
            funcionarios_unicos = df['matricula'].nunique()
            print(f"  Funcionarios unicos demitidos: {funcionarios_unicos}")
        
        print(f"  Validacao concluida")
        
    except Exception as e:
        print(f"  Erro na validacao: {e}")

def processar_integracao_completa():
    """
    Funcao principal que executa todo o processo: API -> CSV -> SOAP
    """
    print("=" * 80)
    print("    INTEGRACAO COMPLETA DE DEMISSOES - eContador -> CSV -> SOAP")
    print("=" * 80)
    
    # Etapa 1: Gerar CSV das demissoes
    print("\nETAPA 1: Coletando demissoes da API eContador...")
    demissoes_csv = gerar_csv_demissoes()
    
    if not demissoes_csv:
        print("Falha na geracao dos dados. Processo interrompido.")
        return False
    
    # Etapa 2: Validar dados do CSV
    print("\nETAPA 2: Validando dados...")
    validar_dados_demissoes_csv("demissoes_api.csv")
    
    # Etapa 3: Enviar via SOAP
    print("\nETAPA 3: Enviando demissoes via SOAP...")
    sucesso_soap = enviar_demissoes_via_soap(demissoes_csv)
    
    if sucesso_soap:
        print("\nINTEGRACAO COMPLETA FINALIZADA COM SUCESSO!")
        print(f"Demissoes coletadas da API eContador")
        print(f"CSV gerado: demissoes_api.csv")
        print(f"Demissoes enviadas via SOAP")
        print(f"XMLs salvos em: logs_demissao/")
        
        # Mostrar todos os registros gerados
        try:
            df = pd.read_csv('demissoes_api.csv', sep=';')
            print(f"\nREGISTROS GERADOS ({len(df)} total):")
            for i, row in df.iterrows():
                print(f"   {row['matricula']}: {row['DATA_DEMISSAO']} | {row['obs']}")
                
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
            
        return True
    else:
        print("\nFALHA NA INTEGRACAO!")
        print(f"CSV gerado: demissoes_api.csv")
        print(f"Falha no envio via SOAP")
        return False

# Exemplo de uso
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        comando = sys.argv[1].lower()
        
        if comando == "completo" or comando == "integracao":
            # Processo completo: API -> CSV -> SOAP
            sucesso = processar_integracao_completa()
            
        elif comando == "csv":
            # Apenas gerar CSV
            dados = gerar_csv_demissoes()
            if dados:
                print(f"\nCSV GERADO COM MATRICULA COMPOSTA!")
                print(f"Arquivo: demissoes_api.csv")
                
                # Mostrar todos os registros
                try:
                    df = pd.read_csv('demissoes_api.csv', sep=';')
                    print(f"\nTODOS OS REGISTROS ({len(df)}):")
                    for i, row in df.iterrows():
                        print(f"   {row['matricula']}: {row['DATA_DEMISSAO']} | {row['obs']}")
                        
                except Exception as e:
                    print(f"Erro ao analisar CSV: {e}")
                    
        elif comando == "enviar":
            # Apenas enviar via SOAP
            nome_arquivo = sys.argv[2] if len(sys.argv) > 2 else "demissoes_api.csv"
            if os.path.exists(nome_arquivo):
                # Carregar dados do CSV para enviar via SOAP
                try:
                    df = pd.read_csv(nome_arquivo, sep=';')
                    demissoes_data = df.to_dict('records')
                    resultado = enviar_demissoes_via_soap(demissoes_data)
                    if resultado:
                        print(f"\nARQUIVO ENVIADO COM SUCESSO VIA SOAP!")
                    else:
                        print(f"\nFALHA NO ENVIO VIA SOAP!")
                except Exception as e:
                    print(f"Erro ao processar arquivo: {e}")
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