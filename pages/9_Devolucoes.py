import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
from auth import show_login_form
from sqlalchemy import text

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
    if st.button("Logout", key="devolucoes_logout"):
        from auth import logout
        logout()
    st.markdown("---")
    st.markdown(f"""
        <div class="sidebar-footer">
            <a href="https://github.com/caufreitxs026" target="_blank" title="GitHub"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/github.svg"></a>
            <a href="https://linkedin.com/in/cauafreitas" target="_blank" title="LinkedIn"><img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/brands/linkedin.svg"></a>
        </div>
        """, unsafe_allow_html=True)

# --- Funções de Banco de Dados ---
def get_db_connection():
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def carregar_aparelhos_em_uso():
    conn = get_db_connection()
    query = """
        WITH UltimaMovimentacao AS (
            SELECT
                h.aparelho_id,
                h.colaborador_id,
                ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
            FROM historico_movimentacoes h
        )
        SELECT
            a.id as aparelho_id,
            a.numero_serie,
            mo.nome_modelo,
            ma.nome_marca,
            c.id as colaborador_id,
            c.nome_completo as colaborador_nome
        FROM aparelhos a
        JOIN status s ON a.status_id = s.id
        LEFT JOIN UltimaMovimentacao um ON a.id = um.aparelho_id AND um.rn = 1
        LEFT JOIN colaboradores c ON um.colaborador_id = c.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        WHERE s.nome_status = 'Em uso' AND c.id IS NOT NULL
        ORDER BY c.nome_completo;
    """
    df = conn.query(query)
    return df.to_dict('records')

def processar_devolucao(aparelho_id, colaborador_id, nome_colaborador_devolveu, checklist_data, destino_final, observacoes):
    """Processa a devolução, atualiza status e integra-se com a manutenção se necessário."""
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            localizacao = ""
            
            if destino_final == "Devolver ao Estoque":
                novo_status_nome = "Em estoque"
                localizacao = "Estoque Interno"
            elif destino_final == "Enviar para Manutenção":
                novo_status_nome = "Em manutenção"
                localizacao = "Triagem Manutenção"
            else: # Baixar/Inutilizar
                novo_status_nome = "Baixado/Inutilizado"
                localizacao = "Descarte"

            novo_status_id = s.execute(text("SELECT id FROM status WHERE nome_status = :nome"), {"nome": novo_status_nome}).scalar_one()
            checklist_json = json.dumps(checklist_data)

            # Insere o novo registo no histórico com o snapshot do nome do colaborador que devolveu.
            query_hist = text("""
                INSERT INTO historico_movimentacoes 
                (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, checklist_devolucao, colaborador_snapshot)
                VALUES (:data, :ap_id, NULL, :status_id, :loc, :obs, :checklist, :col_snap)
            """)
            s.execute(query_hist, {
                "data": datetime.now(), "ap_id": aparelho_id, "status_id": novo_status_id,
                "loc": localizacao, "obs": observacoes, "checklist": checklist_json, 
                "col_snap": nome_colaborador_devolveu 
            })

            s.execute(text("UPDATE aparelhos SET status_id = :status_id WHERE id = :ap_id"), 
                      {"status_id": novo_status_id, "ap_id": aparelho_id})

            if destino_final == "Enviar para Manutenção":
                # Guarda o snapshot do nome na tabela de manutenções também
                query_manut = text("""
                    INSERT INTO manutencoes (aparelho_id, colaborador_id_no_envio, data_envio, defeito_reportado, status_manutencao, colaborador_snapshot)
                    VALUES (:ap_id, :col_id, :data, :defeito, 'Em Andamento', :col_snap)
                """)
                s.execute(query_manut, {
                    "ap_id": aparelho_id, "col_id": colaborador_id, 
                    "data": date.today(), "defeito": observacoes,
                    "col_snap": nome_colaborador_devolveu
                })

            s.commit()
            st.success(f"Devolução processada com sucesso! Novo status do aparelho: {novo_status_nome}.")
            
            if destino_final == "Enviar para Manutenção":
                st.info("Uma Ordem de Serviço preliminar foi aberta. Aceda à página 'Manutenções' para adicionar o fornecedor e outros detalhes.")
            
            return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar a devolução: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_historico_devolucoes(start_date=None, end_date=None):
    """Carrega o histórico de devoluções, usando o nome do colaborador guardado no momento da devolução."""
    conn = get_db_connection()
    
    # --- LÓGICA ATUALIZADA ---
    # A query agora é muito mais simples e correta, lendo diretamente do snapshot.
    query = """
        SELECT
            h.id,
            h.data_movimentacao,
            ma.nome_marca || ' ' || mo.nome_modelo AS aparelho,
            a.numero_serie,
            h.colaborador_snapshot AS colaborador_devolveu, -- Usa o nome guardado no momento
            s.nome_status AS destino_final,
            h.localizacao_atual,
            h.observacoes,
            h.checklist_devolucao
        FROM historico_movimentacoes h
        JOIN aparelhos a ON h.aparelho_id = a.id
        JOIN status s ON h.status_id = s.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        WHERE 
            h.checklist_devolucao IS NOT NULL
    """
    
    params = {}
    conditions = []

    if start_date:
        conditions.append("CAST(h.data_movimentacao AS DATE) >= :start_date")
        params['start_date'] = start_date
    if end_date:
        conditions.append("CAST(h.data_movimentacao AS DATE) <= :end_date")
        params['end_date'] = end_date

    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += " ORDER BY h.data_movimentacao DESC"
    
    df = conn.query(query, params=params)
    
    if not df.empty and 'checklist_devolucao' in df.columns:
        df['checklist_detalhes'] = df['checklist_devolucao'].apply(
            lambda x: json.loads(x) if isinstance(x, str) and x.strip() else (x if isinstance(x, dict) else {})
        )
    
    return df

