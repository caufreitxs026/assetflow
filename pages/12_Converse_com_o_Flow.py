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
	/* --- Início do Bloco da Logo --- */
	.logo-text {
		font-family: 'Courier New', monospace;
		font-size: 28px; /* Ajuste o tamanho se necessário para as páginas internas */
		font-weight: bold;
		padding-top: 20px;
	}
	/* Estilos para o tema claro (light) */
	.logo-asset {
		color: #FFFFFF; /* Fonte branca */
		text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7); /* Sombra preta */
	}
	.logo-flow {
		color: #E30613; /* Fonte vermelha */
		text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7); /* Sombra preta */
	}

	/* Estilos para o tema escuro (dark) */
	@media (prefers-color-scheme: dark) {
		.logo-asset {
			color: #FFFFFF;
			text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7); /* Mantém a sombra preta para contraste */
		}
		.logo-flow {
			color: #FF4B4B; /* Um vermelho mais vibrante para o tema escuro */
			text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7); /* Sombra preta */
		}
	}
	/* --- Fim do Bloco da Logo --- */
    /* Estilos para o footer na barra lateral */
    .sidebar-footer { text-align: center; padding-top: 20px; padding-bottom: 20px; }
    .sidebar-footer a { margin-right: 15px; text-decoration: none; }
    .sidebar-footer img { width: 25px; height: 25px; filter: grayscale(1) opacity(0.5); transition: filter 0.3s; }
    .sidebar-footer img:hover { filter: grayscale(0) opacity(1); }
    @media (prefers-color-scheme: dark) { .sidebar-footer img { filter: grayscale(1) opacity(0.6) invert(1); } .sidebar-footer img:hover { filter: opacity(1) invert(1); } }
    
    /* --- ESTILOS ATUALIZADOS PARA A LOGO DO CHAT --- */
    .flow-title { display: flex; align-items: center; padding-bottom: 10px; }
    .flow-title .icon { font-size: 2.5em; margin-right: 15px; }
    .flow-title h1 { 
        font-family: 'Courier New', monospace; 
        font-size: 3em; 
        font-weight: bold; 
        margin: 0; 
        padding: 0; 
        line-height: 1;
        /* Adiciona a sombra a todo o texto do título */
        text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7);
    }
    .flow-title .text-chat { color: #003366; } 
    .flow-title .text-flow { color: #E30613; }
    @media (prefers-color-scheme: dark) { 
        .flow-title .text-chat { color: #FFFFFF; } 
        .flow-title .text-flow { color: #FF4B4B; } 
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
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
    else: return "Critério de pesquisa de colaborador inválido."
    query = f"SELECT c.nome_completo, c.cpf, c.gmail, s.nome_setor as funcao, c.status FROM colaboradores c LEFT JOIN setores s ON c.setor_id = s.id WHERE {' AND '.join(where_clauses)}"
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
    else: return "Critério de pesquisa de aparelho inválido."
    
    query_info = f"""
        SELECT ma.nome_marca || ' - ' || mo.nome_modelo as modelo, a.numero_serie, a.imei1, a.imei2, s.nome_status,
                CASE WHEN s.nome_status = 'Em uso' THEN h.colaborador_snapshot ELSE 'N/A' END as responsavel
        FROM aparelhos a
        LEFT JOIN modelos mo ON a.modelo_id = mo.id LEFT JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN status s ON a.status_id = s.id
        LEFT JOIN (SELECT aparelho_id, colaborador_snapshot, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn FROM historico_movimentacoes) h ON a.id = h.aparelho_id AND h.rn = 1
        WHERE {' AND '.join(where_clauses)};
    """
    info_df = conn.query(query_info, params=params)
    
    if info_df.empty: return pd.DataFrame()

    query_hist = f"""
        SELECT h.data_movimentacao, h.colaborador_snapshot, s.nome_status, h.observacoes
        FROM historico_movimentacoes h JOIN status s ON h.status_id = s.id JOIN aparelhos a ON h.aparelho_id = a.id
        WHERE {' AND '.join(where_clauses)} ORDER BY h.data_movimentacao DESC;
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
    
    query = f"SELECT h.data_movimentacao, h.colaborador_snapshot, a.numero_serie, s.nome_status, h.observacoes FROM historico_movimentacoes h JOIN aparelhos a ON h.aparelho_id = a.id JOIN status s ON h.status_id = s.id WHERE {' AND '.join(where_clauses)} ORDER BY h.data_movimentacao DESC"
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

    query = f"SELECT cg.email, cg.senha, c.nome_completo as vinculado_a FROM contas_gmail cg LEFT JOIN colaboradores c ON cg.colaborador_id = c.id WHERE {' AND '.join(where_clauses)}"
    return conn.query(query, params=params)

def executar_criar_colaborador(dados):
    req_keys = ['nome_completo', 'codigo', 'cpf', 'nome_setor']
    if not dados or not all(k in dados for k in req_keys):
        return f"Não foi possível criar o colaborador. Faltam informações: {', '.join(k for k in req_keys if k not in dados)}."
    
    conn = get_db_connection()
    with conn.session as s:
        try:
            s.begin()
            query_setor = text("SELECT id FROM setores WHERE nome_setor ILIKE :nome_setor")
            setor_result = s.execute(query_setor, {"nome_setor": dados['nome_setor']}).fetchone()
            if not setor_result:
                return f"Setor '{dados['nome_setor']}' não encontrado. Cadastro cancelado."
            setor_id = setor_result[0]

            query_insert = text("""
                INSERT INTO colaboradores (nome_completo, cpf, gmail, setor_id, data_cadastro, codigo, status) 
                VALUES (:nome, :cpf, :gmail, :setor_id, :data, :codigo, 'Ativo')
            """)
            s.execute(query_insert, {
                "nome": dados['nome_completo'], "cpf": dados['cpf'], "gmail": dados.get('gmail', ''), 
                "setor_id": setor_id, "data": date.today(), "codigo": dados['codigo']
            })
            s.commit()
            st.cache_data.clear() # Limpa o cache para refletir o novo cadastro
            return f"Colaborador '{dados['nome_completo']}' criado com sucesso!"
        except Exception as e:
            s.rollback()
            if 'unique constraint' in str(e).lower():
                return "Ocorreu um erro: o CPF ou o Código/Setor já existem."
            return f"Ocorreu um erro técnico: {e}"

def executar_criar_aparelho(dados):
    # (Implementação futura)
    return "A função para criar aparelhos ainda está em desenvolvimento."

def executar_criar_conta_gmail(dados):
    # (Implementação futura)
    return "A função para criar contas Gmail ainda está em desenvolvimento."

# --- Lógica do Chatbot ---
schema = {
    "type": "OBJECT",
    "properties": {
        "acao": {"type": "STRING", "enum": [
            "iniciar_criacao", "consultar_colaborador", "consultar_aparelho", "consultar_movimentacoes", 
            "consultar_gmail", "limpar_chat", "logout", "saudacao", "desconhecido", "cancelar"
        ]},
        "entidade": {"type": "STRING", "enum": ["colaborador", "aparelho", "conta_gmail"]},
        "filtros": { "type": "OBJECT", "properties": { "nome_colaborador": {"type": "STRING"}, "cpf": {"type": "STRING"}, "gmail": {"type": "STRING"}, "numero_serie": {"type": "STRING"}, "imei": {"type": "STRING"}, "data": {"type": "STRING"}, "email": {"type": "STRING"} } }
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
    contextual_prompt = f"O utilizador '{user_name}' pediu: {prompt}. Traduza este pedido para uma das ações JSON disponíveis."
    
    system_prompt = """
    Você é o Flow, um assistente especialista em gestão de ativos. Sua única função é traduzir os pedidos do utilizador para um formato JSON estruturado, de acordo com o schema fornecido.
    REGRAS IMPORTANTES:
    1. Para a ação 'consultar_gmail', o endereço de email DEVE ser extraído para o campo 'filtros.email'.
    2. Para a ação 'consultar_colaborador' usando um email, o endereço DEVE ser extraído para o campo 'filtros.gmail'.
    3. Para a ação 'iniciar_criacao', identifique a 'entidade' (colaborador, aparelho, conta_gmail) com base em palavras como 'criar', 'cadastrar', 'adicionar novo', etc.
    4. Se não entender o pedido, use a ação 'desconhecido'.
    """
    
    chatHistory = [
        {"role": "user", "parts": [{"text": system_prompt}]},
        {"role": "model", "parts": [{"text": "Entendido. Foco total em traduzir pedidos de gestão de ativos para JSON, seguindo as regras de extração."}]},
        {"role": "user", "parts": [{"text": contextual_prompt}]}
    ]
    payload = { "contents": chatHistory, "generationConfig": { "responseMimeType": "application/json", "responseSchema": schema } }
    
    try:
        apiKey = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return {"acao": "desconhecido", "filtros": {"erro": "Chave de API não configurada."}}

    # --- CORREÇÃO: Usa o modelo recomendado e mais recente ---
    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={apiKey}"
    
    result = await make_api_call(apiUrl, payload)

    if result.get("error"):
        return {"acao": "desconhecido", "filtros": {"erro": result["error"]}}
    if result.get('candidates'):
        try:
            json_text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(json_text)
        except (json.JSONDecodeError, KeyError, IndexError):
            return {"acao": "desconhecido", "filtros": {"erro": "A API retornou uma resposta em formato inesperado."}}
    return {"acao": "desconhecido", "filtros": {"erro": f"Resposta inválida da API: {result}"}}

def get_info_text():
    return """
    Olá! Sou o Flow, o seu assistente especialista. Aqui está o que posso fazer por si:

    ---
    ### **Consultar Informações**
    Pergunte-me sobre qualquer coisa no inventário.
    - **Sobre Colaboradores:**
      - `dados do colaborador [nome]`
      - `info do cpf [número]`
      - `quem usa o gmail [email]?`
    - **Sobre Aparelhos:**
      - `status do aparelho [n/s]`
      - `detalhes do imei [número]`
    - **Sobre Movimentações:**
      - `histórico do [nome]`
      - `movimentações do aparelho [n/s] em [data AAAA-MM-DD]`
    - **Sobre Contas Gmail:**
      - `senha do gmail [email]`
      - `qual o gmail do [nome]?`

    ---
    ### **Criar Novos Registos**
    Diga-me o que quer criar e eu guio-o no processo.
    - `criar colaborador`
    - `adicionar novo aparelho`
    - `cadastrar conta gmail`

    ---
    ### **Comandos do Chat**
    Use estes comandos para gerir a nossa conversa.
    - `#info`: Mostra esta mensagem de ajuda.
    - `limpar chat`: Apaga todo o nosso histórico.
    - `cancelar` ou `voltar`: Interrompe a ação atual.
    - `logout`: Encerra a sua sessão no sistema.
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

# --- UI ---
st.markdown("""<div class="flow-title"><span class="icon">💬</span><h1><span class="text-chat">Converse com o </span><span class="text-flow">Flow</span></h1></div>""", unsafe_allow_html=True)
st.markdown("---")
st.info("Sou o Flow, seu assistente especialista. Diga `#info` para ver os comandos.")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Como posso ajudar?"}]

async def handle_prompt(user_prompt):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    prompt_lower = user_prompt.strip().lower()

    # --- CORREÇÃO: Lógica para continuar uma conversa de cadastro ---
    if st.session_state.get('conversa_em_andamento'):
        entidade = st.session_state.conversa_em_andamento
        campos = CAMPOS_CADASTRO[entidade]
        dados_recolhidos = st.session_state.dados_recolhidos
        
        # Encontra o campo atual para salvar a resposta
        campo_atual = campos[len(dados_recolhidos)]
        dados_recolhidos[campo_atual] = user_prompt.strip()

        # Verifica se ainda há campos a serem preenchidos
        if len(dados_recolhidos) < len(campos):
            proximo_campo = campos[len(dados_recolhidos)]
            st.session_state.messages.append({"role": "assistant", "content": f"Entendido. Agora, qual é o **{proximo_campo.replace('_', ' ')}**?"})
        else:
            # Todos os dados foram recolhidos, executa a ação
            with st.spinner("A processar o seu pedido de criação..."):
                resultado_criacao = ""
                if entidade == "colaborador":
                    resultado_criacao = executar_criar_colaborador(dados_recolhidos)
                elif entidade == "aparelho":
                    resultado_criacao = executar_criar_aparelho(dados_recolhidos)
                elif entidade == "conta_gmail":
                    resultado_criacao = executar_criar_conta_gmail(dados_recolhidos)
                
                st.session_state.messages.append({"role": "assistant", "content": resultado_criacao})
                reset_conversation_flow() # Limpa o estado da conversa
        st.rerun()

    # Processa comandos universais primeiro
    elif prompt_lower == '#info':
        st.session_state.messages.append({"role": "assistant", "content": get_info_text()})
    elif prompt_lower == 'limpar chat':
        reset_chat_state()
    elif prompt_lower in ['cancelar', 'voltar', 'menu']:
        st.session_state.messages.append({"role": "assistant", "content": "Não há nenhuma ação em andamento para cancelar."})
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
                logout(rerun=False) # Evita o rerun imediato para mostrar a mensagem
                st.switch_page("app.py")
            elif acao == 'saudacao':
                st.session_state.messages.append({"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Sou o Flow. Diga `#info` para ver os comandos."})
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

# --- Loop de Exibição e Captura de Input ---
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

if prompt := st.chat_input("Como posso ajudar?"):
    asyncio.run(handle_prompt(prompt))
