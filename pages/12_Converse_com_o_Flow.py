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
# (As funções auxiliares e a lógica do chatbot permanecem as mesmas, mas serão chamadas pela nova estrutura abaixo)

# Inicialização do estado da sessão
if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": f"Olá {st.session_state['user_name']}! Como posso ajudar?"}]
if "pending_action" not in st.session_state: st.session_state.pending_action = None
if "conversa_em_andamento" not in st.session_state: st.session_state.conversa_em_andamento = None
if "dados_recolhidos" not in st.session_state: st.session_state.dados_recolhidos = {}
if "campo_para_corrigir" not in st.session_state: st.session_state.campo_para_corrigir = None
if "modo_correcao" not in st.session_state: st.session_state.modo_correcao = False

def adicionar_mensagem(role, content):
    st.session_state.messages.append({"role": role, "content": content})

# ... (outras funções auxiliares como get_info_text, reset_chat_state, etc., permanecem as mesmas) ...

async def handle_prompt(prompt):
    # Lógica de processamento do prompt do utilizador
    adicionar_mensagem("user", prompt)
    prompt_lower = prompt.strip().lower()

    if prompt_lower == '#info':
        adicionar_mensagem("assistant", get_info_text())
    elif prompt_lower == 'limpar chat':
        reset_chat_state()
    elif prompt_lower in ['cancelar', 'voltar', 'menu']:
        if st.session_state.get('conversa_em_andamento') or st.session_state.get('pending_action'):
            reset_conversation_flow()
        else:
            adicionar_mensagem("assistant", "Não há nenhuma ação em andamento para cancelar.")
    
    elif st.session_state.get('conversa_em_andamento'):
        # Lógica de cadastro
        pass # Placeholder for brevity, o código completo será inserido

    else:
        # Lógica de novos comandos com chamada à API
        with st.spinner("A pensar..."):
            response_data = await get_flow_response(prompt, st.session_state['user_name'])
            # ... resto da lógica de processamento
            pass # Placeholder for brevity

# --- Interface Principal do Chat ---
st.markdown("""<div class="flow-title"><span class="icon">💬</span><h1><span class="text-chat">Converse com o </span><span class="text-flow">Flow</span></h1></div>""", unsafe_allow_html=True)
st.markdown("---")
st.info("Sou o Flow, seu assistente especialista. Diga `#info` para ver os comandos.")

# 1. Exibe o histórico de mensagens
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

# (O código para os botões de confirmação e correção vem aqui)

# 2. Captura o input do utilizador no final
if prompt := st.chat_input("Como posso ajudar?"):
    asyncio.run(handle_prompt(prompt))
    st.rerun()

