import streamlit as st
import pandas as pd
import httpx
from auth import show_login_form, logout
from sqlalchemy import text

# --- Autenticação e Permissão ---
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
    if st.button("Logout", key="mdm_logout"):
        logout()
    st.markdown("---")
    st.markdown(f"""
        <div class="sidebar-footer">
            <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg"></a>
            <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg"></a>
        </div>
        """, unsafe_allow_html=True)

# --- Funções da Página ---

@st.cache_data(ttl=300) # Cache de 5 minutos
def get_pulsus_data():
    """Busca os dados dos aparelhos na API do Pulsus MDM."""
    try:
        api_key = st.secrets["PULSUS_API_KEY"]
    except KeyError:
        st.error("A chave da API do Pulsus (PULSUS_API_KEY) não foi encontrada nos segredos do Streamlit.")
        return None

    # Nota: Este é um URL padrão para APIs. Verifique na documentação do Pulsus se é o correto.
    url = "https://api.pulsus.mobi/v1/devices"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status() # Lança um erro para status 4xx ou 5xx
            data = response.json()
            
            # Extrai os campos relevantes para um DataFrame
            # Nota: Os nomes das colunas ('serial_number', 'user_name', etc.) podem precisar de ajuste
            #       consoante a resposta real da API do Pulsus.
            records = []
            for device in data.get('devices', []):
                records.append({
                    "numero_serie_pulsus": device.get("serial_number"),
                    "imei_pulsus": device.get("imei"),
                    "responsavel_pulsus": device.get("user_name", "Não atribuído"),
                    "ultimo_sync_pulsus": device.get("last_sync")
                })
            
            df = pd.DataFrame(records)
            # Remove linhas onde o número de série está em falta, pois é a nossa chave principal
            df.dropna(subset=['numero_serie_pulsus'], inplace=True)
            return df

    except httpx.HTTPStatusError as e:
        st.error(f"Erro ao comunicar com a API do Pulsus: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao buscar dados do Pulsus: {e}")
        return None

@st.cache_data(ttl=30)
def get_assetflow_data():
    """Busca os dados dos aparelhos no banco de dados do AssetFlow."""
    conn = st.connection("supabase", type="sql")
    query = """
        WITH UltimoResponsavel AS (
            SELECT
                h.aparelho_id,
                h.colaborador_snapshot,
                ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
            FROM historico_movimentacoes h
        )
        SELECT 
            a.numero_serie,
            ma.nome_marca || ' - ' || mo.nome_modelo as modelo,
            s.nome_status,
            CASE 
                WHEN s.nome_status = 'Em uso' THEN ur.colaborador_snapshot
                ELSE NULL 
            END as responsavel_assetflow
        FROM aparelhos a
        LEFT JOIN modelos mo ON a.modelo_id = mo.id
        LEFT JOIN marcas ma ON mo.marca_id = ma.id
        JOIN status s ON a.status_id = s.id
        LEFT JOIN UltimoResponsavel ur ON a.id = ur.aparelho_id AND ur.rn = 1;
    """
    df = conn.query(query)
    df['responsavel_assetflow'] = df['responsavel_assetflow'].fillna("Não atribuído")
    return df

# --- UI da Página ---
st.title("🔬 Sincronização e Auditoria MDM (Pulsus)")
st.markdown("---")
st.info("Esta ferramenta compara o inventário do **AssetFlow** com os dados do **Pulsus MDM** para identificar discrepâncias, aparelhos em falta ou não cadastrados.")

if st.button("Comparar Inventários Agora", type="primary", use_container_width=True):
    with st.spinner("A buscar dados do AssetFlow..."):
        df_assetflow = get_assetflow_data()
    
    with st.spinner("A conectar com o Pulsus MDM..."):
        df_pulsus = get_pulsus_data()

    if df_assetflow is not None and df_pulsus is not None:
        st.success(f"Comparação concluída! Encontrados {len(df_assetflow)} aparelhos no AssetFlow e {len(df_pulsus)} no Pulsus.")
        st.markdown("---")

        # Faz o merge dos dois dataframes usando o número de série como chave
        df_merged = pd.merge(
            df_assetflow, 
            df_pulsus, 
            left_on='numero_serie', 
            right_on='numero_serie_pulsus',
            how='outer'
        )

        # 1. Aparelhos Sincronizados e Corretos
        df_sync = df_merged[
            (df_merged['numero_serie'].notna()) & 
            (df_merged['numero_serie_pulsus'].notna()) &
            (df_merged['responsavel_assetflow'] == df_merged['responsavel_pulsus'])
        ]
        
        # 2. Aparelhos com Responsáveis Divergentes
        df_divergent = df_merged[
            (df_merged['numero_serie'].notna()) & 
            (df_merged['numero_serie_pulsus'].notna()) &
            (df_merged['responsavel_assetflow'] != df_merged['responsavel_pulsus'])
        ]

        # 3. Aparelhos que só existem no AssetFlow (Fantasmas)
        df_only_assetflow = df_merged[df_merged['numero_serie_pulsus'].isna()]

        # 4. Aparelhos que só existem no Pulsus (Surpresas)
        df_only_pulsus = df_merged[df_merged['numero_serie'].isna()]

        # --- Exibição dos Resultados ---
        st.subheader("Resultados da Auditoria")

        # Abas para organizar os resultados
        tab_diverg, tab_asset, tab_pulsus, tab_sync = st.tabs([
            f"Divergências ({len(df_divergent)})", 
            f"Apenas no AssetFlow ({len(df_only_assetflow)})", 
            f"Apenas no Pulsus ({len(df_only_pulsus)})",
            f"Sincronizados ({len(df_sync)})"
        ])

        with tab_diverg:
            st.warning("Estes aparelhos estão em ambos os sistemas, mas o responsável atribuído é diferente.")
            st.dataframe(df_divergent[[
                'numero_serie', 'modelo', 'responsavel_assetflow', 'responsavel_pulsus', 'ultimo_sync_pulsus'
            ]], use_container_width=True, hide_index=True)

        with tab_asset:
            st.info("Estes aparelhos estão no seu inventário (AssetFlow), mas não foram encontrados no MDM (Pulsus). Podem estar offline, desligados ou terem sido removidos do MDM.")
            st.dataframe(df_only_assetflow[[
                'numero_serie', 'modelo', 'nome_status', 'responsavel_assetflow'
            ]], use_container_width=True, hide_index=True)

        with tab_pulsus:
            st.info("Estes aparelhos foram encontrados no MDM (Pulsus), mas não estão cadastrados no seu inventário (AssetFlow).")
            st.dataframe(df_only_pulsus[[
                'numero_serie_pulsus', 'imei_pulsus', 'responsavel_pulsus', 'ultimo_sync_pulsus'
            ]], use_container_width=True, hide_index=True)

        with tab_sync:
            st.success("Estes aparelhos estão corretamente sincronizados entre os dois sistemas.")
            st.dataframe(df_sync[[
                'numero_serie', 'modelo', 'nome_status', 'responsavel_assetflow'
            ]], use_container_width=True, hide_index=True)
