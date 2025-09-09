import streamlit as st
import json
import pandas as pd
from auth import show_login_form, logout
import asyncio
import httpx
from datetime import date, datetime
from sqlalchemy import text
import time

# --- Autenticação e Configuração da Página ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

# --- Configuração de Layout (Header, Footer e CSS) ---
st.markdown("""
<style>
    /* Estilos da Logo Principal */
    .logo-text {
        font-family: 'Courier New', monospace;
        font-size: 28px;
        font-weight: bold;
        padding-top: 20px;
    }
    .logo-asset { color: #003366; }
    .logo-flow { color: #E30613; }
    @media (prefers-color-scheme: dark) {
        .logo-asset { color: #FFFFFF; }
        .logo-flow { color: #FF4B4B; }
    }
    /* Estilos para o footer na barra lateral */
    .sidebar-footer {
        text-align: center;
        padding-top: 20px;
        padding-bottom: 20px;
    }
    .sidebar-footer a { margin-right: 15px; text-decoration: none; }
    .sidebar-footer img {
        width: 25px; height: 25px; filter: grayscale(1) opacity(0.5);
        transition: filter 0.3s;
    }
    .sidebar-footer img:hover { filter: grayscale(0) opacity(1); }
    @media (prefers-color-scheme: dark) {
        .sidebar-footer img { filter: grayscale(1) opacity(0.6) invert(1); }
        .sidebar-footer img:hover { filter: opacity(1) invert(1); }
    }
    /* --- NOVO: Estilos para a Logo do Chat --- */
    .flow-title {
        display: flex;
        align-items: center;
        padding-bottom: 10px;
    }
    .flow-title .icon {
        font-size: 2.5em;
        margin-right: 15px;
    }
    .flow-title h1 {
        font-family: 'Courier New', monospace;
        font-size: 3em;
        font-weight: bold;
        margin: 0;
        padding: 0;
        line-height: 1;
    }
    .flow-title .text-chat { color: #003366; }
    .flow-title .text-flow { color: #E30613; }
    @media (prefers-color-scheme: dark) {
        .flow-title .text-chat { color: #FFFFFF; }
        .flow-title .text-flow { color: #FF4B4B; }
    }
</style>
""", unsafe_allow_html=True)

