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
    /* Estilo para as fontes da pesquisa Google */
    .source-link {
        font-size: 0.8rem;
        color: #888;
        text-decoration: none;
        margin-right: 10px;
    }
    .source-link:hover {
        text-decoration: underline;
    }
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

def executar_pesquisa_aparelho(filtros):
    if not filtros:
        return "Por favor, forneça um critério de pesquisa, como o nome do colaborador ou o número de série."
    conn = get_db_connection()
    query = """
        WITH UltimoResponsavel AS (
            SELECT
                h.aparelho_id, h.colaborador_id, h.colaborador_snapshot,
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

def executar_pesquisa_movimentacoes(filtros):
    if not filtros:
        return "Por favor, forneça um critério de pesquisa (colaborador, N/S ou data)."
    conn = get_db_connection()
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
    "properties": { "acao": { "type": "STRING", "enum": ["iniciar_criacao", "fornecer_dado", "pesquisar_aparelho", "pesquisar_movimentacoes", "pesquisar_na_web", "limpar_chat", "logout", "saudacao", "desconhecido", "cancelar"] }, "entidade": {"type": "STRING", "enum": ["colaborador", "aparelho", "conta_gmail"]}, "dados": { "type": "OBJECT", "properties": { "valor_dado": {"type": "STRING"} } }, "filtros": { "type": "OBJECT", "properties": { "nome_colaborador": {"type": "STRING"}, "numero_serie": {"type": "STRING"}, "data": {"type": "STRING"} } } },
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
    contextual_prompt = f"O utilizador '{user_name}' pediu: {prompt}. Palavras como 'cancelar', 'voltar' ou 'menu' devem ser interpretadas como a ação 'cancelar'. Se o pedido não corresponder a nenhuma das funções de gestão de inventário (criar ou pesquisar), classifique a ação como 'pesquisar_na_web'."
    
    chatHistory = [
        {"role": "user", "parts": [{"text": "Você é o Flow, um assistente para um sistema de gestão de ativos. Sua função é interpretar os pedidos do utilizador e traduzi-los para um formato JSON estruturado. Suas funções são: 'iniciar_criacao', 'pesquisar_aparelho', 'pesquisar_movimentacoes'. Se o pedido for um comando de chat ('limpar chat', 'logout', 'saudacao', 'cancelar'), use a ação correspondente. Se for uma pergunta de conhecimento geral (ex: 'qual a capital do Brasil?'), use a ação 'pesquisar_na_web'. Se não entender, use 'desconhecido'."}]},
        {"role": "model", "parts": [{"text": "Entendido."}]},
        {"role": "user", "parts": [{"text": contextual_prompt}]}
    ]
    payload = { "contents": chatHistory, "generationConfig": { "responseMimeType": "application/json", "responseSchema": schema } }
    
    try:
        apiKey = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return {"acao": "desconhecido", "dados": {"erro": "Chave de API não configurada."}}

    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={apiKey}"
    
    result = await make_api_call(apiUrl, payload)

    if result.get("error"):
        return {"acao": "desconhecido", "dados": {"erro": result["error"]}}
    if result.get('candidates'):
        try:
            json_text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(json_text)
        except (json.JSONDecodeError, KeyError):
             return {"acao": "desconhecido", "dados": {"erro": "A API retornou uma resposta em formato inesperado."}}
    return {"acao": "desconhecido", "dados": {"erro": f"Resposta inválida da API: {result}"}}

async def get_grounded_response(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }
    try:
        apiKey = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return {"text": "Chave de API não configurada.", "sources": []}
    
    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={apiKey}"
    
    result = await make_api_call(apiUrl, payload)

    if result.get("error"):
        return {"text": result["error"], "sources": []}
    
    candidate = result.get('candidates', [{}])[0]
    text_response = candidate.get('content', {}).get('parts', [{}])[0].get('text', "Não consegui encontrar uma resposta.")
    
    sources = []
    grounding_metadata = candidate.get('groundingMetadata', {})
    if grounding_metadata and grounding_metadata.get('groundingAttributions'):
        sources = [
            {"uri": attr['web']['uri'], "title": attr['web']['title']}
            for attr in grounding_metadata['groundingAttributions']
            if 'web' in attr and attr.get('web')
        ]
    return {"text": text_response, "sources": sources}

def get_info_text():
    return """
    Olá! Sou o Flow, o seu assistente. Agora estou mais poderoso!

    **1. Perguntas sobre o Inventário:**
    - "pesquisar aparelho do João Silva"
    - "encontrar aparelho com n/s ABC123"
    - "mostrar histórico do aparelho XYZ"
    
    **2. Perguntas Gerais (com acesso à Internet!):**
    - "qual o preço do novo iPhone?"
    - "quem ganhou o último campeonato brasileiro?"
    - "resuma as notícias de tecnologia de hoje"

    **3. Para Criar Novos Registos (Fluxo Guiado):**
    - "criar colaborador"
    - "adicionar novo aparelho"
    - "cadastrar conta gmail"

    **4. Comandos do Chat:**
    - `#info`: Mostra esta mensagem.
    - `limpar chat`: Apaga o histórico da conversa.
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
    st.session_state.pending_action = None
    st.session_state.conversa_em_andamento = None
    st.session_state.dados_recolhidos = {}
    st.session_state.campo_para_corrigir = None
    st.session_state.modo_correcao = False

def reset_conversation_flow():
    st.session_state.conversa_em_andamento = None
    st.session_state.dados_recolhidos = {}
    st.session_state.pending_action = None
    st.session_state.campo_para_corrigir = None
    st.session_state.modo_correcao = False
    adicionar_mensagem("assistant", "Ok, ação cancelada. Como posso ajudar agora?")

