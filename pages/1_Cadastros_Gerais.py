import streamlit as st
import pandas as pd
from sqlalchemy import text
from auth import logout
from datetime import date, datetime
import uuid
from supabase import create_client, Client

# --- Autenticação e Permissão ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

if st.session_state.get('user_role') != 'Administrador':
    st.error("Acesso negado. Apenas administradores podem aceder a esta página.")
    st.stop()

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
    if st.button("Logout", key="cadastros_logout"):
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

# --- Funções de Banco de Dados e Storage ---
def get_db_connection():
    return st.connection("supabase", type="sql")

def init_supabase_client():
    try:
        url = st.secrets["connections"]["supabase_storage"]["url"]
        key = st.secrets["connections"]["supabase_storage"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Credenciais do Supabase Storage não encontradas nos secrets.")
        st.info("Por favor, adicione [connections.supabase_storage] com 'url' e 'key' ao seu ficheiro secrets.toml.")
        return None

@st.cache_data(ttl=60)
def get_foreign_key_map(table_name, name_column, key_column='id', join_clause=""):
    conn = get_db_connection()
    query = f"SELECT {key_column} as key_col, {name_column} as name_col FROM {table_name} {join_clause}"
    df = conn.query(query)
    return pd.Series(df['key_col'].values, index=df['name_col']).to_dict()

# Funções para Marcas
@st.cache_data(ttl=30)
def carregar_marcas():
    conn = get_db_connection()
    df = conn.query("SELECT id, nome_marca FROM marcas ORDER BY nome_marca;")
    return df
def adicionar_marca(nome_marca):
    if not nome_marca or not nome_marca.strip(): st.error("O nome da marca não pode ser vazio."); return
    try:
        conn = get_db_connection()
        with conn.session as s:
            query_check = text("SELECT id FROM marcas WHERE TRIM(LOWER(nome_marca)) = :nome")
            if s.execute(query_check, {"nome": nome_marca.strip().lower()}).fetchone():
                st.warning(f"A marca '{nome_marca}' já existe."); return
            query_insert = text("INSERT INTO marcas (nome_marca) VALUES (:nome)")
            s.execute(query_insert, {"nome": nome_marca.strip()}); s.commit()
        st.success(f"Marca '{nome_marca}' adicionada com sucesso!"); st.cache_data.clear()
    except Exception as e: st.error(f"Ocorreu um erro ao adicionar a marca: {e}")
def atualizar_marca(marca_id, nome_marca):
    try:
        conn = get_db_connection();
        with conn.session as s:
            query = text("UPDATE marcas SET nome_marca = :nome WHERE id = :id"); s.execute(query, {"nome": nome_marca, "id": marca_id}); s.commit()
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro ao atualizar marca: {e}"); return False

# Funções para Modelos
@st.cache_data(ttl=30)
def carregar_modelos():
    conn = get_db_connection()
    return conn.query("SELECT m.id, m.nome_modelo, ma.nome_marca FROM modelos m JOIN marcas ma ON m.marca_id = ma.id ORDER BY ma.nome_marca, m.nome_modelo;")
def adicionar_modelo(nome_modelo, marca_id):
    if not nome_modelo or not nome_modelo.strip() or not marca_id: st.error("O nome do modelo e a marca são obrigatórios."); return
    try:
        conn = get_db_connection();
        with conn.session as s:
            query = text("INSERT INTO modelos (nome_modelo, marca_id) VALUES (:nome, :marca_id)"); s.execute(query, {"nome": nome_modelo.strip(), "marca_id": marca_id}); s.commit()
        st.success(f"Modelo '{nome_modelo}' adicionado com sucesso!"); st.cache_data.clear()
    except Exception as e: st.error(f"Ocorreu um erro ao adicionar o modelo: {e}")
def atualizar_modelo(modelo_id, nome_modelo, marca_id):
    try:
        conn = get_db_connection();
        with conn.session as s:
            query = text("UPDATE modelos SET nome_modelo = :nome, marca_id = :marca_id WHERE id = :id"); s.execute(query, {"nome": nome_modelo, "marca_id": marca_id, "id": modelo_id}); s.commit()
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro ao atualizar modelo: {e}"); return False

# Funções para Setores
@st.cache_data(ttl=30)
def carregar_setores():
    conn = get_db_connection(); return conn.query("SELECT id, nome_setor FROM setores ORDER BY nome_setor;")
def adicionar_setor(nome_setor):
    if not nome_setor or not nome_setor.strip(): st.error("O nome do setor não pode ser vazio."); return
    try:
        conn = get_db_connection();
        with conn.session as s:
            query_check = text("SELECT id FROM setores WHERE TRIM(LOWER(nome_setor)) = :nome")
            if s.execute(query_check, {"nome": nome_setor.strip().lower()}).fetchone():
                st.warning(f"O setor '{nome_setor}' já existe."); return
            query_insert = text("INSERT INTO setores (nome_setor) VALUES (:nome)"); s.execute(query_insert, {"nome": nome_setor.strip()}); s.commit()
        st.success(f"Setor '{nome_setor}' adicionado com sucesso!"); st.cache_data.clear()
    except Exception as e: st.error(f"Ocorreu um erro ao adicionar o setor: {e}")
def atualizar_setor(setor_id, nome_setor):
    try:
        conn = get_db_connection();
        with conn.session as s:
            query = text("UPDATE setores SET nome_setor = :nome WHERE id = :id"); s.execute(query, {"nome": nome_setor, "id": setor_id}); s.commit()
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro ao atualizar setor: {e}"); return False

# Funções para Gestão de Compras
def registrar_compra(dados, anexo):
    supabase_client = init_supabase_client()
    if not supabase_client: return False

    path_anexo = None
    if anexo is not None:
        try:
            file_ext = anexo.name.split('.')[-1]
            path_anexo = f"{date.today().strftime('%Y/%m')}/{uuid.uuid4()}.{file_ext}"
            supabase_client.storage.from_("notas_fiscais").upload(path_anexo, anexo.getvalue())
        except Exception as e:
            st.error(f"Erro ao fazer o upload do anexo: {e}"); return False
    
    conn = get_db_connection()
    with conn.session as s:
        try:
            s.begin()
            query = text("""
                INSERT INTO compras_ativos (data_compra, modelo_id, quantidade, valor_unitario, imeis_texto, 
                                            comprador_nome, comprador_cpf, loja, loja_login, loja_senha, nota_fiscal_path)
                VALUES (:data_compra, :modelo_id, :quantidade, :valor_unitario, :imeis_texto, 
                        :comprador_nome, :comprador_cpf, :loja, :loja_login, :loja_senha, :nota_fiscal_path)
            """)
            s.execute(query, {**dados, "nota_fiscal_path": path_anexo})
            s.commit()
            st.success("Registo de compra adicionado com sucesso!"); st.cache_data.clear(); return True
        except Exception as e:
            s.rollback(); st.error(f"Erro ao registar a compra na base de dados: {e}"); return False

@st.cache_data(ttl=30)
def carregar_compras():
    conn = get_db_connection()
    df = conn.query("""
        SELECT 
            ca.id, ca.data_compra, ma.nome_marca || ' - ' || mo.nome_modelo as modelo, ca.quantidade, 
            ca.valor_unitario, ca.comprador_nome, ca.loja, ca.nota_fiscal_path
        FROM compras_ativos ca
        JOIN modelos mo ON ca.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        ORDER BY ca.data_compra DESC;
    """)
    if not df.empty and 'nota_fiscal_path' in df.columns:
        supabase_client = init_supabase_client()
        if supabase_client:
            df['link_nota_fiscal'] = df['nota_fiscal_path'].apply(
                lambda path: supabase_client.storage.from_("notas_fiscais").create_signed_url(path, 60)['signedURL'] if path else None
            )
    return df

# --- UI ---
st.title("Cadastros Gerais")
st.markdown("---")

try:
    option = st.radio(
        "Selecione o cadastro:",
        ("Registar Compra de Ativos", "Consultar Compras", "Marcas e Modelos", "Setores"),
        horizontal=True,
        label_visibility="collapsed",
        key="cadastros_tab_selector"
    )
    st.markdown("---")

    if option == "Registar Compra de Ativos":
        st.header("Registar Compra de Ativos em Lote")
        with st.form("form_nova_compra", clear_on_submit=True):
            st.subheader("Dados da Mercadoria")
            modelos_map = get_foreign_key_map("modelos", "ma.nome_marca || ' - ' || mo.nome_modelo", key_column="mo.id", join_clause="mo JOIN marcas ma ON mo.marca_id = ma.id")
            
            c1, c2 = st.columns(2)
            data_compra = c1.date_input("Data da Compra*", value=date.today())
            modelo_selecionado = c2.selectbox("Marca e Modelo Comprado*", options=list(modelos_map.keys()), index=None, placeholder="Selecione...")
            
            c3, c4 = st.columns(2)
            quantidade = c3.number_input("Quantidade de Aparelhos*", min_value=1, step=1)
            valor_unitario = c4.number_input("Valor por Unidade (R$)", min_value=0.0, format="%.2f")
            
            imeis = st.text_area("IMEIs dos Aparelhos", placeholder="Um IMEI por linha, se disponível.")

            st.subheader("Dados do Comprador e Anexo")
            comprador_nome = st.text_input("Nome Completo do Comprador")
            comprador_cpf = st.text_input("CPF do Comprador")
            loja = st.text_input("Loja onde ocorreu a compra")
            loja_login = st.text_input("Login (site/aplicativo)")
            loja_senha = st.text_input("Senha (site/aplicativo)", type="password")
            
            anexo_nf = st.file_uploader("Anexar Nota Fiscal (PDF, DOCX, Imagem)", type=['pdf', 'docx', 'png', 'jpg', 'jpeg'])

            submitted = st.form_submit_button("Registar Compra", use_container_width=True, type="primary")
            if submitted:
                if not all([data_compra, modelo_selecionado, quantidade]):
                    st.error("Data da compra, Modelo e Quantidade são campos obrigatórios.")
                else:
                    dados_compra = {
                        "data_compra": data_compra, "modelo_id": modelos_map[modelo_selecionado],
                        "quantidade": quantidade, "valor_unitario": valor_unitario, "imeis_texto": imeis,
                        "comprador_nome": comprador_nome, "comprador_cpf": comprador_cpf, "loja": loja,
                        "loja_login": loja_login, "loja_senha": loja_senha
                    }
                    if registrar_compra(dados_compra, anexo_nf):
                        st.rerun()

    elif option == "Consultar Compras":
        st.header("Histórico de Compras de Ativos")
        df_compras = carregar_compras()
        st.dataframe(df_compras, use_container_width=True, hide_index=True,
            column_config={
                "id": "ID", "data_compra": st.column_config.DateColumn("Data da Compra", format="DD/MM/YYYY"),
                "modelo": "Modelo", "quantidade": "Qtd.", "valor_unitario": st.column_config.NumberColumn("Valor Unit.", format="R$ %.2f"),
                "comprador_nome": "Comprador", "loja": "Loja",
                "nota_fiscal_path": None, # Oculta a coluna com o caminho do ficheiro
                "link_nota_fiscal": st.column_config.LinkColumn("Nota Fiscal", display_text="Baixar Anexo")
            }
        )

    elif option == "Marcas e Modelos":
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Marcas")
            with st.form("form_nova_marca", clear_on_submit=True):
                novo_nome_marca = st.text_input("Cadastrar nova marca")
                if st.form_submit_button("Adicionar Marca", use_container_width=True, type="primary"):
                    adicionar_marca(novo_nome_marca); st.rerun()
            with st.expander("Ver e Editar Marcas", expanded=True):
                marcas_df = carregar_marcas(); session_key_marcas = "original_marcas_df"
                if session_key_marcas not in st.session_state: st.session_state[session_key_marcas] = marcas_df.copy()
                edited_marcas_df = st.data_editor(marcas_df, key="edit_marcas", hide_index=True, disabled=["id"], use_container_width=True)
                if st.button("Salvar Alterações de Marcas", use_container_width=True):
                    original_df = st.session_state[session_key_marcas]; changes_made = False
                    for index, row in edited_marcas_df.iterrows():
                        if index < len(original_df) and not row.equals(original_df.loc[index]):
                            if atualizar_marca(row['id'], row['nome_marca']):
                                st.toast(f"Marca '{row['nome_marca']}' atualizada!", icon="✅"); changes_made = True
                    if changes_made: st.cache_data.clear(); del st.session_state[session_key_marcas]; st.rerun()
                    else: st.info("Nenhuma alteração detetada.")
        with col2:
            st.subheader("Modelos")
            marcas_df_options = carregar_marcas(); marcas_dict = {row['nome_marca']: row['id'] for index, row in marcas_df_options.iterrows()}
            with st.form("form_novo_modelo", clear_on_submit=True):
                novo_nome_modelo = st.text_input("Cadastrar novo modelo")
                marca_selecionada_nome = st.selectbox("Selecione a Marca", options=list(marcas_dict.keys()), index=None, placeholder="Selecione...")
                if st.form_submit_button("Adicionar Modelo", use_container_width=True, type="primary"):
                    if marca_selecionada_nome and novo_nome_modelo:
                        adicionar_modelo(novo_nome_modelo, marcas_dict[marca_selecionada_nome]); st.rerun()
                    else: st.warning("Preencha o nome do modelo e selecione uma marca.")
            with st.expander("Ver e Editar Modelos", expanded=True):
                modelos_df = carregar_modelos(); session_key_modelos = "original_modelos_df"
                if session_key_modelos not in st.session_state: st.session_state[session_key_modelos] = modelos_df.copy()
                edited_modelos_df = st.data_editor(modelos_df, column_config={"id": None, "nome_modelo": st.column_config.TextColumn("Modelo", required=True), "nome_marca": st.column_config.SelectboxColumn("Marca", options=list(marcas_dict.keys()), required=True)}, hide_index=True, key="edit_modelos", use_container_width=True)
                if st.button("Salvar Alterações de Modelos", use_container_width=True):
                    original_df = st.session_state[session_key_modelos]; changes_made = False
                    for index, row in edited_modelos_df.iterrows():
                        if index < len(original_df) and not row.equals(original_df.loc[index]):
                            nova_marca_id = marcas_dict[row['nome_marca']]
                            if atualizar_modelo(row['id'], row['nome_modelo'], nova_marca_id):
                                st.toast(f"Modelo '{row['nome_modelo']}' atualizado!", icon="✅"); changes_made = True
                    if changes_made: st.cache_data.clear(); del st.session_state[session_key_modelos]; st.rerun()
                    else: st.info("Nenhuma alteração detetada.")

    elif option == "Setores":
        col1_setor, col2_setor = st.columns([1, 2])
        with col1_setor:
            st.subheader("Adicionar Setor")
            with st.form("form_novo_setor", clear_on_submit=True):
                novo_nome_setor = st.text_input("Cadastrar novo setor")
                if st.form_submit_button("Adicionar Setor", use_container_width=True, type="primary"):
                    adicionar_setor(novo_nome_setor); st.rerun()
        with col2_setor:
            st.subheader("Setores Registrados")
            with st.expander("Ver e Editar Setores", expanded=True):
                setores_df = carregar_setores(); session_key_setores = "original_setores_df"
                if session_key_setores not in st.session_state: st.session_state[session_key_setores] = setores_df.copy()
                edited_setores_df = st.data_editor(setores_df, key="edit_setores", hide_index=True, disabled=["id"], use_container_width=True)
                if st.button("Salvar Alterações de Setores", use_container_width=True):
                    original_df = st.session_state[session_key_setores]; changes_made = False
                    for index, row in edited_setores_df.iterrows():
                        if index < len(original_df) and not row.equals(original_df.loc[index]):
                            if atualizar_setor(row['id'], row['nome_setor']):
                                st.toast(f"Setor '{row['nome_setor']}' atualizado!", icon="✅"); changes_made = True
                    if changes_made: st.cache_data.clear(); del st.session_state[session_key_setores]; st.rerun()
                    else: st.info("Nenhuma alteração detetada.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de cadastros: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")

