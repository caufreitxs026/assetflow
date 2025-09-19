import streamlit as st
import pandas as pd
from datetime import datetime, date
from auth import show_login_form, logout
from sqlalchemy import text
from sqlalchemy.engine.base import Connection

# --- Verificação de Autenticação ---
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
    if st.button("Logout", key="mov_logout"):
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

# --- FUNÇÃO DE VALIDAÇÃO APRIMORADA (O "Guarda de Trânsito") ---
def validar_movimentacao(conn: Connection, aparelho_id: int, novo_status_nome: str):
    """
    Valida a transição de status de um aparelho, garantindo a integridade do fluxo.
    Verifica o status atual e permite apenas movimentações válidas.
    """
    try:
        # 1. Descobre de onde o aparelho está saindo (status atual)
        query_str = """
            SELECT s.nome_status 
            FROM aparelhos a
            JOIN status s ON a.status_id = s.id
            WHERE a.id = :ap_id
        """
        resultado = conn.query(query_str, params={"ap_id": aparelho_id})
        
        if resultado.empty:
            return False, f"Erro: Aparelho com ID {aparelho_id} não encontrado."

        status_atual = resultado.iloc[0]['nome_status']

        if status_atual == novo_status_nome:
            return False, f"AVISO: O aparelho já se encontra no status '{status_atual}'. Nenhuma movimentação foi registrada."

        # 2. REGRAS DE TRÂNSITO (State Machine)
        
        # REGRA PARA APARELHOS 'Em uso'
        if status_atual == 'Em uso':
            # Um aparelho 'Em uso' só pode ser devolvido, ir para manutenção ou ser baixado.
            destinos_permitidos = ['Disponível', 'Em manutenção', 'Baixado/Inutilizado']
            if novo_status_nome not in destinos_permitidos:
                return False, f"BLOQUEADO: Um aparelho 'Em uso' não pode ser movido para '{novo_status_nome}'. Rotas permitidas: Devolução (Disponível) ou Envio para Manutenção."

        # REGRA PARA APARELHOS 'Em manutenção'
        elif status_atual == 'Em manutenção':
            # Um aparelho 'Em manutenção' só pode voltar ao estoque ou ser baixado. NUNCA direto para um colaborador.
            destinos_permitidos = ['Disponível', 'Baixado/Inutilizado']
            if novo_status_nome not in destinos_permitidos:
                return False, f"BLOQUEADO: Um aparelho 'Em manutenção' não pode ser vinculado a um colaborador. Primeiro, mova-o para 'Disponível'."
        
        # Se nenhuma regra de bloqueio foi acionada, a movimentação é válida.
        return True, "Movimentação Válida."

    except Exception as e:
        st.error(f"Ocorreu um erro crítico na validação: {e}")
        return False, "Erro de sistema ao validar o aparelho."


@st.cache_data(ttl=30)
def carregar_dados_para_selects():
    """Carrega aparelhos, colaboradores ATIVOS e status para as caixas de seleção."""
    conn = get_db_connection()
    aparelhos_df = conn.query("""
        SELECT a.id, a.numero_serie, mo.nome_modelo, ma.nome_marca, s.nome_status
        FROM aparelhos a
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        JOIN status s ON a.status_id = s.id
        WHERE s.nome_status != 'Baixado/Inutilizado'
        ORDER BY ma.nome_marca, mo.nome_modelo, a.numero_serie
    """)
    colaboradores_df = conn.query("SELECT id, nome_completo FROM colaboradores WHERE status = 'Ativo' ORDER BY nome_completo")
    status_df = conn.query("SELECT id, nome_status FROM status ORDER BY nome_status")
    return aparelhos_df.to_dict('records'), colaboradores_df.to_dict('records'), status_df.to_dict('records')

