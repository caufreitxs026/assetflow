import streamlit as st
import pandas as pd
from auth import show_login_form, hash_password # Importa a função de hash
from sqlalchemy import text

# --- Autenticação e Permissão ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

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
    if st.button("Logout"):
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

# --- Configurações da Página ---
st.title("Gerenciamento de Usuários")
st.markdown("---")

# --- Funções do Banco de Dados (MODIFICADAS PARA POSTGRESQL) ---
def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

def adicionar_usuario(nome, login, senha, cargo):
    """Adiciona um novo usuário ao banco de dados."""
    if not all([nome, login, senha, cargo]):
        st.error("Todos os campos são obrigatórios.")
        return
    try:
        conn = get_db_connection()
        senha_hashed = hash_password(senha)
        with conn.session as s:
            query = text("INSERT INTO usuarios (nome, login, senha, cargo) VALUES (:nome, :login, :senha, :cargo)")
            s.execute(query, {"nome": nome, "login": login, "senha": senha_hashed, "cargo": cargo})
            s.commit()
        st.success(f"Usuário '{login}' criado com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        if 'unique constraint' in str(e).lower() and 'usuarios_login_key' in str(e).lower():
            st.error(f"O login '{login}' já existe.")
        else:
            st.error(f"Ocorreu um erro ao criar o usuário: {e}")

@st.cache_data(ttl=30)
def carregar_usuarios():
    """Carrega a lista de usuários do banco de dados."""
    conn = get_db_connection()
    df = conn.query("SELECT id, nome, login, cargo FROM usuarios ORDER BY nome")
    return df

def atualizar_usuario(user_id, nome, cargo):
    """Atualiza os dados de um usuário existente."""
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("UPDATE usuarios SET nome = :nome, cargo = :cargo WHERE id = :id")
            s.execute(query, {"nome": nome, "cargo": cargo, "id": user_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar o usuário ID {user_id}: {e}")
        return False

def excluir_usuario(user_id):
    """Exclui um usuário do banco de dados."""
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("DELETE FROM usuarios WHERE id = :id")
            s.execute(query, {"id": user_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir o usuário ID {user_id}: {e}")
        return False

# --- Interface do Usuário ---
try:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Adicionar Novo Usuário")
        with st.form("form_novo_usuario", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            login = st.text_input("Login de Acesso")
            senha = st.text_input("Senha", type="password")
            cargo = st.selectbox("Cargo/Permissão", ["Administrador", "Editor", "Leitor"], index=None, placeholder="Selecione o cargo...")
            
            if st.form_submit_button("Criar Usuário", use_container_width=True):
                adicionar_usuario(nome, login, senha, cargo)
                st.rerun()

    with col2:
        with st.expander("Ver, Editar e Excluir Usuários", expanded=True):
            usuarios_df = carregar_usuarios()
            
            edited_df = st.data_editor(
                usuarios_df,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "nome": st.column_config.TextColumn("Nome", required=True),
                    "login": st.column_config.TextColumn("Login", disabled=True),
                    "cargo": st.column_config.SelectboxColumn(
                        "Cargo",
                        options=["Administrador", "Editor", "Leitor"],
                        required=True,
                    ),
                },
                hide_index=True,
                num_rows="dynamic",
                key="usuarios_editor"
            )

            if st.button("Salvar Alterações", use_container_width=True):
                # Lógica para Exclusão
                deleted_ids = set(usuarios_df['id']) - set(edited_df['id'])
                for user_id in deleted_ids:
                    if st.session_state['username'] == usuarios_df.loc[usuarios_df['id'] == user_id, 'login'].iloc[0]:
                        st.error("Não é possível excluir o seu próprio utilizador.")
                    elif excluir_usuario(user_id):
                        st.toast(f"Utilizador ID {user_id} excluído!", icon="🗑️")

                # Lógica para Atualização
                # Compara o dataframe editado com o original para encontrar mudanças
                if not edited_df.equals(usuarios_df.loc[edited_df.index]):
                    diff_df = pd.concat([edited_df, usuarios_df]).drop_duplicates(keep=False)
                    for index, row in diff_df.iterrows():
                        if row['id'] in edited_df['id'].values: # Garante que é uma linha atualizada
                            user_id = row['id']
                            novo_nome = row['nome']
                            novo_cargo = row['cargo']
                            if atualizar_usuario(user_id, novo_nome, novo_cargo):
                                st.toast(f"Utilizador '{novo_nome}' atualizado!", icon="✅")
                
                # Recarrega a página para mostrar os dados atualizados
                st.rerun()

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de utilizadores: {e}")
    st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")
