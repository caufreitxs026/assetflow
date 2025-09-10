import streamlit as st
import pandas as pd
import plotly.express as px
from auth import show_login_form, logout
from datetime import datetime, timedelta
from sqlalchemy import text

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
            
            # KPIs Ativos
            kpis_ativos = conn.query("""
                SELECT COUNT(a.id), COALESCE(SUM(a.valor), 0)
                FROM aparelhos a
                JOIN status s ON a.status_id = s.id
                WHERE s.nome_status != 'Baixado/Inutilizado'
            """, ttl=600).iloc[0]
            
            # KPIs Manutenção e Estoque
            kpis_manutencao = conn.query("SELECT COUNT(a.id), COALESCE(SUM(a.valor), 0) FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status = 'Em manutenção'", ttl=600).iloc[0]
            aparelhos_estoque = conn.query("SELECT COUNT(a.id) FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status = 'Em estoque'", ttl=600).iloc[0, 0] or 0
            
            total_colaboradores = conn.query("SELECT COUNT(id) FROM colaboradores", ttl=600).iloc[0, 0] or 0

            # --- NOVO KPI: Colaboradores com múltiplos aparelhos ---
            df_multiplos = conn.query("""
                WITH AparelhosPorColaborador AS (
                    SELECT 
                        h.colaborador_id
                    FROM aparelhos a
                    JOIN status s ON a.status_id = s.id
                    JOIN (
                        SELECT aparelho_id, colaborador_id, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
                        FROM historico_movimentacoes
                        WHERE colaborador_id IS NOT NULL
                    ) h ON a.id = h.aparelho_id AND h.rn = 1
                    WHERE s.nome_status = 'Em uso'
                )
                SELECT colaborador_id, COUNT(*) as contagem
                FROM AparelhosPorColaborador
                GROUP BY colaborador_id
                HAVING COUNT(*) > 1;
            """, ttl=600)
            colaboradores_multiplos_aparelhos = len(df_multiplos)

            # --- NOVA QUERY: Detalhes dos colaboradores com múltiplos aparelhos ---
            df_detalhes_multiplos = pd.DataFrame()
            if colaboradores_multiplos_aparelhos > 0:
                # Garante que a lista não esteja vazia para evitar erro de sintaxe SQL com 'IN ()'
                ids_colaboradores_list = df_multiplos['colaborador_id'].tolist()
                if ids_colaboradores_list:
                    ids_colaboradores = tuple(ids_colaboradores_list)
                    df_detalhes_multiplos = conn.query(f"""
                        SELECT 
                            c.nome_completo,
                            setor.nome_setor,
                            ma.nome_marca || ' - ' || mo.nome_modelo as modelo_completo,
                            a.numero_serie
                        FROM aparelhos a
                        JOIN status s ON a.status_id = s.id
                        JOIN (
                            SELECT aparelho_id, colaborador_id, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
                            FROM historico_movimentacoes
                            WHERE colaborador_id IS NOT NULL
                        ) h ON a.id = h.aparelho_id AND h.rn = 1
                        JOIN colaboradores c ON h.colaborador_id = c.id
                        JOIN setores setor ON c.setor_id = setor.id
                        JOIN modelos mo ON a.modelo_id = mo.id
                        JOIN marcas ma ON mo.marca_id = ma.id
                        WHERE s.nome_status = 'Em uso' AND c.id IN {ids_colaboradores}
                        ORDER BY c.nome_completo, modelo_completo;
                    """, ttl=600)

            # Gráficos
            df_status = conn.query("SELECT s.nome_status, COUNT(a.id) as quantidade FROM aparelhos a JOIN status s ON a.status_id = s.id GROUP BY s.nome_status", ttl=600)
            df_setor = conn.query("""
                SELECT s.nome_setor, COUNT(a.id) as quantidade
                FROM aparelhos a
                JOIN (
                    SELECT aparelho_id, colaborador_id, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
                    FROM historico_movimentacoes WHERE colaborador_id IS NOT NULL
                ) h ON a.id = h.aparelho_id AND h.rn = 1
                JOIN colaboradores c ON h.colaborador_id = c.id
                JOIN setores s ON c.setor_id = s.id
                JOIN status st ON a.status_id = st.id
                WHERE st.nome_status = 'Em uso'
                GROUP BY s.nome_setor
            """, ttl=600)

            # Painel de Ação Rápida
            data_limite = datetime.now() - timedelta(days=5)
            df_manut_atrasadas = conn.query("SELECT a.numero_serie, mo.nome_modelo, m.fornecedor, m.data_envio FROM manutencoes m JOIN aparelhos a ON m.aparelho_id = a.id JOIN modelos mo ON a.modelo_id = mo.id WHERE m.status_manutencao = 'Em Andamento' AND m.data_envio < :data_limite", params={"data_limite": data_limite}, ttl=600)
            df_ultimas_mov = conn.query("SELECT h.data_movimentacao, h.colaborador_snapshot as nome_completo, s.nome_status, a.numero_serie FROM historico_movimentacoes h JOIN status s ON h.status_id = s.id JOIN aparelhos a ON h.aparelho_id = a.id ORDER BY h.data_movimentacao DESC LIMIT 5", ttl=60)

            return {
                "kpis": {
                    "total_aparelhos": kpis_ativos[0] or 0, 
                    "valor_total": kpis_ativos[1] or 0,
                    "total_colaboradores": total_colaboradores, 
                    "aparelhos_manutencao": kpis_manutencao[0] or 0,
                    "valor_manutencao": kpis_manutencao[1] or 0, 
                    "aparelhos_estoque": aparelhos_estoque,
                    "colaboradores_multiplos": colaboradores_multiplos_aparelhos
                },
                "graficos": {"status": df_status, "setor": df_setor},
                "acao_rapida": {"manut_atrasadas": df_manut_atrasadas, "ultimas_mov": df_ultimas_mov},
                "detalhes": {"multiplos_aparelhos": df_detalhes_multiplos}
            }
        except Exception:
            return None

    # --- Conteúdo do Dashboard ---
    col_titulo, col_botao = st.columns([3, 1])
    with col_titulo:
        st.title("Dashboard Gerencial")
    with col_botao:
        st.write("") 
        st.write("") 
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
    detalhes = dados['detalhes']

    st.subheader("Visão Geral (Aparelhos Ativos)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Aparelhos Ativos", f"{int(kpis['total_aparelhos']):,}".replace(",", "."))
    col2.metric("Valor do Inventário Ativo", f"R$ {kpis.get('valor_total', 0):,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
    col3.metric("Total de Colaboradores", f"{int(kpis['total_colaboradores']):,}".replace(",", "."))
    col4.metric("Aparelhos em Estoque", f"{int(kpis['aparelhos_estoque']):,}".replace(",", "."))
    
    st.markdown("---")
    st.subheader("Indicadores de Alerta")
    col5, col6 = st.columns(2)
    col5.metric("Aparelhos em Manutenção", f"{int(kpis['aparelhos_manutencao']):,}".replace(",", "."))
    col6.metric("Colaboradores com Múltiplos Aparelhos", f"{int(kpis['colaboradores_multiplos']):,}".replace(",", "."))
    
    if not detalhes['multiplos_aparelhos'].empty:
        with st.expander("Alerta: Detalhes de Colaboradores com Múltiplos Aparelhos"):
            grouped = detalhes['multiplos_aparelhos'].groupby('nome_completo')
            for nome, grupo in grouped:
                setor = grupo['nome_setor'].iloc[0]
                st.markdown(f"**Nome:** {nome} | **Setor:** {setor}")
                st.dataframe(
                    grupo[['modelo_completo', 'numero_serie']],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "modelo_completo": "Modelo do Aparelho",
                        "numero_serie": "Número de Série"
                    }
                )
    
    st.markdown("---")

    st.subheader("Análise Operacional")
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.markdown("###### Aparelhos por Status (Visão Total)")
        if not graficos['status'].empty:
            # CORREÇÃO: O gráfico agora usa o dataframe completo 'graficos['status']', sem filtrar.
            fig = px.pie(graficos['status'], names='nome_status', values='quantidade', hole=.4)
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
                          "data_envio": st.column_config.DateColumn("Data de Envio", format="DD/MM/YYYY")
                      })
    with acol2:
        st.markdown("###### Últimas 5 Movimentações")
        st.dataframe(acao_rapida['ultimas_mov'], hide_index=True, use_container_width=True,
                      column_config={
                          "data_movimentacao": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
                          "nome_completo": "Colaborador"
                      })


