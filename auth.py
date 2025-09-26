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
        st.session_state['user_id'] = user['id'] 
        return True
        
    return False

def iniciar_redefinicao_de_senha(login):
    """Inicia o processo de redefinição de senha para um utilizador."""
    conn = get_db_connection()
    with conn.session as s:
        s.begin()
        query_user = text("SELECT id, nome FROM usuarios WHERE login = :login")
        user = s.execute(query_user, {"login": login}).fetchone()

        if not user:
            st.error("Login não encontrado no sistema.")
            s.rollback()
            return

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=15)

        query_insert_token = text("""
            INSERT INTO password_resets (user_id, reset_token, expires_at)
            VALUES (:user_id, :token, :expires)
        """)
        s.execute(query_insert_token, {"user_id": user.id, "token": token, "expires": expires_at})
        s.commit()

        if enviar_email_de_redefinicao(destinatario_email=login, destinatario_nome=user.nome, token=token):
            st.success("Um e-mail com as instruções para redefinir a sua senha foi enviado. Por favor, verifique a sua caixa de entrada e spam.")
            st.info("O link é válido por 15 minutos.")
        else:
            st.warning("Não foi possível enviar o e-mail. Verifique as configurações e tente novamente.")


def show_login_form():
    """Exibe o formulário de login centralizado e com novo design."""

    if "forgot_password" in st.query_params:
        st.session_state.show_reset_form = True
        st.query_params.clear()
    
    # --- CSS COMPLETO PARA A TELA DE LOGIN ---
    st.markdown("""
    <style>
        /* --- Fundo e Layout Geral --- */
        [data-testid="stAppViewContainer"] {
            background-color: #FFFFFF;
        }
        @media (prefers-color-scheme: dark) {
            [data-testid="stAppViewContainer"] {
                background-color: #121212;
            }
        }
        [data-testid="stSidebar"], [data-testid="stHeader"] {
            display: none;
        }
        /* --- Cartão de Login --- */
        .login-card {
            background-color: #F0F2F6;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 450px; /* Limita a largura em ecrãs grandes */
            margin: auto; /* Centraliza o cartão */
        }
        @media (prefers-color-scheme: dark) {
            .login-card {
                background-color: #282828;
                box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            }
        }
        /* --- Logo --- */
        .login-logo-text {
            font-family: 'Courier New', monospace;
            font-size: 42px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 2rem;
        }
        .login-logo-asset { color: #003366; }
        .login-logo-flow { color: #E30613; }
        @media (prefers-color-scheme: dark) {
            .login-logo-asset { color: #FFFFFF; }
            .login-logo-flow { color: #FF4B4B; }
        }
        /* --- Botão Principal --- */
        .stButton button {
            background-color: #003366;
            color: white;
            border-radius: 50px !important;
            padding: 10px 0;
            font-weight: bold;
            border: none;
            width: 100%;
            transition: background-color 0.2s, transform 0.2s;
        }
        .stButton button:hover {
            background-color: #0055A4;
            transform: scale(1.02);
        }
        /* --- Link "Esqueceu a senha?" --- */
        .forgot-password-link {
            text-align: right;
            margin-top: -15px; /* Puxa o link para mais perto do botão */
            margin-bottom: 20px;
        }
        .forgot-password-link a {
            color: #5a5a5a;
            font-size: 14px;
            text-decoration: none;
        }
        .forgot-password-link a:hover { text-decoration: underline; }
        @media (prefers-color-scheme: dark) { .forgot-password-link a { color: #b3b3b3; } }
        
        /* --- Divisor --- */
        hr {
            border-top: 1px solid #d9d9d9;
            margin: 2rem 0;
        }
        @media (prefers-color-scheme: dark) { hr { border-color: #404040; } }
        
        /* --- Footer com Ícones Sociais --- */
        .social-footer { text-align: center; }
        .social-footer p {
            font-size: 14px;
            font-weight: bold;
            color: #5a5a5a;
            margin-bottom: 1rem;
        }
        .social-icons a { margin: 0 15px; }
        .social-icons img {
            width: 30px;
            height: 30px;
            filter: grayscale(1) opacity(0.6);
            transition: filter 0.3s, transform 0.3s;
        }
        .social-icons img:hover {
            filter: grayscale(0) opacity(1);
            transform: scale(1.1);
        }
        @media (prefers-color-scheme: dark) {
            .social-footer p { color: #b3b3b3; }
            .social-icons img { filter: grayscale(1) opacity(0.7) invert(1); }
            .social-icons img:hover { filter: opacity(1) invert(1); }
        }
        /* --- Texto da Versão --- */
        .version-text {
            font-size: 12px;
            color: #a0a0a0;
            text-align: center;
            margin-top: 40px;
        }
        @media (prefers-color-scheme: dark) { .version-text { color: #5a5a5a; } }
    </style>
    """, unsafe_allow_html=True)

    # --- ESTRUTURA DA PÁGINA ---
    # Colunas para centralizar o conteúdo principal
    _, main_col, _ = st.columns([1, 1.5, 1])

    with main_col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        
        # Logo
        st.markdown(
            """
            <div class="login-logo-text">
                <span class="login-logo-asset">ASSET</span><span class="login-logo-flow">FLOW</span>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        if 'show_reset_form' not in st.session_state:
            st.session_state.show_reset_form = False
        
        if st.session_state.show_reset_form:
            st.subheader("Redefinir Senha")
            with st.form("form_reset_request"):
                login_para_reset = st.text_input("Seu login (e-mail)", key="reset_email")
                submitted = st.form_submit_button("Enviar E-mail de Redefinição")
                if submitted:
                    iniciar_redefinicao_de_senha(login_para_reset)

            if st.button("Voltar para o Login", use_container_width=True):
                st.session_state.show_reset_form = False
                st.rerun()
        else:
            with st.form("login_form"):
                username = st.text_input("Utilizador ou e-mail", key="username")
                password = st.text_input("Senha", type="password", key="password")
                submitted = st.form_submit_button("Entrar")

                if submitted:
                    if check_login(username, password):
                        st.rerun()
                    else:
                        st.error("Utilizador ou senha inválidos.")
            
            # Link "Esqueceu a senha?"
            st.markdown(
                '<div class="forgot-password-link"><a href="?forgot_password=true" target="_self">Esqueceu a senha?</a></div>',
                unsafe_allow_html=True
            )

            st.markdown("<hr>", unsafe_allow_html=True)

            # Footer com ícones
            st.markdown(
                f"""
                <div class="social-footer">
                    <p>Conecte-se com o desenvolvedor</p>
                    <div class="social-icons">
                        <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub">
                            <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg">
                        </a>
                        <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn">
                            <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg">
                        </a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown('</div>', unsafe_allow_html=True) # Fecha login-card
        
        # Texto da Versão
        st.markdown('<p class="version-text">V 3.1.1</p>', unsafe_allow_html=True)

def logout():
    """Faz o logout do utilizador, limpando a sessão."""
    st.session_state['logged_in'] = False
    keys_to_pop = ['username', 'user_role', 'user_name', 'user_id']
    for key in keys_to_pop:
        st.session_state.pop(key, None)
    st.rerun()

