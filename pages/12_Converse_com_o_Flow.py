import streamlit as st
import json
import pandas as pd
from auth import show_login_form, logout
import asyncio
import httpx
from datetime import date, datetime
from sqlalchemy import text

# --- Autenticação e Configuração da Página ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

# --- Configuração de Layout (Header, Footer e CSS) ---
st.markdown("""
<style>
    /* Estilos da Logo Principal */
    .logo-text { font-family: 'Courier New', monospace; font-size: 28px; font-weight: bold; padding-top: 20px; }
    .logo-asset { color: #003366; } .logo-flow { color: #E30613; }
    @media (prefers-color-scheme: dark) { .logo-asset { color: #FFFFFF; } .logo-flow { color: #FF4B4B; } }
    /* Estilos para o footer na barra lateral */
    .sidebar-footer { text-align: center; padding-top: 20px; padding-bottom: 20px; }
    .sidebar-footer a { margin-right: 15px; text-decoration: none; }
    .sidebar-footer img { width: 25px; height: 25px; filter: grayscale(1) opacity(0.5); transition: filter 0.3s; }
    .sidebar-footer img:hover { filter: grayscale(0) opacity(1); }
    @media (prefers-color-scheme: dark) { .sidebar-footer img { filter: grayscale(1) opacity(0.6) invert(1); } .sidebar-footer img:hover { filter: opacity(1) invert(1); } }
    /* Estilos para a Logo do Chat */
    .flow-title { display: flex; align-items: center; padding-bottom: 10px; }
    .flow-title .icon { font-size: 2.5em; margin-right: 15px; }
    .flow-title h1 { font-family: 'Courier New', monospace; font-size: 3em; font-weight: bold; margin: 0; padding: 0; line-height: 1; }
    .flow-title .text-chat { color: #003366; } .flow-title .text-flow { color: #E30613; }
    @media (prefers-color-scheme: dark) { .flow-title .text-chat { color: #FFFFFF; } .flow-title .text-flow { color: #FF4B4B; } }
</style>
""", unsafe_allow_html=True)

# --- Header (Logo no canto superior esquerdo) ---
st.markdown("""<div class="logo-text"><span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span></div>""", unsafe_allow_html=True)

# --- Barra Lateral ---
with st.sidebar:
    st.write(f"Bem-vindo, **{st.session_state['user_name']}**!")
    st.write(f"Cargo: **{st.session_state['user_role']}**")
    if st.button("Logout", key="flow_logout"):
        logout()
    st.markdown("---")
    st.markdown(f"""
        <div class="sidebar-footer">
            <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg"></a>
            <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg"></a>
        </div>
        """, unsafe_allow_html=True)

# --- Funções do Executor de Ações ---
def get_db_connection():
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def consultar_colaborador(filtros):
    if not filtros: return "Por favor, especifique o colaborador (nome, CPF ou Gmail)."
    conn = get_db_connection()
    params, where_clauses = {}, []
    if filtros.get("nome_colaborador"):
        where_clauses.append("c.nome_completo ILIKE :valor")
        params['valor'] = f"%{filtros['nome_colaborador']}%"
    elif filtros.get("cpf"):
        where_clauses.append("c.cpf = :valor")
        params['valor'] = filtros['cpf']
    elif filtros.get("gmail"):
        where_clauses.append("c.gmail ILIKE :valor")
        params['valor'] = f"%{filtros['gmail']}%"
    else:
        return "Critério de pesquisa de colaborador inválido."

    query = f"""
        SELECT c.nome_completo, c.cpf, c.gmail, s.nome_setor as funcao, c.status
        FROM colaboradores c
        LEFT JOIN setores s ON c.setor_id = s.id
        WHERE {' AND '.join(where_clauses)}
    """
    return conn.query(query, params=params)

