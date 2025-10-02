import streamlit as st
import hashlib
from sqlalchemy import text
import secrets
from datetime import datetime, timedelta
from email_utils import enviar_email_de_redefinicao

# ---------------- CONFIGURAÇÕES GLOBAIS ----------------
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
            st.success("Um e-mail com instruções foi enviado. Verifique sua caixa de entrada/spam.")
            st.info("O link é válido por 15 minutos.")
        else:
            st.warning("Não foi possível enviar o e-mail. Verifique as configurações e tente novamente.")

# ---------------- FRONT-END ----------------
st.set_page_config(page_title="ASSETFLOW", layout="centered")

# Carregar Font Awesome
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
""", unsafe_allow_html=True)

# CSS Global
st.markdown("""
<style>
/* Layout */
[data-testid="stAppViewContainer"] {
    background-color: #FFFFFF;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
}
@media (prefers-color-scheme: dark) { 
    [data-testid="stAppViewContainer"] { background-color: #0d1117; } 
}
[data-testid="stSidebar"], [data-testid="stHeader"] { display: none; }

/* Logo */
.login-logo-text {
    font-family: 'Courier New', monospace;
    font-size: 38px;
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

/* Form */
[data-testid="stForm"] {
    background-color: #f6f8fa;
    padding: 2rem;
    border-radius: 10px;
    border: 1px solid #d0d7de;
    width: 100%;
    max-width: 400px;
    margin: 0 auto 2rem auto;
}
@media (prefers-color-scheme: dark) { 
    [data-testid="stForm"] { background-color: #161b22; border: 1px solid #30363d; } 
}

/* Botões */
.stButton > button {
    background-color: #1677FF !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 10px 0 !important;
    font-weight: 600 !important;
    border: none !important;
    width: 100% !important;
    transition: background-color 0.2s ease-in-out;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 8px !important;
}
.stButton > button:hover {
    background-color: #0f5dcc !important;
}

/* Rodapé */
.footer {
    position: fixed;
    bottom: 10px;
    left: 0;
    width: 100%;
    text-align: center;
    font-size: 14px;
    color: #999;
}
.footer .social-icons {
    margin-top: 4px;
}
.footer .social-icons a {
    margin: 0 8px;
    text-decoration: none;
    color: #1677FF;
    font-size: 20px;
    transition: color 0.2s ease-in-out;
}
.footer .social-icons a:hover {
    color: #0f5dcc;
}
.footer .version-badge {
    display: inline-block;
    background: #1677FF;
    color: white;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 12px;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

# Ícones nos botões
st.markdown("""
<style>
/* Ícone Entrar */
div[data-testid="stForm"]:first-of-type .stButton > button:before {
    content: '\\f090';
    font-family: "Font Awesome 5 Free";
    font-weight: 900;
}
/* Ícone Redefinir */
div[data-testid="stForm"]:nth-of-type(2) .stButton > button:first-child:before {
    content: '\\f084';
    font-family: "Font Awesome 5 Free";
    font-weight: 900;
}
/* Ícone Voltar */
div[data-testid="stForm"]:nth-of-type(2) .stButton > button:nth-of-type(2):before {
    content: '\\f2f5';
    font-family: "Font Awesome 5 Free";
    font-weight: 900;
}
</style>
""", unsafe_allow_html=True)

# ---------------- Login Form ----------------
if "forgot_password" in st.query_params:
    st.session_state.show_reset_form = True
    st.query_params.clear()

if 'show_reset_form' not in st.session_state:
    st.session_state.show_reset_form = False

if st.session_state.show_reset_form:
    with st.form("form_reset_request"):
        st.markdown("""
            <div class="login-logo-text">
                <span class="login-logo-asset">ASSET</span><span class="login-logo-flow">FLOW</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown('<h1 class="card-title">Redefinir Senha</h1>', unsafe_allow_html=True)
        login_para_reset = st.text_input("Seu login (e-mail)", key="reset_email_input", label_visibility="collapsed")

        col1, col2 = st.columns([2, 1])
        with col1:
            submitted = st.form_submit_button(" Redefinir Senha")
        with col2:
            voltar = st.form_submit_button(" Voltar para Login")

        if submitted:
            iniciar_redefinicao_de_senha(login_para_reset)
        if voltar:
            st.session_state.show_reset_form = False
            st.rerun()
else:
    with st.form("login_form"):
        st.markdown("""
            <div class="login-logo-text">
                <span class="login-logo-asset">ASSET</span><span class="login-logo-flow">FLOW</span>
            </div>
        """, unsafe_allow_html=True)
        username = st.text_input("E-mail", key="login_username_input", label_visibility="collapsed")
        password = st.text_input("Senha", type="password", key="login_password_input", label_visibility="collapsed")

        submitted = st.form_submit_button(" Entrar")
        if submitted:
            if check_login(username, password):
                st.rerun()
            else:
                st.error("Utilizador ou senha inválidos.")

# ---------------- Rodapé ----------------
st.markdown("""
<div class="footer">
    <div class="social-icons">
        <a href="https://github.com/caufreitxs026" target="_blank"><i class="fab fa-github"></i></a>
        <a href="https://linkedin.com/in/cauafreitas" target="_blank"><i class="fab fa-linkedin"></i></a>
    </div>
    <div class="version-badge">v3.1.1</div>
</div>
""", unsafe_allow_html=True)
