import configparser
import os

def ler_config():
    """
    Lê o arquivo .config e retorna um dicionário com todas as seções
    """
    try:
        if not os.path.exists('.config'):
            print("❌ Arquivo .config não encontrado")
            return None
        
        config = configparser.ConfigParser()
        config.read('.config', encoding='utf-8')
        
        # Converter para dicionário para facilitar o uso
        config_dict = {}
        for secao in config.sections():
            config_dict[secao] = dict(config[secao])
        
        return config_dict
        
    except Exception as e:
        print(f"❌ Erro ao ler arquivo .config: {e}")
        return None

def ler_token_config():
    """
    Lê especificamente o token da seção APISOURCE
    """
    try:
        config = ler_config()
        if config and 'APISOURCE' in config:
            token = config['APISOURCE'].get('token')
            if token:
                print("Token carregado do arquivo .config")
                return token.strip('"')  # Remove aspas se houver
        
        print("Token nao encontrado na secao [APISOURCE]")
        return None
        
    except Exception as e:
        print(f"Erro ao ler token: {e}")
        return None

def obter_headers_api():
    """
    Obtém os headers necessários para chamadas à API da Alterdata
    """
    token = ler_token_config()
    if not token:
        return None
    
    headers = {
        'Content-Type': 'application/vnd.api+json',
        'Authorization': f'Bearer {token}'
    }
    
    return headers

def ler_campo_chave_funcionarios():
    """
    Lê o campo_chave configurado na seção FUNCIONARIOS do .config
    """
    try:
        config = ler_config()
        if config and 'FUNCIONARIOS' in config:
            campo_chave = config['FUNCIONARIOS'].get('campo_chave', 'matricula')
            print(f"✅ Campo chave carregado: {campo_chave}")
            return campo_chave.strip()
        
        print("⚠️ Seção [FUNCIONARIOS] não encontrada, usando 'matricula' como padrão")
        return 'matricula'
        
    except Exception as e:
        print(f"❌ Erro ao ler campo_chave: {e}")
        return 'matricula'