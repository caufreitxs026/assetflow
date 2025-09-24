import streamlit as st
import pandas as pd
from datetime import date
from auth import show_login_form, logout
from sqlalchemy import text
import numpy as np

# --- Verificação de Autenticação ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

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

# --- Funções do DB ---
def get_db_connection():
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def carregar_setores():
    conn = get_db_connection()
    setores_df = conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
    return setores_df.to_dict('records')

def verificar_duplicidade_codigo(codigo, setor_id):
    """Verifica se um código já existe no setor e retorna os dados do colaborador existente."""
    conn = get_db_connection()
    query_check_codigo = text("""
        SELECT c.nome_completo, s.nome_setor
        FROM colaboradores c
        JOIN setores s ON c.setor_id = s.id
        WHERE c.codigo = :codigo AND c.setor_id = :setor_id AND c.status = 'Ativo'
    """)
    with conn.session as s:
        result = s.execute(query_check_codigo, {"codigo": str(codigo), "setor_id": setor_id}).fetchone()
    return result

def adicionar_colaborador_banco(nome, cpf, gmail, setor_id, codigo):
    """Realiza a inserção do colaborador no banco de dados, sem verificações de duplicidade de código."""
    try:
        conn = get_db_connection()
        with conn.session as s:
            s.begin()
            # A verificação de CPF ainda é um bloqueio rígido, pois CPF deve ser único.
            query_check_cpf = text("SELECT 1 FROM colaboradores WHERE cpf = :cpf")
            cpf_existe = s.execute(query_check_cpf, {"cpf": cpf}).fetchone()
            if cpf_existe:
                st.error(f"O CPF '{cpf}' já está cadastrado para outro colaborador. O cadastro foi cancelado.")
                s.rollback()
                return False

            query_insert = text("""
                INSERT INTO colaboradores (nome_completo, cpf, gmail, setor_id, data_cadastro, codigo, status) 
                VALUES (:nome, :cpf, :gmail, :setor_id, :data, :codigo, 'Ativo')
            """)
            s.execute(query_insert, {
                "nome": nome, "cpf": cpf, "gmail": gmail, 
                "setor_id": setor_id, "data": date.today(), "codigo": str(codigo)
            })
            s.commit()
        st.success(f"Colaborador '{nome}' adicionado com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar colaborador: {e}")
        return False

@st.cache_data(ttl=30)
def contar_codigos_duplicados():
    """Conta quantos grupos de códigos estão duplicados dentro do mesmo setor."""
    conn = get_db_connection()
    query = """
        SELECT COUNT(*)
        FROM (
            SELECT 1
            FROM colaboradores
            WHERE status = 'Ativo'
            GROUP BY codigo, setor_id
            HAVING COUNT(id) > 1
        ) as duplicados;
    """
    count = conn.query(query, ttl=30).iloc[0, 0]
    return count

@st.cache_data(ttl=30)
def carregar_detalhes_duplicados():
    """Carrega os detalhes dos códigos duplicados para exibição."""
    conn = get_db_connection()
    query = """
        WITH Duplicados AS (
            SELECT codigo, setor_id
            FROM colaboradores
            WHERE status = 'Ativo'
            GROUP BY codigo, setor_id
            HAVING COUNT(id) > 1
        )
        SELECT
            c.codigo,
            s.nome_setor,
            c.nome_completo
        FROM colaboradores c
        JOIN setores s ON c.setor_id = s.id
        JOIN Duplicados d ON c.codigo = d.codigo AND c.setor_id = d.setor_id
        WHERE c.status = 'Ativo'
        ORDER BY s.nome_setor, c.codigo, c.nome_completo;
    """
    df = conn.query(query, ttl=30)
    return df

