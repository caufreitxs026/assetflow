import streamlit as st
import pandas as pd
import plotly.express as px
from auth import show_login_form, logout
from datetime import datetime, timedelta

# --- Configuração inicial da página e do estado da sessão ---
st.set_page_config(page_title="AssetFlow", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- Lógica de Autenticação ---
if not st.session_state['logged_in']:
    show_login_form()
else:
    # --- Se logado, mostra a aplicação completa ---

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
        if st.button("Logout", key="app_logout"):
            logout()
        st.markdown("---")
        st.markdown(f"""
            <div class="sidebar-footer">
                <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg"></a>
                <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg"></a>
            </div>
            """, unsafe_allow_html=True)

    # --- Funções do Banco de Dados para o Dashboard ---
    def get_db_connection():
        return st.connection("supabase", type="sql")

    @st.cache_data(ttl=600)
    def carregar_dados_dashboard():
        try:
            conn = get_db_connection()
            
            kpis_ativos = conn.query("""
                SELECT COUNT(a.id), COALESCE(SUM(a.valor), 0)
                FROM aparelhos a
                JOIN status s ON a.status_id = s.id
                WHERE s.nome_status != 'Baixado/Inutilizado'
            """, ttl=600).iloc[0]
            total_aparelhos = kpis_ativos[0] or 0
            valor_total = kpis_ativos[1] or 0
            
            total_colaboradores = conn.query("SELECT COUNT(id) FROM colaboradores", ttl=600).iloc[0, 0] or 0
            
            kpis_manutencao = conn.query("""
                SELECT COUNT(a.id), COALESCE(SUM(a.valor), 0)
                FROM aparelhos a JOIN status s ON a.status_id = s.id 
                WHERE s.nome_status = 'Em manutenção'
            """, ttl=600).iloc[0]
            aparelhos_manutencao = kpis_manutencao[0] or 0
            valor_manutencao = kpis_manutencao[1] or 0
            
            aparelhos_estoque = conn.query("""
                SELECT COUNT(a.id) FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status = 'Em estoque'
            """, ttl=600).iloc[0, 0] or 0

            df_status = conn.query("""
                SELECT s.nome_status, 
                COUNT(a.id) as quantidade 
                FROM aparelhos a 
                JOIN status s ON a.status_id = s.id 
                GROUP BY s.nome_status
            """, ttl=600)
            
            df_setor = conn.query("""
                WITH UltimaMovimentacao AS (
                    SELECT 
                        h.aparelho_id, 
                        h.colaborador_id,
                        ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
                    FROM historico_movimentacoes h
                )
                SELECT s.nome_setor, COUNT(a.id) as quantidade
                FROM aparelhos a
                JOIN UltimaMovimentacao um ON a.id = um.aparelho_id AND um.rn = 1
                JOIN colaboradores c ON um.colaborador_id = c.id
                JOIN setores s ON c.setor_id = s.id
                JOIN status st ON a.status_id = st.id
                WHERE st.nome_status = 'Em uso'
                GROUP BY s.nome_setor
            """, ttl=600)

            data_limite = datetime.now() - timedelta(days=5)
            df_manut_atrasadas = conn.query("""
                SELECT a.numero_serie, mo.nome_modelo, m.fornecedor, m.data_envio
                FROM manutencoes m
                JOIN aparelhos a ON m.aparelho_id = a.id
                JOIN modelos mo ON a.modelo_id = mo.id
                WHERE m.status_manutencao = 'Em Andamento' AND m.data_envio < :data_limite
            """, params={"data_limite": data_limite}, ttl=600)

            # --- LÓGICA ATUALIZADA ---
            # Busca o nome do colaborador a partir do 'colaborador_snapshot' para o histórico
            df_ultimas_mov = conn.query("""
                SELECT h.data_movimentacao, h.colaborador_snapshot as nome_completo, s.nome_status, a.numero_serie
                FROM historico_movimentacoes h
                JOIN status s ON h.status_id = s.id
                JOIN aparelhos a ON h.aparelho_id = a.id
                ORDER BY h.data_movimentacao DESC LIMIT 5
            """, ttl=60)

            return {
                "kpis": {
                    "total_aparelhos": total_aparelhos, "valor_total": valor_total,
                    "total_colaboradores": total_colaboradores, "aparelhos_manutencao": aparelhos_manutencao,
                    "valor_manutencao": valor_manutencao, "aparelhos_estoque": aparelhos_estoque
                },
                "graficos": {"status": df_status, "setor": df_setor},
                "acao_rapida": {"manut_atrasadas": df_manut_atrasadas, "ultimas_mov": df_ultimas_mov}
            }
        except Exception:
            return None

    # --- Conteúdo do Dashboard ---
    col_titulo, col_botao = st.columns([3, 1])
    with col_titulo:
        st.title("Dashboard Gerencial")
    with col_botao:
        st.write("") # Espaçador
        st.write("") # Espaçador
        if st.button("Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    dados = carregar_dados_dashboard()
    
    if dados is None:
        st.warning("Não foi possível carregar os dados do dashboard. As tabelas da base de dados podem não ter sido inicializadas.")
        st.info("Por favor, vá à página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados'.")
        st.stop()

    kpis = dados['kpis']
    graficos = dados['graficos']
    acao_rapida = dados['acao_rapida']

    st.subheader("Visão Geral (Aparelhos Ativos)")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Aparelhos Ativos", f"{kpis['total_aparelhos']:,}".replace(",", "."))
    col2.metric("Valor do Inventário Ativo", f"R$ {kpis.get('valor_total', 0):,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
    col3.metric("Total de Colaboradores", f"{kpis['total_colaboradores']:,}".replace(",", "."))
    
    col4, col5, col6 = st.columns(3)
    col4.metric("Aparelhos em Manutenção", f"{kpis['aparelhos_manutencao']:,}".replace(",", "."))
    col5.metric("Valor em Manutenção", f"R$ {kpis.get('valor_manutencao', 0):,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
    col6.metric("Aparelhos em Estoque", f"{kpis['aparelhos_estoque']:,}".replace(",", "."))

    st.markdown("---")

    st.subheader("Análise Operacional")
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.markdown("###### Aparelhos por Status (Excluindo Baixados)")
        df_status_filtrado = graficos['status'][graficos['status']['nome_status'] != 'Baixado/Inutilizado']
        if not df_status_filtrado.empty:
            fig = px.pie(df_status_filtrado, names='nome_status', values='quantidade', hole=.4)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Não há dados de status para exibir.")
    with gcol2:
        st.markdown("###### Distribuição de Aparelhos por Setor")
        if not graficos['setor'].empty:
            fig2 = px.bar(graficos['setor'], x='nome_setor', y='quantidade', text_auto=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Não há aparelhos 'Em uso' para exibir a distribuição por setor.")

    st.markdown("---")

    st.subheader("Painel de Ação Rápida")
    acol1, acol2 = st.columns(2)
    with acol1:
        st.markdown("###### Alerta: Manutenções Atrasadas (> 5 dias)")
        st.dataframe(acao_rapida['manut_atrasadas'], hide_index=True, use_container_width=True,
                     column_config={
                         "data_envio": st.column_config.DateColumn("Data Envio", format="DD/MM/YYYY")
                     })
    with acol2:
        st.markdown("###### Últimas 5 Movimentações")
        st.dataframe(acao_rapida['ultimas_mov'], hide_index=True, use_container_width=True,
                     column_config={
                         "data_movimentacao": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
                         "nome_completo": "Colaborador"
                     })

