import streamlit as st
import pandas as pd
from datetime import date
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
    if st.button("Logout", key="colab_logout"):
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

# --- Funções do DB (MODIFICADAS PARA POSTGRESQL) ---
def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def carregar_setores():
    conn = get_db_connection()
    setores_df = conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
    return setores_df.to_dict('records')

def adicionar_colaborador(nome, cpf, gmail, setor_id, codigo):
    if not nome or not cpf or not codigo:
        st.error("Nome, CPF e Código são campos obrigatórios.")
        return False
    try:
        conn = get_db_connection()
        with conn.session as s:
            s.begin()
            query_check = text("SELECT 1 FROM colaboradores WHERE cpf = :cpf OR codigo = :codigo")
            existe = s.execute(query_check, {"cpf": cpf, "codigo": str(codigo)}).fetchone()
            if existe:
                st.warning("Um colaborador com este CPF ou Código já existe.")
                s.rollback()
                return False

            query_insert = text("""
                INSERT INTO colaboradores (nome_completo, cpf, gmail, setor_id, data_cadastro, codigo) 
                VALUES (:nome, :cpf, :gmail, :setor_id, :data, :codigo)
            """)
            s.execute(query_insert, {
                "nome": nome, "cpf": cpf, "gmail": gmail, 
                "setor_id": setor_id, "data": date.today(), "codigo": str(codigo)
            })
            s.commit()
        st.success(f"Colaborador '{nome}' adicionado com sucesso!")
        st.cache_data.clear()
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
             st.warning("Um colaborador com este CPF ou Código já existe.")
        else:
            st.error(f"Erro ao adicionar colaborador: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_colaboradores(order_by="c.nome_completo ASC"):
    """Carrega os colaboradores, permitindo a ordenação dinâmica."""
    conn = get_db_connection()
    if "codigo" in order_by:
        order_clause = "ORDER BY LPAD(c.codigo, 10, '0')"
        if "DESC" in order_by:
            order_clause += " DESC"
    else:
        order_clause = f"ORDER BY {order_by}"

    query = f"""
        SELECT c.id, c.codigo, c.nome_completo, c.cpf, c.gmail, s.nome_setor
        FROM colaboradores c
        LEFT JOIN setores s ON c.setor_id = s.id
        {order_clause}
    """
    df = conn.query(query)
    return df

def atualizar_colaborador(col_id, codigo, nome, cpf, gmail, setor_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("""
                UPDATE colaboradores SET codigo = :codigo, nome_completo = :nome, 
                cpf = :cpf, gmail = :gmail, setor_id = :setor_id 
                WHERE id = :id
            """)
            s.execute(query, {
                "codigo": str(codigo), "nome": nome, "cpf": cpf, 
                "gmail": gmail, "setor_id": setor_id, "id": col_id
            })
            s.commit()
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower() and 'cpf' in str(e).lower():
            st.error(f"Erro: O CPF '{cpf}' já pertence a outro colaborador.")
        else:
            st.error(f"Erro ao atualizar o colaborador ID {col_id}: {e}")
        return False

def excluir_colaborador(col_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("DELETE FROM colaboradores WHERE id = :id")
            s.execute(query, {"id": col_id})
            s.commit()
        return True
    except Exception as e:
        if 'foreign key constraint' in str(e).lower():
            st.error(f"Erro: Não é possível excluir o colaborador ID {col_id}, pois ele possui aparelhos ou outros registos associados.")
        else:
            st.error(f"Erro ao excluir o colaborador ID {col_id}: {e}")
        return False

# --- UI ---
st.title("Gestão de Colaboradores")
st.markdown("---")

try:
    setores_list = carregar_setores()
    setores_dict = {s['nome_setor']: s['id'] for s in setores_list}

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Adicionar Novo Colaborador")
        with st.form("form_novo_colaborador", clear_on_submit=True):
            novo_codigo = st.text_input("Código*")
            novo_nome = st.text_input("Nome Completo*")
            novo_cpf = st.text_input("CPF*")
            novo_gmail = st.text_input("Gmail")
            setor_selecionado_nome = st.selectbox("Setor", options=setores_dict.keys(), index=None, placeholder="Selecione...")

            if st.form_submit_button("Adicionar Colaborador", use_container_width=True):
                if setor_selecionado_nome:
                    setor_id = setores_dict.get(setor_selecionado_nome)
                    if adicionar_colaborador(novo_nome, novo_cpf, novo_gmail, setor_id, novo_codigo):
                        st.rerun()
                else:
                    st.warning("Por favor, selecione um setor.")

    with col2:
        with st.expander("Ver, Editar e Excluir Colaboradores", expanded=True):
            
            sort_options = {
                "Nome (A-Z)": "c.nome_completo ASC",
                "Código (Crescente)": "codigo ASC",
                "Setor (A-Z)": "s.nome_setor ASC"
            }
            sort_selection = st.selectbox("Organizar por:", options=sort_options.keys())

            colaboradores_df = carregar_colaboradores(order_by=sort_options[sort_selection])
            
            # Armazenar o DF original no estado da sessão para uma comparação fiável
            if 'original_colabs_df' not in st.session_state or not st.session_state.original_colabs_df.equals(colaboradores_df):
                 st.session_state.original_colabs_df = colaboradores_df.copy()

            setores_options = list(setores_dict.keys())
            
            edited_df = st.data_editor(
                st.session_state.original_colabs_df,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "codigo": st.column_config.TextColumn("Código", required=True),
                    "nome_completo": st.column_config.TextColumn("Nome Completo", required=True),
                    "cpf": st.column_config.TextColumn("CPF", required=True),
                    "gmail": st.column_config.TextColumn("Gmail"),
                    "nome_setor": st.column_config.SelectboxColumn(
                        "Setor", options=setores_options, required=True
                    ),
                },
                hide_index=True,
                num_rows="dynamic",
                key="colaboradores_editor"
            )
            
            if st.button("Salvar Alterações", use_container_width=True):
                original_df = st.session_state.original_colabs_df
                changes_made = False

                # Lógica para Exclusão
                deleted_ids = set(original_df['id']) - set(edited_df['id'])
                for col_id in deleted_ids:
                    if excluir_colaborador(col_id):
                        st.toast(f"Colaborador ID {col_id} excluído!", icon="🗑️")
                        changes_made = True

                # Lógica para Atualização (comparação mais robusta)
                # Alinhar os dataframes pelo ID para comparar corretamente
                original_df_indexed = original_df.set_index('id')
                edited_df_indexed = edited_df.set_index('id')

                common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)
                
                for col_id in common_ids:
                    original_row = original_df_indexed.loc[col_id]
                    edited_row = edited_df_indexed.loc[col_id]

                    if not original_row.equals(edited_row):
                        novo_setor_id = setores_dict.get(edited_row['nome_setor'])
                        if atualizar_colaborador(col_id, edited_row['codigo'], edited_row['nome_completo'], edited_row['cpf'], edited_row['gmail'], novo_setor_id):
                            st.toast(f"Colaborador '{edited_row['nome_completo']}' atualizado!", icon="✅")
                            changes_made = True

                if changes_made:
                    # Limpa o cache e o estado da sessão para forçar o recarregamento
                    st.cache_data.clear()
                    del st.session_state.original_colabs_df
                    st.rerun()
                else:
                    st.info("Nenhuma alteração foi detetada.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de colaboradores: {e}")
    st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")
