# AssetFlow v3.1.1 - Gestão de Ativos com IA e Banco de Dados na Nuvem

Uma aplicação web completa e robusta construída com Python e Streamlit para gerir todo o ciclo de vida de ativos de TI. A versão 3.1.1 representa uma evolução crucial em segurança e usabilidade, **introduzindo um fluxo completo de redefinição de senha por e-mail e aprimorando significativamente a interface do utilizador e as regras de negócio**.

Esta versão mantém a base sólida da v3.1, **com o assistente de IA Flow e o banco de dados PostgreSQL na nuvem (Supabase)**, garantindo persistência, segurança e escalabilidade dos dados.

## Novidades da Versão 3.1.1

-   **Fluxo Completo de Redefinição de Senha:** Utilizadores podem agora redefinir as suas senhas de forma autónoma através de um link seguro enviado para o seu e-mail, com tokens de uso único e tempo de expiração.
-   **Interface de Login Profissional:** A tela de login foi completamente redesenhada, com um layout moderno, centralizado, menu lateral oculto e um rodapé fixo com informações de versão e links sociais.
-   **Gestão Financeira em Manutenções:** Ao fechar uma Ordem de Serviço, agora é possível definir a responsabilidade do custo com opções fixas (Empresa, Colaborador, Empresa / Colaborador), permitindo uma auditoria financeira mais precisa.
-   **Flexibilidade no Cadastro de Colaboradores:** O sistema agora permite o registo de códigos de colaborador duplicados no mesmo setor (para casos de transição), mas emite um alerta e exige confirmação do administrador, garantindo controlo e integridade.
-   **Melhorias na Experiência do Administrador:** A página de gestão de utilizadores foi aprimorada para incluir a redefinição de senhas de qualquer utilizador diretamente pela interface.

---

## Funcionalidades Principais

-   **Banco de Dados Persistente na Nuvem:** Todos os dados são armazenados de forma segura num banco de dados PostgreSQL, eliminando o risco de perda de informação a cada reinicialização da aplicação.
-   **Dashboard Gerencial:** Visualização em tempo real dos principais indicadores (KPIs) do inventário.
-   **Sistema de Login Seguro:** Acesso protegido com hashing de senhas e diferentes níveis de permissão (Administrador, Editor, Leitor).
-   **Gestão de Utilizadores:** Painel administrativo para criar e gerir os acessos ao sistema.
-   **Interface Profissional e Consistente:**
    -   **Identidade Visual:** Logo da aplicação e links de contacto profissionalmente integrados na interface.
    -   **Layout Otimizado:** Uso de secções expansíveis e um design limpo em todas as páginas.
    -   **Usabilidade Aprimorada:** Listas suspensas com pesquisa integrada para encontrar rapidamente registos.
-   **Edição Direta na Tabela:** A maioria das tabelas de gestão permite a edição direta, adição e exclusão de dados, tornando as atualizações rápidas e intuitivas.

---

### Módulos e Fluxos de Trabalho Inteligentes

#### **Converse com o Flow (Assistente de IA)**

-   **Interface Conversacional:** Interaja com o sistema usando linguagem natural.
-   **Criação de Registos:** Peça ao Flow para criar novos colaboradores, aparelhos ou contas Gmail. Ele guia o utilizador passo a passo.
-   **Pesquisas Inteligentes:** Faça perguntas como "Quais aparelhos estão com o Cauã Freitas?" ou "Mostre o histórico do aparelho com n/s X".

#### Gestão de Cadastros

-   **Controlo Total:** Gestão completa de Aparelhos, Colaboradores, Marcas, Modelos, Setores e Contas Gmail.

#### Fluxo de Devolução e Triagem

-   **Processo Guiado:** Uma página dedicada para registar a devolução de um aparelho, com checklist de inspeção e decisão de destino (Estoque, Manutenção ou Baixa).

#### Fluxo de Manutenção Completo

-   **Controlo de O.S.:** Abertura, acompanhamento e fecho de Ordens de Serviço, com registo de fornecedores, custos e soluções.

#### Geração de Documentos Profissionais em PDF

-   **Termo de Responsabilidade:** Geração de termos de entrega em PDF com um design limpo, a partir de um "molde" HTML, garantindo consistência e profissionalismo.

#### Importação e Exportação de Dados

-   **Importação em Lote:** Secção para importar dados em massa a partir de planilhas Excel (.xlsx), com download de modelos e validação inteligente.
-   **Exportação de Relatórios:** Exporte o inventário completo ou o histórico de movimentações para Excel com um único clique.

## Como Executar Localmente ou Fazer o Deploy

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/caufreitxs026/AssetFl0w.git](https://github.com/caufreitxs026/AssetFl0w.git)
    cd AssetFl0w
    ```

2.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
    Se estiver a fazer o deploy no Streamlit Cloud, crie também um ficheiro `packages.txt` e adicione a seguinte linha:
    ```
    libpangocairo-1.0-0
    ```

3.  **Configure o Banco de Dados (Supabase):**
    -   Crie um projeto gratuito no [Supabase](https://supabase.com/).
    -   No seu projeto Supabase, vá a **SQL Editor** -> **+ New query**.
    -   Copie todo o conteúdo do ficheiro `schema.sql` deste repositório, cole no editor e clique em **RUN**.
    -   Vá a **Settings** -> **Database**.
    -   Em **Connection string**, copie o URI do **Transaction pooler**.

4.  **Configure os Segredos do Streamlit:**
    -   Crie um ficheiro `.streamlit/secrets.toml` no seu projeto.
    -   Adicione a sua chave da API Gemini e a connection string do Supabase:
    ```toml
    # Chave da API para o assistente Flow
    GEMINI_API_KEY = "SUA_CHAVE_API_AQUI"

    # Conexão com o banco de dados Supabase PostgreSQL
    [connections.supabase]
    url = "SUA_CONNECTION_STRING_DO_SUPABASE_AQUI"
    ```
    *Lembre-se de substituir `[YOUR-PASSWORD]` na connection string pela sua senha real do banco de dados.*

5.  **Execute a aplicação:**
    ```bash
    streamlit run app.py
    ```

6.  **Aceda à aplicação** no seu navegador, geralmente em `http://localhost:8501`.
    -   **Login Padrão:** `admin`
    -   **Senha Padrão:** `123`

---
*LinkedIn: [https://www.linkedin.com/in/cauafreitas](https://www.linkedin.com/in/cauafreitas)*

*GitHub: [https://github.com/caufreitxs026](https://github.com/caufreitxs026)*