@st.cache_data(ttl=30)
def carregar_colaboradores(order_by="c.nome_completo ASC", search_term=None, setor_id=None, status_filter=None):
    # (Função original sem modificações)
    conn = get_db_connection()
    params = {}
    where_clauses = []

    if setor_id:
        where_clauses.append("s.id = :setor_id")
        params["setor_id"] = setor_id
    
    if status_filter and status_filter != "Todos":
        where_clauses.append("c.status = :status")
        params["status"] = status_filter
    
    if search_term:
        search_like = f"%{search_term}%"
        where_clauses.append("(c.nome_completo ILIKE :search OR c.codigo ILIKE :search OR c.gmail ILIKE :search)")
        params["search"] = search_like

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
        
    order_clause = f"ORDER BY {order_by}"

    query = f"""
        SELECT c.id, c.codigo, c.nome_completo, c.cpf, c.gmail, s.nome_setor, c.status
        FROM colaboradores c
        LEFT JOIN setores s ON c.setor_id = s.id
        {where_sql}
        {order_clause}
    """
    df = conn.query(query, params=params)
    
    df['Status Visual'] = df['status'].apply(lambda s: '🟢' if s == 'Ativo' else '🔴')

    for col in ['codigo', 'nome_completo', 'cpf', 'gmail', 'nome_setor', 'status']:
        if col in df.columns:
            df[col] = df[col].fillna('')
    return df

def atualizar_colaborador(col_id, codigo, nome, cpf, gmail, setor_id, status):
    # (Função original com uma pequena melhoria na mensagem de erro)
    try:
        conn = get_db_connection()
        with conn.session as s:
            s.begin()
            
            query_check_cpf = text("SELECT 1 FROM colaboradores WHERE cpf = :cpf AND id != :id")
            cpf_existe = s.execute(query_check_cpf, {"cpf": cpf, "id": col_id}).fetchone()
            if cpf_existe:
                st.error(f"Erro: O CPF '{cpf}' já pertence a outro colaborador.")
                s.rollback()
                return False
            
            # A verificação aqui continua, pois ao EDITAR, a intenção não é duplicar.
            query_check_codigo = text("SELECT nome_completo FROM colaboradores WHERE codigo = :codigo AND setor_id = :setor_id AND id != :id AND status = 'Ativo'")
            colaborador_existente = s.execute(query_check_codigo, {"codigo": str(codigo), "setor_id": setor_id, "id": col_id}).fetchone()
            if colaborador_existente:
                st.error(f"Erro: O código '{codigo}' já está em uso por '{colaborador_existente[0]}' neste setor.")
                s.rollback()
                return False

            query = text("""
                UPDATE colaboradores SET codigo = :codigo, nome_completo = :nome, 
                cpf = :cpf, gmail = :gmail, setor_id = :setor_id, status = :status 
                WHERE id = :id
            """)
            s.execute(query, {
                "codigo": str(codigo), "nome": nome, "cpf": cpf, 
                "gmail": gmail, "setor_id": setor_id, "status": status, "id": col_id
            })
            s.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar o colaborador ID {col_id}: {e}")
        return False

def inativar_colaborador(col_id):
    # (Função original sem modificações)
    try:
        conn = get_db_connection()
        with conn.session as s:
            s.begin()
            query_check = text("""
                SELECT 1 FROM aparelhos a
                JOIN status s ON a.status_id = s.id
                JOIN (
                    SELECT aparelho_id, colaborador_id, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
                    FROM historico_movimentacoes
                ) h ON a.id = h.aparelho_id AND h.rn = 1
                WHERE s.nome_status = 'Em uso' AND h.colaborador_id = :col_id
            """)
            tem_aparelho = s.execute(query_check, {"col_id": col_id}).fetchone()
            if tem_aparelho:
                st.error(f"Erro: Não é possível inativar o colaborador, pois ele ainda possui aparelhos 'Em uso' associados. Por favor, processe a devolução primeiro.")
                s.rollback()
                return False

            query_update = text("UPDATE colaboradores SET status = 'Inativo' WHERE id = :id")
            s.execute(query_update, {"id": col_id})
            s.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao inativar o colaborador ID {col_id}: {e}")
        return False