@st.cache_data(ttl=30)
def consultar_aparelho_completo(filtros):
    if not filtros: return "Por favor, especifique o aparelho (N/S ou IMEI)."
    conn = get_db_connection()
    params, where_clauses = {}, []
    if filtros.get("numero_serie"):
        where_clauses.append("a.numero_serie ILIKE :valor")
        params['valor'] = f"%{filtros['numero_serie']}%"
    elif filtros.get("imei"):
        where_clauses.append("(a.imei1 = :valor OR a.imei2 = :valor)")
        params['valor'] = filtros['imei']
    else:
        return "Critério de pesquisa de aparelho inválido."
    
    query_info = f"""
        SELECT 
            ma.nome_marca || ' - ' || mo.nome_modelo as modelo,
            a.numero_serie, a.imei1, a.imei2, s.nome_status,
            CASE WHEN s.nome_status = 'Em uso' THEN h.colaborador_snapshot ELSE 'N/A' END as responsavel
        FROM aparelhos a
        LEFT JOIN modelos mo ON a.modelo_id = mo.id
        LEFT JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN status s ON a.status_id = s.id
        LEFT JOIN (
            SELECT aparelho_id, colaborador_snapshot, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
            FROM historico_movimentacoes
        ) h ON a.id = h.aparelho_id AND h.rn = 1
        WHERE {' AND '.join(where_clauses)};
    """
    info_df = conn.query(query_info, params=params)
    
    if info_df.empty: return pd.DataFrame()

    query_hist = f"""
        SELECT h.data_movimentacao, h.colaborador_snapshot, s.nome_status, h.observacoes
        FROM historico_movimentacoes h
        JOIN status s ON h.status_id = s.id
        JOIN aparelhos a ON h.aparelho_id = a.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY h.data_movimentacao DESC;
    """
    hist_df = conn.query(query_hist, params=params)
    
    return {"info": info_df, "historico": hist_df}

@st.cache_data(ttl=30)
def consultar_movimentacoes(filtros):
    if not filtros: return "Por favor, forneça um critério de pesquisa (colaborador, N/S, IMEI ou data)."
    conn = get_db_connection()
    params, where_clauses = {}, []
    if filtros.get("nome_colaborador"):
        where_clauses.append("h.colaborador_snapshot ILIKE :colab")
        params['colab'] = f"%{filtros['nome_colaborador']}%"
    if filtros.get("numero_serie"):
        where_clauses.append("a.numero_serie ILIKE :ns")
        params['ns'] = f"%{filtros['numero_serie']}%"
    if filtros.get("imei"):
        where_clauses.append("(a.imei1 = :imei OR a.imei2 = :imei)")
        params['imei'] = filtros['imei']
    if filtros.get("data"):
        try:
            data_valida = datetime.strptime(filtros['data'], '%Y-%m-%d').date()
            where_clauses.append("CAST(h.data_movimentacao AS DATE) = :data")
            params['data'] = data_valida
        except ValueError:
            return "Formato de data inválido. Por favor, use AAAA-MM-DD."
    
    if not where_clauses: return "Critério de pesquisa de movimentações inválido."
    
    query = f"""
        SELECT h.data_movimentacao, h.colaborador_snapshot, a.numero_serie, s.nome_status, h.observacoes
        FROM historico_movimentacoes h
        JOIN aparelhos a ON h.aparelho_id = a.id
        JOIN status s ON h.status_id = s.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY h.data_movimentacao DESC
    """
    return conn.query(query, params=params)

@st.cache_data(ttl=30)
def consultar_gmail(filtros):
    if not filtros: return "Por favor, especifique o Gmail ou o colaborador."
    conn = get_db_connection()
    params, where_clauses = {}, []
    if filtros.get("email"):
        where_clauses.append("cg.email ILIKE :valor")
        params['valor'] = f"%{filtros['email']}%"
    elif filtros.get("nome_colaborador"):
        where_clauses.append("c.nome_completo ILIKE :valor")
        params['valor'] = f"%{filtros['nome_colaborador']}%"
    else:
        return "Critério de pesquisa de Gmail inválido."

    query = f"""
        SELECT cg.email, cg.senha, c.nome_completo as vinculado_a
        FROM contas_gmail cg
        LEFT JOIN colaboradores c ON cg.colaborador_id = c.id
        WHERE {' AND '.join(where_clauses)}
    """
    return conn.query(query, params=params)

