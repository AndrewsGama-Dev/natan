# Histórico da análise do projeto – Integração IFPonto ↔ Alterdata

Este arquivo registra o que foi analisado no projeto para você não perder o contexto ao trocar de pasta, reabrir o Cursor ou no futuro.

---

## O que este projeto faz

- **Origem:** sistema de **folha de pagamento Alterdata** (API REST em `dp.pack.alterdata.com.br`).
- **Destino:** sistema de **ponto eletrônico IFPonto** (cadastro via API/CSV e demissões via SOAP).
- Sincroniza: funcionários ativos, afastamentos (exceto férias), demissões e, em módulos separados, férias.

---

## Fluxo resumido

| Etapa | Módulo | Origem | Destino |
|-------|--------|--------|---------|
| 1 | Funcionários | API Alterdata (funcionários ativos) | CSV → POST na API de cadastro IFPonto |
| 2 | Afastamentos | API Alterdata (afastamentos que não são férias) | CSV → API |
| 3 | Demissões | API Alterdata (funcionários demitidos) | CSV + **SOAP** IFPonto (`urn:ifPonto`) |

- **Funcionários:** matrícula com 6 dígitos, CPF com 11 dígitos, departamento/cargo da API; token da API = SHA256(`token_base` + data DD/MM/AAAA).
- **Demissões:** matrícula composta no formato `cod_empresab000002`; envio via webservice SOAP com `clientId`, `usuario`, `senha` do `.config`.

---

## Estrutura dos arquivos principais

- **main.py** – Orquestra: funcionários → afastamentos → demissões (não chama empresas, departamentos, cargos nem férias).
- **config_reader.py** – Lê `.config` (token Alterdata, headers da API).
- **funcionarios.py** – Busca ativos na Alterdata, gera CSV, envia para a API de cadastro IFPonto.
- **afastamentos.py** – Afastamentos (excluindo férias) → CSV → API.
- **demissoes.py** – Demitidos → CSV e envio via SOAP IFPonto.
- **ferias.py** – Férias (uso separado; não está na sequência do `main.py`).
- **empresas.py, departamentos.py, cargos.py** – Existem mas não são usados pelo `main.py` atual.

---

## Configuração (.config)

- **[APISOURCE]** – `token`: Bearer da API Alterdata.
- **[APITARGET]** – `url`, `integracao`, `token_base`: API de cadastro em massa (IFPonto); token do dia = SHA256(`token_base` + data).
- **[SOAP]** – `url`, `client_id`, `usuario`, `senha`: webservice SOAP do IFPonto para demissões.
- **[FUNCIONARIOS]** – `campo_chave`: `matricula` ou `cpf` (opcional).

O código às vezes cita “eContador” e “Hevi”; na prática a origem é **Alterdata** e o destino é **IFPonto**.

---

## O que já foi feito (ajustes para Git e VPS)

1. **.gitignore** – Para não subir: `.config`, CSVs gerados, `logs_demissao/`, `venv/`, `__pycache__`, etc.
2. **.config.example** – Modelo do `.config` com todas as seções documentadas.
3. **README.md** – Instruções de uso, configuração, como subir para o Git e como instalar na VPS Hostinger (incluindo exemplo de cron).

---

## Possíveis ajustes futuros

- Incluir **férias** na sequência do `main.py` (módulo `ferias`).
- Incluir **empresas, departamentos, cargos** no fluxo principal, se necessário.
- Alinhar nomes em comentários e mensagens (Alterdata / IFPonto em vez de eContador / Hevi).
- Em produção na VPS: considerar uso de variáveis de ambiente para tokens/senhas.

---

*Documento gerado para preservar o histórico da análise do projeto. Atualize este arquivo quando fizer novas análises ou decisões importantes.*