def registar_movimentacao(aparelho_id, colaborador_id, colaborador_nome, novo_status_id, novo_status_nome, localizacao, observacoes):
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            
            id_colaborador_final = colaborador_id
            nome_colaborador_snapshot = colaborador_nome

            if novo_status_nome == "Em manutenção":
                query_last_user = text("""
                    SELECT colaborador_id, colaborador_snapshot FROM historico_movimentacoes 
                    WHERE aparelho_id = :ap_id AND (colaborador_id IS NOT NULL OR colaborador_snapshot IS NOT NULL)
                    ORDER BY data_movimentacao DESC LIMIT 1
                """)
                ultimo_colaborador = s.execute(query_last_user, {"ap_id": aparelho_id}).fetchone()
                if ultimo_colaborador:
                    id_colaborador_final = ultimo_colaborador[0]
                    nome_colaborador_snapshot = ultimo_colaborador[1]

            query_hist = text("""
                INSERT INTO historico_movimentacoes (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, colaborador_snapshot) 
                VALUES (:data, :ap_id, :col_id, :status_id, :loc, :obs, :col_snap)
            """)
            s.execute(query_hist, {
                "data": datetime.now(), "ap_id": aparelho_id, "col_id": id_colaborador_final, "status_id": novo_status_id,
                "loc": localizacao, "obs": observacoes, "col_snap": nome_colaborador_snapshot
            })

            s.execute(text("UPDATE aparelhos SET status_id = :status_id WHERE id = :ap_id"), 
                      {"status_id": novo_status_id, "ap_id": aparelho_id})
            
            if novo_status_nome == "Em manutenção":
                query_manut = text("""
                    INSERT INTO manutencoes (aparelho_id, colaborador_id_no_envio, data_envio, defeito_reportado, status_manutencao, colaborador_snapshot)
                    VALUES (:ap_id, :col_id, :data, :defeito, 'Em Andamento', :col_snap)
                """)
                s.execute(query_manut, {
                    "ap_id": aparelho_id, "col_id": id_colaborador_final, "data": date.today(), 
                    "defeito": observacoes, "col_snap": nome_colaborador_snapshot
                })

            s.commit()
            st.success("Movimentação registada com sucesso!")
            if novo_status_nome == "Em manutenção":
                st.info("Uma Ordem de Serviço preliminar foi aberta. Aceda à página 'Manutenções' para adicionar o fornecedor.")
            return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao registar a movimentação: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_historico_completo(status_filter=None, start_date=None, end_date=None, search_term=None):
    # ... (código da função sem alterações)
    conn = get_db_connection()
    query = """
        SELECT 
            h.id, h.data_movimentacao, a.numero_serie, mo.nome_modelo,
            h.colaborador_snapshot as colaborador,
            s.nome_status,
            h.localizacao_atual, h.observacoes
        FROM historico_movimentacoes h
        JOIN aparelhos a ON h.aparelho_id = a.id
        JOIN status s ON h.status_id = s.id
        LEFT JOIN modelos mo ON a.modelo_id = mo.id
    """
    params = {}
    where_clauses = []
    if status_filter and status_filter != "Todos":
        where_clauses.append("s.nome_status = :status")
        params['status'] = status_filter
    if start_date:
        where_clauses.append("CAST(h.data_movimentacao AS DATE) >= :start_date")
        params['start_date'] = start_date
    if end_date:
        where_clauses.append("CAST(h.data_movimentacao AS DATE) <= :end_date")
        params['end_date'] = end_date
    if search_term:
        search_like = f"%{search_term}%"
        where_clauses.append("(a.numero_serie ILIKE :search OR mo.nome_modelo ILIKE :search OR h.colaborador_snapshot ILIKE :search OR h.observacoes ILIKE :search)")
        params['search'] = search_like
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY h.data_movimentacao DESC"
    df = conn.query(query, params=params)
    return df

# --- UI ---
st.title("Gestão de Movimentações")
st.markdown("---")

