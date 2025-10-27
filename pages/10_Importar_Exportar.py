import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
from auth import show_login_form, logout
from sqlalchemy import text

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
    if st.button("Logout", key="import_export_logout"):
        logout()
    st.markdown("---")

# --- Funções do DB ---
def get_db_connection():
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=60)
def get_foreign_key_map(table_name, name_column, key_column='id', join_clause=""):
    conn = get_db_connection()
    query = f"SELECT {key_column} as key_col, {name_column} as name_col FROM {table_name} {join_clause}"
    df = conn.query(query)
    return pd.Series(df['key_col'].values, index=df['name_col']).to_dict()

# --- UI ---
st.title("Importar e Exportar Dados")
st.markdown("---")

option = st.radio(
    "Selecione a operação:",
    ("Importar em Lote", "Exportar Relatórios"),
    horizontal=True,
    label_visibility="collapsed",
    key="import_export_tab_selector"
)
st.markdown("---")

if option == "Importar em Lote":
    st.info("Selecione a operação, baixe o modelo, preencha com seus dados e faça o upload para importar em massa.")

    tabela_selecionada = st.selectbox(
        "1. Selecione a operação de importação:",
        ["Importar Colaboradores", "Importar Aparelhos", "Importar Marcas", "Importar Contas Gmail", "Importar Movimentações"]
    )

    try:
        if tabela_selecionada == "Importar Colaboradores":
            st.subheader("Importar Novos Colaboradores")
            setores_map = get_foreign_key_map("setores", "nome_setor")
            exemplo_setor = list(setores_map.keys())[0] if setores_map else "TI"
            df_modelo = pd.DataFrame({"codigo": ["1001"], "nome_completo": ["Nome Sobrenome Exemplo"], "cpf": ["123.456.789-00"], "gmail": ["exemplo.email@gmail.com"], "nome_setor": [exemplo_setor]})
            
            output = io.BytesIO()
            df_modelo.to_excel(output, index=False, sheet_name='Colaboradores')
            output.seek(0)
            
            st.download_button(label="Baixar Planilha Modelo", data=output, file_name="modelo_colaboradores.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            uploaded_file = st.file_uploader("Escolha a planilha de Colaboradores (.xlsx)", type="xlsx", key="upload_colab")
            if uploaded_file:
                df_upload = pd.read_excel(uploaded_file, dtype=str).fillna('')
                st.dataframe(df_upload)
                if st.button("Importar Dados dos Colaboradores", use_container_width=True, type="primary"):
                    conn = get_db_connection()
                    sucesso, erros = 0, 0
                    with st.spinner("Importando dados..."), conn.session as s:
                        for index, row in df_upload.iterrows():
                            try:
                                setor_id = setores_map.get(row['nome_setor'].strip())
                                if setor_id is None:
                                    st.warning(f"Linha {index+2}: Setor '{row['nome_setor']}' não encontrado. Pulando registo.")
                                    erros += 1; continue
                                
                                query = text("INSERT INTO colaboradores (codigo, nome_completo, cpf, gmail, setor_id, data_cadastro) VALUES (:codigo, :nome, :cpf, :gmail, :setor_id, :data)")
                                s.execute(query, {"codigo": row['codigo'], "nome": row['nome_completo'], "cpf": row['cpf'], "gmail": row['gmail'], "setor_id": setor_id, "data": date.today()})
                                sucesso += 1
                            except Exception as e:
                                s.rollback() # Garante que a transação falha seja desfeita
                                if 'unique constraint' in str(e).lower():
                                    st.warning(f"Linha {index+2}: Colaborador com código, CPF ou setor já existe. Pulando registo.")
                                else:
                                    st.error(f"Linha {index+2}: Erro inesperado - {e}. Pulando registo.")
                                erros += 1
                        if erros == 0:
                            s.commit()
                    st.success(f"Importação concluída! {sucesso} registos importados com sucesso.")
                    if erros > 0: st.error(f"{erros} registos continham erros e não foram importados.")
                    st.cache_data.clear()

        elif tabela_selecionada == "Importar Aparelhos":
            st.subheader("Importar Novos Aparelhos")
            modelos_map = get_foreign_key_map("modelos", "ma.nome_marca || ' - ' || mo.nome_modelo", key_column="mo.id", join_clause="mo JOIN marcas ma ON mo.marca_id = ma.id")
            status_map = get_foreign_key_map("status", "nome_status")
            exemplo_modelo = list(modelos_map.keys())[0] if modelos_map else "Samsung - Galaxy S24"
            exemplo_status = 'Em estoque' if 'Em estoque' in status_map else (list(status_map.keys())[0] if status_map else "")
            df_modelo = pd.DataFrame({"numero_serie": ["ABC123456789"], "imei1": ["111111111111111"], "imei2": ["222222222222222"], "valor": [4999.90], "modelo_completo": [exemplo_modelo], "status_inicial": [exemplo_status]})
            
            output = io.BytesIO()
            df_modelo.to_excel(output, index=False, sheet_name='Aparelhos')
            output.seek(0)
            st.download_button(label="Baixar Planilha Modelo", data=output, file_name="modelo_aparelhos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            uploaded_file = st.file_uploader("Escolha a planilha de Aparelhos (.xlsx)", type="xlsx", key="upload_aparelho")
            if uploaded_file:
                df_upload = pd.read_excel(uploaded_file).fillna('')
                st.dataframe(df_upload)
                if st.button("Importar Dados dos Aparelhos", use_container_width=True, type="primary"):
                    conn = get_db_connection()
                    sucesso, erros = 0, 0
                    with st.spinner("Importando dados..."), conn.session as s:
                        for index, row in df_upload.iterrows():
                            try:
                                s.begin()
                                modelo_id = modelos_map.get(str(row['modelo_completo']).strip())
                                status_id = status_map.get(str(row['status_inicial']).strip())
                                if not all([modelo_id, status_id]):
                                    st.warning(f"Linha {index+2}: Modelo ou Status inválido. Pulando registo.")
                                    erros += 1; s.rollback(); continue
                                
                                q_aparelho = text("INSERT INTO aparelhos (numero_serie, imei1, imei2, valor, modelo_id, status_id, data_cadastro) VALUES (:ns, :i1, :i2, :val, :mid, :sid, :data) RETURNING id")
                                result = s.execute(q_aparelho, {"ns": str(row['numero_serie']), "i1": str(row['imei1']), "i2": str(row['imei2']), "val": float(row['valor']), "mid": modelo_id, "sid": status_id, "data": date.today()})
                                aparelho_id = result.scalar_one()
                                
                                q_hist = text("INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, status_id, localizacao_atual, observacoes) VALUES (:data, :apid, :sid, :loc, :obs)")
                                s.execute(q_hist, {"data": datetime.now(), "apid": aparelho_id, "sid": status_id, "loc": "Estoque Interno", "obs": "Entrada via importação."})
                                s.commit()
                                sucesso += 1
                            except Exception as e:
                                s.rollback()
                                if 'unique constraint' in str(e).lower():
                                    st.warning(f"Linha {index+2}: Aparelho com N/S já existe. Pulando registo.")
                                else:
                                    st.error(f"Linha {index+2}: Erro inesperado - {e}. Pulando registo.")
                                erros += 1
                    st.success(f"Importação concluída! {sucesso} registos importados com sucesso.")
                    if erros > 0: st.error(f"{erros} registos continham erros.")
                    st.cache_data.clear()

        elif tabela_selecionada == "Importar Marcas":
            st.subheader("Importar Novas Marcas")
            df_modelo = pd.DataFrame({"nome_marca": ["Nome da Marca Exemplo"]})
            
            output = io.BytesIO()
            df_modelo.to_excel(output, index=False, sheet_name='Marcas')
            output.seek(0)
            st.download_button(label="Baixar Planilha Modelo", data=output, file_name="modelo_marcas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            uploaded_file = st.file_uploader("Escolha a planilha de Marcas (.xlsx)", type="xlsx", key="upload_marca")
            if uploaded_file:
                df_upload = pd.read_excel(uploaded_file, dtype=str).fillna('')
                st.dataframe(df_upload)
                if st.button("Importar Dados de Marcas", use_container_width=True, type="primary"):
                    conn = get_db_connection()
                    sucesso, erros = 0, 0
                    with st.spinner("Importando dados..."), conn.session as s:
                        for index, row in df_upload.iterrows():
                            try:
                                query = text("INSERT INTO marcas (nome_marca) VALUES (:nome)")
                                s.execute(query, {"nome": row['nome_marca'].strip()})
                                sucesso += 1
                            except Exception as e:
                                if 'unique constraint' in str(e).lower():
                                    st.warning(f"Linha {index+2}: Marca '{row['nome_marca']}' já existe. Pulando registo.")
                                else:
                                    st.error(f"Linha {index+2}: Erro inesperado - {e}. Pulando registo.")
                                erros += 1
                        s.commit()
                    st.success(f"Importação concluída! {sucesso} registos importados com sucesso.")
                    if erros > 0: st.error(f"{erros} registos continham erros.")
                    st.cache_data.clear()
        
        elif tabela_selecionada == "Importar Contas Gmail":
            st.subheader("Importar Novas Contas Gmail")
            colaboradores_map = get_foreign_key_map("colaboradores", "nome_completo")
            exemplo_colaborador = list(colaboradores_map.keys())[0] if colaboradores_map else ""
            df_modelo = pd.DataFrame({"email": ["conta.exemplo@gmail.com"], "senha": ["senhaforte123"], "telefone_recuperacao": ["11999998888"], "email_recuperacao": ["recuperacao@email.com"], "nome_colaborador": [exemplo_colaborador]})
            
            output = io.BytesIO()
            df_modelo.to_excel(output, index=False, sheet_name='Contas_Gmail')
            output.seek(0)
            
            st.download_button(label="Baixar Planilha Modelo", data=output, file_name="modelo_contas_gmail.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            uploaded_file = st.file_uploader("Escolha a planilha de Contas Gmail (.xlsx)", type="xlsx", key="upload_gmail")
            if uploaded_file:
                df_upload = pd.read_excel(uploaded_file, dtype=str).fillna('')
                st.dataframe(df_upload)
                if st.button("Importar Dados de Contas Gmail", use_container_width=True, type="primary"):
                    conn = get_db_connection()
                    sucesso, erros = 0, 0
                    with st.spinner("Importando dados..."), conn.session as s:
                        for index, row in df_upload.iterrows():
                            try:
                                colaborador_id = colaboradores_map.get(row['nome_colaborador'].strip()) if row['nome_colaborador'] else None
                                
                                query = text("INSERT INTO contas_gmail (email, senha, telefone_recuperacao, email_recuperacao, colaborador_id) VALUES (:email, :senha, :tel, :email_rec, :cid)")
                                s.execute(query, {"email": row['email'], "senha": row['senha'], "tel": row['telefone_recuperacao'], "email_rec": row['email_recuperacao'], "cid": colaborador_id})
                                sucesso += 1
                            except Exception as e:
                                if 'unique constraint' in str(e).lower():
                                    st.warning(f"Linha {index+2}: E-mail '{row['email']}' já existe. Pulando registo.")
                                else:
                                    st.error(f"Linha {index+2}: Erro inesperado - {e}. Pulando registo.")
                                erros += 1
                        s.commit()
                    st.success(f"Importação concluída! {sucesso} registos importados com sucesso.")
                    if erros > 0: st.error(f"{erros} registos continham erros.")
                    st.cache_data.clear()

        elif tabela_selecionada == "Importar Movimentações":
            st.subheader("Importar Novas Movimentações (Entregas)")
            st.warning("Esta funcionalidade é ideal para registar a entrega de aparelhos a colaboradores em massa.")

            aparelhos_map = get_foreign_key_map("aparelhos", "numero_serie")
            colaboradores_map = get_foreign_key_map("colaboradores", "nome_completo")
            status_map = get_foreign_key_map("status", "nome_status")
            status_em_uso_id = status_map.get("Em uso")

            exemplo_ns = list(aparelhos_map.keys())[0] if aparelhos_map else "NUMERO_DE_SERIE_DO_APARELHO"
            exemplo_colab = list(colaboradores_map.keys())[0] if colaboradores_map else "Nome Completo do Colaborador"
            df_modelo = pd.DataFrame({"numero_serie_aparelho": [exemplo_ns], "nome_colaborador": [exemplo_colab], "localizacao": ["Mesa do Colaborador"], "observacoes": ["Entrega para novo colaborador."]})
            
            output = io.BytesIO()
            df_modelo.to_excel(output, index=False, sheet_name='Movimentacoes')
            output.seek(0)
            
            st.download_button(label="Baixar Planilha Modelo de Movimentações", data=output, file_name="modelo_movimentacoes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            uploaded_file = st.file_uploader("Escolha a planilha de Movimentações (.xlsx)", type="xlsx", key="upload_mov")
            if uploaded_file:
                df_upload = pd.read_excel(uploaded_file, dtype=str).fillna('')
                st.dataframe(df_upload)
                if st.button("Importar Movimentações", use_container_width=True, type="primary"):
                    conn = get_db_connection()
                    sucesso, erros = 0, 0
                    with st.spinner("Processando movimentações..."), conn.session as s:
                        for index, row in df_upload.iterrows():
                            try:
                                s.begin()
                                aparelho_id = aparelhos_map.get(row['numero_serie_aparelho'].strip())
                                nome_colaborador_snapshot = row['nome_colaborador'].strip()
                                colaborador_id = colaboradores_map.get(nome_colaborador_snapshot)

                                if not all([aparelho_id, colaborador_id, status_em_uso_id]):
                                    st.warning(f"Linha {index+2}: Aparelho ou Colaborador não encontrado/disponível. Pulando registo.")
                                    erros += 1; s.rollback(); continue
                                
                                q_hist = text("INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, colaborador_snapshot) VALUES (:data, :apid, :cid, :sid, :loc, :obs, :snap)")
                                s.execute(q_hist, {"data": datetime.now(), "apid": aparelho_id, "cid": colaborador_id, "sid": status_em_uso_id, "loc": row['localizacao'], "obs": row['observacoes'], "snap": nome_colaborador_snapshot})
                                
                                q_update = text("UPDATE aparelhos SET status_id = :sid WHERE id = :apid")
                                s.execute(q_update, {"sid": status_em_uso_id, "apid": aparelho_id})
                                s.commit()
                                sucesso += 1
                            except Exception as e:
                                s.rollback()
                                st.error(f"Linha {index+2}: Erro inesperado - {e}. Pulando registo.")
                                erros += 1
                    st.success(f"Importação concluída! {sucesso} movimentações registadas com sucesso.")
                    if erros > 0: st.error(f"{erros} registos continham erros.")
                    st.cache_data.clear()

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar a página de importação: {e}")
        st.info("Verifique se o banco de dados está inicializado na página '⚙️ Configurações'.")

elif option == "Exportar Relatórios":
    st.header("Exportar Relatórios Completos")
    st.write("Exporte os dados completos do sistema para uma planilha Excel (.xlsx).")

    conn = get_db_connection()

    def to_excel_single_sheet(df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Relatorio')
        processed_data = output.getvalue()
        return processed_data
    
    # --- NOVA FUNÇÃO PARA EXPORTAR COM SUMÁRIOS ---
    def to_excel_with_summaries(main_df, status_summary_df, setor_summary_df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Escreve o relatório principal
            main_df.to_excel(writer, index=False, sheet_name='Inventario_Completo')
            
            # Calcula a posição inicial para o primeiro sumário (2 colunas à direita do principal)
            start_col_status = main_df.shape[1] + 2
            status_summary_df.to_excel(writer, index=False, sheet_name='Inventario_Completo', startcol=start_col_status)

            # Calcula a posição para o segundo sumário (2 colunas à direita do primeiro sumário)
            start_col_setor = start_col_status + status_summary_df.shape[1] + 2
            setor_summary_df.to_excel(writer, index=False, sheet_name='Inventario_Completo', startcol=start_col_setor)
            
        processed_data = output.getvalue()
        return processed_data

    try:
        # Exportar Inventário Completo
        st.subheader("Inventário Geral de Aparelhos")
        inventario_df = conn.query("""
            WITH UltimoResponsavel AS (
                SELECT
                    h.aparelho_id, h.colaborador_id, h.colaborador_snapshot,
                    ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
                FROM historico_movimentacoes h
            )
            SELECT 
                a.id, a.numero_serie, ma.nome_marca, mo.nome_modelo, s.nome_status,
                CASE WHEN s.nome_status = 'Em uso' THEN COALESCE(ur.colaborador_snapshot, c.nome_completo) ELSE NULL END as responsavel_atual,
                CASE WHEN s.nome_status = 'Em uso' THEN setor.nome_setor ELSE NULL END as setor_atual,
                a.valor, a.imei1, a.imei2, a.data_cadastro
            FROM aparelhos a
            LEFT JOIN modelos mo ON a.modelo_id = mo.id
            LEFT JOIN marcas ma ON mo.marca_id = ma.id
            LEFT JOIN status s ON a.status_id = s.id
            LEFT JOIN UltimoResponsavel ur ON a.id = ur.aparelho_id AND ur.rn = 1
            LEFT JOIN colaboradores c ON ur.colaborador_id = c.id
            LEFT JOIN setores setor ON c.setor_id = setor.id
            ORDER BY a.id;
        """)
        if not inventario_df.empty:
            # --- LÓGICA PARA CRIAR OS SUMÁRIOS ---
            # 1. Sumário por Status
            status_summary = inventario_df['nome_status'].value_counts().reset_index()
            status_summary.columns = ['nome_status', 'Aparelhos']

            # 2. Sumário por Setor (apenas para aparelhos 'Em uso')
            setor_summary = inventario_df[inventario_df['nome_status'] == 'Em uso']['setor_atual'].value_counts().reset_index()
            setor_summary.columns = ['setor_atual', 'Aparelhos']

            st.download_button(
                label="Baixar Relatório de Inventário com Sumários",
                data=to_excel_with_summaries(inventario_df, status_summary, setor_summary),
                file_name=f"relatorio_inventario_completo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("Não há dados de inventário para exportar.")

        # Exportar Histórico de Movimentações (sem alterações)
        st.subheader("Histórico Completo de Movimentações")
        historico_df = conn.query("""
            SELECT 
                h.id, h.data_movimentacao, a.numero_serie, mo.nome_modelo,
                h.colaborador_snapshot as colaborador, s.nome_status,
                h.localizacao_atual, h.observacoes
            FROM historico_movimentacoes h
            JOIN aparelhos a ON h.aparelho_id = a.id
            JOIN status s ON h.status_id = s.id
            LEFT JOIN modelos mo ON a.modelo_id = mo.id
            ORDER BY h.data_movimentacao DESC;
        """)
        if not historico_df.empty:
            st.download_button(
                label="Baixar Histórico de Movimentações",
                data=to_excel_single_sheet(historico_df),
                file_name=f"relatorio_movimentacoes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("Não há dados de movimentações para exportar.")

    except Exception as e:
        st.error(f"Ocorreu um erro ao gerar os relatórios para exportação: {e}")
        st.info("Verifique se o banco de dados está inicializado na página 'Configurações'.")



