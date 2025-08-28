import streamlit as st
import pandas as pd
from datetime import date, datetime
from auth import show_login_form
from sqlalchemy import text

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

# --- Conteúdo Principal da Página ---
st.title("Gestão de Aparelhos")
st.markdown("---")

# --- Funções de Banco de Dados (MODIFICADAS PARA POSTGRESQL) ---

def get_db_connection():
    """Retorna uma conexão ao banco de dados Supabase."""
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def carregar_dados_para_selects():
    conn = get_db_connection()
    modelos_df = conn.query("""
        SELECT m.id, m.nome_modelo, ma.nome_marca 
        FROM modelos m 
        JOIN marcas ma ON m.marca_id = ma.id 
        ORDER BY ma.nome_marca, m.nome_modelo;
    """)
    status_df = conn.query("SELECT id, nome_status FROM status ORDER BY nome_status;")
    return modelos_df.to_dict('records'), status_df.to_dict('records')

def adicionar_aparelho_e_historico(serie, imei1, imei2, valor, modelo_id, status_id):
    conn = get_db_connection()
    try:
        with conn.session as s:
            # Verifica se o número de série já existe
            query_check = text("SELECT 1 FROM aparelhos WHERE numero_serie = :serie")
            existe = s.execute(query_check, {"serie": serie}).fetchone()
            if existe:
                st.error(f"O aparelho com Número de Série '{serie}' já existe.")
                return

            # Insere o aparelho e retorna o ID gerado
            query_insert_aparelho = text("""
                INSERT INTO aparelhos (numero_serie, imei1, imei2, valor, modelo_id, status_id, data_cadastro) 
                VALUES (:serie, :imei1, :imei2, :valor, :modelo_id, :status_id, :data)
                RETURNING id;
            """)
            result = s.execute(query_insert_aparelho, {
                "serie": serie, "imei1": imei1, "imei2": imei2, "valor": valor,
                "modelo_id": modelo_id, "status_id": status_id, "data": date.today()
            })
            aparelho_id = result.scalar_one() # Pega o ID retornado

            # Insere o primeiro registo no histórico
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
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

@st.cache_data(ttl=30)
def carregar_inventario_completo(order_by="a.data_cadastro DESC"):
    conn = get_db_connection()
    # A query com CTE (WITH) é compatível com PostgreSQL
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
            c.nome_completo as responsavel_atual,
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
        ORDER BY {order_by}
    """
    df = conn.query(query)
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
                "valor": valor, "modelo_id": modelo_id, "id": aparelho_id
            })
            s.commit()
        st.cache_data.clear()
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
            # PRAGMA não é necessário/válido em PostgreSQL
            query = text("DELETE FROM aparelhos WHERE id = :id")
            s.execute(query, {"id": aparelho_id})
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        if 'foreign key constraint' in str(e).lower():
            st.error(f"Erro: Não é possível excluir o aparelho ID {aparelho_id}, pois ele possui um histórico de movimentações ou manutenções.")
        else:
            st.error(f"Erro ao excluir o aparelho ID {aparelho_id}: {e}")
        return False

# --- Interface do Usuário ---
try:
    modelos_list, status_list = carregar_dados_para_selects()
    modelos_dict = {f"{m['nome_marca']} - {m['nome_modelo']}": m['id'] for m in modelos_list}

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Adicionar Novo Aparelho")
        with st.form("form_novo_aparelho", clear_on_submit=True):
            novo_serie = st.text_input("Número de Série*")
            
            modelo_selecionado_str = st.selectbox(
                "Modelo*",
                options=modelos_dict.keys(),
                index=None,
                placeholder="Selecione um modelo...",
                help="Clique na lista e comece a digitar para pesquisar."
            )
            
            novo_imei1 = st.text_input("IMEI 1")
            novo_imei2 = st.text_input("IMEI 2")
            novo_valor = st.number_input("Valor (R$)", min_value=0.0, value=0.0, format="%.2f")
            status_dict = {s['nome_status']: s['id'] for s in status_list}
            
            # Garante que 'Em estoque' seja o padrão, se existir
            status_options = list(status_dict.keys())
            default_status_index = status_options.index('Em estoque') if 'Em estoque' in status_options else 0
            
            status_selecionado_str = st.selectbox("Status Inicial*", options=status_options, index=default_status_index)

            if st.form_submit_button("Adicionar Aparelho", use_container_width=True):
                if not novo_serie or not modelo_selecionado_str:
                    st.error("Número de Série e Modelo são campos obrigatórios.")
                else:
                    modelo_id = modelos_dict[modelo_selecionado_str]
                    status_id = status_dict[status_selecionado_str]
                    adicionar_aparelho_e_historico(novo_serie, novo_imei1, novo_imei2, novo_valor, modelo_id, status_id)
                    st.rerun()

    with col2:
        with st.expander("Ver, Editar e Excluir Inventário de Aparelhos", expanded=True):
            
            # Caixa de seleção para ordenação
            sort_options = {
                "Data de Entrada (Mais Recente)": "a.data_cadastro DESC",
                "Número de Série (A-Z)": "a.numero_serie ASC",
                "Modelo (A-Z)": "modelo_completo ASC",
                "Status (A-Z)": "s.nome_status ASC",
                "Responsável (A-Z)": "responsavel_atual ASC"
            }
            sort_selection = st.selectbox("Organizar por:", options=sort_options.keys())

            inventario_df = carregar_inventario_completo(order_by=sort_options[sort_selection])
            
            edited_df = st.data_editor(
                inventario_df,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "numero_serie": st.column_config.TextColumn("N/S", required=True),
                    "modelo_completo": st.column_config.SelectboxColumn(
                        "Modelo",
                        options=list(modelos_dict.keys()),
                        required=True
                    ),
                    "nome_status": st.column_config.TextColumn("Status Atual", disabled=True),
                    "responsavel_atual": st.column_config.TextColumn("Responsável Atual", disabled=True),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                    "imei1": st.column_config.TextColumn("IMEI 1"),
                    "imei2": st.column_config.TextColumn("IMEI 2"),
                    "data_cadastro": st.column_config.DateColumn("Data de Entrada", format="DD/MM/YYYY", disabled=True),
                },
                hide_index=True,
                num_rows="dynamic",
                key="aparelhos_editor"
            )
            
            if st.button("Salvar Alterações", use_container_width=True):
                # Lógica para Exclusão
                deleted_ids = set(inventario_df['id']) - set(edited_df['id'])
                for aparelho_id in deleted_ids:
                    if excluir_aparelho(aparelho_id):
                        st.toast(f"Aparelho ID {aparelho_id} excluído!", icon="🗑️")

                # Lógica para Atualização
                # Compara o dataframe editado com o original para encontrar mudanças
                if not edited_df.equals(inventario_df.loc[edited_df.index]):
                    # Encontra as diferenças
                    diff_df = pd.concat([edited_df, inventario_df]).drop_duplicates(keep=False)
                    for index, row in diff_df.iterrows():
                        if row['id'] in edited_df['id'].values: # Garante que é uma linha atualizada
                            aparelho_id = row['id']
                            novo_serie = row['numero_serie']
                            novo_imei1 = row['imei1']
                            novo_imei2 = row['imei2']
                            novo_valor = row['valor']
                            novo_modelo_id = modelos_dict[row['modelo_completo']]
                            
                            if atualizar_aparelho_completo(aparelho_id, novo_serie, novo_imei1, novo_imei2, novo_valor, novo_modelo_id):
                                st.toast(f"Aparelho N/S '{row['numero_serie']}' atualizado!", icon="✅")
                st.rerun()

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de aparelhos: {e}")
    st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")

