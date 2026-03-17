# Integração IFPonto ↔ Alterdata (Folha)

Sistema de integração entre o **ponto eletrônico IFPonto** e o **sistema de folha de pagamento Alterdata**.

> **Histórico da análise:** o resumo do que já foi analisado no projeto está em [ANALISE.md](ANALISE.md). Consulte esse arquivo para não perder o contexto ao trocar de pasta ou reabrir o projeto. Sincroniza funcionários, afastamentos, férias e demissões da API Alterdata para o IFPonto (cadastro em massa via API/CSV e demissões via SOAP).

---

## Visão geral do fluxo

| Origem | Destino | O que faz |
|--------|---------|-----------|
| **Alterdata** (API REST `dp.pack.alterdata.com.br`) | **IFPonto** | Funcionários ativos → CSV → POST para API de cadastro |
| **Alterdata** | **IFPonto** | Afastamentos (exceto férias) → CSV → API |
| **Alterdata** | **IFPonto** | Demitidos → CSV + **SOAP** (webservice `urn:ifPonto`) |

- **Funcionários**: matrícula 6 dígitos, CPF 11 dígitos, departamento/cargo da API; envio por CSV para a API de destino (token = SHA256 do `token_base` + data atual).
- **Demissões**: matrícula composta `cod_empresab000002`; envio via SOAP com `clientId`, `usuario`, `senha` do `.config`.
- **Férias** e **afastamentos**: módulos separados (`ferias.py`, `afastamentos.py`); o `main.py` atual só chama funcionários, afastamentos e demissões.

---

## Estrutura do projeto

```
live-integracao/
├── main.py              # Orquestrador: funcionarios → afastamentos → demissoes
├── config_reader.py     # Leitura do .config (token, headers API)
├── funcionarios.py      # Coleta ativos Alterdata → CSV → POST IFPonto
├── afastamentos.py      # Afastamentos (não férias) → CSV → API
├── demissoes.py         # Demitidos → CSV + SOAP IFPonto
├── ferias.py            # Férias (pode ser chamado separado)
├── empresas.py          # Empresas (não usado no main atual)
├── departamentos.py     # Departamentos (não usado no main atual)
├── cargos.py            # Cargos (não usado no main atual)
├── .config              # Configuração local (não versionar)
├── .config.example      # Modelo do .config
├── requirements.txt
├── README.md
└── ANALISE.md           # Histórico da análise do projeto (contexto preservado)
```

---

## Configuração

1. Copie o exemplo de configuração:
   ```bash
   cp .config.example .config
   ```
2. Edite `.config` e preencha:
   - **[APISOURCE]**  
     - `token`: token Bearer da API Alterdata.
   - **[APITARGET]**  
     - `url`, `integracao`, `token_base`: API de cadastro em massa (IFPonto/Hevi). O token do dia é `SHA256(token_base + DD/MM/AAAA)`.
   - **[SOAP]**  
     - `url`, `client_id`, `usuario`, `senha`: webservice SOAP do IFPonto para demissões.
   - **[FUNCIONARIOS]** (opcional)  
     - `campo_chave`: `matricula` ou `cpf`.

---

## Uso local

```bash
# Criar ambiente (recomendado)
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux

pip install -r requirements.txt

# Integração completa (funcionários + afastamentos + demissões)
python main.py

# Apenas gerar CSV de funcionários
python funcionarios.py csv

# Integração só de funcionários
python funcionarios.py completo
```

---

## Subir para o Git

1. Inicialize o repositório (se ainda não existir):
   ```bash
   git init
   ```
2. O `.gitignore` já evita commitar:
   - `.config` (tokens e senhas)
   - `*_api.csv`, `relatorio_*.json`, `relatorio_*.txt`
   - `logs_demissao/`, `venv/`, `__pycache__/`
3. Adicione os arquivos e faça o primeiro commit:
   ```bash
   git add .
   git status   # confira que .config e CSVs não entram
   git commit -m "Integração IFPonto Alterdata - versão inicial"
   git remote add origin https://github.com/SEU_USUARIO/live-integracao.git
   git push -u origin main
   ```

---

## Instalação na VPS (Hostinger)

1. **Conectar na VPS** (SSH):
   ```bash
   ssh usuario@ip-da-vps
   ```

2. **Instalar Python 3 e pip** (se necessário):
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv -y
   ```

3. **Clonar o repositório** (ou enviar os arquivos via FTP/SCP):
   ```bash
   cd /var/www   # ou outro diretório desejado
   git clone https://github.com/SEU_USUARIO/live-integracao.git
   cd live-integracao
   ```

4. **Criar ambiente virtual e instalar dependências**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Configurar o .config na VPS**:
   ```bash
   cp .config.example .config
   nano .config   # ou vim – preencher com os dados reais
   ```

6. **Executar a integração** (manual ou agendada):
   ```bash
   source venv/bin/activate
   python main.py
   ```

7. **Agendar com cron** (ex.: todo dia às 6h):
   ```bash
   crontab -e
   ```
   Adicione (ajuste o caminho):
   ```cron
   0 6 * * * cd /var/www/live-integracao && /var/www/live-integracao/venv/bin/python main.py >> /var/www/live-integracao/log_integracao.log 2>&1
   ```

---

## Possíveis ajustes futuros

- **Incluir férias no `main.py`**: adicionar o módulo `ferias` na `sequencia_modulos` em `main.py` se quiser rodar férias na mesma execução.
- **Incluir empresas/departamentos/cargos**: hoje o banner cita esses módulos, mas só funcionários, afastamentos e demissões são executados; pode-se incluir na sequência se a API de destino exigir.
- **Nomenclatura**: o código menciona “eContador” e “Hevi”; na prática a origem é **Alterdata** e o destino é **IFPonto** (SOAP `urn:ifPonto` e API de cadastro). Vale alinhar comentários e mensagens ao nome correto do sistema.
- **Ambiente**: em produção, considerar variáveis de ambiente para token/senha em vez de `.config`, e garantir que o `.config` não seja exposto na web.

---

## Requisitos

- Python 3.8+
- Dependências em `requirements.txt` (requests, pandas, pytz, etc.)