# --- Interface Principal ---
st.title("Fluxo de Devolução e Triagem")
st.markdown("---")

try:
    tab1, tab2 = st.tabs(["Registar Devolução", "Histórico de Devoluções"])

    with tab1:
        st.subheader("1. Selecione o Aparelho a Ser Devolvido")
        aparelhos_em_uso = carregar_aparelhos_em_uso()

        if not aparelhos_em_uso:
            st.info("Não há aparelhos com o status 'Em uso' para serem devolvidos no momento.")
        else:
            aparelhos_dict = {
                f"{ap['colaborador_nome']} - {ap['nome_marca']} {ap['nome_modelo']} (S/N: {ap['numero_serie']})": ap
                for ap in aparelhos_em_uso
            }
            
            aparelho_selecionado_str = st.selectbox(
                "Selecione o aparelho e colaborador:",
                options=list(aparelhos_dict.keys()),
                index=None,
                placeholder="Clique ou digite para pesquisar...",
                key="sb_aparelho_devolucao"
            )
            
            if aparelho_selecionado_str:
                aparelho_selecionado_data = aparelhos_dict[aparelho_selecionado_str]
                aparelho_id = aparelho_selecionado_data['aparelho_id']
                colaborador_id = aparelho_selecionado_data['colaborador_id']
                colaborador_nome = aparelho_selecionado_data['colaborador_nome'] # Captura o nome para o snapshot

                st.markdown("---")

                st.subheader("2. Realize a Inspeção e Decida o Destino Final")
                with st.form("form_devolucao"):
                    st.markdown("##### Checklist de Devolução")
                    
                    checklist_data = {}
                    itens_checklist = ["Tela", "Carcaça", "Bateria", "Botões", "USB", "Chip", "Carregador", "Cabo USB", "Capa", "Película"]
                    opcoes_estado = ["Bom", "Riscado", "Quebrado", "Faltando"]
                    
                    cols = st.columns(2)
                    for i, item in enumerate(itens_checklist):
                        with cols[i % 2]:
                            entregue = st.checkbox(f"{item}", value=True, key=f"entregue_{item}")
                            estado = st.selectbox(f"Estado de {item}", options=opcoes_estado, key=f"estado_{item}", label_visibility="collapsed")
                            checklist_data[item] = {'entregue': entregue, 'estado': estado}
                    
                    observacoes = st.text_area("Observações Gerais da Devolução", placeholder="Ex: Tela com risco profundo no canto superior direito.")
                    
                    st.markdown("---")
                    st.markdown("##### Destino Final do Aparelho")
                    destino_final = st.radio(
                        "Selecione o destino do aparelho após a inspeção:",
                        ["Devolver ao Estoque", "Enviar para Manutenção", "Baixar/Inutilizado"],
                        horizontal=True,
                        key="destino_final"
                    )

                    submitted = st.form_submit_button("Processar Devolução", use_container_width=True)
                    if submitted:
                        # Passa o nome do colaborador para a função de processamento
                        if processar_devolucao(aparelho_id, colaborador_id, colaborador_nome, checklist_data, destino_final, observacoes):
                            st.cache_data.clear()
                            st.rerun()

    with tab2:
        st.subheader("Histórico Completo de Devoluções")
        
        st.markdown("###### Filtros do Histórico")
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Período de:", value=None, format="DD/MM/YYYY", key="hist_start")
        with col2:
            data_fim = st.date_input("Até:", value=None, format="DD/MM/YYYY", key="hist_end")

        historico_df = carregar_historico_devolucoes(start_date=data_inicio, end_date=data_fim)
        
        if historico_df.empty:
            st.warning("Nenhum registo de devolução encontrado para os filtros selecionados.")
        else:
            df_para_exibir = historico_df.drop(columns=['id', 'checklist_devolucao', 'checklist_detalhes'], errors='ignore').copy()
            df_para_exibir.rename(columns={
                'data_movimentacao': 'Data da Devolução',
                'aparelho': 'Aparelho',
                'numero_serie': 'N/S do Aparelho',
                'colaborador_devolveu': 'Devolvido por',
                'destino_final': 'Destino Final',
                'localizacao_atual': 'Localização Pós-Devolução',
                'observacoes': 'Observações'
            }, inplace=True)
            
            st.markdown("###### Resultados")
            st.dataframe(df_para_exibir, use_container_width=True, hide_index=True, column_config={
                "Data da Devolução": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
            })

            st.markdown("---")
            st.markdown("##### Detalhes do Checklist da Devolução")

            opcoes_detalhe = [
                f"ID {row['id']}: {pd.to_datetime(row['data_movimentacao']).strftime('%d/%m/%Y %H:%M')} - {row['aparelho']} (Devolvido por: {row['colaborador_devolveu'] or 'N/A'})" 
                for index, row in historico_df.iterrows()
            ]
            
            linha_selecionada_str = st.selectbox(
                "Selecione uma devolução para ver os detalhes do checklist:", 
                options=opcoes_detalhe, 
                index=None, 
                placeholder="Escolha um registro da lista..."
            )

            if linha_selecionada_str:
                selected_id = int(linha_selecionada_str.split(':')[0].replace('ID ', ''))
                
                linha_selecionada_data = historico_df[historico_df['id'] == selected_id].iloc[0]
                
                checklist_info = linha_selecionada_data.get('checklist_detalhes', {})
                
                if isinstance(checklist_info, dict) and checklist_info:
                    checklist_items = []
                    for item, details in checklist_info.items():
                        entregue_status = "Sim" if details.get('entregue', False) else "Não"
                        estado_status = details.get('estado', 'N/A')
                        checklist_items.append({"Item": item, "Entregue": entregue_status, "Estado": estado_status})
                    
                    st.table(pd.DataFrame(checklist_items))
                else:
                    st.info("Não há detalhes de checklist registados para esta devolução.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de devoluções: {e}")
    st.info("Se esta é a primeira configuração, por favor, vá até a página '⚙️ Configurações' e clique em 'Inicializar Banco de Dados' para criar as tabelas necessárias.")