def executar_criar_colaborador(dados):
    if not dados or not all(k in dados for k in ['nome_completo', 'codigo', 'cpf', 'nome_setor']):
        return "Não foi possível criar o colaborador. Faltam informações essenciais (nome, código, CPF e setor)."
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            setor_id_res = s.execute(text("SELECT id FROM setores WHERE nome_setor ILIKE :nome LIMIT 1"), {"nome": f"%{dados['nome_setor']}%"}).fetchone()
            if not setor_id_res:
                s.rollback()
                return f"Erro: O setor '{dados['nome_setor']}' não foi encontrado."
            setor_id = setor_id_res[0]
            
            q_check = text("SELECT 1 FROM colaboradores WHERE (cpf = :cpf AND cpf IS NOT NULL AND cpf != '') OR (codigo = :codigo AND setor_id = :setor_id)")
            existe = s.execute(q_check, {"cpf": dados.get('cpf'), "codigo": dados.get('codigo'), "setor_id": setor_id}).fetchone()
            if existe:
                s.rollback()
                return "Erro: Já existe um colaborador com este CPF ou com este código neste setor."

            s.execute(
                text("INSERT INTO colaboradores (nome_completo, codigo, cpf, gmail, setor_id, data_cadastro, status) VALUES (:nome, :codigo, :cpf, :gmail, :setor_id, :data, 'Ativo')"),
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
                s.rollback()
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
                colab_res = s.execute(text("SELECT id FROM colaboradores WHERE nome_completo ILIKE :nome AND status = 'Ativo' LIMIT 1"), {"nome": f"%{dados['nome_colaborador']}%"}).fetchone()
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
    "properties": {
        "acao": {"type": "STRING", "enum": [
            "iniciar_criacao", "consultar_colaborador", "consultar_aparelho", "consultar_movimentacoes", 
            "consultar_gmail", "limpar_chat", "logout", "saudacao", "desconhecido", "cancelar"
        ]},
        "entidade": {"type": "STRING", "enum": ["colaborador", "aparelho", "conta_gmail"]},
        "filtros": {
            "type": "OBJECT", "properties": {
                "nome_colaborador": {"type": "STRING"}, "cpf": {"type": "STRING"}, "gmail": {"type": "STRING"},
                "numero_serie": {"type": "STRING"}, "imei": {"type": "STRING"},
                "data": {"type": "STRING"}, "email": {"type": "STRING"}
            }
        }
    },
    "required": ["acao"]
}

async def make_api_call(apiUrl, payload):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload, timeout=45)
                if response.status_code in [429, 503] and attempt < max_retries - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [429, 503] and attempt < max_retries - 1:
                continue
            return {"error": f"Erro na API ({e.response.status_code}). O serviço pode estar sobrecarregado ou a sua chave de API pode ter atingido o limite."}
        except Exception as e:
            return {"error": f"Ocorreu um erro de comunicação: {e}"}
    return {"error": "O serviço de IA está temporariamente indisponível. Por favor, tente mais tarde."}

async def get_flow_response(prompt, user_name):
    contextual_prompt = f"O utilizador '{user_name}' pediu: {prompt}. Traduza este pedido para uma das ações JSON disponíveis no schema. Foque-se apenas nas ações de gestão de inventário e comandos do chat."
    
    chatHistory = [
        {"role": "user", "parts": [{"text": "Você é o Flow, um assistente especialista em gestão de ativos. Sua única função é traduzir os pedidos do utilizador para um formato JSON estruturado. Suas funções são: 'iniciar_criacao' (para pedidos como 'criar', 'cadastrar', 'adicionar'), 'consultar_colaborador', 'consultar_aparelho', 'consultar_movimentacoes', 'consultar_gmail', e comandos de chat ('limpar chat', 'logout', 'saudacao', 'cancelar'). Se não entender, use 'desconhecido'."}]},
        {"role": "model", "parts": [{"text": "Entendido. Foco total em traduzir pedidos de gestão de ativos para JSON."}]},
        {"role": "user", "parts": [{"text": contextual_prompt}]}
    ]
    payload = { "contents": chatHistory, "generationConfig": { "responseMimeType": "application/json", "responseSchema": schema } }
    
    try:
        apiKey = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return {"acao": "desconhecido", "filtros": {"erro": "Chave de API não configurada."}}

    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={apiKey}"
    
    result = await make_api_call(apiUrl, payload)

    if result.get("error"):
        return {"acao": "desconhecido", "filtros": {"erro": result["error"]}}
    if result.get('candidates'):
        try:
            json_text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(json_text)
        except (json.JSONDecodeError, KeyError):
             return {"acao": "desconhecido", "filtros": {"erro": "A API retornou uma resposta em formato inesperado."}}
    return {"acao": "desconhecido", "filtros": {"erro": f"Resposta inválida da API: {result}"}}

