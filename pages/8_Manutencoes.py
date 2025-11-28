import streamlit as st
import pandas as pd
from datetime import date, datetime
from auth import show_login_form, logout
from sqlalchemy import text, exc
import traceback
import numpy as np
# Importamos as funções de e-mail
from email_utils import enviar_email, montar_layout_base

# --- Autenticação ---
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
    if st.button("Logout", key="manutencoes_logout"):
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
def carregar_dados_para_selects_manutencao():
    conn = get_db_connection()
    # Aparelhos que não estão em manutenção ou baixados
    aparelhos_df = conn.query("""
        WITH UltimoHistorico AS (
            SELECT
                aparelho_id, colaborador_id, colaborador_snapshot,
                ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
            FROM historico_movimentacoes
        )
        SELECT
            a.id, a.numero_serie, mo.nome_modelo, ma.nome_marca,
            COALESCE(uh.colaborador_snapshot, c.nome_completo) as ultimo_colaborador
        FROM aparelhos a
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN UltimoHistorico uh ON a.id = uh.aparelho_id AND uh.rn = 1
        LEFT JOIN colaboradores c ON uh.colaborador_id = c.id
        WHERE a.status_id NOT IN (
            SELECT id FROM status WHERE nome_status IN ('Em manutenção', 'Baixado/Inutilizado')
        )
        ORDER BY ma.nome_marca, mo.nome_modelo;
    """)
    # Colaboradores para o filtro do histórico
    colaboradores_df = conn.query("SELECT DISTINCT colaborador_snapshot FROM manutencoes WHERE colaborador_snapshot IS NOT NULL ORDER BY colaborador_snapshot;")
    # Status de manutenção para o filtro do histórico
    status_manutencao_df = conn.query("SELECT DISTINCT status_manutencao FROM manutencoes ORDER BY status_manutencao;")
    # Responsabilidade de Custo para o filtro do histórico
    responsabilidade_df = conn.query("SELECT DISTINCT responsabilidade_custo FROM manutencoes WHERE responsabilidade_custo IS NOT NULL ORDER BY responsabilidade_custo;")
    
    return (
        aparelhos_df.to_dict('records'), 
        ["Todos"] + colaboradores_df['colaborador_snapshot'].tolist(),
        ["Todos"] + status_manutencao_df['status_manutencao'].tolist(),
        ["Todos"] + responsabilidade_df['responsabilidade_custo'].tolist()
    )

