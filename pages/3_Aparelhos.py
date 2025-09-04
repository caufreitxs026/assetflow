import streamlit as st
import pandas as pd
from datetime import date, datetime
from auth import show_login_form
from sqlalchemy import text
import numpy as np

# --- Verificação de Autenticação ---
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
    if st.button("Logout", key="aparelhos_logout"):
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

# --- Funções de Banco de Dados ---
def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def carregar_dados_para_selects():
    conn = get_db_connection()
    modelos_df = conn.query("""
        SELECT m.id, ma.nome_marca || ' - ' || m.nome_modelo as modelo_completo 
        FROM modelos m 
        JOIN marcas ma ON m.marca_id = ma.id 
        ORDER BY modelo_completo;
    """)
    status_df = conn.query("SELECT id, nome_status FROM status ORDER BY nome_status;")
    setores_df = conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
    return modelos_df.to_dict('records'), status_df.to_dict('records'), setores_df.to_dict('records')

def adicionar_aparelho_e_historico(serie, imei1, imei2, valor, modelo_id, status_id):
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            query_check = text("SELECT 1 FROM aparelhos WHERE numero_serie = :serie")
            existe = s.execute(query_check, {"serie": serie}).fetchone()
            if existe:
                st.error(f"O aparelho com Número de Série '{serie}' já existe.")
                s.rollback()
                return False

            query_insert_aparelho = text("""
                INSERT INTO aparelhos (numero_serie, imei1, imei2, valor, modelo_id, status_id, data_cadastro) 
                VALUES (:serie, :imei1, :imei2, :valor, :modelo_id, :status_id, :data)
                RETURNING id;
            """)
            result = s.execute(query_insert_aparelho, {
                "serie": serie, "imei1": imei1, "imei2": imei2, "valor": valor,
                "modelo_id": modelo_id, "status_id": status_id, "data": date.today()
            })
            aparelho_id = result.scalar_one()

            query_insert_historico = text("""
                INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, status_id, localizacao_atual, observacoes) 
                VALUES (:data, :ap_id, :stat_id, :loc, :obs)
            """)
            s.execute(query_insert_historico, {
                "data": datetime.now(), "ap_id": aparelho_id, "stat_id": status_id,
                "loc": "Estoque Interno", "obs": "Entrada inicial no sistema."
            })
            
            s.commit()
            st.success(f"Aparelho N/S '{serie}' cadastrado com sucesso!")
            return True
    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_inventario_completo(order_by, search_term=None, status_id=None, modelo_id=None, setor_id=None):
    """Carrega o inventário com filtros avançados."""
    conn = get_db_connection()
    
    params = {}
    where_clauses = []

    if status_id:
        where_clauses.append("a.status_id = :status_id")
        params["status_id"] = status_id
    if modelo_id:
        where_clauses.append("a.modelo_id = :modelo_id")
        params["modelo_id"] = modelo_id
    if setor_id:
        where_clauses.append("c.setor_id = :setor_id")
        params["setor_id"] = setor_id
    
    if search_term:
        search_like = f"%{search_term}%"
        where_clauses.append("""
            (a.numero_serie ILIKE :search OR 
             a.imei1 ILIKE :search OR 
             a.imei2 ILIKE :search OR 
             COALESCE(h_atual.colaborador_snapshot, c.nome_completo) ILIKE :search)
        """)
        params["search"] = search_like

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        WITH UltimoResponsavel AS (
            SELECT
                h.aparelho_id,
                h.colaborador_id,
                ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
            FROM historico_movimentacoes h
        )
        SELECT 
            a.id,
            a.numero_serie,
            ma.nome_marca || ' - ' || mo.nome_modelo as modelo_completo,
            s.nome_status,
            COALESCE(h_atual.colaborador_snapshot, c.nome_completo) as responsavel_atual,
            setor.nome_setor as setor_atual,
            a.valor,
            a.imei1,
            a.imei2,
            a.data_cadastro
        FROM aparelhos a
        LEFT JOIN modelos mo ON a.modelo_id = mo.id
        LEFT JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN status s ON a.status_id = s.id
        LEFT JOIN UltimoResponsavel ur ON a.id = ur.aparelho_id AND ur.rn = 1
        LEFT JOIN colaboradores c ON ur.colaborador_id = c.id
        LEFT JOIN setores setor ON c.setor_id = setor.id
        LEFT JOIN historico_movimentacoes h_atual ON h_atual.aparelho_id = a.id AND h_atual.id = (SELECT MAX(id) FROM historico_movimentacoes WHERE aparelho_id = a.id)
        {where_sql}
        ORDER BY {order_by}
    """
    df = conn.query(query, params=params)
    
    for col in ['responsavel_atual', 'setor_atual', 'imei1', 'imei2', 'numero_serie', 'modelo_completo', 'nome_status']:
        if col in df.columns:
            df[col] = df[col].fillna('')
    if 'valor' in df.columns:
        df['valor'] = pd.to_numeric(df['valor'].fillna(0))
    return df

def atualizar_aparelho_completo(aparelho_id, serie, imei1, imei2, valor, modelo_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("""
                UPDATE aparelhos SET numero_serie = :serie, imei1 = :imei1, imei2 = :imei2, 
                valor = :valor, modelo_id = :modelo_id WHERE id = :id
            """)
            s.execute(query, {
                "serie": serie, "imei1": imei1, "imei2": imei2, 
                "valor": float(valor), "modelo_id": modelo_id, "id": aparelho_id
            })
            s.commit()
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            st.error(f"Erro: O Número de Série '{serie}' já pertence a outro aparelho.")
        else:
            st.error(f"Erro ao atualizar o aparelho ID {aparelho_id}: {e}")
        return False

def excluir_aparelho(aparelho_id):
    try:
        conn = get_db_connection()
        with conn.session as s:
            query = text("DELETE FROM aparelhos WHERE id = :id")
            s.execute(query, {"id": aparelho_id})
            s.commit()
        return True
    except Exception as e:
        if 'foreign key constraint' in str(e).lower():
            st.error(f"Erro: Não é possível excluir o aparelho ID {aparelho_id}, pois ele possui um histórico de movimentações ou manutenções.")
        else:
            st.error(f"Erro ao excluir o aparelho ID {aparelho_id}: {e}")
        return False

# --- UI ---
st.title("Gestão de Aparelhos")
st.markdown("---")

try:
    modelos_list, status_list, setores_list = carregar_dados_para_selects()
    modelos_dict = {m['modelo_completo']: m['id'] for m in modelos_list}
    status_dict = {s['nome_status']: s['id'] for s in status_list}
    setores_dict = {s['nome_setor']: s['id'] for s in setores_list}
    
    tab_cadastro, tab_consulta = st.tabs(["Cadastrar Novo Aparelho", "Consultar Inventário"])

    with tab_cadastro:
        with st.form("form_novo_aparelho", clear_on_submit=True):
            st.subheader("Dados do Novo Aparelho")
            novo_serie = st.text_input("Número de Série*")
            modelo_selecionado_str = st.selectbox(
                "Modelo*", options=list(modelos_dict.keys()), index=None,
                placeholder="Selecione um modelo...", help="Clique na lista e comece a digitar para pesquisar."
            )
            novo_imei1 = st.text_input("IMEI 1")
            novo_imei2 = st.text_input("IMEI 2")
            novo_valor = st.number_input("Valor (R$)", min_value=0.0, value=0.0, format="%.2f")
            status_options = list(status_dict.keys())
            default_status_index = status_options.index('Em estoque') if 'Em estoque' in status_options else 0
            status_selecionado_str = st.selectbox("Status Inicial*", options=status_options, index=default_status_index)

            if st.form_submit_button("Adicionar Aparelho", use_container_width=True, type="primary"):
                if not novo_serie or not modelo_selecionado_str:
                    st.error("Número de Série e Modelo são campos obrigatórios.")
                else:
                    modelo_id = modelos_dict[modelo_selecionado_str]
                    status_id = status_dict[status_selecionado_str]
                    if adicionar_aparelho_e_historico(novo_serie, novo_imei1, novo_imei2, novo_valor, modelo_id, status_id):
                        st.cache_data.clear()
                        for key in list(st.session_state.keys()):
                            if key.startswith('original_aparelhos_df_'):
                                del st.session_state[key]
                        st.rerun()

    with tab_consulta:
        st.subheader("Inventário de Aparelhos")

        # --- FILTROS ---
        filter_cols = st.columns(3)
        with filter_cols[0]:
            status_filtro_nome = st.selectbox("Filtrar por Status:", ["Todos"] + list(status_dict.keys()), key="status_filter")
        with filter_cols[1]:
            modelo_filtro_nome = st.selectbox("Filtrar por Modelo:", ["Todos"] + list(modelos_dict.keys()), key="modelo_filter")
        with filter_cols[2]:
            setor_filtro_nome = st.selectbox("Filtrar por Setor:", ["Todos"] + list(setores_dict.keys()), key="setor_filter")

        termo_pesquisa = st.text_input("Pesquisar por N/S, IMEI ou Responsável:", placeholder="Digite para buscar...", key="search_filter")

        status_id_filtro = status_dict.get(status_filtro_nome) if status_filtro_nome != "Todos" else None
        modelo_id_filtro = modelos_dict.get(modelo_filtro_nome) if modelo_filtro_nome != "Todos" else None
        setor_id_filtro = setores_dict.get(setor_filtro_nome) if setor_filtro_nome != "Todos" else None
        
        # --- ORDENAÇÃO ---
        sort_options = {
            "Data de Entrada (Mais Recente)": "a.data_cadastro DESC",
            "Número de Série (A-Z)": "a.numero_serie ASC",
            "Modelo (A-Z)": "modelo_completo ASC",
            "Status (A-Z)": "s.nome_status ASC",
            "Responsável (A-Z)": "responsavel_atual ASC",
            "Setor (A-Z)": "setor_atual ASC"
        }
        sort_selection = st.selectbox("Organizar por:", options=sort_options.keys(), key="sort_selection")

        inventario_df = carregar_inventario_completo(
            order_by=sort_options[sort_selection],
            search_term=termo_pesquisa,
            status_id=status_id_filtro,
            modelo_id=modelo_id_filtro,
            setor_id=setor_id_filtro
        )
        
        session_state_key = f"original_aparelhos_df_{sort_selection}_{termo_pesquisa}_{status_filtro_nome}_{modelo_filtro_nome}_{setor_filtro_nome}"
        if session_state_key not in st.session_state:
            for key in list(st.session_state.keys()):
                if key.startswith('original_aparelhos_df_'):
                    del st.session_state[key]
            st.session_state[session_state_key] = inventario_df.copy()

        edited_df = st.data_editor(
            inventario_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "numero_serie": st.column_config.TextColumn("N/S", required=True),
                "modelo_completo": st.column_config.SelectboxColumn("Modelo", options=list(modelos_dict.keys()), required=True),
                "nome_status": st.column_config.TextColumn("Status", disabled=True),
                "responsavel_atual": st.column_config.TextColumn("Responsável", disabled=True),
                "setor_atual": st.column_config.TextColumn("Setor", disabled=True),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                "imei1": st.column_config.TextColumn("IMEI 1"),
                "imei2": st.column_config.TextColumn("IMEI 2"),
                "data_cadastro": st.column_config.DateColumn("Data de Entrada", format="DD/MM/YYYY", disabled=True),
            },
            hide_index=True,
            num_rows="dynamic",
            key="aparelhos_editor",
            use_container_width=True
        )
        
        if st.button("Salvar Alterações", use_container_width=True, key="save_aparelhos_changes"):
            original_df = st.session_state[session_state_key]
            changes_made = False

            deleted_ids = set(original_df['id']) - set(edited_df['id'])
            for aparelho_id in deleted_ids:
                if excluir_aparelho(aparelho_id):
                    st.toast(f"Aparelho ID {aparelho_id} excluído!", icon="🗑️")
                    changes_made = True

            original_df_indexed = original_df.set_index('id')
            edited_df_indexed = edited_df.set_index('id')
            common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)
            
            for aparelho_id in common_ids:
                original_row = original_df_indexed.loc[aparelho_id]
                edited_row = edited_df_indexed.loc[aparelho_id]
                
                if not original_row.equals(edited_row):
                    novo_modelo_id = modelos_dict[edited_row['modelo_completo']]
                    
                    if atualizar_aparelho_completo(
                        aparelho_id, edited_row['numero_serie'], edited_row['imei1'], 
                        edited_row['imei2'], edited_row['valor'], novo_modelo_id
                    ):
                        st.toast(f"Aparelho N/S '{edited_row['numero_serie']}' atualizado!", icon="✅")
                        changes_made = True
            
            if changes_made:
                st.cache_data.clear()
                del st.session_state[session_state_key]
                st.rerun()
            else:
                st.info("Nenhuma alteração foi detetada.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de aparelhos: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")