def get_info_text():
    return """
    Olá! Sou o Flow, o seu assistente especialista.

    **1. Para Consultar:**
    - **Colaborador:** "dados do colaborador [nome]", "info do cpf [número]", "quem usa o gmail [email]?"
    - **Aparelho:** "status do aparelho [n/s]", "detalhes do imei [número]"
    - **Movimentações:** "histórico do [nome]", "movimentações do aparelho [n/s] em [data AAAA-MM-DD]"
    - **Contas Gmail:** "senha do gmail [email]", "qual o gmail do [nome]?"

    **2. Para Criar (Fluxo Guiado):**
    - "criar colaborador"
    - "adicionar novo aparelho"
    - "cadastrar conta gmail"

    **3. Comandos do Chat:**
    - `#info`: Mostra esta mensagem.
    - `limpar chat`: Apaga o histórico.
    - `cancelar` ou `voltar`: Interrompe a ação atual.
    - `logout`: Faz o logout do sistema.
    """

CAMPOS_CADASTRO = {
    "colaborador": ["codigo", "nome_completo", "cpf", "gmail", "nome_setor"],
    "aparelho": ["marca", "modelo", "numero_serie", "valor", "imei1", "imei2"],
    "conta_gmail": ["email", "senha", "telefone_recuperacao", "email_recuperacao", "nome_setor", "nome_colaborador"]
}

def reset_chat_state():
    st.session_state.messages = [{"role": "assistant", "content": "Chat limpo! Como posso ajudar a recomeçar?"}]
    st.session_state.pop('conversa_em_andamento', None)
    st.session_state.pop('dados_recolhidos', None)
    st.session_state.pop('pending_action', None)

def reset_conversation_flow():
    st.session_state.pop('conversa_em_andamento', None)
    st.session_state.pop('dados_recolhidos', None)
    st.session_state.pop('pending_action', None)
    st.session_state.messages.append({"role": "assistant", "content": "Ok, ação cancelada. Como posso ajudar agora?"})

def apresentar_resumo():
    entidade = st.session_state.get('conversa_em_andamento')
    if not entidade: return
    dados = st.session_state.dados_recolhidos
    resumo = f"Perfeito! Recolhi as informações. Por favor, confirme os dados para criar o **{entidade}**:\n"
    for key, value in dados.items():
        resumo += f"- **{key.replace('_', ' ').title()}:** {value}\n"
    st.session_state.messages.append({"role": "assistant", "content": resumo})
    st.session_state.pending_action = {"acao": f"criar_{entidade}", "dados": dados}
    st.session_state.conversa_em_andamento = None

# --- UI e Lógica Principal do Chat ---
st.markdown("""<div class="flow-title"><span class="icon">💬</span><h1><span class="text-chat">Converse com o </span><span class="text-flow">Flow</span></h1></div>""", unsafe_allow_html=True)
st.markdown("---")
st.info("Sou o Flow, seu assistente especialista. Diga `#info` para ver os comandos.")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Como posso ajudar?"}]

