import streamlit as st
from auth import show_login_form, hash_password
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

# --- Funções do Banco de Dados ---
def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

def inicializar_db():
    """Lê o schema.sql e executa-o para criar/recriar as tabelas."""
    try:
        with open('schema.sql', 'r') as f:
            sql_script = f.read()
        
        conn = get_db_connection()
        with conn.session as s:
            # PostgreSQL não suporta múltiplos comandos em uma única chamada execute, 
            # então dividimos o script em comandos individuais.
            # Ignoramos linhas vazias e comentários.
            comandos = [cmd for cmd in sql_script.split(';') if cmd.strip()]
            for comando in comandos:
                s.execute(text(comando))
            s.commit()
        return True, "Banco de dados inicializado com sucesso!"
    except FileNotFoundError:
        return False, "Erro: Ficheiro 'schema.sql' não encontrado. Certifique-se de que ele está no diretório principal do seu projeto."
    except Exception as e:
        return False, f"Ocorreu um erro ao inicializar o banco de dados: {e}"

# --- Interface do Usuário ---
st.title("Configurações do Sistema")
st.markdown("---")

st.subheader("Inicialização do Banco de Dados")
st.warning(
    """
    **ATENÇÃO: AÇÃO DESTRUTIVA!**

    - Use esta função **APENAS UMA VEZ** para a configuração inicial do sistema.
    - Clicar neste botão irá **APAGAR TODAS AS TABELAS E DADOS EXISTENTES** e recriá-los do zero.
    - **NÃO** utilize esta função se já tiver dados importantes no sistema.
    """
)

if 'confirm_init' not in st.session_state:
    st.session_state.confirm_init = False

if st.button("Inicializar Banco de Dados", type="primary"):
    st.session_state.confirm_init = True

if st.session_state.confirm_init:
    st.error("Tem a certeza absoluta de que deseja apagar todos os dados e recriar a estrutura do banco de dados?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, eu entendo os riscos e quero continuar.", use_container_width=True):
            with st.spinner("A criar tabelas e a configurar o sistema..."):
                sucesso, mensagem = inicializar_db()
                if sucesso:
                    st.success(mensagem)
                    st.info("O utilizador 'admin' com a senha '123' foi criado. Altere esta senha assim que possível.")
                else:
                    st.error(mensagem)
            st.session_state.confirm_init = False
            st.rerun()

    with col2:
        if st.button("Não, cancelar operação.", use_container_width=True):
            st.session_state.confirm_init = False
            st.info("Operação de inicialização cancelada.")
            st.rerun()