def excluir_colaborador_permanentemente(col_id):
    # (Função original sem modificações)
    try:
        conn = get_db_connection()
        with conn.session as s:
            s.begin()
            # 1. Pega os dados do colaborador
            query_select = text("""
                SELECT c.id, c.codigo, c.nome_completo, c.cpf, c.gmail, s.nome_setor, c.data_cadastro
                FROM colaboradores c
                LEFT JOIN setores s ON c.setor_id = s.id
                WHERE c.id = :id
            """)
            colaborador = s.execute(query_select, {"id": col_id}).fetchone()
            
            if not colaborador:
                st.warning(f"Colaborador ID {col_id} não encontrado para exclusão.")
                s.rollback()
                return False

            # 2. Insere os dados no log de desligados
            query_log = text("""
                INSERT INTO colaboradores_desligados (id, codigo, nome_completo, cpf, gmail, setor_nome, data_cadastro, data_exclusao)
                VALUES (:id, :codigo, :nome, :cpf, :gmail, :setor, :data_cad, NOW())
            """)
            s.execute(query_log, {
                "id": colaborador.id, "codigo": colaborador.codigo, "nome": colaborador.nome_completo,
                "cpf": colaborador.cpf, "gmail": colaborador.gmail, "setor": colaborador.nome_setor,
                "data_cad": colaborador.data_cadastro
            })

            # 3. Desvincula o colaborador de todas as tabelas referenciadas
            s.execute(text("UPDATE contas_gmail SET colaborador_id = NULL WHERE colaborador_id = :id"), {"id": col_id})
            s.execute(text("UPDATE historico_movimentacoes SET colaborador_id = NULL WHERE colaborador_id = :id"), {"id": col_id})
            s.execute(text("UPDATE manutencoes SET colaborador_id_no_envio = NULL WHERE colaborador_id_no_envio = :id"), {"id": col_id})

            # 4. Exclui o colaborador da tabela principal
            query_delete = text("DELETE FROM colaboradores WHERE id = :id")
            s.execute(query_delete, {"id": col_id})
            
            s.commit()
        return True
    except Exception as e:
        st.error(f"Erro na exclusão permanente do colaborador ID {col_id}: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_log_desligados():
    """Carrega o log de colaboradores excluídos permanentemente."""
    conn = get_db_connection()
    df = conn.query("SELECT * FROM colaboradores_desligados ORDER BY data_exclusao DESC;")
    return df

# --- UI ---
st.title("Gestão de Colaboradores")
st.markdown("---")

try:
    setores_list = carregar_setores()
    setores_dict = {s['nome_setor']: s['id'] for s in setores_list}
    
    option = st.radio(
        "Selecione a operação:",
        ("Cadastrar Novo Colaborador", "Consultar Colaboradores", "Log de Excluídos"),
        horizontal=True,
        label_visibility="collapsed",
        key="colab_tab_selector"
    )
    st.markdown("---") 

    if option == "Cadastrar Novo Colaborador":
        st.subheader("Dados do Novo Colaborador")

        # --- LÓGICA DE CONFIRMAÇÃO ---
        if 'show_colab_confirmation' in st.session_state:
            st.warning(st.session_state['confirmation_message'])
            col1, col2 = st.columns(2)
            if col1.button("Sim, confirmar cadastro", type="primary", use_container_width=True):
                data = st.session_state['colab_to_add']
                if adicionar_colaborador_banco(data['nome'], data['cpf'], data['gmail'], data['setor_id'], data['codigo']):
                    st.cache_data.clear()
                    del st.session_state['show_colab_confirmation']
                    del st.session_state['colab_to_add']
                    st.rerun()
            
            if col2.button("Não, cancelar", use_container_width=True):
                del st.session_state['show_colab_confirmation']
                del st.session_state['colab_to_add']
                st.rerun()
        else:
            with st.form("form_novo_colaborador"):
                novo_codigo = st.text_input("Código*")
                novo_nome = st.text_input("Nome Completo*")
                novo_cpf = st.text_input("CPF*")
                novo_gmail = st.text_input("Gmail")
                setor_selecionado_nome = st.selectbox("Setor*", options=setores_dict.keys(), index=None, placeholder="Selecione...")

                submitted = st.form_submit_button("Adicionar Colaborador", use_container_width=True, type="primary")

                if submitted:
                    setor_id = setores_dict.get(setor_selecionado_nome)
                    
                    # --- CORREÇÃO: Limpeza dos dados de entrada ---
                    nome_limpo = novo_nome.strip()
                    cpf_limpo = novo_cpf.strip()
                    gmail_limpo = novo_gmail.strip() if novo_gmail else ""
                    codigo_limpo = novo_codigo.strip()

                    if not all([nome_limpo, cpf_limpo, codigo_limpo, setor_id]):
                        st.error("Nome, CPF, Código e Setor são campos obrigatórios.")
                    else:
                        colaborador_existente = verificar_duplicidade_codigo(codigo_limpo, setor_id)
                        
                        if colaborador_existente:
                            st.session_state['show_colab_confirmation'] = True
                            st.session_state['confirmation_message'] = (
                                f"ATENÇÃO: O código '{codigo_limpo}' já está em uso por "
                                f"**{colaborador_existente.nome_completo}** no setor **{colaborador_existente.nome_setor}**. "
                                "Deseja mesmo assim prosseguir com o cadastro?"
                            )
                            st.session_state['colab_to_add'] = {
                                "nome": nome_limpo, "cpf": cpf_limpo, "gmail": gmail_limpo,
                                "setor_id": setor_id, "codigo": codigo_limpo
                            }
                            st.rerun()
                        else:
                            if adicionar_colaborador_banco(nome_limpo, cpf_limpo, gmail_limpo, setor_id, codigo_limpo):
                                st.cache_data.clear()
                                st.rerun()
    
    elif option == "Consultar Colaboradores":
        st.subheader("Colaboradores Registrados")

        # --- ALERTA DE CÓDIGOS DUPLICADOS APRIMORADO ---
        num_duplicados = contar_codigos_duplicados()
        if num_duplicados > 0:
            st.warning(f"**Alerta de Integridade:** Existem **{num_duplicados}** grupos de códigos sendo utilizados por mais de um colaborador no mesmo setor.")
            with st.expander("Clique aqui para ver os detalhes"):
                detalhes_df = carregar_detalhes_duplicados()
                st.dataframe(
                    detalhes_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "codigo": "Código Duplicado",
                        "nome_setor": "Setor",
                        "nome_completo": "Colaborador Vinculado"
                    }
                )
            st.markdown("---")

        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
        with col_filtro1:
            setor_filtro_nome = st.selectbox("Filtrar por Setor:", ["Todos"] + list(setores_dict.keys()))
        with col_filtro2:
            status_filtro = st.selectbox("Filtrar por Status:", ["Todos", "Ativo", "Inativo"])
        with col_filtro3:
            termo_pesquisa = st.text_input("Pesquisar por Nome, Código ou Gmail:")
        
        setor_id_filtro = setores_dict.get(setor_filtro_nome) if setor_filtro_nome != "Todos" else None

        sort_options = {
            "Nome (A-Z)": "c.nome_completo ASC", "Código (Crescente)": "c.codigo ASC",
            "Setor (A-Z)": "s.nome_setor ASC", "Status (A-Z)": "c.status ASC"
        }
        sort_selection = st.selectbox("Organizar por:", options=sort_options.keys())

        colaboradores_df = carregar_colaboradores(
            order_by=sort_options[sort_selection],
            search_term=termo_pesquisa,
            setor_id=setor_id_filtro,
            status_filter=status_filtro
        )
        
        session_state_key = f"original_colabs_df_{sort_selection}_{termo_pesquisa}_{setor_filtro_nome}_{status_filtro}"
        if session_state_key not in st.session_state:
            for key in list(st.session_state.keys()):
                if key.startswith('original_colabs_df_'): del st.session_state[key]
            st.session_state[session_state_key] = colaboradores_df.copy()

        setores_options = list(setores_dict.keys())
        
        if 'colabs_para_excluir' in st.session_state and st.session_state.colabs_para_excluir:
            st.warning("**Atenção!** Você está prestes a **excluir permanentemente** os seguintes colaboradores inativos. Esta ação não pode ser desfeita e os seus dados serão movidos para o Log de Excluídos.")
            
            for col_id_to_delete in st.session_state.colabs_para_excluir:
                original_df = st.session_state[session_state_key]
                nome_colaborador_row = original_df.loc[original_df['id'] == col_id_to_delete, 'nome_completo']
                if not nome_colaborador_row.empty:
                    st.markdown(f"- **{nome_colaborador_row.iloc[0]}** (ID: {col_id_to_delete})")

            confirm_col1, confirm_col2 = st.columns(2)
            if confirm_col1.button("Confirmar Exclusão Definitiva", type="primary", use_container_width=True):
                for col_id_to_delete in st.session_state.colabs_para_excluir:
                    if excluir_colaborador_permanentemente(col_id_to_delete):
                        st.toast(f"Colaborador ID {col_id_to_delete} excluído permanentemente.", icon="✅")
                del st.session_state.colabs_para_excluir
                st.cache_data.clear()
                del st.session_state[session_state_key]
                st.rerun()

            if confirm_col2.button("Cancelar", use_container_width=True):
                del st.session_state.colabs_para_excluir
                st.rerun()
        else:
            edited_df = st.data_editor(
                st.session_state[session_state_key],
                disabled=["Status Visual", "id"],
                column_order=("Status Visual", "codigo", "nome_completo", "cpf", "gmail", "nome_setor", "status"),
                column_config={
                    "id": None, "Status Visual": st.column_config.TextColumn("Status", help="🟢 Ativo | 🔴 Inativo", width="small"),
                    "codigo": st.column_config.TextColumn("Código", required=True), "nome_completo": st.column_config.TextColumn("Nome Completo", required=True),
                    "cpf": st.column_config.TextColumn("CPF", required=True), "gmail": st.column_config.TextColumn("Gmail"),
                    "nome_setor": st.column_config.SelectboxColumn("Setor", options=setores_options, required=True),
                    "status": st.column_config.SelectboxColumn("Alterar Status", options=["Ativo", "Inativo"], required=True)
                },
                hide_index=True, num_rows="dynamic", key="colaboradores_editor", use_container_width=True
            )
            st.info("Para desligar um colaborador, altere o seu status para 'Inativo' ou, se já estiver inativo, remova a linha da tabela para iniciar a exclusão permanente.")
            
            if st.button("Salvar Alterações", use_container_width=True, key="save_colabs_changes"):
                original_df = st.session_state[session_state_key]
                changes_made = False
                
                deleted_ids = set(original_df['id']) - set(edited_df['id'])
                colabs_para_inativar = []
                colabs_para_excluir_perm = []

                for col_id in deleted_ids:
                    original_row = original_df[original_df['id'] == col_id].iloc[0]
                    if original_row['status'] == 'Ativo':
                        colabs_para_inativar.append(col_id)
                    elif original_row['status'] == 'Inativo':
                        colabs_para_excluir_perm.append(col_id)
                
                for col_id in colabs_para_inativar:
                    if inativar_colaborador(col_id):
                        st.toast(f"Colaborador ID {col_id} foi inativado!", icon="⚪")
                        changes_made = True

                if colabs_para_excluir_perm:
                    st.session_state.colabs_para_excluir = colabs_para_excluir_perm
                    changes_made = True
                
                original_df_indexed = original_df.set_index('id')
                edited_df_indexed = edited_df.set_index('id')
                common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)
                
                for col_id in common_ids:
                    original_row = original_df_indexed.loc[col_id]
                    edited_row = edited_df_indexed.loc[col_id]
                    original_data = original_row.drop('Status Visual')
                    edited_data = edited_row.drop('Status Visual')
                    if not original_data.equals(edited_data):
                        novo_setor_id = setores_dict.get(edited_row['nome_setor'])
                        if atualizar_colaborador(col_id, edited_row['codigo'], edited_row['nome_completo'], edited_row['cpf'], edited_row['gmail'], novo_setor_id, edited_row['status']):
                            st.toast(f"Colaborador '{edited_row['nome_completo']}' atualizado!", icon="✅")
                            changes_made = True

                if changes_made:
                    st.cache_data.clear()
                    del st.session_state[session_state_key]
                    st.rerun()
                else:
                    st.info("Nenhuma alteração foi detetada.")

    elif option == "Log de Excluídos":
        st.subheader("Histórico de Colaboradores Excluídos")
        log_df = carregar_log_desligados()
        if log_df.empty:
            st.info("Ainda não há registos de colaboradores excluídos permanentemente.")
        else:
            st.dataframe(
                log_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": "ID Original",
                    "codigo": "Código",
                    "nome_completo": "Nome Completo",
                    "cpf": "CPF",
                    "gmail": "Gmail",
                    "setor_nome": "Último Setor",
                    "data_cadastro": st.column_config.DateColumn("Data de Cadastro", format="DD/MM/YYYY"),
                    "data_exclusao": st.column_config.DatetimeColumn("Data de Exclusão", format="DD/MM/YYYY HH:mm")
                }
            )

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de colaboradores: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")

