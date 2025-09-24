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

    # --- CSS para o Dashboard Interativo ---
    st.markdown("""
    <style>
        /* Estilos da Logo */
        .logo-text { font-family: 'Courier New', monospace; font-size: 28px; font-weight: bold; padding-top: 20px; }
        
        /* --- ESTILOS ATUALIZADOS PARA A LOGO --- */
        /* Estilos para o tema claro (light) */
        .logo-asset {
            color: #FFFFFF; /* Fonte branca */
            text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7); /* Sombra preta */
        }
        .logo-flow {
            color: #E30613; /* Fonte vermelha */
            text-shadow: 1px 1px 3px rgba(255, 255, 255, 0.5); /* Sombra branca sutil */
        }
        
        /* Estilos para o tema escuro (dark) */
        @media (prefers-color-scheme: dark) {
            .logo-asset {
                color: #FFFFFF;
                text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7); /* Mantém a sombra preta para contraste */
            }
            .logo-flow {
                color: #FF4B4B; /* Um vermelho mais vibrante para o tema escuro */
                text-shadow: none; /* Remove a sombra branca */
            }
        }
        /* Estilos para o footer na barra lateral */
        .sidebar-footer { text-align: center; padding-top: 20px; padding-bottom: 20px; }
        .sidebar-footer a { margin-right: 15px; text-decoration: none; }
        .sidebar-footer img { width: 25px; height: 25px; filter: grayscale(1) opacity(0.5); transition: filter 0.3s; }
        .sidebar-footer img:hover { filter: grayscale(0) opacity(1); }
        @media (prefers-color-scheme: dark) { .sidebar-footer img { filter: grayscale(1) opacity(0.6) invert(1); } .sidebar-footer img:hover { filter: opacity(1) invert(1); } }

        /* Estilo para o cartão de métrica personalizado */
        .metric-card {
            background-color: #f0f2f6;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border: 1px solid #e6e6e6;
            margin-bottom: 10px;
        }
        @media (prefers-color-scheme: dark) {
            .metric-card {
                background-color: #1E1E1E;
                border: 1px solid #333;
            }
        }
        .metric-card h3 {
            margin: 0 0 5px 0;
            color: #5a5a5a;
            font-size: 1rem;
        }
        @media (prefers-color-scheme: dark) {
            .metric-card h3 { color: #a0a0a0; }
        }
        .metric-card p {
            font-size: 2rem;
            font-weight: bold;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        /* Animação do ponto a piscar */
        @keyframes pulse {
            0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(227, 6, 19, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(227, 6, 19, 0); }
            100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(227, 6, 19, 0); }
        }
        .blinking-dot {
            height: 15px;
            width: 15px;
            background-color: #E30613;
            border-radius: 50%;
            display: inline-block;
            margin-left: 10px;
            animation: pulse 1.5s infinite;
        }
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
            
            kpis_ativos = conn.query("SELECT COUNT(a.id), COALESCE(SUM(a.valor), 0) FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status != 'Baixado/Inutilizado'").iloc[0]
            kpis_manutencao = conn.query("SELECT COUNT(a.id), COALESCE(SUM(a.valor), 0) FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status = 'Em manutenção'").iloc[0]
            aparelhos_estoque = conn.query("SELECT COUNT(a.id) FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status = 'Em estoque'").iloc[0, 0] or 0
            total_colaboradores = conn.query("SELECT COUNT(id) FROM colaboradores").iloc[0, 0] or 0

            df_multiplos_ids = conn.query("""
                WITH AparelhosPorColaborador AS (
                    SELECT h.colaborador_id FROM aparelhos a JOIN status s ON a.status_id = s.id
                    JOIN (SELECT aparelho_id, colaborador_id, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn FROM historico_movimentacoes WHERE colaborador_id IS NOT NULL) h ON a.id = h.aparelho_id AND h.rn = 1
                    WHERE s.nome_status = 'Em uso'
                )
                SELECT colaborador_id FROM AparelhosPorColaborador GROUP BY colaborador_id HAVING COUNT(*) > 1;
            """)
            colaboradores_multiplos_aparelhos_count = len(df_multiplos_ids)

            df_detalhes_multiplos = pd.DataFrame()
            if not df_multiplos_ids.empty:
                ids_colaboradores_list = df_multiplos_ids['colaborador_id'].tolist()
                if ids_colaboradores_list:
                    # Adiciona uma verificação para garantir que a lista não está vazia antes de criar a tupla
                    if len(ids_colaboradores_list) == 1:
                        ids_colaboradores = f"({ids_colaboradores_list[0]})"
                    else:
                        ids_colaboradores = tuple(ids_colaboradores_list)

                    df_detalhes_multiplos = conn.query(f"""
                        SELECT c.nome_completo, setor.nome_setor, ma.nome_marca || ' - ' || mo.nome_modelo as modelo_completo, a.numero_serie, h.data_movimentacao
                        FROM aparelhos a JOIN status s ON a.status_id = s.id
                        JOIN (SELECT aparelho_id, colaborador_id, data_movimentacao, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn FROM historico_movimentacoes WHERE colaborador_id IS NOT NULL) h ON a.id = h.aparelho_id AND h.rn = 1
                        JOIN colaboradores c ON h.colaborador_id = c.id JOIN setores setor ON c.setor_id = setor.id JOIN modelos mo ON a.modelo_id = mo.id JOIN marcas ma ON mo.marca_id = ma.id
                        WHERE s.nome_status = 'Em uso' AND c.id IN {ids_colaboradores}
                        ORDER BY c.nome_completo, h.data_movimentacao;
                    """)
            
            df_detalhes_manutencao = conn.query("""
                SELECT a.numero_serie, mo.nome_modelo, m.fornecedor, m.data_envio, m.defeito_reportado
                FROM manutencoes m
                JOIN aparelhos a ON m.aparelho_id = a.id
                JOIN modelos mo ON a.modelo_id = mo.id
                WHERE m.status_manutencao = 'Em Andamento'
                ORDER BY m.data_envio ASC;
            """)

            df_status = conn.query("SELECT s.nome_status, COUNT(a.id) as quantidade FROM aparelhos a JOIN status s ON a.status_id = s.id GROUP BY s.nome_status")
            df_setor = conn.query("""
                SELECT s.nome_setor, COUNT(a.id) as quantidade
                FROM aparelhos a
                JOIN (SELECT aparelho_id, colaborador_id, ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn FROM historico_movimentacoes WHERE colaborador_id IS NOT NULL) h ON a.id = h.aparelho_id AND h.rn = 1
                JOIN colaboradores c ON h.colaborador_id = c.id JOIN setores s ON c.setor_id = s.id JOIN status st ON a.status_id = st.id
                WHERE st.nome_status = 'Em uso' GROUP BY s.nome_setor
            """)

            data_limite = datetime.now() - timedelta(days=5)
            df_manut_atrasadas = conn.query("SELECT a.numero_serie, mo.nome_modelo, m.fornecedor, m.data_envio FROM manutencoes m JOIN aparelhos a ON m.aparelho_id = a.id JOIN modelos mo ON a.modelo_id = mo.id WHERE m.status_manutencao = 'Em Andamento' AND m.data_envio < :data_limite", params={"data_limite": data_limite})
            df_ultimas_mov = conn.query("SELECT h.data_movimentacao, h.colaborador_snapshot as nome_completo, s.nome_status, a.numero_serie FROM historico_movimentacoes h JOIN status s ON h.status_id = s.id JOIN aparelhos a ON h.aparelho_id = a.id ORDER BY h.data_movimentacao DESC LIMIT 5")

            return {
                "kpis": {
                    "total_aparelhos": kpis_ativos[0] or 0, "valor_total": kpis_ativos[1] or 0,
                    "total_colaboradores": total_colaboradores, "aparelhos_manutencao": kpis_manutencao[0] or 0,
                    "aparelhos_estoque": aparelhos_estoque, "colaboradores_multiplos": colaboradores_multiplos_aparelhos_count
                },
                "graficos": {"status": df_status, "setor": df_setor},
                "acao_rapida": {"manut_atrasadas": df_manut_atrasadas, "ultimas_mov": df_ultimas_mov},
                "detalhes": {
                    "multiplos_aparelhos": df_detalhes_multiplos,
                    "manutencoes_em_andamento": df_detalhes_manutencao
                }
            }
        except Exception as e:
            st.error(f"Erro ao carregar dados do dashboard: {e}")
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
    
    # Cartão de Manutenção
    with col5:
        blinking_dot_manut = "<span class='blinking-dot'></span>" if int(kpis['aparelhos_manutencao']) > 0 else ""
        st.markdown(f"""
        <div class='metric-card'>
            <h3>Aparelhos em Manutenção</h3>
            <p>{int(kpis['aparelhos_manutencao'])}{blinking_dot_manut}</p>
        </div>
        """, unsafe_allow_html=True)
        if int(kpis['aparelhos_manutencao']) > 0:
            if st.button("Ver Detalhes", key="btn_manut", use_container_width=True):
                st.session_state.show_manutencao_details = not st.session_state.get("show_manutencao_details", False)

    # Cartão de Múltiplos Aparelhos
    with col6:
        blinking_dot_multi = "<span class='blinking-dot'></span>" if int(kpis['colaboradores_multiplos']) > 0 else ""
        st.markdown(f"""
        <div class='metric-card'>
            <h3>Colaboradores com Múltiplos Aparelhos</h3>
            <p>{int(kpis['colaboradores_multiplos'])}{blinking_dot_multi}</p>
        </div>
        """, unsafe_allow_html=True)
        if int(kpis['colaboradores_multiplos']) > 0:
            if st.button("Ver Detalhes", key="btn_multi", use_container_width=True):
                st.session_state.show_multiplos_details = not st.session_state.get("show_multiplos_details", False)


    # --- Lógica para exibir os detalhes abaixo dos alertas ---
    if st.session_state.get("show_manutencao_details", False):
        st.subheader("Detalhes de Aparelhos em Manutenção")
        st.dataframe(
            detalhes['manutencoes_em_andamento'],
            hide_index=True,
            use_container_width=True,
            column_config={
                "numero_serie": "N/S", "nome_modelo": "Modelo", "fornecedor": "Fornecedor",
                "data_envio": st.column_config.DateColumn("Data de Envio", format="DD/MM/YYYY"),
                "defeito_reportado": "Defeito Reportado"
            }
        )

    if st.session_state.get("show_multiplos_details", False):
        st.subheader("Detalhes de Colaboradores com Múltiplos Aparelhos")
        grouped = detalhes['multiplos_aparelhos'].groupby('nome_completo')
        for nome, grupo in grouped:
            setor = grupo['nome_setor'].iloc[0]
            st.markdown(f"**Nome:** {nome} | **Setor:** {setor}")
            st.dataframe(
                grupo[['modelo_completo', 'numero_serie', 'data_movimentacao']],
                hide_index=True, use_container_width=True,
                column_config={
                    "modelo_completo": "Modelo do Aparelho", "numero_serie": "Número de Série",
                    "data_movimentacao": st.column_config.DatetimeColumn("Data da Entrega", format="DD/MM/YYYY HH:mm")
                }
            )

    st.markdown("---")

    st.subheader("Análise Operacional")
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.markdown("###### Aparelhos por Status (Visão Total)")
        if not graficos['status'].empty:
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
                      column_config={"data_envio": st.column_config.DateColumn("Data de Envio", format="DD/MM/YYYY")})
    with acol2:
        st.markdown("###### Últimas 5 Movimentações")
        st.dataframe(acao_rapida['ultimas_mov'], hide_index=True, use_container_width=True,
                      column_config={
                          "data_movimentacao": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
                          "nome_completo": "Colaborador"
                      })

# Forçando a reconstrução do cache - v1.3

