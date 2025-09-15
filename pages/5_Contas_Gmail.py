import streamlit as st
import pandas as pd
import re
from auth import show_login_form, logout
from sqlalchemy import text
import numpy as np

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
    st.write(f"Cargo, **{st.session_state['user_role']}**!")
    if st.button("Logout", key="gmail_logout"):
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
    return st.connection("supabase", type="sql")

def validar_formato_gmail(email):
    if not email: return False
    padrao = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(padrao, email) is not None

@st.cache_data(ttl=30)
def carregar_setores_e_colaboradores_ativos():
    conn = get_db_connection()
    setores_df = conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
    # --- MUDANÇA AQUI: Carrega apenas colaboradores ativos ---
    colaboradores_df = conn.query("SELECT id, nome_completo FROM colaboradores WHERE status = 'Ativo' ORDER BY nome_completo;")
    return setores_df.to_dict('records'), colaboradores_df.to_dict('records')

def adicionar_conta(email, senha, tel_rec, email_rec, setor_id, col_id):
    if not email:
        st.error("O campo E-mail é obrigatório.")
        return False
    try:
        conn = get_db_connection()
        with conn.session as s:
            s.begin()
            query_check = text("SELECT 1 FROM contas_gmail WHERE email = :email")
            existe = s.execute(query_check, {"email": email}).fetchone()
            if existe:
                st.warning(f"O e-mail '{email}' já está cadastrado.")
                s.rollback()
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
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            st.warning(f"O e-mail '{email}' já está cadastrado.")
        else:
            st.error(f"Ocorreu um erro: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_contas(order_by="cg.email ASC", search_term=None, setor_id=None):
    conn = get_db_connection()
    params = {}
    where_clauses = []
    if setor_id:
        where_clauses.append("s.id = :setor_id")
        params["setor_id"] = setor_id
    if search_term:
        search_like = f"%{search_term}%"
        where_clauses.append("(cg.email ILIKE :search OR c.nome_completo ILIKE :search)")
        params["search"] = search_like
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    query = f"""
        SELECT 
            cg.id, cg.email, cg.senha, cg.telefone_recuperacao, 
            cg.email_recuperacao, s.nome_setor, c.nome_completo as colaborador
        FROM contas_gmail cg
        LEFT JOIN setores s ON cg.setor_id = s.id
        LEFT JOIN colaboradores c ON cg.colaborador_id = c.id
        {where_sql}
        ORDER BY {order_by}
    """
    df = conn.query(query, params=params)
    for col in ['senha', 'telefone_recuperacao', 'email_recuperacao', 'nome_setor', 'colaborador']:
        if col in df.columns:
            df[col] = df[col].fillna('')
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
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar a conta ID {conta_id}: {e}")
        return False

def excluir_conta(conta_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("DELETE FROM contas_gmail WHERE id = :id")
            s.execute(query, {"id": conta_id})
            s.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir a conta ID {conta_id}: {e}")
        return False

# --- UI ---
st.title("Gestão de Contas Gmail")
st.markdown("---")

try:
    setores_list, colaboradores_list = carregar_setores_e_colaboradores_ativos()
    setores_dict = {s['nome_setor']: s['id'] for s in setores_list}
    colaboradores_dict = {"Nenhum": None}
    colaboradores_dict.update({c['nome_completo']: c['id'] for c in colaboradores_list})

    option = st.radio(
        "Selecione a operação:",
        ("Cadastrar Nova Conta", "Consultar Contas"),
        horizontal=True,
        label_visibility="collapsed",
        key="gmail_tab_selector"
    )
    st.markdown("---")

    if option == "Cadastrar Nova Conta":
        with st.form("form_nova_conta", clear_on_submit=True):
            st.subheader("Dados da Nova Conta")
            st.warning("Atenção: As senhas são armazenadas em texto plano. Use com cautela.", icon="⚠️")
            email = st.text_input("E-mail/Gmail*")
            senha = st.text_input("Senha")
            tel_rec = st.text_input("Telefone de Recuperação")
            email_rec = st.text_input("E-mail de Recuperação")
            setor_sel = st.selectbox("Função (Setor)", options=setores_dict.keys(), index=None, placeholder="Selecione...")
            col_sel = st.selectbox("Vinculado ao Colaborador", options=colaboradores_dict.keys(), help="Clique na lista e comece a digitar para pesquisar.")

            if st.form_submit_button("Adicionar Conta", use_container_width=True, type="primary"):
                if validar_formato_gmail(email):
                    setor_id = setores_dict.get(setor_sel)
                    col_id = colaboradores_dict.get(col_sel)
                    if adicionar_conta(email, senha, tel_rec, email_rec, setor_id, col_id):
                        st.cache_data.clear()
                        for key in list(st.session_state.keys()):
                            if key.startswith('original_contas_df_'):
                                del st.session_state[key]
                        st.rerun() 
                else:
                    st.error("Formato de e-mail inválido. Certifique-se de que termina com '@gmail.com'.")

    elif option == "Consultar Contas":
        st.subheader("Contas Registradas")
        
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            setor_filtro_nome = st.selectbox("Filtrar por Setor:", ["Todos"] + list(setores_dict.keys()))
        with col_filtro2:
            termo_pesquisa = st.text_input("Pesquisar por E-mail ou Colaborador:")

        setor_id_filtro = None
        if setor_filtro_nome != "Todos":
            setor_id_filtro = setores_dict.get(setor_filtro_nome)

        sort_options = {
            "Email (A-Z)": "cg.email ASC",
            "Setor (A-Z)": "s.nome_setor ASC",
            "Colaborador (A-Z)": "colaborador ASC"
        }
        sort_selection = st.selectbox("Organizar por:", options=sort_options.keys())

        contas_df = carregar_contas(
            order_by=sort_options[sort_selection],
            search_term=termo_pesquisa,
            setor_id=setor_id_filtro
        )
        
        session_state_key = f"original_contas_df_{sort_selection}_{termo_pesquisa}_{setor_filtro_nome}"
        if session_state_key not in st.session_state:
            for key in list(st.session_state.keys()):
                if key.startswith('original_contas_df_'):
                    del st.session_state[key]
            st.session_state[session_state_key] = contas_df.copy()

        setores_options = list(setores_dict.keys())
        # --- MUDANÇA AQUI: A lista de seleção agora também mostra apenas os ativos ---
        colaboradores_options_select = list(colaboradores_dict.keys())

        edited_df = st.data_editor(
            st.session_state[session_state_key],
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "email": st.column_config.TextColumn("E-mail", disabled=True),
                "senha": st.column_config.TextColumn("Senha", required=False),
                "telefone_recuperacao": st.column_config.TextColumn("Telefone Recuperação"),
                "email_recuperacao": st.column_config.TextColumn("E-mail Recuperação"),
                "nome_setor": st.column_config.SelectboxColumn("Setor", options=setores_options),
                "colaborador": st.column_config.SelectboxColumn("Colaborador", options=colaboradores_options_select),
            },
            hide_index=True,
            num_rows="dynamic",
            key="contas_editor",
            use_container_width=True
        )

        if st.button("Salvar Alterações", use_container_width=True, key="save_contas_changes"):
            original_df = st.session_state[session_state_key]
            changes_made = False

            deleted_ids = set(original_df['id']) - set(edited_df['id'])
            for conta_id in deleted_ids:
                if excluir_conta(conta_id):
                    st.toast(f"Conta ID {conta_id} excluída!", icon="🗑️")
                    changes_made = True

            original_df_indexed = original_df.set_index('id')
            edited_df_indexed = edited_df.set_index('id')
            common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)
            
            for conta_id in common_ids:
                original_row = original_df_indexed.loc[conta_id]
                edited_row = edited_df_indexed.loc[conta_id]
                if not original_row.equals(edited_row):
                    novo_setor_id = setores_dict.get(edited_row['nome_setor'])
                    novo_col_id = colaboradores_dict.get(edited_row['colaborador'])

                    if atualizar_conta(conta_id, edited_row['senha'], edited_row['telefone_recuperacao'], edited_row['email_recuperacao'], novo_setor_id, novo_col_id):
                        st.toast(f"Conta '{edited_row['email']}' atualizada!", icon="✅")
                        changes_made = True
            
            if changes_made:
                st.cache_data.clear()
                del st.session_state[session_state_key]
                st.rerun()
            else:
                st.info("Nenhuma alteração foi detetada.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de contas: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")

