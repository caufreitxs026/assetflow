    import streamlit as st
    import pandas as pd
    from datetime import date, datetime
    from auth import show_login_form
    from sqlalchemy import text, exc
    import traceback
    import numpy as np
    
    # --- Autenticação ---
    if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
        st.switch_page("app.py")
    
    # --- Configuração de Layout (Header, Footer e CSS) ---
    st.markdown("""
    <style>
        /* Estilos da Logo */
        .logo-text { font-family: 'Courier New', monospace; font-size: 28px; font-weight: bold; padding-top: 20px; }
        .logo-asset { color: #003366; } .logo-flow { color: #E30613; }
        @media (prefers-color-scheme: dark) { .logo-asset { color: #FFFFFF; } .logo-flow { color: #FF4B4B; } }
        /* Estilos para o footer na barra lateral */
        .sidebar-footer { text-align: center; padding-top: 20px; padding-bottom: 20px; }
        .sidebar-footer a { margin-right: 15px; text-decoration: none; }
        .sidebar-footer img { width: 25px; height: 25px; filter: grayscale(1) opacity(0.5); transition: filter 0.3s; }
        .sidebar-footer img:hover { filter: grayscale(0) opacity(1); }
        @media (prefers-color-scheme: dark) { .sidebar-footer img { filter: grayscale(1) opacity(0.6) invert(1); } .sidebar-footer img:hover { filter: opacity(1) invert(1); } }
    </style>
    """, unsafe_allow_html=True)
    
    # --- Header ---
    st.markdown("""<div class="logo-text"><span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span></div>""", unsafe_allow_html=True)
    
    # --- Barra Lateral ---
    with st.sidebar:
        st.write(f"Bem-vindo, **{st.session_state['user_name']}**!")
        st.write(f"Cargo: **{st.session_state['user_role']}**")
        if st.button("Logout", key="manutencoes_logout"):
            from auth import logout
            logout()
        st.markdown("---")
        st.markdown(f"""
            <div class="sidebar-footer">
                <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg"></a>
                <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg"></a>
            </div>
            """, unsafe_allow_html=True)
    
    # --- Funções do DB ---
    def get_db_connection():
        return st.connection("supabase", type="sql")
    
    @st.cache_data(ttl=30)
    def carregar_aparelhos_para_manutencao():
        conn = get_db_connection()
        # --- LÓGICA ATUALIZADA ---
        # Busca também o snapshot do nome e o ID do último colaborador
        query = """
            WITH UltimoHistorico AS (
                SELECT
                    aparelho_id, colaborador_id, colaborador_snapshot,
                    ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
                FROM historico_movimentacoes
            )
            SELECT
                a.id, a.numero_serie, mo.nome_modelo, ma.nome_marca,
                uh.colaborador_snapshot as ultimo_colaborador,
                uh.colaborador_id as ultimo_colaborador_id
            FROM aparelhos a
            JOIN modelos mo ON a.modelo_id = mo.id
            JOIN marcas ma ON mo.marca_id = ma.id
            LEFT JOIN UltimoHistorico uh ON a.id = uh.aparelho_id AND uh.rn = 1
            WHERE a.status_id NOT IN (
                SELECT id FROM status WHERE nome_status IN ('Em manutenção', 'Baixado/Inutilizado')
            )
            ORDER BY ma.nome_marca, mo.nome_modelo;
        """
        df = conn.query(query)
        return df.to_dict('records')
    
    def abrir_ordem_servico(aparelho_id, ultimo_colaborador_id, ultimo_colaborador_snapshot, fornecedor, defeito):
        conn = get_db_connection()
        try:
            with conn.session as s:
                s.begin()
                
                status_manutencao_id = s.execute(text("SELECT id FROM status WHERE nome_status = 'Em manutenção'")).scalar_one()
    
                # --- LÓGICA ATUALIZADA ---
                # Insere o snapshot do nome na tabela de manutenções
                query_insert_manut = text("""
                    INSERT INTO manutencoes (aparelho_id, colaborador_id_no_envio, fornecedor, data_envio, defeito_reportado, status_manutencao, colaborador_snapshot)
                    VALUES (:ap_id, :col_id, :forn, :data, :defeito, 'Em Andamento', :col_snap)
                """)
                s.execute(query_insert_manut, {
                    "ap_id": aparelho_id, "col_id": ultimo_colaborador_id, "forn": fornecedor, 
                    "data": date.today(), "defeito": defeito, "col_snap": ultimo_colaborador_snapshot
                })
    
                s.execute(text("UPDATE aparelhos SET status_id = :status_id WHERE id = :ap_id"), 
                          {"status_id": status_manutencao_id, "ap_id": aparelho_id})
    
                # --- LÓGICA ATUALIZADA ---
                # Insere o snapshot também no histórico da movimentação
                query_insert_hist = text("""
                    INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, colaborador_snapshot)
                    VALUES (:data, :ap_id, :col_id, :status_id, :loc, :obs, :col_snap)
                """)
                s.execute(query_insert_hist, {
                    "data": datetime.now(), "ap_id": aparelho_id, "col_id": ultimo_colaborador_id, 
                    "status_id": status_manutencao_id, "loc": f"Assistência: {fornecedor}", 
                    "obs": f"Defeito: {defeito}", "col_snap": ultimo_colaborador_snapshot
                })
                
                s.commit()
                st.success("Ordem de Serviço aberta e aparelho enviado para manutenção!")
                return True
        except Exception as e:
            st.error(f"Erro ao abrir a Ordem de Serviço: {e}")
            return False
    
    @st.cache_data(ttl=30)
    def carregar_manutencoes_em_andamento(order_by="m.data_envio ASC"):
        conn = get_db_connection()
        query = f"""
            SELECT m.id, a.numero_serie, mo.nome_modelo, m.fornecedor, m.data_envio, m.defeito_reportado
            FROM manutencoes m
            JOIN aparelhos a ON m.aparelho_id = a.id
            JOIN modelos mo ON a.modelo_id = mo.id
            WHERE m.status_manutencao = 'Em Andamento'
            ORDER BY {order_by};
        """
        df = conn.query(query)
        for col in ['fornecedor', 'defeito_reportado']:
            if col in df.columns:
                df[col] = df[col].fillna('')
        return df
    
    def fechar_ordem_servico(manutencao_id, solucao, custo, novo_status_nome):
        conn = get_db_connection()
        try:
            with conn.session as s:
                s.begin()
                query_check = text("SELECT aparelho_id FROM manutencoes WHERE id = :id AND status_manutencao = 'Em Andamento'")
                aparelho_id_result = s.execute(query_check, {"id": manutencao_id}).fetchone()
                
                if not aparelho_id_result:
                    st.error(f"O.S. Nº {manutencao_id} não foi encontrada ou já foi fechada. Por favor, atualize a página.")
                    s.rollback()
                    return False
    
                aparelho_id = aparelho_id_result[0]
                
                novo_status_id = s.execute(text("SELECT id FROM status WHERE nome_status = :nome"), {"nome": novo_status_nome}).scalar_one()
                status_manutencao = 'Concluída' if novo_status_nome == 'Em estoque' else 'Sem Reparo'
                
                query_update_manut = text("""
                    UPDATE manutencoes 
                    SET data_retorno = :data, solucao_aplicada = :solucao, custo_reparo = :custo, status_manutencao = :status_m
                    WHERE id = :id
                """)
                s.execute(query_update_manut, {
                    "data": date.today(), "solucao": solucao, "custo": custo, 
                    "status_m": status_manutencao, "id": manutencao_id
                })
                
                s.execute(text("UPDATE aparelhos SET status_id = :status_id WHERE id = :ap_id"), 
                          {"status_id": novo_status_id, "ap_id": aparelho_id})
                
                # O snapshot fica NULL porque esta movimentação não está associada a uma pessoa
                query_insert_hist = text("""
                    INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, colaborador_snapshot)
                    VALUES (:data, :ap_id, NULL, :status_id, 'Estoque Interno', :obs, NULL)
                """)
                s.execute(query_insert_hist, {
                    "data": datetime.now(), "ap_id": aparelho_id, "status_id": novo_status_id,
                    "obs": f"Retorno da manutenção. Solução: {solucao}. Custo: R${custo or 0:.2f}"
                })
                
                s.commit()
                st.success("Ordem de Serviço fechada com sucesso!")
                return True
        except Exception as e:
            st.error(f"Erro ao fechar a Ordem de Serviço: {e}")
            st.code(traceback.format_exc())
            return False
    
    def atualizar_manutencao(manutencao_id, fornecedor, defeito):
        conn = get_db_connection()
        try:
            with conn.session as s:
                query = text("UPDATE manutencoes SET fornecedor = :forn, defeito_reportado = :defeito WHERE id = :id")
                s.execute(query, {"forn": fornecedor, "defeito": defeito, "id": manutencao_id})
                s.commit()
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar manutenção: {e}")
            return False
    
    @st.cache_data(ttl=30)
    def carregar_historico_manutencoes(status_filter=None, colaborador_filter=None):
        conn = get_db_connection()
        # --- LÓGICA ATUALIZADA ---
        # Busca o nome a partir do snapshot
        query = """
            SELECT 
                m.id, a.numero_serie, mo.nome_modelo, m.colaborador_snapshot as colaborador,
                m.data_envio, m.data_retorno, m.custo_reparo, m.status_manutencao, m.fornecedor,
                m.defeito_reportado, m.solucao_aplicada
            FROM manutencoes m
            JOIN aparelhos a ON m.aparelho_id = a.id
            JOIN modelos mo ON a.modelo_id = mo.id
        """
        params = {}
        where_clauses = []
    
        if status_filter and status_filter != "Todos":
            where_clauses.append("m.status_manutencao = :status")
            params['status'] = status_filter
        
        if colaborador_filter and colaborador_filter != "Todos":
            where_clauses.append("m.colaborador_snapshot = :colab") # <-- Filtra pelo snapshot
            params['colab'] = colaborador_filter
    
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " ORDER BY m.data_envio DESC"
        
        df = conn.query(query, params=params)
        return df
    
    @st.cache_data(ttl=60)
    def carregar_colaboradores_nomes():
        conn = get_db_connection()
        df = conn.query("SELECT DISTINCT colaborador_snapshot FROM manutencoes WHERE colaborador_snapshot IS NOT NULL ORDER BY colaborador_snapshot;")
        return ["Todos"] + df['colaborador_snapshot'].tolist()
    
    # --- UI ---
    st.title("Fluxo de Manutenção")
    st.markdown("---")
    
    try:
        tab1, tab2, tab3 = st.tabs(["Abrir Ordem de Serviço", "Acompanhar e Fechar O.S.", "Histórico de Manutenções"])
    
        with tab1:
            st.subheader("1. Enviar Aparelho para Manutenção")
            aparelhos_list = carregar_aparelhos_para_manutencao()
            
            aparelhos_dict = {
                f"{ap['nome_marca']} {ap['nome_modelo']} (S/N: {ap['numero_serie']}) - [Com: {ap.get('ultimo_colaborador') or 'Ninguém'}]": ap
                for ap in aparelhos_list
            }
    
            if not aparelhos_dict:
                st.info("Nenhum aparelho disponível para enviar para manutenção.")
            else:
                with st.form("form_nova_os", clear_on_submit=True):
                    aparelho_selecionado_str = st.selectbox(
                        "Selecione o Aparelho*",
                        options=aparelhos_dict.keys(),
                        index=None, placeholder="Selecione...",
                        help="Clique na lista e comece a digitar para pesquisar."
                    )
                    fornecedor = st.text_input("Fornecedor / Assistência Técnica*")
                    defeito = st.text_area("Defeito Reportado*")
                    if st.form_submit_button("Abrir Ordem de Serviço", use_container_width=True):
                        if not all([aparelho_selecionado_str, fornecedor, defeito]):
                            st.error("Todos os campos são obrigatórios.")
                        else:
                            aparelho_data = aparelhos_dict[aparelho_selecionado_str]
                            aparelho_id = aparelho_data['id']
                            ultimo_colaborador_id = aparelho_data.get('ultimo_colaborador_id')
                            ultimo_colaborador_snapshot = aparelho_data.get('ultimo_colaborador')
                            if abrir_ordem_servico(aparelho_id, ultimo_colaborador_id, ultimo_colaborador_snapshot, fornecedor, defeito):
                                st.cache_data.clear()
                                st.session_state.pop('original_manutencoes_df', None)
                                st.rerun()
    
        with tab2:
            st.subheader("2. Ordens de Serviço em Andamento")
    
            with st.expander("Ver e Editar Ordens de Serviço em Andamento", expanded=True):
                manutencoes_df = carregar_manutencoes_em_andamento()
                if manutencoes_df.empty:
                    st.info("Nenhuma ordem de serviço em andamento no momento.")
                else:
                    if 'original_manutencoes_df' not in st.session_state:
                        st.session_state.original_manutencoes_df = manutencoes_df.copy()
    
                    edited_df = st.data_editor(
                        manutencoes_df,
                        column_config={
                            "id": st.column_config.NumberColumn("O.S. Nº", disabled=True),
                            "numero_serie": st.column_config.TextColumn("N/S", disabled=True),
                            "nome_modelo": st.column_config.TextColumn("Modelo", disabled=True),
                            "fornecedor": st.column_config.TextColumn("Fornecedor", required=True),
                            "data_envio": st.column_config.DateColumn("Data Envio", format="DD/MM/YYYY", disabled=True),
                            "defeito_reportado": st.column_config.TextColumn("Defeito Reportado", required=True),
                        },
                        hide_index=True, key="manutencoes_editor"
                    )
                    
                    if st.button("Salvar Alterações nas O.S.", use_container_width=True, key="save_os_changes"):
                        changes_made = False
                        original_df = st.session_state.original_manutencoes_df
    
                        original_df_indexed = original_df.set_index('id')
                        edited_df_indexed = edited_df.set_index('id')
                        common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)
    
                        for manut_id in common_ids:
                            original_row = original_df_indexed.loc[manut_id]
                            edited_row = edited_df_indexed.loc[manut_id]
                            
                            if str(original_row['fornecedor']) != str(edited_row['fornecedor']) or str(original_row['defeito_reportado']) != str(edited_row['defeito_reportado']):
                                if atualizar_manutencao(manut_id, edited_row['fornecedor'], edited_row['defeito_reportado']):
                                    st.toast(f"O.S. Nº {manut_id} atualizada!", icon="✅")
                                    changes_made = True
                        
                        if changes_made:
                            st.cache_data.clear()
                            st.session_state.pop('original_manutencoes_df', None)
                            st.rerun()
                        else:
                            st.info("Nenhuma alteração foi detetada.")
    
            st.markdown("---")
            st.subheader("3. Fechar Ordem de Serviço")
            
            # Recarrega os dados aqui para garantir que o selectbox está atualizado
            manutencoes_em_andamento_df = carregar_manutencoes_em_andamento()
    
            if manutencoes_em_andamento_df.empty:
                st.info("Nenhuma O.S. para fechar.")
            else:
                with st.form("form_fechar_os", clear_on_submit=True):
                    os_dict = {f"O.S. Nº {row['id']} - {row['nome_modelo']} (S/N: {row['numero_serie']})": row['id'] for index, row in manutencoes_em_andamento_df.iterrows()}
                    
                    os_selecionada_str = st.selectbox(
                        "Selecione a Ordem de Serviço para fechar*",
                        options=os_dict.keys(),
                        index=None, placeholder="Selecione...",
                        help="Clique na lista e comece a digitar para pesquisar."
                    )
                    solucao = st.text_area("Solução Aplicada / Laudo Técnico*")
                    custo = st.number_input("Custo do Reparo (R$)", min_value=0.0, value=0.0, format="%.2f")
                    novo_status_final = st.selectbox("Status Final do Aparelho*", ["Em estoque", "Baixado/Inutilizado"])
    
                    if st.form_submit_button("Fechar Ordem de Serviço", use_container_width=True):
                        if not all([os_selecionada_str, solucao]):
                            st.error("Ordem de Serviço e Solução são campos obrigatórios.")
                        else:
                            os_id = os_dict[os_selecionada_str]
                            if fechar_ordem_servico(os_id, solucao, custo, novo_status_final):
                                st.cache_data.clear()
                                st.session_state.pop('original_manutencoes_df', None)
                                st.rerun()
    
        with tab3:
            st.subheader("Histórico Completo de Manutenções")
    
            colaboradores_options = carregar_colaboradores_nomes()
            status_manutencao_df = get_db_connection().query("SELECT DISTINCT status_manutencao FROM manutencoes;")
            status_manutencao_options = ["Todos"] + status_manutencao_df['status_manutencao'].tolist()
            
            col_filtro1, col_filtro2 = st.columns(2)
            with col_filtro1:
                status_filtro = st.selectbox("Filtrar por Status da O.S.:", options=status_manutencao_options)
            with col_filtro2:
                colaborador_filtro = st.selectbox("Filtrar por Colaborador:", options=colaboradores_options)
    
            historico_df = carregar_historico_manutencoes(status_filter=status_filtro, colaborador_filter=colaborador_filtro)
            st.dataframe(historico_df, hide_index=True, use_container_width=True,
                          column_config={
                              "id": "O.S. Nº",
                              "data_envio": st.column_config.DateColumn("Data Envio", format="DD/MM/YYYY"),
                              "data_retorno": st.column_config.DateColumn("Data Retorno", format="DD/MM/YYYY"),
                              "custo_reparo": st.column_config.NumberColumn("Custo", format="R$ %.2f")
                          })
    
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar a página de manutenções: {e}")
        st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")
    

