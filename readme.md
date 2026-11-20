# 📲 Automação de Salvamento de Contatos — WhatsApp Web (Microsoft Edge)


Script em Python utilizando **Playwright** e o **Microsoft Edge** para varrer conversas do WhatsApp Web, identificar números ainda não salvos na agenda, cadastrá-los diretamente na conta nativa do WhatsApp no formato **`[Nome no WhatsApp] + Cliente`** (com sincronização ativada para o iPhone) e exportar todo o histórico para uma planilha CSV.

---

## 📋 Índice

- [Pré-requisitos](#-pré-requisitos)
- [Configuração no iPhone](#-configuração-no-iphone-sincronização-de-status)
- [Instalação](#-instalação)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Configuração do `.gitignore`](#-configuração-do-gitignore-importante-para-o-git)
- [Parâmetros Configuráveis](#-parâmetros-configuráveis)
- [Como Executar](#-como-executar)
- [Relatório CSV Gerado](#-relatório-csv-gerado-contatos_salvoscsv)
- [Fluxo da Automação](#-fluxo-executado-pelo-script)

---

## 💻 Pré-requisitos

* **Sistema Operacional:** Windows (com o **Microsoft Edge** já instalado).
* **Python:** Versão `3.9` ou superior.
* **Smartphone (iPhone):** WhatsApp conectado no aparelho.

---

## 📱 Configuração no iPhone (Sincronização de Status)

Para que os contatos salvos pelo WhatsApp Web sincronizem automaticamente com a agenda do iPhone e possam visualizar seus Status (desde que também tenham o seu número salvo):

1. Abra o **WhatsApp** no iPhone.
2. Acesse **Configurações** > **Privacidade** > **Contatos**.
3. Ative a opção **Contatos do WhatsApp**.

---

## 🚀 Instalação

1. Clone este repositório (ou crie uma pasta local e adicione o arquivo `salvar_clientes.py`):
   ```powershell
   git clone [https://github.com/vitsantos/automacao-wpp.git](https://github.com/SEU-USUARIO/automacao-wpp.git)
   cd automacao-wpp
   ```

2. Crie e ative o ambiente virtual:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. Instale o Playwright:
   ```powershell
   pip install playwright
   ```
---

## 📁 Estrutura do Projeto

```text
automacao_wpp/
├── salvar_clientes.py     # Script principal da automação
├── README.md              # Documentação do repositório
├── .gitignore             # Ignora ambiente virtual, sessão do navegador e CSV
├── contatos_salvos.csv    # Relatório gerado automaticamente (ignorado no Git)
└── sessao_wpp_edge/       # Cookies/sessão do WhatsApp Web (ignorado no Git)
```

---


## ⚙️ Parâmetros Configuráveis

No topo do arquivo `salvar_clientes.py`, ajuste as constantes conforme a sua necessidade:

| Constante | Valor Padrão | Descrição |
| :--- | :--- | :--- |
| `USER_DATA_DIR` | `./sessao_wpp_edge` | Pasta isolada da sessão do Edge (não interfere no seu navegador pessoal). |
| `ARQUIVO_CSV` | `contatos_salvos.csv` | Arquivo de relatório e controle de números já salvos. |
| `TEMPO_SINCRONIZACAO_INICIAL` | `15` | Segundos de espera após abrir o WhatsApp Web para sincronizar conversas antigas. |
| `MAX_ROLAGENS` | `150` | Limite máximo de rolagens suaves (`350px`) na lista de conversas. |
| `LIMITE_POR_EXECUCAO` | `40` | Quantidade máxima de novos contatos salvos por execução antes de encerrar com segurança. |

---

## ▶️ Como Executar

1. Com o ambiente virtual ativado, inicie o script:
   ```powershell
   python salvar_clientes.py
   ```
2. **Primeira execução:** O Microsoft Edge abrirá maximizado no WhatsApp Web exibindo o **QR Code**.
   * No iPhone, abra **WhatsApp** > **Configurações** > **Dispositivos conectados** > **Conectar dispositivo** e escaneie a tela.
3. **Execuções seguintes:** Como os dados de login ficam salvos em `sessao_wpp_edge/`, o script abrirá diretamente na lista de conversas sem exigir novo QR Code.
4. **Prevenção de duplicados:** Ao iniciar, o script lê o `contatos_salvos.csv` e ignora automaticamente qualquer número já cadastrado em execuções anteriores.

---

## 📊 Relatório CSV Gerado (`contatos_salvos.csv`)

Cada novo contato salvo é registrado imediatamente no arquivo **`contatos_salvos.csv`** (delimitado por `;` e codificado em `UTF-8-SIG` para abertura direta em colunas no Excel):

| Data/Hora | Numero | Nome Original WPP | Nome Salvo |
| :--- | :--- | :--- | :--- |
| 2026-11-20 18:10:05 | +55 88 99999-9999 | Maria Silva | Maria Silva Cliente |
| 2026-11-20 18:10:14 | +55 85 98888-8888 | (Sem nome) | Contato Cliente |

---

## 🔄 Fluxo Executado pelo Script

1. Aguarda o carregamento da barra lateral (`#pane-side`) e espera `15s` para sincronização do histórico.
2. Percorre cada conversa visível identificando números não salvos (`cell-frame-title`).
3. Abre a conversa e clica no cabeçalho (`conversation-info-header-button`) para exibir os **Dados do contato**.
4. Captura o nome público (`~Nome`) e formata como `[Nome] Cliente` (ou `Contato Cliente` caso não haja nome público).
5. Clica no botão exato **`Adicionar`** (ignorando *Adicionar à lista*), preenche `contact-first-name-input`, garante que a chave **`Sincronizar contato com`** esteja marcada e confirma no botão **`save-contact-btn`**.
6. Registra no CSV e rola a lista suavemente até atingir `LIMITE_POR_EXECUCAO` ou o fim do histórico.