# Exibe o histórico de mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], pd.DataFrame):
            st.dataframe(message["content"], hide_index=True, use_container_width=True)
        elif isinstance(message["content"], dict) and 'info' in message["content"]:
            st.write("**Informações do Aparelho:**")
            st.dataframe(message["content"]["info"], hide_index=True, use_container_width=True)
            st.write("**Histórico de Movimentações:**")
            st.dataframe(message["content"]["historico"], hide_index=True, use_container_width=True,
                         column_config={"data_movimentacao": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm")})
        else:
            st.markdown(message["content"], unsafe_allow_html=True)

# Lógica de processamento e resposta
async def handle_response(user_prompt):
    prompt_lower = user_prompt.strip().lower()

    # Comandos universais
    if prompt_lower == '#info':
        st.session_state.messages.append({"role": "assistant", "content": get_info_text()})
    elif prompt_lower == 'limpar chat':
        reset_chat_state()
    elif prompt_lower in ['cancelar', 'voltar', 'menu']:
        if st.session_state.get('conversa_em_andamento'):
            reset_conversation_flow()
        else:
            st.session_state.messages.append({"role": "assistant", "content": "Não há nenhuma ação em andamento para cancelar."})
    
    # Lógica de conversa para cadastro
    elif st.session_state.get('conversa_em_andamento'):
        entidade = st.session_state.conversa_em_andamento
        campos = CAMPOS_CADASTRO.get(entidade, [])
        campo_atual = next((c for c in campos if c not in st.session_state.dados_recolhidos), None)
        if campo_atual:
            st.session_state.dados_recolhidos[campo_atual] = user_prompt
            proximo_campo = next((c for c in campos if c not in st.session_state.dados_recolhidos), None)
            if proximo_campo:
                st.session_state.messages.append({"role": "assistant", "content": f"Entendido. Agora, qual é o **{proximo_campo.replace('_', ' ')}**?"})
            else:
                apresentar_resumo()
    
    # Lógica para novos comandos (chamada à API)
    else:
        with st.spinner("A pensar..."):
            response_data = await get_flow_response(user_prompt, st.session_state['user_name'])
            acao = response_data.get('acao')
            filtros = response_data.get('filtros')
            entidade = response_data.get('entidade')
            
            resultados = None
            if acao == 'iniciar_criacao':
                if entidade in CAMPOS_CADASTRO:
                    st.session_state.conversa_em_andamento = entidade
                    st.session_state.dados_recolhidos = {}
                    primeiro_campo = CAMPOS_CADASTRO[entidade][0]
                    st.session_state.messages.append({"role": "assistant", "content": f"Ótimo! Para criar um novo **{entidade}**, vamos começar. Qual é o **{primeiro_campo.replace('_', ' ')}**?"})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "Desculpe, não sei como criar essa entidade."})
            elif acao == 'consultar_colaborador': resultados = consultar_colaborador(filtros)
            elif acao == 'consultar_aparelho': resultados = consultar_aparelho_completo(filtros)
            elif acao == 'consultar_movimentacoes': resultados = consultar_movimentacoes(filtros)
            elif acao == 'consultar_gmail': resultados = consultar_gmail(filtros)
            elif acao == 'logout':
                st.session_state.messages.append({"role": "assistant", "content": "A encerrar a sessão..."})
                logout()
            elif acao == 'saudacao':
                st.session_state.messages.append({"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Sou o Flow. Diga `#info` para ver o que posso fazer."})
            else:
                erro = response_data.get("filtros", {}).get("erro", "Não consegui entender o seu pedido.")
                st.session_state.messages.append({"role": "assistant", "content": f"Desculpe, ocorreu um problema: {erro}"})

            if isinstance(resultados, (pd.DataFrame, dict, str)):
                if isinstance(resultados, pd.DataFrame) and resultados.empty:
                    st.session_state.messages.append({"role": "assistant", "content": "Não encontrei nenhum resultado com esses critérios."})
                elif isinstance(resultados, dict) and resultados.get("info", pd.DataFrame()).empty:
                    st.session_state.messages.append({"role": "assistant", "content": "Não encontrei nenhum resultado com esses critérios."})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": resultados})
    st.rerun()

# Captura o input do utilizador
if prompt := st.chat_input("Como posso ajudar?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    # O rerun vai disparar a lógica acima
    st.rerun()

