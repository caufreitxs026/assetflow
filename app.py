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
# Se o utilizador não estiver logado, mostra apenas o formulário de login.
if not st.session_state['logged_in']:
    show_login_form()
else:
    # --- Se logado, mostra a aplicação completa ---

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
        .sidebar-footer {
            text-align: center;
            padding-top: 20px;
            padding-bottom: 20px;
        }
        .sidebar-footer a {
            margin-right: 15px;
            text-decoration: none;
        }
        .sidebar-footer img {
            width: 25px;
            height: 25px;
            filter: grayscale(1) opacity(0.5);
            transition: filter 0.3s;
        }
        .sidebar-footer img:hover {
            filter: grayscale(0) opacity(1);
        }
        
        @media (prefers-color-scheme: dark) {
            .sidebar-footer img {
                filter: grayscale(1) opacity(0.6) invert(1);
            }
            .sidebar-footer img:hover {
                filter: opacity(1) invert(1);
            }
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

    # --- Barra Lateral (Agora contém informações e o footer) ---
    with st.sidebar:
        st.write(f"Bem-vindo, **{st.session_state['user_name']}**!")
        st.write(f"Cargo: **{st.session_state['user_role']}**")
        if st.button("Logout"):
            logout()

        st.markdown("---")
        st.markdown(
            f"""
            <div class="sidebar-footer">
                <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub">
                    <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg">
                </a>
                <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn">
                    <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg">
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- Funções do Banco de Dados para o Dashboard (MODIFICADAS PARA POSTGRESQL) ---
    def get_db_connection():
        """Retorna uma conexão ao banco de dados Supabase."""
        return st.connection("supabase", type="sql")

    @st.cache_data(ttl=600) # O cache otimiza o desempenho
    def carregar_dados_dashboard():
        conn = get_db_connection()
        
        # KPIs - Aparelhos Ativos (Excluindo Baixados/Inutilizados)
        kpis_ativos_df = conn.query("""
            SELECT COUNT(a.id) as total, COALESCE(SUM(a.valor), 0) as valor
            FROM aparelhos a
            JOIN status s ON a.status_id = s.id
            WHERE s.nome_status != 'Baixado/Inutilizado';
        """)
        total_aparelhos = kpis_ativos_df['total'].iloc[0] if not kpis_ativos_df.empty else 0
        valor_total = kpis_ativos_df['valor'].iloc[0] if not kpis_ativos_df.empty else 0
        
        total_colaboradores_df = conn.query("SELECT COUNT(id) as total FROM colaboradores;")
        total_colaboradores = total_colaboradores_df['total'].iloc[0] if not total_colaboradores_df.empty else 0
        
        kpis_manutencao_df = conn.query("""
            SELECT COUNT(a.id) as total, COALESCE(SUM(a.valor), 0) as valor 
            FROM aparelhos a JOIN status s ON a.status_id = s.id 
            WHERE s.nome_status = 'Em manutenção';
        """)
        aparelhos_manutencao = kpis_manutencao_df['total'].iloc[0] if not kpis_manutencao_df.empty else 0
        valor_manutencao = kpis_manutencao_df['valor'].iloc[0] if not kpis_manutencao_df.empty else 0
        
        aparelhos_estoque_df = conn.query("""
            SELECT COUNT(a.id) as total FROM aparelhos a JOIN status s ON a.status_id = s.id WHERE s.nome_status = 'Em estoque';
        """)
        aparelhos_estoque = aparelhos_estoque_df['total'].iloc[0] if not aparelhos_estoque_df.empty else 0

        # Gráficos (Excluindo Baixados/Inutilizados)
        df_status = conn.query("""
            SELECT s.nome_status, 
            COUNT(a.id) as quantidade 
            FROM aparelhos a 
            JOIN status s ON a.status_id = s.id 
            GROUP BY s.nome_status;
        """)
        
        df_setor = conn.query("""
            WITH UltimaMovimentacao AS (
                SELECT 
                    aparelho_id,
                    colaborador_id,
                    ROW_NUMBER() OVER(PARTITION BY aparelho_id ORDER BY data_movimentacao DESC) as rn
                FROM historico_movimentacoes
                WHERE colaborador_id IS NOT NULL
            )
            SELECT 
                se.nome_setor, 
                COUNT(DISTINCT a.id) as quantidade
            FROM aparelhos a
            JOIN UltimaMovimentacao um ON a.id = um.aparelho_id AND um.rn = 1
            JOIN colaboradores c ON um.colaborador_id = c.id
            JOIN setores se ON c.setor_id = se.id
            JOIN status s ON a.status_id = s.id
            WHERE s.nome_status = 'Em uso'
            GROUP BY se.nome_setor;
        """)

        # Painel de Ação Rápida
        data_limite = datetime.now() - timedelta(days=5)
        df_manut_atrasadas = conn.query(f"""
            SELECT a.numero_serie, mo.nome_modelo, m.fornecedor, m.data_envio
            FROM manutencoes m
            JOIN aparelhos a ON m.aparelho_id = a.id
            JOIN modelos mo ON a.modelo_id = mo.id
            WHERE m.status_manutencao = 'Em Andamento' AND m.data_envio < :data_limite;
        """, params={"data_limite": data_limite})

        df_ultimas_mov = conn.query("""
            SELECT h.data_movimentacao, c.nome_completo, s.nome_status, a.numero_serie
            FROM historico_movimentacoes h
            LEFT JOIN colaboradores c ON h.colaborador_id = c.id
            JOIN status s ON h.status_id = s.id
            JOIN aparelhos a ON h.aparelho_id = a.id
            ORDER BY h.data_movimentacao DESC LIMIT 5;
        """)

        return {
            "kpis": {
                "total_aparelhos": total_aparelhos, "valor_total": valor_total,
                "total_colaboradores": total_colaboradores, "aparelhos_manutencao": aparelhos_manutencao,
                "valor_manutencao": valor_manutencao, "aparelhos_estoque": aparelhos_estoque
            },
            "graficos": {"status": df_status, "setor": df_setor},
            "acao_rapida": {"manut_atrasadas": df_manut_atrasadas, "ultimas_mov": df_ultimas_mov}
        }

    # --- Conteúdo do Dashboard ---
    try:
        # Título e Botão de Atualização
        col_titulo, col_botao = st.columns([3, 1])
        with col_titulo:
            st.title("Dashboard Gerencial")
        with col_botao:
            st.write("") # Espaçador
            st.write("") # Espaçador
            if st.button("Atualizar Dados", use_container_width=True):
                st.cache_data.clear() # Limpa o cache para buscar novos dados
                st.rerun()

        st.markdown("---")

        dados = carregar_dados_dashboard()
        kpis = dados['kpis']
        graficos = dados['graficos']
        acao_rapida = dados['acao_rapida']

        # 1. Visão Geral
        st.subheader("Visão Geral (Aparelhos Ativos)")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Aparelhos Ativos", f"{kpis['total_aparelhos']:,}".replace(",", "."))
        col2.metric("Valor do Inventário Ativo", f"R$ {kpis['valor_total']:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
        col3.metric("Total de Colaboradores", f"{kpis['total_colaboradores']:,}".replace(",", "."))
        
        col4, col5, col6 = st.columns(3)
        col4.metric("Aparelhos em Manutenção", f"{kpis['aparelhos_manutencao']:,}".replace(",", "."))
        col5.metric("Valor em Manutenção", f"R$ {kpis['valor_manutencao']:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
        col6.metric("Aparelhos em Estoque", f"{kpis['aparelhos_estoque']:,}".replace(",", "."))

        st.markdown("---")

        # 2. Análise Operacional
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

        # 3. Painel de Ação Rápida
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
                             "data_movimentacao": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm")
                         })
    
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar ou consultar o banco de dados: {e}")
        st.warning("O banco de dados parece estar vazio ou inacessível.")
        st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")

