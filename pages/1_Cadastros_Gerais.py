import streamlit as st
import pandas as pd
from sqlalchemy import text

# --- Autenticação e Permissão ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

# Apenas Administradores podem aceder a esta página
if st.session_state.get('user_role') != 'Administrador':
    st.error("Acesso negado. Apenas administradores podem aceder a esta página.")
    st.stop()

# --- Configuração de Layout (Header, Footer e CSS) ---
st.markdown("""
<style>
    /* Estilos da Logo */
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
    .sidebar-footer { text-align: center; padding-top: 20px; padding-bottom: 20px; }
    .sidebar-footer a { margin-right: 15px; text-decoration: none; }
    .sidebar-footer img { width: 25px; height: 25px; filter: grayscale(1) opacity(0.5); transition: filter 0.3s; }
    .sidebar-footer img:hover { filter: grayscale(0) opacity(1); }
    @media (prefers-color-scheme: dark) {
        .sidebar-footer img { filter: grayscale(1) opacity(0.6) invert(1); }
        .sidebar-footer img:hover { filter: opacity(1) invert(1); }
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
    if st.button("Logout", key="cadastros_logout"):
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

# --- Funções de Banco de Dados ---
def get_db_connection():
    return st.connection("supabase", type="sql")

# --- Funções para Marcas ---
@st.cache_data(ttl=30)
def carregar_marcas():
    conn = get_db_connection()
    df = conn.query("SELECT id, nome_marca FROM marcas ORDER BY nome_marca;")
    return df

def adicionar_marca(nome_marca):
    if not nome_marca or not nome_marca.strip():
        st.error("O nome da marca não pode ser vazio.")
        return
    try:
        conn = get_db_connection()
        with conn.session as s:
            query_check = text("SELECT id FROM marcas WHERE TRIM(LOWER(nome_marca)) = :nome")
            existe = s.execute(query_check, {"nome": nome_marca.strip().lower()}).fetchone()
            if existe:
                st.warning(f"A marca '{nome_marca}' já existe.")
                return

            query_insert = text("INSERT INTO marcas (nome_marca) VALUES (:nome)")
            s.execute(query_insert, {"nome": nome_marca.strip()})
            s.commit()
        st.success(f"Marca '{nome_marca}' adicionada com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Ocorreu um erro ao adicionar a marca: {e}")

def atualizar_marca(marca_id, nome_marca):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("UPDATE marcas SET nome_marca = :nome WHERE id = :id")
            s.execute(query, {"nome": nome_marca, "id": marca_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar marca: {e}")
        return False

# --- Funções para Modelos ---
@st.cache_data(ttl=30)
def carregar_modelos():
    conn = get_db_connection()
    df = conn.query("""
        SELECT m.id, m.nome_modelo, ma.nome_marca 
        FROM modelos m
        JOIN marcas ma ON m.marca_id = ma.id
        ORDER BY ma.nome_marca, m.nome_modelo;
    """)
    return df

def adicionar_modelo(nome_modelo, marca_id):
    if not nome_modelo or not nome_modelo.strip() or not marca_id:
        st.error("O nome do modelo e a marca são obrigatórios.")
        return
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("INSERT INTO modelos (nome_modelo, marca_id) VALUES (:nome, :marca_id)")
            s.execute(query, {"nome": nome_modelo.strip(), "marca_id": marca_id})
            s.commit()
        st.success(f"Modelo '{nome_modelo}' adicionado com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Ocorreu um erro ao adicionar o modelo: {e}")

def atualizar_modelo(modelo_id, nome_modelo, marca_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("UPDATE modelos SET nome_modelo = :nome, marca_id = :marca_id WHERE id = :id")
            s.execute(query, {"nome": nome_modelo, "marca_id": marca_id, "id": modelo_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar modelo: {e}")
        return False

# --- Funções para Setores ---
@st.cache_data(ttl=30)
def carregar_setores():
    conn = get_db_connection()
    df = conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
    return df

def adicionar_setor(nome_setor):
    if not nome_setor or not nome_setor.strip():
        st.error("O nome do setor não pode ser vazio.")
        return
    try:
        conn = get_db_connection()
        with conn.session as s:
            query_check = text("SELECT id FROM setores WHERE TRIM(LOWER(nome_setor)) = :nome")
            existe = s.execute(query_check, {"nome": nome_setor.strip().lower()}).fetchone()
            if existe:
                st.warning(f"O setor '{nome_setor}' já existe.")
                return
            
            query_insert = text("INSERT INTO setores (nome_setor) VALUES (:nome)")
            s.execute(query_insert, {"nome": nome_setor.strip()})
            s.commit()
        st.success(f"Setor '{nome_setor}' adicionado com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Ocorreu um erro ao adicionar o setor: {e}")

def atualizar_setor(setor_id, nome_setor):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("UPDATE setores SET nome_setor = :nome WHERE id = :id")
            s.execute(query, {"nome": nome_setor, "id": setor_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar setor: {e}")
        return False

# --- UI ---
st.title("Cadastros Gerais")
st.markdown("---")

try:
    option = st.radio(
        "Selecione o cadastro:",
        ("Marcas e Modelos", "Setores"),
        horizontal=True,
        label_visibility="collapsed",
        key="cadastros_tab_selector"
    )
    st.markdown("---")

    if option == "Marcas e Modelos":
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Marcas")
            with st.form("form_nova_marca", clear_on_submit=True):
                novo_nome_marca = st.text_input("Cadastrar nova marca")
                if st.form_submit_button("Adicionar Marca", use_container_width=True, type="primary"):
                    adicionar_marca(novo_nome_marca)
                    st.rerun()
            
            with st.expander("Ver e Editar Marcas", expanded=True):
                marcas_df = carregar_marcas()
                
                session_key_marcas = "original_marcas_df"
                if session_key_marcas not in st.session_state:
                    st.session_state[session_key_marcas] = marcas_df.copy()

                edited_marcas_df = st.data_editor(
                    marcas_df, 
                    key="edit_marcas", 
                    hide_index=True, 
                    disabled=["id"],
                    use_container_width=True
                )
                
                if st.button("Salvar Alterações de Marcas", use_container_width=True):
                    original_df = st.session_state[session_key_marcas]
                    changes_made = False
                    for index, row in edited_marcas_df.iterrows():
                         if index < len(original_df) and not row.equals(original_df.loc[index]):
                            if atualizar_marca(row['id'], row['nome_marca']):
                                st.toast(f"Marca '{row['nome_marca']}' atualizada!", icon="✅")
                                changes_made = True
                    if changes_made:
                        st.cache_data.clear()
                        del st.session_state[session_key_marcas]
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detetada.")

        with col2:
            st.subheader("Modelos")
            marcas_df_options = carregar_marcas()
            marcas_dict = {row['nome_marca']: row['id'] for index, row in marcas_df_options.iterrows()}

            with st.form("form_novo_modelo", clear_on_submit=True):
                novo_nome_modelo = st.text_input("Cadastrar novo modelo")
                marca_selecionada_nome = st.selectbox("Selecione a Marca", options=marcas_dict.keys(), index=None, placeholder="Selecione...")
                if st.form_submit_button("Adicionar Modelo", use_container_width=True, type="primary"):
                    if marca_selecionada_nome and novo_nome_modelo:
                        adicionar_modelo(novo_nome_modelo, marcas_dict[marca_selecionada_nome])
                        st.rerun()
                    else:
                        st.warning("Preencha o nome do modelo e selecione uma marca.")

            with st.expander("Ver e Editar Modelos", expanded=True):
                modelos_df = carregar_modelos()

                session_key_modelos = "original_modelos_df"
                if session_key_modelos not in st.session_state:
                    st.session_state[session_key_modelos] = modelos_df.copy()

                edited_modelos_df = st.data_editor(
                    modelos_df,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "nome_modelo": st.column_config.TextColumn("Modelo", required=True),
                        "nome_marca": st.column_config.SelectboxColumn(
                            "Marca", options=list(marcas_dict.keys()), required=True
                        )
                    },
                    hide_index=True, key="edit_modelos", use_container_width=True
                )
                if st.button("Salvar Alterações de Modelos", use_container_width=True):
                    original_df = st.session_state[session_key_modelos]
                    changes_made = False
                    for index, row in edited_modelos_df.iterrows():
                        if index < len(original_df) and not row.equals(original_df.loc[index]):
                            nova_marca_id = marcas_dict[row['nome_marca']]
                            if atualizar_modelo(row['id'], row['nome_modelo'], nova_marca_id):
                                st.toast(f"Modelo '{row['nome_modelo']}' atualizado!", icon="✅")
                                changes_made = True
                    
                    if changes_made:
                        st.cache_data.clear()
                        del st.session_state[session_key_modelos]
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detetada.")

    elif option == "Setores":
        col1_setor, col2_setor = st.columns([1, 2])
        with col1_setor:
            st.subheader("Adicionar Setor")
            with st.form("form_novo_setor", clear_on_submit=True):
                novo_nome_setor = st.text_input("Cadastrar novo setor")
                if st.form_submit_button("Adicionar Setor", use_container_width=True, type="primary"):
                    adicionar_setor(novo_nome_setor)
                    st.rerun()
        
        with col2_setor:
            st.subheader("Setores Registrados")
            with st.expander("Ver e Editar Setores", expanded=True):
                setores_df = carregar_setores()

                session_key_setores = "original_setores_df"
                if session_key_setores not in st.session_state:
                    st.session_state[session_key_setores] = setores_df.copy()

                edited_setores_df = st.data_editor(
                    setores_df, 
                    key="edit_setores", 
                    hide_index=True, 
                    disabled=["id"],
                    use_container_width=True
                )
                if st.button("Salvar Alterações de Setores", use_container_width=True):
                    original_df = st.session_state[session_key_setores]
                    changes_made = False
                    for index, row in edited_setores_df.iterrows():
                        if index < len(original_df) and not row.equals(original_df.loc[index]):
                            if atualizar_setor(row['id'], row['nome_setor']):
                                st.toast(f"Setor '{row['nome_setor']}' atualizado!", icon="✅")
                                changes_made = True
                    
                    if changes_made:
                        st.cache_data.clear()
                        del st.session_state[session_key_setores]
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração foi detetada.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de cadastros: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")