def abrir_ordem_servico(aparelho_id, fornecedor, defeito):
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            query_colab = text("""
                SELECT colaborador_id, colaborador_snapshot FROM historico_movimentacoes 
                WHERE aparelho_id = :ap_id AND (colaborador_id IS NOT NULL OR colaborador_snapshot IS NOT NULL) 
                ORDER BY data_movimentacao DESC LIMIT 1
            """)
            result_colab = s.execute(query_colab, {"ap_id": aparelho_id}).fetchone()
            ultimo_colaborador_id = result_colab[0] if result_colab else None
            ultimo_colaborador_snapshot = result_colab[1] if result_colab else "N/A"

            status_manutencao_id = s.execute(text("SELECT id FROM status WHERE nome_status = 'Em manutenção'")).scalar_one()

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

            query_insert_hist = text("""
                INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, colaborador_snapshot)
                VALUES (:data, :ap_id, :col_id, :status_id, :loc, :obs, :col_snap)
            """)
            s.execute(query_insert_hist, {
                "data": datetime.now(), "ap_id": aparelho_id, "col_id": ultimo_colaborador_id, 
                "status_id": status_manutencao_id, "loc": f"Assistência: {fornecedor}", "obs": f"Defeito: {defeito}",
                "col_snap": ultimo_colaborador_snapshot
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
        df[col] = df[col].fillna('')
    return df

def fechar_ordem_servico(manutencao_id, solucao, custo, novo_status_nome, responsabilidade_custo):
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            query_check = text("SELECT aparelho_id, colaborador_snapshot FROM manutencoes WHERE id = :id AND status_manutencao = 'Em Andamento'")
            manut_result = s.execute(query_check, {"id": manutencao_id}).fetchone()
            
            if not manut_result:
                st.error(f"O.S. Nº {manutencao_id} não foi encontrada ou já foi fechada. Por favor, atualize a página.")
                s.rollback()
                return False

            aparelho_id, colab_snapshot = manut_result
            
            novo_status_id_result = s.execute(text("SELECT id FROM status WHERE nome_status = :nome"), {"nome": novo_status_nome}).scalar()
            if novo_status_id_result is None:
                st.error(f"Status '{novo_status_nome}' não encontrado no sistema.")
                s.rollback()
                return False
            novo_status_id = novo_status_id_result
            
            status_manutencao = 'Concluída' if novo_status_nome == 'Em estoque' else 'Baixado/Inutilizado'
            
            query_update_manut = text("""
                UPDATE manutencoes 
                SET data_retorno = :data, solucao_aplicada = :solucao, custo_reparo = :custo, 
                    status_manutencao = :status_m, responsabilidade_custo = :resp_custo
                WHERE id = :id
            """)
            s.execute(query_update_manut, {
                "data": date.today(), "solucao": solucao, "custo": custo, 
                "status_m": status_manutencao, "id": manutencao_id,
                "resp_custo": responsabilidade_custo
            })
            
            s.execute(text("UPDATE aparelhos SET status_id = :status_id WHERE id = :ap_id"), 
                      {"status_id": novo_status_id, "ap_id": aparelho_id})
            
            obs_historico = (
                f"Retorno da manutenção. Solução: {solucao}. "
                f"Custo: R${custo or 0:.2f} ({responsabilidade_custo})."
            )
            
            query_insert_hist = text("""
                INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, colaborador_snapshot)
                VALUES (:data, :ap_id, NULL, :status_id, 'Estoque Interno', :obs, :col_snap)
            """)
            s.execute(query_insert_hist, {
                "data": datetime.now(), "ap_id": aparelho_id, "status_id": novo_status_id,
                "obs": obs_historico,
                "col_snap": colab_snapshot
            })
            
            s.commit()
            st.success("Ordem de Serviço fechada com sucesso!")
            return True
    except exc.IntegrityError as e:
        st.error("Erro de Duplicidade no Banco de Dados. Tente sincronizar os IDs na página de 'Configurações'.")
        st.error(f"Detalhe técnico: {e}")
        return False
    except Exception as e:
        st.error(f"Erro ao fechar a Ordem de Serviço: {e}")
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
def carregar_historico_manutencoes(status_filter=None, colaborador_filter=None, responsabilidade_filter=None, start_date=None, end_date=None, start_date_retorno=None, end_date_retorno=None):
    conn = get_db_connection()
    # Query ajustada para trazer Marca e Setor para o relatório completo
    query = """
        SELECT 
            m.id, a.numero_serie, ma.nome_marca, mo.nome_modelo, 
            m.colaborador_snapshot as colaborador,
            s.nome_setor as setor,
            m.data_envio, m.data_retorno, m.custo_reparo, m.responsabilidade_custo, 
            m.status_manutencao, m.fornecedor,
            m.defeito_reportado, m.solucao_aplicada
        FROM manutencoes m
        JOIN aparelhos a ON m.aparelho_id = a.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN colaboradores c ON m.colaborador_id_no_envio = c.id
        LEFT JOIN setores s ON c.setor_id = s.id
    """
    params = {}
    where_clauses = []
    if status_filter and status_filter != "Todos":
        where_clauses.append("m.status_manutencao = :status")
        params['status'] = status_filter
    if colaborador_filter and colaborador_filter != "Todos":
        where_clauses.append("m.colaborador_snapshot = :colab")
        params['colab'] = colaborador_filter
    if responsabilidade_filter and responsabilidade_filter != "Todos":
        where_clauses.append("m.responsabilidade_custo = :resp")
        params['resp'] = responsabilidade_filter
    if start_date:
        where_clauses.append("CAST(m.data_envio AS DATE) >= :start_date")
        params['start_date'] = start_date
    if end_date:
        where_clauses.append("CAST(m.data_envio AS DATE) <= :end_date")
        params['end_date'] = end_date
    if start_date_retorno:
        where_clauses.append("CAST(m.data_retorno AS DATE) >= :start_date_retorno")
        params['start_date_retorno'] = start_date_retorno
    if end_date_retorno:
        where_clauses.append("CAST(m.data_retorno AS DATE) <= :end_date_retorno")
        params['end_date_retorno'] = end_date_retorno
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY m.data_envio DESC"
    df = conn.query(query, params=params)
    return df

# --- FUNÇÃO: Gerar HTML de Manutenção para E-mail ---
def gerar_conteudo_email_historico_manutencao(df_selecionado):
    # Calcula o total
    total_custo = df_selecionado['custo_reparo'].fillna(0).sum()
    
    linhas_html = ""
    for index, row in df_selecionado.iterrows():
        # Formata datas e valores
        data_ida = row['data_envio'].strftime('%d/%m/%Y') if pd.notnull(row['data_envio']) else "-"
        data_volta = row['data_retorno'].strftime('%d/%m/%Y') if pd.notnull(row['data_retorno']) else "-"
        valor = f"R$ {float(row['custo_reparo']):.2f}" if pd.notnull(row['custo_reparo']) else "R$ 0.00"
        
        # Formata strings compostas
        aparelho = f"{row['nome_marca']} {row['nome_modelo']} (S/N: {row['numero_serie']})"
        # Se não houver setor, assume N/A
        setor_str = row['setor'] if row['setor'] else 'N/A'
        responsavel = f"{setor_str} - {row['colaborador']}"
        
        # Constrói a linha da tabela
        linhas_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{row['id']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{aparelho}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{responsavel}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{row['fornecedor'] or '-'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{data_ida}<br/>{data_volta}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{row['defeito_reportado']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{row['solucao_aplicada'] or '-'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px;">{row['responsabilidade_custo'] or '-'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eeeeee; font-family: Arial; font-size: 11px; white-space: nowrap;">{valor}</td>
        </tr>
        """
    
    # Miolo da tabela HTML (sem as tags <html>, <body>, pois o montar_layout_base faz isso)
    miolo_tabela = f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <thead>
            <tr bgcolor="#f2f2f2">
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">O.S.</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Aparelho</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Setor - Responsável</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Prestador</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Datas</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Defeito</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Solução</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Resp. Custo</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #003366; font-family: Arial; font-size: 11px; color: #003366;">Valor</th>
            </tr>
        </thead>
        <tbody>
            {linhas_html}
        </tbody>
        <tfoot>
            <tr>
                <td colspan="8" align="right" style="padding: 10px; font-weight: bold; font-family: Arial; font-size: 12px;">TOTAL:</td>
                <td style="padding: 10px; font-weight: bold; font-family: Arial; font-size: 12px; white-space: nowrap;">R$ {total_custo:.2f}</td>
            </tr>
        </tfoot>
    </table>
    """
    
    # Envolve o miolo no layout padrão (cabeçalho preto, rodapé, etc.)
    miolo_completo = f"""
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; padding-bottom: 15px;">
            Relatório de Manutenções Selecionadas
        </td>
    </tr>
    <tr>
        <td>
            {miolo_tabela}
        </td>
    </tr>
    """
    
    return montar_layout_base("Relatório de Manutenções", miolo_completo)

# --- UI ---
st.title("Fluxo de Manutenção")
st.markdown("---")

try:
    aparelhos_list, colaboradores_options, status_manutencao_options, responsabilidade_options = carregar_dados_para_selects_manutencao()

    option = st.radio(
        "Selecione a operação:",
        ("Abrir Ordem de Serviço", "Acompanhar e Fechar O.S.", "Histórico de Manutenções"),
        horizontal=True,
        label_visibility="collapsed",
        key="manutencoes_tab_selector"
    )
    st.markdown("---")

    if option == "Abrir Ordem de Serviço":
        st.subheader("1. Enviar Aparelho para Manutenção")
        aparelhos_dict = {f"{ap['nome_marca']} {ap['nome_modelo']} (S/N: {ap['numero_serie']}) - [Com: {ap['ultimo_colaborador'] or 'Ninguém'}]": ap['id'] for ap in aparelhos_list}
        if not aparelhos_dict:
            st.info("Nenhum aparelho disponível para enviar para manutenção.")
        else:
            with st.form("form_nova_os", clear_on_submit=True):
                aparelho_selecionado_str = st.selectbox(
                    "Selecione o Aparelho*", options=aparelhos_dict.keys(),
                    index=None, placeholder="Selecione...", help="Clique na lista e comece a digitar para pesquisar."
                )
                fornecedor = st.text_input("Fornecedor / Assistência Técnica*")
                defeito = st.text_area("Defeito Reportado*")
                if st.form_submit_button("Abrir Ordem de Serviço", use_container_width=True, type="primary"):
                    if not all([aparelho_selecionado_str, fornecedor, defeito]):
                        st.error("Todos os campos são obrigatórios.")
                    else:
                        aparelho_id = aparelhos_dict[aparelho_selecionado_str]
                        if abrir_ordem_servico(aparelho_id, fornecedor, defeito):
                            st.cache_data.clear()
                            st.rerun()

    elif option == "Acompanhar e Fechar O.S.":
        st.subheader("2. Ordens de Serviço em Andamento")
        with st.expander("Ver e Editar Ordens de Serviço em Andamento", expanded=True):
            manutencoes_df = carregar_manutencoes_em_andamento()
            if manutencoes_df.empty:
                st.info("Nenhuma ordem de serviço em andamento no momento.")
            else:
                session_state_key = "original_manutencoes_df"
                if session_state_key not in st.session_state:
                    st.session_state[session_state_key] = manutencoes_df.copy()
                
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
                    hide_index=True, key="manutencoes_editor", use_container_width=True
                )
                
                if st.button("Salvar Alterações nas O.S.", use_container_width=True, key="save_os_changes"):
                    changes_made = False
                    original_df = st.session_state[session_state_key]
                    original_df_indexed = original_df.set_index('id')
                    edited_df_indexed = edited_df.set_index('id')
                    common_ids = original_df_indexed.index.intersection(edited_df_indexed.index)

                    for manut_id in common_ids:
                        original_row = original_df_indexed.loc[manut_id]
                        edited_row = edited_df_indexed.loc[manut_id]
                        if not original_row.equals(edited_row):
                            if atualizar_manutencao(manut_id, edited_row['fornecedor'], edited_row['defeito_reportado']):
                                st.toast(f"O.S. Nº {manut_id} atualizada!", icon="✅")
                                changes_made = True
                    
                    if changes_made:
                        st.cache_data.clear()
                        del st.session_state[session_state_key]
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração foi detetada.")

        st.markdown("---")
        st.subheader("3. Fechar Ordem de Serviço")
        
        manutencoes_em_andamento_df = carregar_manutencoes_em_andamento()
        if manutencoes_em_andamento_df.empty:
            st.info("Nenhuma O.S. para fechar.")
        else:
            with st.form("form_fechar_os", clear_on_submit=True):
                os_dict = {f"O.S. Nº {row['id']} - {row['nome_modelo']} (S/N: {row['numero_serie']})": row['id'] for index, row in manutencoes_em_andamento_df.iterrows()}
                os_selecionada_str = st.selectbox(
                    "Selecione a Ordem de Serviço para fechar*", options=os_dict.keys(),
                    index=None, placeholder="Selecione...", help="Clique na lista e comece a digitar para pesquisar."
                )
                solucao = st.text_area("Solução Aplicada / Laudo Técnico*")
                
                col_custo1, col_custo2 = st.columns(2)
                with col_custo1:
                    custo = st.number_input("Custo do Reparo (R$)", min_value=0.0, value=0.0, format="%.2f")
                with col_custo2:
                    responsabilidade = st.selectbox("Responsabilidade do Custo*", ["Empresa", "Colaborador", "Empresa / Colaborador"])

                novo_status_final = st.selectbox("Status Final do Aparelho*", ["Em estoque", "Baixado/Inutilizado"])

                if st.form_submit_button("Fechar Ordem de Serviço", use_container_width=True, type="primary"):
                    if not all([os_selecionada_str, solucao]):
                        st.error("Ordem de Serviço e Solução são campos obrigatórios.")
                    else:
                        os_id = os_dict[os_selecionada_str]
                        if fechar_ordem_servico(os_id, solucao, custo, novo_status_final, responsabilidade):
                            st.cache_data.clear()
                            if 'original_manutencoes_df' in st.session_state:
                                del st.session_state.original_manutencoes_df
                            st.rerun()

    elif option == "Histórico de Manutenções":
        st.subheader("Histórico Completo de Manutenções")

        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
        with col_filtro1:
            status_filtro = st.selectbox("Filtrar por Status da O.S.:", options=status_manutencao_options)
        with col_filtro2:
            colaborador_filtro = st.selectbox("Filtrar por Colaborador:", options=colaboradores_options)
        with col_filtro3:
            responsabilidade_filtro = st.selectbox("Filtrar por Respons. Custo:", options=responsabilidade_options)

        st.markdown("---") 

        col_data1, col_data2 = st.columns(2)
        with col_data1:
            st.markdown("###### Período de Envio")
            data_inicio_envio = st.date_input("De:", value=None, format="DD/MM/YYYY", key="envio_de")
            data_fim_envio = st.date_input("Até:", value=None, format="DD/MM/YYYY", key="envio_ate")
        with col_data2:
            st.markdown("###### Período de Retorno")
            data_inicio_retorno = st.date_input("De:", value=None, format="DD/MM/YYYY", key="retorno_de")
            data_fim_retorno = st.date_input("Até:", value=None, format="DD/MM/YYYY", key="retorno_ate")

        historico_df = carregar_historico_manutencoes(
            status_filter=status_filtro, 
            colaborador_filter=colaborador_filtro,
            responsabilidade_filter=responsabilidade_filtro,
            start_date=data_inicio_envio,
            end_date=data_fim_envio,
            start_date_retorno=data_inicio_retorno,
            end_date_retorno=data_fim_retorno
        )
        
        # Adicionar coluna de Seleção para o E-mail
        historico_df['Selecionar'] = False
        
        # Configuração da tabela interativa
        column_config = {
             "Selecionar": st.column_config.CheckboxColumn("Selecionar", help="Selecione para enviar relatório por e-mail"),
             "id": "O.S. Nº",
             "numero_serie": "N/S",
             "nome_modelo": "Modelo",
             "nome_marca": "Marca",
             "colaborador": "Colaborador no Envio",
             "setor": "Setor",
             "data_envio": st.column_config.DateColumn("Data Envio", format="DD/MM/YYYY"),
             "data_retorno": st.column_config.DateColumn("Data Retorno", format="DD/MM/YYYY"),
             "custo_reparo": st.column_config.NumberColumn("Custo", format="R$ %.2f"),
             "responsabilidade_custo": "Respons. Custo",
             "status_manutencao": "Status O.S.",
             "fornecedor": "Prestador", # Renomeado para Prestador na UI
             "defeito_reportado": "Defeito Reportado",
             "solucao_aplicada": "Solução Aplicada"
        }
        
        # Ordem das colunas com 'Selecionar' primeiro
        cols = ['Selecionar', 'id', 'nome_marca', 'nome_modelo', 'numero_serie', 'colaborador', 'setor', 'fornecedor', 'defeito_reportado', 'solucao_aplicada', 'responsabilidade_custo', 'custo_reparo', 'status_manutencao', 'data_envio', 'data_retorno']
        
        edited_df = st.data_editor(
            historico_df,
            column_config=column_config,
            column_order=cols,
            hide_index=True,
            use_container_width=True,
            disabled=[c for c in historico_df.columns if c != 'Selecionar'] # Apenas checkboxes editáveis
        )

        # --- LÓGICA DE ENVIO DE E-MAIL ---
        selecionados = edited_df[edited_df['Selecionar']]
        
        if not selecionados.empty:
            st.markdown("---")
            with st.expander("Enviar Relatório por E-mail", expanded=True):
                st.write(f"**{len(selecionados)} registos selecionados.**")
                destinatarios_str = st.text_area("Destinatários (separados por vírgula):", placeholder="exemplo1@email.com, exemplo2@email.com")
                
                if st.button("Enviar Relatório Selecionado", type="primary"):
                    if destinatarios_str:
                        destinatarios_list = [email.strip() for email in destinatarios_str.split(',') if email.strip()]
                        if destinatarios_list:
                            with st.spinner("A gerar e enviar relatório..."):
                                html_email = gerar_conteudo_email_historico_manutencao(selecionados)
                                if enviar_email(destinatarios_list, "AssetFlow - Relatório de Manutenções", html_email, "Consulte a versão HTML para ver o relatório."):
                                    st.success("Relatório enviado com sucesso!")
                                else:
                                    st.error("Falha ao enviar e-mail.")
                        else:
                            st.warning("Insira e-mails válidos.")
                    else:
                        st.warning("Preencha o campo de destinatários.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de manutenções: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")
    traceback.print_exc()
