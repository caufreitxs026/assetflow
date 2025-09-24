import streamlit as st
import hashlib
from sqlalchemy import text 
import secrets
from datetime import datetime, timedelta
# Importamos a nossa nova função de envio de e-mail. Certifique-se de que o ficheiro email_utils.py está na mesma pasta.
from email_utils import enviar_email_de_redefinicao

def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

def hash_password(password):
    """Gera um hash seguro para a senha."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    """Verifica as credenciais do utilizador no banco de dados PostgreSQL."""
    conn = get_db_connection()
    hashed_password = hash_password(password)
    
    query = "SELECT * FROM usuarios WHERE login = :login AND senha = :senha"
    
    user_df = conn.query(query, params={"login": username, "senha": hashed_password})
    
    if not user_df.empty:
        user = user_df.iloc[0].to_dict()
        
        st.session_state['logged_in'] = True
        st.session_state['username'] = user['login']
        st.session_state['user_role'] = user['cargo']
        st.session_state['user_name'] = user['nome']
        # --- Adicionado para a lógica de autoexclusão ---
        st.session_state['user_id'] = user['id'] 
        return True
        
    return False

# --- NOVA FUNÇÃO ---
def iniciar_redefinicao_de_senha(login):
    """Inicia o processo de redefinição de senha para um utilizador."""
    conn = get_db_connection()
    with conn.session as s:
        s.begin()
        # 1. Encontrar o utilizador pelo login para obter o ID e o nome
        query_user = text("SELECT id, nome FROM usuarios WHERE login = :login")
        user = s.execute(query_user, {"login": login}).fetchone()

        if not user:
            st.error("Login não encontrado no sistema.")
            s.rollback()
            return

        # 2. Gerar e guardar o token seguro
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=15) # Token válido por 15 minutos

        query_insert_token = text("""
            INSERT INTO password_resets (user_id, reset_token, expires_at)
            VALUES (:user_id, :token, :expires)
        """)
        s.execute(query_insert_token, {"user_id": user.id, "token": token, "expires": expires_at})
        s.commit()

        # 3. Enviar o e-mail
        # Assumimos que o 'login' é o e-mail do utilizador.
        if enviar_email_de_redefinicao(destinatario_email=login, destinatario_nome=user.nome, token=token):
            st.success("Um e-mail com as instruções para redefinir a sua senha foi enviado. Por favor, verifique a sua caixa de entrada e spam.")
            st.info("O link é válido por 15 minutos.")
        else:
            # A função enviar_email_de_redefinicao já mostra um st.error detalhado.
            st.warning("Não foi possível enviar o e-mail. Verifique as configurações e tente novamente.")


def show_login_form():
    """Exibe o formulário de login ou o de redefinição de senha."""
    
    # CSS para a logo e footer da tela de login
    st.markdown("""
    <style>
        .login-logo-text {
            font-family: 'Courier New', monospace;
            font-size: 48px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20px;
        }
        .login-logo-asset { color: #003366; }
        .login-logo-flow { color: #E30613; }

        @media (prefers-color-scheme: dark) {
            .login-logo-asset { color: #FFFFFF; }
            .login-logo-flow { color: #FF4B4B; }
        }

        .login-footer {
            text-align: center;
            margin-top: 30px;
        }
        .login-footer a {
            margin: 0 10px;
        }
        .login-footer img {
            width: 25px;
            height: 25px;
            filter: grayscale(1) opacity(0.5);
            transition: filter 0.3s;
        }
        .login-footer img:hover {
            filter: grayscale(0) opacity(1);
        }
        @media (prefers-color-scheme: dark) {
            .login-footer img {
                filter: grayscale(1) opacity(0.6) invert(1);
            }
            .login-footer img:hover {
                filter: opacity(1) invert(1);
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # Logo
    st.markdown(
        """
        <div class="login-logo-text">
            <span class="login-logo-asset">ASSET</span><span class="login-logo-flow">FLOW</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Inicializa o estado se não existir
    if 'show_reset_form' not in st.session_state:
        st.session_state.show_reset_form = False
    
    # Usa colunas para centralizar o conteúdo
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        # Se o estado for para mostrar o formulário de reset, mostre-o
        if st.session_state.show_reset_form:
            st.subheader("Redefinir Senha")
            with st.form("form_reset_request"):
                login_para_reset = st.text_input("Digite o seu login (e-mail) para receber o link")
                submitted = st.form_submit_button("Enviar E-mail de Redefinição", use_container_width=True)
                if submitted:
                    iniciar_redefinicao_de_senha(login_para_reset)

            if st.button("Voltar para o Login", use_container_width=True):
                st.session_state.show_reset_form = False
                st.rerun()

        # Caso contrário, mostre o formulário de login normal
        else:
            with st.form("login_form"):
                st.subheader("Login")
                username = st.text_input("Utilizador", placeholder="Usuário")
                password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
                submitted = st.form_submit_button("Entrar", use_container_width=True)

                if submitted:
                    if check_login(username, password):
                        st.rerun()
                    else:
                        st.error("Utilizador ou senha inválidos.")
            
            # Adiciona o botão "Esqueceu a senha?"
            st.markdown("---")
            if st.button("Esqueceu a senha?", use_container_width=True):
                st.session_state.show_reset_form = True
                st.rerun()

    # Footer com ícones
    st.markdown(
        f"""
        <div class="login-footer">
            <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub">
                <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg">
            </a>
            <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn">
                <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg">
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

def logout():
    """Faz o logout do utilizador, limpando a sessão."""
    st.session_state['logged_in'] = False
    keys_to_pop = ['username', 'user_role', 'user_name', 'user_id']
    for key in keys_to_pop:
        st.session_state.pop(key, None)
    st.rerun()
