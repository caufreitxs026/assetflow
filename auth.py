import streamlit as st
import hashlib
from sqlalchemy import text
import secrets
from datetime import datetime, timedelta
from email_utils import enviar_email_de_redefinicao


def get_db_connection():
    return st.connection("supabase", type="sql")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def check_login(username, password):
    conn = get_db_connection()
    hashed_password = hash_password(password)
    query = "SELECT * FROM usuarios WHERE login = :login AND senha = :senha"
    user_df = conn.query(query, params={"login": username, "senha": hashed_password})
    if not user_df.empty:
        user = user_df.iloc[0].to_dict()
        st.session_state['logged_in'] = True
        st.session_state['user_login'] = user['login']
        st.session_state['user_role'] = user['cargo']
        st.session_state['user_name'] = user['nome']
        st.session_state['user_id'] = user['id']
        return True
    return False


def iniciar_redefinicao_de_senha(login):
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
            st.success("Um e-mail com as instruções para redefinir a sua senha foi enviado. Verifique sua caixa de entrada/spam.")
            st.info("O link é válido por 15 minutos.")
        else:
            st.warning("Não foi possível enviar o e-mail. Verifique as configurações e tente novamente.")


def show_login_form():
    if "forgot_password" in st.query_params:
        st.session_state.show_reset_form = True
        st.query_params.clear()

    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] {
            background-color: #FFFFFF;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        @media (prefers-color-scheme: dark) { [data-testid="stAppViewContainer"] { background-color: #0d1117; } }
        [data-testid="stSidebar"], [data-testid="stHeader"] { display: none; }

        [data-testid="stAppViewContainer"] > .main {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            text-align: center;
        }

        .login-logo-text {
            font-family: 'Courier New', monospace;
            font-size: 38px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 2rem;
            width: 100%;
            max-width: 400px;
            margin-left: auto;
            margin-right: auto;
        }
        .login-logo-asset { color: #003366; }
        .login-logo-flow { color: #E30613; }
        @media (prefers-color-scheme: dark) { .login-logo-asset { color: #FFFFFF; } .login-logo-flow { color: #FF4B4B; } }

        [data-testid="stForm"] {
            background-color: #f6f8fa;
            padding: 2rem;
            border-radius: 10px;
            border: 1px solid #d0d7de;
            width: 100%;
            max-width: 400px;
            margin: 0 auto 2rem auto;
        }
        @media (prefers-color-scheme: dark) { [data-testid="stForm"] { background-color: #161b22; border: 1px solid #30363d; } }

        .card-title { text-align: center; font-size: 24px; margin-bottom: 2rem; font-weight: 300; }

        .stButton button {
            background-color: #003366;
            color: white;
            border-radius: 6px !important;
            padding: 10px 0;
            font-weight: bold;
            border: 1px solid rgba(27, 31, 36, 0.15);
            width: 100%;
            transition: background-color 0.2s;
            margin-top: 1rem;
        }
        .stButton button:hover { background-color: #0055A4; }

        .form-label-container { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
        .form-label { font-weight: 600; font-size: 14px; }
        .forgot-password-link a { color: #0969da; font-size: 12px; text-decoration: none; }
        .forgot-password-link a:hover { text-decoration: underline; }

        .login-footer {
            text-align: center;
            width: 100%;
            max-width: 400px;
            margin-left: auto;
            margin-right: auto;
        }
        .social-icons a { margin: 0 10px; }
        .social-icons img { width: 28px; height: 28px; filter: grayscale(1) opacity(0.6); transition: filter 0.3s, opacity 0.3s; }
        .social-icons img:hover { filter: grayscale(0) opacity(1); }
        @media (prefers-color-scheme: dark) { .social-icons img { filter: grayscale(1) opacity(0.7) invert(1); } }

        .version-badge {
            display: inline-block;
            margin-top: 15px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
            color: #fff;
            background-color: #003366;
            border-radius: 12px;
            border: 1px solid rgba(0,0,0,0.1);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        @media (prefers-color-scheme: dark) { .version-badge { background-color: #0055A4; border: 1px solid #30363d; } }

        /* Botão minimalista no canto direito */
        .voltar-btn-right {
            display: flex;
            justify-content: flex-end;
            margin-top: 0.5rem;
            max-width: 400px;
            width: 100%;
        }
        .voltar-btn-right button {
            background: none !important;
            color: #0969da !important;
            border: none !important;
            font-weight: 600 !important;
            text-decoration: underline;
            cursor: pointer;
            font-size: 14px !important;
        }
        .voltar-btn-right button:hover { color: #0645ad !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="login-logo-text">
            <span class="login-logo-asset">ASSET</span><span class="login-logo-flow">FLOW</span>
        </div>
    """, unsafe_allow_html=True)

    if 'show_reset_form' not in st.session_state:
        st.session_state.show_reset_form = False

    if st.session_state.show_reset_form:
        with st.form("form_reset_request"):
            st.markdown('<h1 class="card-title">Redefinir Senha</h1>', unsafe_allow_html=True)
            st.markdown('<p class="form-label">Seu login (e-mail)</p>', unsafe_allow_html=True)
            login_para_reset = st.text_input("Seu login (e-mail)", key="reset_email_input", label_visibility="collapsed")
            submitted = st.form_submit_button("Enviar E-mail de Redefinição")
            if submitted:
                iniciar_redefinicao_de_senha(login_para_reset)

        # Botão no canto direito da box
        st.markdown("""
            <div class="voltar-btn-right">
                <form action="">
                    <button type="submit" onclick="window.location.reload();">Voltar para o Login</button>
                </form>
            </div>
        """, unsafe_allow_html=True)

    else:
        with st.form("login_form"):
            st.markdown('<h1 class="card-title">Entrar no AssetFlow</h1>', unsafe_allow_html=True)
            st.markdown('<p class="form-label">Utilizador ou e-mail</p>', unsafe_allow_html=True)
            username = st.text_input("Utilizador ou e-mail", key="login_username_input", label_visibility="collapsed")

            st.markdown("""
                <div class="form-label-container">
                    <span class="form-label">Senha</span>
                    <span class="forgot-password-link"><a href="?forgot_password=true" target="_self">Esqueceu a senha?</a></span>
                </div>
            """, unsafe_allow_html=True)
            password = st.text_input("Senha", type="password", key="login_password_input", label_visibility="collapsed")

            submitted = st.form_submit_button("Entrar")
            if submitted:
                if check_login(username, password):
                    st.rerun()
                else:
                    st.error("Utilizador ou senha inválidos.")

    st.markdown(f"""
        <div class="login-footer">
            <div class="social-icons">
                <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub">
                    <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg">
                </a>
                <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn">
                    <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg">
                </a>
            </div>
            <div class="version-badge">V 3.1.1</div>
        </div>
    """, unsafe_allow_html=True)


def logout():
    st.session_state['logged_in'] = False
    for key in ['user_login', 'user_role', 'user_name', 'user_id']:
        st.session_state.pop(key, None)
    st.rerun()
