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
        <span class="logo-text"><span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span>
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

def atualizar_senha_usuario(user_id, nova_senha):
    """Atualiza a senha de um usuário específico."""
    if not nova_senha:
        st.error("O campo 'Nova Senha' não pode estar vazio.")
        return False
    try:
        conn = get_db_connection()
        nova_senha_hashed = hash_password(nova_senha)
        with conn.session as s:
            query = text("UPDATE usuarios SET senha = :senha WHERE id = :id")
            s.execute(query, {"senha": nova_senha_hashed, "id": user_id})
            s.commit()
        st.cache_data.clear() # Limpa o cache para futuras operações
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar a senha do usuário ID {user_id}: {e}")
        return False


def excluir_usuario(user_id):
    """Exclui um usuário do banco de dados."""
    # --- REGRA DE NEGÓCIO: IMPEDIR AUTOEXCLUSÃO ---
    if user_id == st.session_state.get('user_id'):
        st.error("Ação bloqueada: Não é possível excluir o seu próprio utilizador.")
        return False
        
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

# --- Interface do Usuário com Radio Buttons ---
try:
    option = st.radio(
        "Selecione a operação:",
        ("Cadastrar Novo Usuário", "Consultar, Editar e Gerenciar Senhas"),
        horizontal=True,
        label_visibility="collapsed"
    )
    st.markdown("---")

    if option == "Cadastrar Novo Usuário":
        st.subheader("Adicionar Novo Usuário")
        with st.form("form_novo_usuario", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            login = st.text_input("Login de Acesso")
            senha = st.text_input("Senha", type="password")
            cargo = st.selectbox("Cargo/Permissão", ["Administrador", "Editor", "Leitor"], index=None, placeholder="Selecione o cargo...")
            
            if st.form_submit_button("Criar Usuário", use_container_width=True):
                adicionar_usuario(nome, login, senha, cargo)
                st.rerun()

    elif option == "Consultar, Editar e Gerenciar Senhas":
        st.subheader("Lista de Usuários")
        
        usuarios_df = carregar_usuarios()
        
        # Guardar uma cópia original no session_state para comparação
        if 'original_users_df' not in st.session_state:
            st.session_state.original_users_df = usuarios_df.copy()

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
            key="usuarios_editor",
            use_container_width=True
        )

        if st.button("Salvar Alterações de Nome/Cargo", use_container_width=True):
            changes_made = False
            original_df = st.session_state.original_users_df

            # Lógica para Exclusão
            deleted_ids = set(original_df['id']) - set(edited_df['id'])
            for user_id in deleted_ids:
                if excluir_usuario(user_id):
                    st.toast(f"Utilizador ID {user_id} excluído!", icon="🗑️")
                    changes_made = True
            
            # Lógica para Atualização
            original_df_indexed = original_df.set_index('id')
            edited_df_indexed = edited_df.set_index('id')
            common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)
            
            for user_id in common_ids:
                original_row = original_df_indexed.loc[user_id]
                edited_row = edited_df_indexed.loc[user_id]
                if not original_row.equals(edited_row):
                    if atualizar_usuario(user_id, edited_row['nome'], edited_row['cargo']):
                        st.toast(f"Utilizador '{edited_row['nome']}' atualizado!", icon="✅")
                        changes_made = True

            if changes_made:
                del st.session_state.original_users_df # Limpa para forçar recarregamento
                st.rerun()
            else:
                st.info("Nenhuma alteração foi detetada.")

        st.markdown("---")
        
        st.subheader("Redefinir Senha de um Usuário")
        usuarios_list = carregar_usuarios()
        usuarios_dict = {f"{row['nome']} ({row['login']})": row['id'] for index, row in usuarios_list.iterrows()}
        
        with st.form("form_reset_senha", clear_on_submit=True):
            usuario_selecionado_str = st.selectbox(
                "Selecione o usuário",
                options=usuarios_dict.keys(),
                index=None,
                placeholder="Selecione um usuário para redefinir a senha..."
            )
            nova_senha = st.text_input("Nova Senha", type="password")
            
            if st.form_submit_button("Atualizar Senha", use_container_width=True, type="primary"):
                if usuario_selecionado_str and nova_senha:
                    user_id_para_reset = usuarios_dict[usuario_selecionado_str]
                    if atualizar_senha_usuario(user_id_para_reset, nova_senha):
                        st.success(f"Senha do usuário '{usuario_selecionado_str.split(' (')[0]}' foi atualizada com sucesso!")
                else:
                    st.warning("Por favor, selecione um usuário e digite uma nova senha.")


except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de utilizadores: {e}")
    st.info("Se esta é a primeira configuração, por favor, vá até a página 'Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")