try:
    aparelhos_list, colaboradores_list, status_list = carregar_dados_para_selects()

    option = st.radio(
        "Selecione a operação:",
        ("Registar Nova Movimentação", "Consultar Histórico"),
        horizontal=True,
        label_visibility="collapsed",
        key="movimentacoes_tab_selector"
    )
    st.markdown("---")

    if option == "Registar Nova Movimentação":
        with st.form("form_movimentacao", clear_on_submit=False): # Alterado para False para manter os campos em caso de erro
            st.subheader("Formulário de Movimentação")
            # Exibe o status atual do lado do aparelho
            aparelhos_dict = {f"{ap['nome_marca']} {ap['nome_modelo']} (S/N: {ap['numero_serie']}) — Status: {ap['nome_status']}": ap['id'] for ap in aparelhos_list}
            aparelho_selecionado_str = st.selectbox("Selecione o Aparelho*", options=aparelhos_dict.keys(), index=None, placeholder="Selecione...")
            
            colaboradores_dict = {col['nome_completo']: col['id'] for col in colaboradores_list}
            opcoes_colaborador_com_nenhum = {"Nenhum": None}
            opcoes_colaborador_com_nenhum.update(colaboradores_dict)
            
            colaborador_selecionado_str = st.selectbox("Atribuir ao Colaborador", options=opcoes_colaborador_com_nenhum.keys(), index=0)
            
            status_dict = {s['nome_status']: s['id'] for s in status_list}
            novo_status_str = st.selectbox("Novo Status do Aparelho*", options=status_dict.keys(), placeholder="Selecione...", index=None)
            nova_localizacao = st.text_input("Nova Localização", placeholder="Ex: Mesa do colaborador, Assistência Técnica XYZ")
            observacoes = st.text_area("Observações", placeholder="Ex: Devolução com tela trincada, Envio para troca de bateria.")

            submitted = st.form_submit_button("Registar Movimentação", use_container_width=True, type="primary")
            if submitted:
                if not aparelho_selecionado_str or not novo_status_str:
                    st.error("Aparelho e Novo Status são campos obrigatórios.")
                else:
                    aparelho_id = aparelhos_dict[aparelho_selecionado_str]
                    
                    # --- CHAMANDO O "Guarda de Trânsito" ANTES DE PROSSEGUIR ---
                    conn = get_db_connection()
                    is_valido, mensagem_validacao = validar_movimentacao(conn, aparelho_id, novo_status_str)

                    if not is_valido:
                        st.error(mensagem_validacao)
                        st.warning("A operação foi cancelada para manter a integridade do sistema.")
                    else:
                        # Se a validação passou, continua com a lógica de registro
                        colaborador_id = opcoes_colaborador_com_nenhum[colaborador_selecionado_str]
                        colaborador_nome = colaborador_selecionado_str if colaborador_selecionado_str != "Nenhum" else None
                        novo_status_id = status_dict[novo_status_str]
                        
                        if registar_movimentacao(aparelho_id, colaborador_id, colaborador_nome, novo_status_id, novo_status_str, nova_localizacao, observacoes):
                            st.cache_data.clear()
                            st.rerun()

    elif option == "Consultar Histórico":
        st.subheader("Histórico de Movimentações")
        
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            search_term = st.text_input("Pesquisar por N/S, Modelo, Colaborador ou Obs:")
            status_options = ["Todos"] + [s['nome_status'] for s in status_list]
            status_filtro = st.selectbox("Filtrar por Status:", status_options)
        with col_filtro2:
            data_inicio = st.date_input("Período de:", value=None, format="DD/MM/YYYY")
            data_fim = st.date_input("Até:", value=None, format="DD/MM/YYYY")

        historico_df = carregar_historico_completo(status_filter=status_filtro, start_date=data_inicio, end_date=data_fim, search_term=search_term)
        
        st.dataframe(historico_df, use_container_width=True, hide_index=True, column_config={
            "data_movimentacao": st.column_config.DatetimeColumn("Data e Hora", format="DD/MM/YYYY HH:mm"),
            "numero_serie": "N/S do Aparelho", "nome_modelo": "Modelo", "colaborador": "Colaborador",
            "nome_status": "Status Registado", "localizacao_atual": "Localização", "observacoes": "Observações"
        })

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")