# --- Header (Logo no canto superior esquerdo) ---
st.markdown(
    """
    <div class="logo-text">
        <span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Barra Lateral ---
with st.sidebar:
    st.write(f"Bem-vindo, **{st.session_state['user_name']}**!")
    st.write(f"Cargo: **{st.session_state['user_role']}**")
    if st.button("Logout", key="flow_logout"):
        from auth import logout
        logout()
    st.markdown("---")
    st.markdown(
        f"""
        <div class="sidebar-footer">
            <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg"></a>
            <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg"></a>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Funções do Executor de Ações ---
def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

def executar_pesquisa_aparelho(filtros):
    if not filtros:
        return "Por favor, forneça um critério de pesquisa, como o nome do colaborador ou o número de série."
    conn = get_db_connection()
    # --- QUERY CORRIGIDA para usar a mesma lógica de 'responsavel_atual' da página de aparelhos ---
    query = """
        WITH UltimoResponsavel AS (
            SELECT
                h.aparelho_id,
                h.colaborador_id,
                h.colaborador_snapshot,
                ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
            FROM historico_movimentacoes h
        )
        SELECT 
            a.numero_serie,
            ma.nome_marca || ' - ' || mo.nome_modelo as modelo,
            s.nome_status as status,
            CASE 
                WHEN s.nome_status = 'Em uso' THEN COALESCE(ur.colaborador_snapshot, c.nome_completo)
                ELSE 'N/A'
            END as responsavel
        FROM aparelhos a
        LEFT JOIN modelos mo ON a.modelo_id = mo.id
        LEFT JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN status s ON a.status_id = s.id
        LEFT JOIN UltimoResponsavel ur ON a.id = ur.aparelho_id AND ur.rn = 1
        LEFT JOIN colaboradores c ON ur.colaborador_id = c.id
    """
    params = {}
    where_clauses = []
    if filtros.get("nome_colaborador"):
        where_clauses.append("COALESCE(ur.colaborador_snapshot, c.nome_completo) ILIKE :nome_colaborador")
        params['nome_colaborador'] = f"%{filtros['nome_colaborador']}%"
    if filtros.get("numero_serie"):
        where_clauses.append("a.numero_serie ILIKE :numero_serie")
        params['numero_serie'] = f"%{filtros['numero_serie']}%"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    df = conn.query(query, params=params)
    return df

def executar_criar_colaborador(dados):
    if not dados or not dados.get('nome_completo') or not dados.get('codigo') or not dados.get('nome_setor'):
        return "Não foi possível criar o colaborador. Faltam informações essenciais (nome, código e setor)."
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            setor_id_res = s.execute(text("SELECT id FROM setores WHERE nome_setor ILIKE :nome LIMIT 1"), {"nome": f"%{dados['nome_setor']}%"}).fetchone()
            if not setor_id_res:
                return f"Erro: O setor '{dados['nome_setor']}' não foi encontrado."
            setor_id = setor_id_res[0]
            
            q_check = text("SELECT 1 FROM colaboradores WHERE (cpf = :cpf AND cpf IS NOT NULL AND cpf != '') OR (codigo = :codigo AND setor_id = :setor_id)")
            existe = s.execute(q_check, {"cpf": dados.get('cpf'), "codigo": dados.get('codigo'), "setor_id": setor_id}).fetchone()
            if existe:
                s.rollback()
                return "Erro: Já existe um colaborador com este CPF ou com este código neste setor."

            s.execute(
                text("INSERT INTO colaboradores (nome_completo, codigo, cpf, gmail, setor_id, data_cadastro) VALUES (:nome, :codigo, :cpf, :gmail, :setor_id, :data)"),
                {"nome": dados['nome_completo'], "codigo": dados.get('codigo'), "cpf": dados.get('cpf'), "gmail": dados.get('gmail'), "setor_id": setor_id, "data": date.today()}
            )
            s.commit()
        st.cache_data.clear()
        return f"Colaborador '{dados['nome_completo']}' criado com sucesso!"
    except Exception as e:
        return f"Ocorreu um erro inesperado ao criar o colaborador: {e}"

def executar_criar_aparelho(dados):
    if not dados or not all(k in dados for k in ['marca', 'modelo', 'numero_serie', 'valor']):
        return "Faltam informações para criar o aparelho (Marca, Modelo, N/S, Valor)."
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            query_modelo = text("SELECT mo.id FROM modelos mo JOIN marcas ma ON mo.marca_id = ma.id WHERE ma.nome_marca ILIKE :marca AND mo.nome_modelo ILIKE :modelo")
            modelo_id_result = s.execute(query_modelo, {"marca": dados['marca'], "modelo": dados['modelo']}).fetchone()
            if not modelo_id_result:
                return f"Erro: O modelo '{dados['marca']} - {dados['modelo']}' não foi encontrado. Cadastre-o primeiro."
            
            modelo_id = modelo_id_result[0]
            status_id = s.execute(text("SELECT id FROM status WHERE nome_status = 'Em estoque'")).scalar_one()
            
            q_aparelho = text("INSERT INTO aparelhos (numero_serie, imei1, imei2, valor, modelo_id, status_id, data_cadastro) VALUES (:ns, :i1, :i2, :val, :mid, :sid, :data) RETURNING id")
            result = s.execute(q_aparelho, {"ns": dados['numero_serie'], "i1": dados.get('imei1'), "i2": dados.get('imei2'), "val": float(dados['valor']), "mid": modelo_id, "sid": status_id, "data": date.today()})
            aparelho_id = result.scalar_one()
            
            q_hist = text("INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, status_id, localizacao_atual, observacoes) VALUES (:data, :apid, :sid, :loc, :obs)")
            s.execute(q_hist, {"data": datetime.now(), "apid": aparelho_id, "sid": status_id, "loc": "Estoque Interno", "obs": "Entrada via assistente Flow."})
            
            s.commit()
        st.cache_data.clear()
        return f"Aparelho '{dados['marca']} {dados['modelo']}' (N/S: {dados['numero_serie']}) criado com sucesso!"
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            return f"Erro: Já existe um aparelho com o Número de Série '{dados['numero_serie']}'."
        return f"Ocorreu um erro inesperado: {e}"

def executar_pesquisa_movimentacoes(filtros):
    if not filtros:
        return "Por favor, forneça um critério de pesquisa (colaborador, N/S ou data)."
    conn = get_db_connection()
    # --- QUERY CORRIGIDA para usar 'colaborador_snapshot' ---
    query = """
        SELECT h.data_movimentacao, a.numero_serie, mo.nome_modelo, h.colaborador_snapshot as colaborador, s.nome_status, h.observacoes
        FROM historico_movimentacoes h
        JOIN aparelhos a ON h.aparelho_id = a.id
        JOIN status s ON h.status_id = s.id
        LEFT JOIN modelos mo ON a.modelo_id = mo.id
    """
    params = {}
    where_clauses = []
    if filtros.get("nome_colaborador"):
        where_clauses.append("h.colaborador_snapshot ILIKE :nome_colaborador")
        params['nome_colaborador'] = f"%{filtros['nome_colaborador']}%"
    if filtros.get("numero_serie"):
        where_clauses.append("a.numero_serie ILIKE :numero_serie")
        params['numero_serie'] = f"%{filtros['numero_serie']}%"
    if filtros.get("data"):
        try:
            data_valida = datetime.strptime(filtros['data'], '%Y-%m-%d').date()
            where_clauses.append("CAST(h.data_movimentacao AS DATE) = :data")
            params['data'] = data_valida
        except ValueError:
            return "Formato de data inválido. Por favor, use AAAA-MM-DD."
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY h.data_movimentacao DESC"
    df = conn.query(query, params=params)
    return df

def executar_criar_conta_gmail(dados):
    if not dados or not dados.get('email'):
        return "Não foi possível criar a conta. O e-mail é obrigatório."
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            setor_id, colaborador_id = None, None
            if dados.get('nome_setor'):
                setor_res = s.execute(text("SELECT id FROM setores WHERE nome_setor ILIKE :nome LIMIT 1"), {"nome": f"%{dados['nome_setor']}%"}).fetchone()
                if setor_res: setor_id = setor_res[0]
            if dados.get('nome_colaborador'):
                colab_res = s.execute(text("SELECT id FROM colaboradores WHERE nome_completo ILIKE :nome LIMIT 1"), {"nome": f"%{dados['nome_colaborador']}%"}).fetchone()
                if colab_res: colaborador_id = colab_res[0]

            query_check = text("SELECT 1 FROM contas_gmail WHERE email = :email")
            existe = s.execute(query_check, {"email": dados['email']}).fetchone()
            if existe:
                s.rollback()
                return f"Erro: A conta Gmail '{dados['email']}' já existe."

            query = text("INSERT INTO contas_gmail (email, senha, telefone_recuperacao, email_recuperacao, setor_id, colaborador_id) VALUES (:email, :senha, :tel, :email_rec, :sid, :cid)")
            s.execute(query, {
                "email": dados['email'], "senha": dados.get('senha'), "tel": dados.get('telefone_recuperacao'),
                "email_rec": dados.get('email_recuperacao'), "sid": setor_id, "cid": colaborador_id
            })
            s.commit()
        st.cache_data.clear()
        return f"Conta Gmail '{dados['email']}' criada com sucesso!"
    except Exception as e:
        return f"Ocorreu um erro inesperado ao criar a conta: {e}"

# --- Lógica do Chatbot ---
schema = {
    "type": "OBJECT",
    "properties": { "acao": { "type": "STRING", "enum": ["iniciar_criacao", "fornecer_dado", "pesquisar_aparelho", "pesquisar_movimentacoes", "limpar_chat", "logout", "saudacao", "desconhecido"] }, "entidade": {"type": "STRING", "enum": ["colaborador", "aparelho", "conta_gmail"]}, "dados": { "type": "OBJECT", "properties": { "valor_dado": {"type": "STRING"} } }, "filtros": { "type": "OBJECT", "properties": { "nome_colaborador": {"type": "STRING"}, "numero_serie": {"type": "STRING"}, "data": {"type": "STRING"} } } },
    "required": ["acao"]
}

async def get_flow_response(prompt, user_name, current_action=None):
    if current_action:
        contextual_prompt = f"O utilizador '{user_name}' está no meio de um processo de criação ({current_action}) e forneceu a seguinte informação: {prompt}. Interprete este dado como o valor para o campo que está a ser solicitado."
    else:
        contextual_prompt = f"O utilizador '{user_name}' pediu: {prompt}"
    
    chatHistory = [
        {"role": "user", "parts": [{"text": "Você é o Flow, um assistente para um sistema de gestão de ativos. Sua função é interpretar os pedidos do utilizador e traduzi-los para um formato JSON estruturado, de acordo com o schema fornecido. Se o utilizador iniciar um processo de criação (ex: 'criar aparelho'), a sua ação deve ser 'iniciar_criacao' e a entidade correspondente. Se o utilizador fornecer um dado no meio de uma conversa, a sua ação deve ser 'fornecer_dado'. Seja conciso e direto."}]},
        {"role": "model", "parts": [{"text": "Entendido. Estou pronto para processar os pedidos e retornar o JSON correspondente."}]},
        {"role": "user", "parts": [{"text": contextual_prompt}]}
    ]
    payload = { "contents": chatHistory, "generationConfig": { "responseMimeType": "application/json", "responseSchema": schema } }
    
    try:
        apiKey = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return {"acao": "desconhecido", "dados": {"erro": "Chave de API não configurada."}}

    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={apiKey}"
    
    # --- LÓGICA DE RETENTATIVA ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload, timeout=45)
                
                if response.status_code == 503 and attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('candidates'):
                    json_text = result['candidates'][0]['content']['parts'][0]['text']
                    return json.loads(json_text)
                else:
                    return {"acao": "desconhecido", "dados": {"erro": f"Resposta inesperada da API: {result}"}}
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                continue # Tenta novamente
            return {"acao": "desconhecido", "dados": {"erro": f"Erro na API ({e.response.status_code}). Verifique o nome do modelo e a chave da API."}}
        except Exception as e:
            return {"acao": "desconhecido", "dados": {"erro": f"Ocorreu um erro de comunicação: {e}"}}
            
    return {"acao": "desconhecido", "dados": {"erro": "O serviço de IA está temporariamente indisponível (Erro 503). Por favor, tente mais tarde."}}

def get_info_text():
    return """
    Olá! Sou o Flow, o seu assistente. Veja como me pode usar:

    **1. Para Pesquisar:**
    - **Aparelhos:** Diga "pesquisar aparelho do [nome do colaborador]" ou "encontrar aparelho com n/s [número de série]".
    - **Movimentações:** Diga "mostrar histórico do [nome do colaborador]", "ver movimentações do aparelho [número de série]" ou "o que aconteceu em [data no formato AAAA-MM-DD]?".

    **2. Para Criar Novos Registos (Fluxo Guiado):**
    - **Colaborador:** Comece por dizer "criar colaborador".
    - **Aparelho:** Comece por dizer "criar aparelho".
    - **Conta Gmail:** Comece por dizer "criar conta gmail".
    Eu irei guiá-lo passo a passo, pedindo cada informação necessária.

    **3. Comandos do Chat:**
    - **`#info`:** Mostra esta mensagem de ajuda.
    - **`limpar chat`:** Apaga o histórico da nossa conversa.
    - **`encerrar chat` ou `logout`:** Faz o logout do sistema.

    Estou aqui para ajudar a tornar a sua gestão mais rápida e fácil!
    """

CAMPOS_CADASTRO = {
    "colaborador": ["codigo", "nome_completo", "cpf", "gmail", "nome_setor"],
    "aparelho": ["marca", "modelo", "numero_serie", "valor", "imei1", "imei2"],
    "conta_gmail": ["email", "senha", "telefone_recuperacao", "email_recuperacao", "nome_setor", "nome_colaborador"]
}

# --- Interface do Chatbot ---
st.markdown(
    """
    <div class="flow-title">
        <span class="icon">💬</span>
        <h1><span class="text-chat">Converse com o </span><span class="text-flow">Flow</span></h1>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown("---")
st.info("Sou o Flow, seu assistente inteligente. Diga `#info` para ver os comandos, `limpar chat` para recomeçar ou `encerrar chat` para sair.")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Como posso ajudar?"}]
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None
if "conversa_em_andamento" not in st.session_state:
    st.session_state.conversa_em_andamento = None
if "dados_recolhidos" not in st.session_state:
    st.session_state.dados_recolhidos = {}
if "campo_para_corrigir" not in st.session_state:
    st.session_state.campo_para_corrigir = None
if "modo_correcao" not in st.session_state:
    st.session_state.modo_correcao = False

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], pd.DataFrame):
            st.dataframe(message["content"], hide_index=True, use_container_width=True)
        else:
            st.markdown(message["content"], unsafe_allow_html=True)

def proximo_campo():
    entidade = st.session_state.conversa_em_andamento
    if not entidade: return None
    campos_necessarios = CAMPOS_CADASTRO[entidade]
    for campo in campos_necessarios:
        if campo not in st.session_state.dados_recolhidos:
            return campo
    return None

def adicionar_mensagem(role, content):
    st.session_state.messages.append({"role": role, "content": content})
    with st.chat_message(role):
        if isinstance(content, pd.DataFrame):
            st.dataframe(content, hide_index=True, use_container_width=True)
        else:
            st.markdown(content, unsafe_allow_html=True)

def apresentar_resumo():
    entidade = st.session_state.get('conversa_em_andamento') or st.session_state.get('entidade_em_correcao')
    if not entidade:
        adicionar_mensagem("assistant", "Ocorreu um erro interno ao tentar apresentar o resumo.")
        return
    dados = st.session_state.dados_recolhidos
    resumo = f"Perfeito! Recolhi as informações. Por favor, confirme os dados para criar o **{entidade}**:\n"
    for key, value in dados.items():
        resumo += f"- **{key.replace('_', ' ').title()}:** {value}\n"
    adicionar_mensagem("assistant", resumo)
    st.session_state.pending_action = {"acao": f"criar_{entidade}", "dados": dados}
    st.session_state.conversa_em_andamento = None
    st.session_state.campo_para_corrigir = None
    st.session_state.entidade_em_correcao = None 

try:
    if prompt := st.chat_input("Como posso ajudar?"):
        adicionar_mensagem("user", prompt)
        with st.spinner("A pensar..."):
            if st.session_state.campo_para_corrigir:
                campo = st.session_state.campo_para_corrigir
                st.session_state.dados_recolhidos[campo] = prompt
                st.session_state.campo_para_corrigir = None
                apresentar_resumo()
                st.rerun()
            elif st.session_state.conversa_em_andamento:
                campo_atual = proximo_campo()
                st.session_state.dados_recolhidos[campo_atual] = prompt
                proximo = proximo_campo()
                if proximo:
                    adicionar_mensagem("assistant", f"Entendido. Agora, qual é o **{proximo.replace('_', ' ')}**?")
                else:
                    apresentar_resumo()
                    st.rerun()
            else:
                if prompt.strip().lower() == '#info':
                    response_data = {"acao": "ajuda"}
                else:
                    response_data = asyncio.run(get_flow_response(prompt, st.session_state['user_name']))
                acao = response_data.get('acao')
                if acao == 'iniciar_criacao':
                    entidade = response_data.get('entidade')
                    if entidade in CAMPOS_CADASTRO:
                        st.session_state.conversa_em_andamento = entidade
                        st.session_state.dados_recolhidos = {}
                        primeiro_campo = proximo_campo()
                        adicionar_mensagem("assistant", f"Ótimo! Para criar um novo **{entidade}**, vamos começar. Qual é o **{primeiro_campo.replace('_', ' ')}**?")
                    else:
                        adicionar_mensagem("assistant", "Desculpe, não sei como criar essa entidade.")
                elif acao in ['pesquisar_aparelho', 'pesquisar_movimentacoes']:
                    executor = executar_pesquisa_aparelho if acao == 'pesquisar_aparelho' else executar_pesquisa_movimentacoes
                    resultados = executor(response_data.get('filtros'))
                    if isinstance(resultados, pd.DataFrame) and not resultados.empty:
                        adicionar_mensagem("assistant", f"Encontrei {len(resultados)} resultado(s):")
                        adicionar_mensagem("assistant", resultados)
                    elif isinstance(resultados, str):
                        adicionar_mensagem("assistant", resultados)
                    else:
                        adicionar_mensagem("assistant", "Não encontrei nenhum resultado com esses critérios.")
                elif acao == 'ajuda':
                    adicionar_mensagem("assistant", get_info_text())
                elif acao == 'limpar_chat':
                    st.session_state.messages = [{"role": "assistant", "content": "Chat limpo! Como posso ajudar a recomeçar?"}]
                    st.session_state.pending_action = None
                    st.rerun()
                elif acao == 'logout':
                    adicionar_mensagem("assistant", "A encerrar a sessão...")
                    logout()
                elif acao == 'saudacao':
                    adicionar_mensagem("assistant", f"Olá {st.session_state['user_name']}! Sou o Flow. Diga `#info` para ver o que posso fazer.")
                else:
                    erro = response_data.get("dados", {}).get("erro", "Não consegui entender o seu pedido. Pode tentar reformular? Diga `#info` para ver exemplos.")
                    adicionar_mensagem("assistant", f"Desculpe, ocorreu um problema: {erro}")
    
    if st.session_state.pending_action:
        action_data = st.session_state.pending_action
        col1, col2, col3 = st.columns([1, 1, 5])
        with col1:
            if st.button("Sim, confirmo", type="primary"):
                resultado = ""
                acao_executar = action_data["acao"]
                dados_executar = action_data["dados"]
                if acao_executar == "criar_colaborador":
                    resultado = executar_criar_colaborador(dados_executar)
                elif acao_executar == "criar_aparelho":
                    resultado = executar_criar_aparelho(dados_executar)
                elif acao_executar == "criar_conta_gmail":
                    resultado = executar_criar_conta_gmail(dados_executar)
                
                if "Erro:" in resultado or "Não foi possível" in resultado:
                    adicionar_mensagem("assistant", f"❌ **Falha:** {resultado}")
                else:
                    adicionar_mensagem("assistant", f"✅ **Sucesso:** {resultado}")
                st.session_state.pending_action = None
                st.rerun()
        with col2:
            if st.button("Não, cancelar"):
                adicionar_mensagem("assistant", "Ação cancelada pelo utilizador.")
                st.session_state.pending_action = None
                st.rerun()
        with col3:
            if st.button("Corrigir uma informação"):
                st.session_state.entidade_em_correcao = action_data['acao'].split('_')[1]
                st.session_state.dados_para_corrigir = action_data["dados"]
                st.session_state.modo_correcao = True
                st.session_state.pending_action = None
                st.rerun()

    if st.session_state.get('modo_correcao'):
        dados_para_corrigir = st.session_state.dados_para_corrigir
        campo_selecionado = st.selectbox(
            "Qual campo deseja corrigir?",
            options=dados_para_corrigir.keys(),
            key="campo_correcao", index=None, placeholder="Selecione um campo..."
        )
        if campo_selecionado:
            st.session_state.campo_para_corrigir = campo_selecionado
            adicionar_mensagem("assistant", f"Entendido. Por favor, insira o novo valor para **{campo_selecionado.replace('_', ' ')}**.")
            st.session_state.modo_correcao = False
            st.session_state.dados_recolhidos = dados_para_corrigir
            st.rerun()
except Exception as e:
    st.error(f"Ocorreu um erro crítico na página do assistente: {e}")
    st.info("Se o problema persistir, verifique a configuração do banco de dados na página '⚙️ Configurações'.")

