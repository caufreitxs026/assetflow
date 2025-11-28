# AssetFlow v3.1.1 — Gestão de Ativos com IA e Banco de Dados na Nuvem

O **AssetFlow v3.1.1** é uma aplicação web completa e robusta construída com **Python** e **Streamlit**, projetada para gerir todo o ciclo de vida de ativos de TI.
Esta versão representa um avanço importante em segurança e usabilidade, **introduzindo um fluxo completo de redefinição de senha por e-mail** e aprimorando significativamente a interface do usuário e as regras de negócio.

A v3.1.1 mantém a base sólida da versão anterior, incluindo o **assistente de IA Flow** e o **banco de dados PostgreSQL na nuvem (Supabase)**, garantindo persistência, segurança e escalabilidade.

---

## Novidades da Versão 3.1.1

* **Fluxo Completo de Redefinição de Senha:**
  Redefinição de senha via link seguro enviado por e-mail, com tokens de uso único e tempo de expiração.

* **Interface de Login Profissional:**
  Tela de login totalmente redesenhada, com layout moderno, conteúdo centralizado, menu lateral oculto e rodapé fixo com versão e links sociais.

* **Gestão Financeira em Manutenções:**
  Agora, ao encerrar uma Ordem de Serviço, é possível definir a responsabilidade do custo (Empresa, Colaborador ou Empresa/Colaborador).

* **Flexibilidade no Cadastro de Colaboradores:**
  Permite registrar códigos duplicados no mesmo setor (casos de transição), mas solicita confirmação do administrador.

* **Melhorias para Administradores:**
  Possibilidade de redefinir senhas de outros utilizadores diretamente pela interface.

---

## Funcionalidades Principais

* **Banco de Dados Persistente:**
  Todos os dados são armazenados de forma segura em um banco PostgreSQL na nuvem.

* **Dashboard Gerencial:**
  KPIs do inventário em tempo real.

* **Sistema de Login Seguro:**
  Hashing de senhas e níveis de permissão (Administrador, Editor e Leitor).

* **Gestão de Utilizadores:**
  Criação e administração completa de acessos.

* **Interface Profissional:**

  * Identidade visual e logotipo integrado.
  * Layout otimizado com seções expansíveis.
  * Listas suspensas com busca embutida.

* **Edição Direta em Tabela:**
  Atualizações rápidas e intuitivas em diversas seções.

---

## Módulos e Fluxos de Trabalho Inteligentes

### Converse com o Flow (Assistente de IA)

* Interface conversacional baseada em linguagem natural.
* Criação de registos (aparelhos, colaboradores, contas Gmail).
* Pesquisas inteligentes como:
  “Quais aparelhos estão com o Cauã Freitas?”
  “Mostrar histórico do aparelho com número de série X.”

### Gestão de Cadastros

* Gestão completa de Aparelhos, Colaboradores, Marcas, Modelos, Setores e Contas Gmail.

### Fluxo de Devolução e Triagem

* Processo guiado com checklist e definição do destino do aparelho (Estoque, Manutenção ou Baixa).

### Fluxo de Manutenção Completo

* Abertura, acompanhamento e fecho de Ordens de Serviço, com fornecedores, custos e relatórios.

### Geração de Documentos em PDF

* Termos de responsabilidade gerados a partir de templates HTML, com design limpo e profissional.

### Importação e Exportação de Dados

* Importação em lote via Excel (.xlsx), com validação e modelos para download.
* Exportação do inventário e históricos com um clique.

---

## Como Executar Localmente ou Fazer Deploy

### 1. Clone o repositório

```bash
git clone https://github.com/caufreitxs026/AssetFl0w.git
cd AssetFl0w
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

Se estiver no Streamlit Cloud, crie o arquivo `packages.txt` com:

```
libpangocairo-1.0-0
```

### 3. Configure o Banco de Dados (Supabase)

1. Crie um projeto no Supabase.
2. Acesse **SQL Editor** → **New Query**.
3. Copie o conteúdo de `schema.sql` deste repositório e execute.
4. Vá a **Settings** → **Database** e copie o URI do **Transaction pooler**.

### 4. Configure os Segredos do Streamlit

Crie o arquivo `.streamlit/secrets.toml`:

```toml
# Chave para o assistente Flow
GEMINI_API_KEY = "SUA_CHAVE_API_AQUI"

# Conexão com o banco Supabase
[connections.supabase]
url = "SUA_CONNECTION_STRING_DO_SUPABASE_AQUI"
```

Substitua `[YOUR-PASSWORD]` na connection string pela sua senha do banco.

### 5. Execute a aplicação

```bash
streamlit run app.py
```

### 6. Aceda à aplicação

```
http://localhost:8501
```

Credenciais padrão:

* **Login:** admin
* **Senha:** 123

---

### Contato

LinkedIn: [https://www.linkedin.com/in/cauafreitas](https://www.linkedin.com/in/cauafreitas)
GitHub: [https://github.com/caufreitxs026](https://github.com/caufreitxs026)

---
