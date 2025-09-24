import streamlit as st
from sqlalchemy import text
from datetime import datetime
# Importa a mesma função de hash usada no login e o logout para limpar a sessão se necessário
from auth import hash_password, logout

# --- BLOCO DE REDIRECIONAMENTO INTELIGENTE ---
# Se o utilizador já estiver logado, esta página não deve ser para ele.
# Redireciona-o para a página de gerenciamento de usuários, que é o local correto para um admin gerir senhas.
if st.session_state.get('logged_in', False):
    st.switch_page("pages/7_Gerenciar_Usuarios.py")


# --- Funções do DB ---
def get_db_connection():
    return st.connection("supabase", type="sql")

def validar_token_e_redefinir_senha(token, nova_senha):
    """
    Verifica se o token é válido e, em caso afirmativo, redefine a senha do utilizador.
    """
    if not token or not nova_senha:
        st.error("Token ou nova senha não fornecidos. A operação não pode continuar.")
        return False
    
    conn = get_db_connection()
    with conn.session as s:
        s.begin()
        try:
            # 1. Encontra o token no banco e verifica se não expirou
            query_find_token = text("""
                SELECT user_id, expires_at FROM password_resets
                WHERE reset_token = :token AND expires_at > NOW()
            """)
            result = s.execute(query_find_token, {"token": token}).fetchone()

            if not result:
                st.error("Link de redefinição inválido ou expirado. Por favor, solicite um novo a partir da tela de login.")
                s.rollback()
                return False

            user_id = result.user_id

            # 2. Atualiza a senha do utilizador
            nova_senha_hashed = hash_password(nova_senha)
            query_update_password = text("UPDATE usuarios SET senha = :senha WHERE id = :id")
            s.execute(query_update_password, {"senha": nova_senha_hashed, "id": user_id})

            # 3. Exclui o token para que não possa ser reutilizado
            query_delete_token = text("DELETE FROM password_resets WHERE reset_token = :token")
            s.execute(query_delete_token, {"token": token})

            s.commit()
            return True
        except Exception as e:
            s.rollback()
            st.error(f"Ocorreu um erro ao tentar redefinir a senha: {e}")
            return False

# --- UI da Página ---
# Esta configuração só será aplicada se o utilizador não estiver logado
st.set_page_config(layout="centered")

# Extrai o token da URL
query_params = st.query_params
token = query_params.get("token")

# --- LÓGICA DE EXIBIÇÃO APRIMORADA ---
# Só mostra o conteúdo da página se houver um token.
if token:
    st.markdown("""
    <style>
        .logo-text { font-family: 'Courier New', monospace; font-size: 32px; font-weight: bold; text-align: center; }
        .logo-asset { color: #003366; } .logo-flow { color: #E30613; }
        @media (prefers-color-scheme: dark) { .logo-asset { color: #FFFFFF; } .logo-flow { color: #FF4B4B; } }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""<div class="logo-text"><span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span></div>""", unsafe_allow_html=True)
    st.title("Crie a sua Nova Senha")

    with st.form("form_nova_senha"):
        st.write("Por favor, digite a sua nova senha abaixo.")
        nova_senha = st.text_input("Nova Senha", type="password", key="nova_senha")
        confirmar_senha = st.text_input("Confirme a Nova Senha", type="password", key="confirmar_senha")
        
        submitted = st.form_submit_button("Redefinir Senha", use_container_width=True, type="primary")

        if submitted:
            if not nova_senha or not confirmar_senha:
                st.error("Ambos os campos de senha devem ser preenchidos.")
            elif nova_senha != confirmar_senha:
                st.error("As senhas não coincidem. Por favor, tente novamente.")
            else:
                if validar_token_e_redefinir_senha(token, nova_senha):
                    st.success("A sua senha foi redefinida com sucesso! ✅")
                    st.info("Pode fechar esta página e voltar à tela de login para entrar com a sua nova senha.")
                    st.page_link("app.py", label="Ir para a Tela de Login", icon="🏠")
                    st.query_params.clear()
else:
    # Se um utilizador não logado tentar aceder a esta página diretamente (sem um token),
    # ele será redirecionado para a página de login.
    st.switch_page("app.py")
