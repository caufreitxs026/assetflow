import streamlit as st
import pandas as pd
import re # Importa a biblioteca para validação de formato (Expressões Regulares)
from auth import show_login_form
from sqlalchemy import text

# --- Autenticação ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

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
st.title("Gestão de Contas Gmail")
st.markdown("---")

# --- Funções do Banco de Dados e Validação (MODIFICADAS PARA POSTGRESQL) ---
def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

def validar_formato_gmail(email):
    """Verifica se o e-mail tem um formato válido e termina com @gmail.com."""
    if not email: return False
    padrao = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(padrao, email) is not None

@st.cache_data(ttl=30)
def carregar_setores_e_colaboradores():
    conn = get_db_connection()
    setores_df = conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
    colaboradores_df = conn.query("SELECT id, nome_completo FROM colaboradores ORDER BY nome_completo;")
    return setores_df.to_dict('records'), colaboradores_df.to_dict('records')

def adicionar_conta(email, senha, tel_rec, email_rec, setor_id, col_id):
    if not email:
        st.error("O campo E-mail é obrigatório.")
        return False
    try:
        conn = get_db_connection()
        with conn.session as s:
            query_check = text("SELECT 1 FROM contas_gmail WHERE email = :email")
            existe = s.execute(query_check, {"email": email}).fetchone()
            if existe:
                st.warning(f"O e-mail '{email}' já está cadastrado.")
                return False

            query_insert = text("""
                INSERT INTO contas_gmail (email, senha, telefone_recuperacao, email_recuperacao, setor_id, colaborador_id) 
                VALUES (:email, :senha, :tel_rec, :email_rec, :setor_id, :col_id)
            """)
            s.execute(query_insert, {
                "email": email, "senha": senha, "tel_rec": tel_rec, 
                "email_rec": email_rec, "setor_id": setor_id, "col_id": col_id
            })
            s.commit()
        st.success(f"Conta '{email}' adicionada com sucesso!")
        st.cache_data.clear()
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            st.warning(f"O e-mail '{email}' já está cadastrado.")
        else:
            st.error(f"Ocorreu um erro: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_contas(order_by="cg.email ASC"):
    """Carrega as contas, permitindo a ordenação dinâmica."""
    conn = get_db_connection()
    query = f"""
        SELECT 
            cg.id, cg.email, cg.senha, cg.telefone_recuperacao, 
            cg.email_recuperacao, s.nome_setor, c.nome_completo as colaborador
        FROM contas_gmail cg
        LEFT JOIN setores s ON cg.setor_id = s.id
        LEFT JOIN colaboradores c ON cg.colaborador_id = c.id
        ORDER BY {order_by}
    """
    df = conn.query(query)
    return df

def atualizar_conta(conta_id, senha, tel_rec, email_rec, setor_id, col_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("""
                UPDATE contas_gmail 
                SET senha = :senha, telefone_recuperacao = :tel_rec, email_recuperacao = :email_rec, 
                    setor_id = :setor_id, colaborador_id = :col_id 
                WHERE id = :id
            """)
            s.execute(query, {
                "senha": senha, "tel_rec": tel_rec, "email_rec": email_rec,
                "setor_id": setor_id, "col_id": col_id, "id": conta_id
            })
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar a conta ID {conta_id}: {e}")
        return False

def excluir_conta(conta_id):
    """Exclui uma conta do banco de dados."""
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("DELETE FROM contas_gmail WHERE id = :id")
            s.execute(query, {"id": conta_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir a conta ID {conta_id}: {e}")
        return False

# --- Interface do Usuário ---
try:
    setores_list, colaboradores_list = carregar_setores_e_colaboradores()
    setores_dict = {s['nome_setor']: s['id'] for s in setores_list}
    colaboradores_dict = {"Nenhum": None}
    colaboradores_dict.update({c['nome_completo']: c['id'] for c in colaboradores_list})

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Adicionar Nova Conta")
        with st.form("form_nova_conta", clear_on_submit=True):
            st.warning("Atenção: As senhas são armazenadas em texto plano. Use com cautela.", icon="⚠️")
            email = st.text_input("E-mail/Gmail*")
            senha = st.text_input("Senha") # Não é mais tipo password para consistência com a tabela
            tel_rec = st.text_input("Telefone de Recuperação")
            email_rec = st.text_input("E-mail de Recuperação")
            setor_sel = st.selectbox("Função (Setor)", options=setores_dict.keys(), index=None, placeholder="Selecione...")
            col_sel = st.selectbox("Vinculado ao Colaborador", options=colaboradores_dict.keys(), help="Clique na lista e comece a digitar para pesquisar.")

            if st.form_submit_button("Adicionar Conta", use_container_width=True):
                if validar_formato_gmail(email):
                    setor_id = setores_dict.get(setor_sel)
                    col_id = colaboradores_dict.get(col_sel)
                    if adicionar_conta(email, senha, tel_rec, email_rec, setor_id, col_id):
                        st.rerun() 
                else:
                    st.error("Formato de e-mail inválido. Certifique-se de que termina com '@gmail.com'.")

    with col2:
        with st.expander("Ver, Editar e Excluir Contas", expanded=True):
            
            sort_options = {
                "Email (A-Z)": "cg.email ASC",
                "Setor (A-Z)": "s.nome_setor ASC",
                "Colaborador (A-Z)": "colaborador ASC"
            }
            sort_selection = st.selectbox("Organizar por:", options=sort_options.keys())

            contas_df = carregar_contas(order_by=sort_options[sort_selection])
            
            setores_options = list(setores_dict.keys())
            colaboradores_options = list(colaboradores_dict.keys())

            edited_df = st.data_editor(
                contas_df, # MUDANÇA: Usando o dataframe original, sem mascarar a senha
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "email": st.column_config.TextColumn("E-mail", disabled=True),
                    # MUDANÇA: A coluna senha agora é um campo de texto normal e editável
                    "senha": st.column_config.TextColumn("Senha", required=False),
                    "telefone_recuperacao": st.column_config.TextColumn("Telefone Recuperação"),
                    "email_recuperacao": st.column_config.TextColumn("E-mail Recuperação"),
                    "nome_setor": st.column_config.SelectboxColumn("Setor", options=setores_options),
                    "colaborador": st.column_config.SelectboxColumn("Colaborador", options=colaboradores_options),
                },
                hide_index=True,
                num_rows="dynamic",
                key="contas_editor"
            )

            if st.button("Salvar Alterações", use_container_width=True):
                # Lógica para Exclusão
                deleted_ids = set(contas_df['id']) - set(edited_df['id'])
                for conta_id in deleted_ids:
                    if excluir_conta(conta_id):
                        st.toast(f"Conta ID {conta_id} excluída!", icon="🗑️")

                # Lógica para Atualização
                # Compara o dataframe editado com o original para encontrar mudanças
                if not edited_df.equals(contas_df.loc[edited_df.index]):
                    # Encontra as diferenças
                    diff_df = pd.concat([edited_df, contas_df]).drop_duplicates(keep=False)
                    for index, row in diff_df.iterrows():
                         if row['id'] in edited_df['id'].values: # Garante que é uma linha atualizada/nova
                            conta_id = row['id']
                            nova_senha = row['senha']
                            novo_tel = row['telefone_recuperacao']
                            novo_email_rec = row['email_recuperacao']
                            novo_setor_id = setores_dict.get(row['nome_setor'])
                            novo_col_id = colaboradores_dict.get(row['colaborador'])
                            
                            if atualizar_conta(conta_id, nova_senha, novo_tel, novo_email_rec, novo_setor_id, novo_col_id):
                                st.toast(f"Conta '{row['email']}' atualizada!", icon="✅")
                
                st.rerun()

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de contas: {e}")
    st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")