# --- Interface do Chatbot ---
st.markdown("""<div class="flow-title"><span class="icon">💬</span><h1><span class="text-chat">Converse com o </span><span class="text-flow">Flow</span></h1></div>""", unsafe_allow_html=True)
st.markdown("---")
st.info("Sou o Flow, seu assistente inteligente. Diga `#info` para ver os comandos.")

if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Como posso ajudar?"}]
if "pending_action" not in st.session_state: st.session_state.pending_action = None
if "conversa_em_andamento" not in st.session_state: st.session_state.conversa_em_andamento = None
if "dados_recolhidos" not in st.session_state: st.session_state.dados_recolhidos = {}
if "campo_para_corrigir" not in st.session_state: st.session_state.campo_para_corrigir = None
if "modo_correcao" not in st.session_state: st.session_state.modo_correcao = False

# Exibe o histórico do chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], pd.DataFrame):
            st.dataframe(message["content"], hide_index=True, use_container_width=True)
        else:
            st.markdown(message["content"], unsafe_allow_html=True)

def proximo_campo():
    entidade = st.session_state.conversa_em_andamento
    if not entidade: return None
    for campo in CAMPOS_CADASTRO.get(entidade, []):
        if campo not in st.session_state.dados_recolhidos:
            return campo
    return None

def adicionar_mensagem(role, content):
    st.session_state.messages.append({"role": role, "content": content})

def apresentar_resumo():
    entidade = st.session_state.get('conversa_em_andamento') or st.session_state.get('entidade_em_correcao')
    if not entidade:
        adicionar_mensagem("assistant", "Ocorreu um erro interno ao tentar apresentar o resumo.")
        return
    dados = st.session_state.dados_recolhidos
    resumo = f"Perfeito! Recolhi as informações. Por favor, confirme os dados para criar o **{entidade}**:\n"
    for key, value in dados.items():
        resumo += f"- **{key.replace('_', ' ').title()}:** {value}\n"
    st.session_state.messages.append({"role": "assistant", "content": resumo})
    st.session_state.pending_action = {"acao": f"criar_{entidade}", "dados": dados}
    st.session_state.conversa_em_andamento = None
    st.session_state.campo_para_corrigir = None
    st.session_state.entidade_em_correcao = None

# --- Loop Principal do Chat ---
if prompt := st.chat_input("Como posso ajudar?"):
    adicionar_mensagem("user", prompt)
    prompt_lower = prompt.strip().lower()

    if prompt_lower == '#info':
        adicionar_mensagem("assistant", get_info_text())
    elif prompt_lower == 'limpar chat':
        reset_chat_state()
    elif prompt_lower in ['cancelar', 'voltar', 'menu']:
        if st.session_state.conversa_em_andamento or st.session_state.pending_action:
            reset_conversation_flow()
        else:
            adicionar_mensagem("assistant", "Não há nenhuma ação em andamento para cancelar. Como posso ajudar?")
    elif st.session_state.conversa_em_andamento:
        campo_atual = proximo_campo()
        if campo_atual:
            st.session_state.dados_recolhidos[campo_atual] = prompt
            proximo = proximo_campo()
            if proximo:
                adicionar_mensagem("assistant", f"Entendido. Agora, qual é o **{proximo.replace('_', ' ')}**?")
            else:
                apresentar_resumo()
    else:
        with st.spinner("A pensar..."):
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
            
            elif acao == 'pesquisar_na_web':
                with st.spinner("A pesquisar na web..."):
                    grounded_response = asyncio.run(get_grounded_response(prompt))
                    resposta = grounded_response['text']
                    fontes = grounded_response['sources']
                    if fontes:
                        resposta += "\n\n**Fontes:**\n"
                        for i, fonte in enumerate(fontes):
                            resposta += f"<a href='{fonte['uri']}' target='_blank' class='source-link'>{i+1}. {fonte['title']}</a> "
                    adicionar_mensagem("assistant", resposta)

            elif acao == 'logout':
                adicionar_mensagem("assistant", "A encerrar a sessão...")
                logout()
            
            elif acao == 'saudacao':
                adicionar_mensagem("assistant", f"Olá {st.session_state['user_name']}! Sou o Flow. Diga `#info` para ver o que posso fazer.")

            elif acao == 'cancelar': 
                reset_conversation_flow()
            
            else:
                erro = response_data.get("dados", {}).get("erro", "Não consegui entender o seu pedido. Pode tentar reformular? Diga `#info` para ver exemplos.")
                adicionar_mensagem("assistant", f"Desculpe, ocorreu um problema: {erro}")
    
    st.rerun()

# --- Botões de Confirmação e Correção ---
if st.session_state.pending_action:
    action_data = st.session_state.pending_action
    col1, col2, col3 = st.columns([1.2, 1, 5])
    
    with col1:
        if st.button("Sim, confirmo", type="primary"):
            resultado = ""
            acao_executar = action_data["acao"]
            dados_executar = action_data["dados"]
            
            if acao_executar == "criar_colaborador": resultado = executar_criar_colaborador(dados_executar)
            elif acao_executar == "criar_aparelho": resultado = executar_criar_aparelho(dados_executar)
            elif acao_executar == "criar_conta_gmail": resultado = executar_criar_conta_gmail(dados_executar)

            if "Erro:" in resultado or "Não foi possível" in resultado:
                adicionar_mensagem("assistant", f"❌ **Falha:** {resultado}")
            else:
                adicionar_mensagem("assistant", f"✅ **Sucesso:** {resultado}")

            st.session_state.pending_action = None
            st.rerun()

    with col2:
        if st.button("Não, cancelar"):
            reset_conversation_flow()
            st.rerun()

    with col3:
        if st.button("Corrigir"):
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

