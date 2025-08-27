import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import json
from auth import show_login_form

# --- Verificação de Autenticação ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

# --- Configuração de Layout (Header, Footer e CSS) ---
st.set_page_config(layout="wide", page_title="AssetFlow - Devoluções")

st.markdown("""
<style>
    /* Estilos da Logo */
    .logo-text {
        font-family: 'Courier New', monospace;
        font-size: 28px;
        font-weight: bold;
        padding-top: 20px;
    }
    /* Cor para o tema claro (padrão) */
    .logo-asset { color: #003366; }
    .logo-flow { color: #E30613; }

    /* Cor para o tema escuro (usando media query) */
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
        from auth import logout
        logout()

    # Footer (Ícones agora no fundo da barra lateral)
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


# --- Funções de Banco de Dados ---

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect('inventario.db')
    conn.row_factory = sqlite3.Row
    return conn

def carregar_aparelhos_em_uso():
    """Carrega apenas os aparelhos que estão atualmente com status 'Em uso'."""
    conn = get_db_connection()
    aparelhos = conn.execute("""
        SELECT
            a.id as aparelho_id,
            a.numero_serie,
            mo.nome_modelo,
            ma.nome_marca,
            c.id as colaborador_id,
            c.nome_completo as colaborador_nome
        FROM aparelhos a
        JOIN historico_movimentacoes h ON a.id = h.aparelho_id
        JOIN (
            SELECT aparelho_id, MAX(data_movimentacao) as max_data
            FROM historico_movimentacoes
            GROUP BY aparelho_id
        ) hm ON h.aparelho_id = hm.aparelho_id AND h.data_movimentacao = hm.max_data
        JOIN colaboradores c ON h.colaborador_id = c.id
        JOIN status s ON a.status_id = s.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        WHERE s.nome_status = 'Em uso'
        ORDER BY c.nome_completo
    """).fetchall()
    conn.close()
    return aparelhos

def processar_devolucao(aparelho_id, colaborador_id, checklist_data, destino_final, observacoes):
    """Processa a devolução, atualiza status e integra-se com a manutenção se necessário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")

        id_colaborador_final = None
        localizacao = ""
        
        if destino_final == "Devolver ao Estoque":
            novo_status_nome = "Em estoque"
            localizacao = "Estoque Interno"
        elif destino_final == "Enviar para Manutenção":
            novo_status_nome = "Em manutenção"
            id_colaborador_final = colaborador_id # Mantém o vínculo para o registo da manutenção
            localizacao = "Triagem Manutenção"
        else: # Baixar/Inutilizar
            novo_status_nome = "Baixado/Inutilizado"
            localizacao = "Descarte"

        novo_status_id = cursor.execute("SELECT id FROM status WHERE nome_status = ?", (novo_status_nome,)).fetchone()[0]
        checklist_json = json.dumps(checklist_data)

        # 1. Insere o novo registo no histórico com os detalhes da devolução
        # O colaborador_id aqui é o responsável pela movimentação, não necessariamente o novo dono.
        # Para devoluções, o novo dono é "Nenhum" (NULL), exceto para manutenção.
        cursor.execute("""
            INSERT INTO historico_movimentacoes 
            (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, checklist_devolucao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now(), aparelho_id, None, novo_status_id, localizacao, observacoes, checklist_json))

        # 2. Atualiza o status principal do aparelho
        cursor.execute("UPDATE aparelhos SET status_id = ? WHERE id = ?", (novo_status_id, aparelho_id))

        # 3. INTEGRAÇÃO: Se o destino for manutenção, abre uma O.S. preliminar
        if destino_final == "Enviar para Manutenção":
            cursor.execute("""
                INSERT INTO manutencoes (aparelho_id, colaborador_id_no_envio, data_envio, defeito_reportado, status_manutencao)
                VALUES (?, ?, ?, ?, ?)
            """, (aparelho_id, colaborador_id, date.today(), observacoes, 'Em Andamento'))

        conn.commit()
        st.success(f"Devolução processada com sucesso! Novo status do aparelho: {novo_status_nome}.")
        
        if destino_final == "Enviar para Manutenção":
            st.info("Uma Ordem de Serviço preliminar foi aberta. Aceda à página 'Manutenções' para adicionar o fornecedor e outros detalhes.")
        
        return True

    except Exception as e:
        conn.rollback()
        st.error(f"Ocorreu um erro ao processar a devolução: {e}")
        return False
    finally:
        conn.close()

def carregar_historico_devolucoes(start_date=None, end_date=None):
    """Carrega o histórico de devoluções, identificando o colaborador que devolveu."""
    conn = get_db_connection()
    
    query = """
        SELECT
            h.id,
            h.data_movimentacao,
            ma.nome_marca || ' ' || mo.nome_modelo AS aparelho,
            a.numero_serie,
            -- Subconsulta para obter o nome do colaborador do registo anterior (quem efetivamente devolveu)
            (SELECT c_prev.nome_completo 
             FROM historico_movimentacoes h_prev
             JOIN colaboradores c_prev ON h_prev.colaborador_id = c_prev.id
             WHERE h_prev.aparelho_id = h.aparelho_id 
               AND h_prev.data_movimentacao < h.data_movimentacao
             ORDER BY h_prev.data_movimentacao DESC
             LIMIT 1) AS colaborador_devolveu,
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
            h.checklist_devolucao IS NOT NULL AND h.checklist_devolucao != ''
    """
    
    params = []
    conditions = []

    if start_date:
        conditions.append("date(h.data_movimentacao) >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date(h.data_movimentacao) <= ?")
        params.append(end_date)

    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += " ORDER BY h.data_movimentacao DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Processa o JSON do checklist para ser mais legível
    if not df.empty and 'checklist_devolucao' in df.columns:
        df['checklist_detalhes'] = df['checklist_devolucao'].apply(
            lambda x: json.loads(x) if x and x.strip() else {}
        )
    
    return df

# --- Interface Principal ---
st.title("Fluxo de Devolução e Triagem")
st.markdown("---")

# --- Criação das Abas ---
tab1, tab2 = st.tabs(["Registrar Devolução", "Histórico de Devoluções"])

# --- Aba 1: Formulário de Devolução ---
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

                submitted = st.form_submit_button("Processar Devolução")
                if submitted:
                    if processar_devolucao(aparelho_id, colaborador_id, checklist_data, destino_final, observacoes):
                        st.success("Operação concluída!")
                        # Não é necessário st.rerun() aqui, o Streamlit já atualiza a página após o sucesso.
                        
# --- Aba 2: Histórico de Devoluções ---
with tab2:
    st.subheader("Histórico Completo de Devoluções")
    
    # --- Filtros ---
    st.markdown("###### Filtros do Histórico")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Período de:", value=None, format="DD/MM/YYYY", key="hist_start")
    with col2:
        data_fim = st.date_input("Até:", value=None, format="DD/MM/YYYY", key="hist_end")

    # --- Carregar e Exibir Dados ---
    historico_df = carregar_historico_devolucoes(start_date=data_inicio, end_date=data_fim)
    
    if historico_df.empty:
        st.warning("Nenhum registro de devolução encontrado para os filtros selecionados.")
    else:
        # Prepara o dataframe para exibição, removendo colunas técnicas
        df_para_exibir = historico_df.drop(columns=['id', 'checklist_devolucao', 'checklist_detalhes']).copy()
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
        st.dataframe(df_para_exibir, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("##### Detalhes do Checklist da Devolução")

        # Cria uma lista de opções para o selectbox para identificar unicamente cada linha
        opcoes_detalhe = [f"ID {row['id']}: {row['data_movimentacao']} - {row['aparelho']} (Devolvido por: {row['colaborador_devolveu'] or 'N/A'})" 
                          for index, row in historico_df.iterrows()]
        
        linha_selecionada_str = st.selectbox(
            "Selecione uma devolução para ver os detalhes do checklist:", 
            options=opcoes_detalhe, 
            index=None, 
            placeholder="Escolha um registro da lista..."
        )

        if linha_selecionada_str:
            # Extrai o ID do início da string para encontrar a linha correta
            selected_id = int(linha_selecionada_str.split(':')[0].replace('ID ', ''))
            
            # Filtra o DataFrame original para encontrar a linha correspondente ao ID
            linha_selecionada_data = historico_df[historico_df['id'] == selected_id].iloc[0]
            
            checklist_info = linha_selecionada_data['checklist_detalhes']
            
            if isinstance(checklist_info, dict) and checklist_info:
                # Transforma o dicionário do checklist num DataFrame para uma exibição mais limpa
                checklist_items = []
                for item, details in checklist_info.items():
                    entregue_status = "Sim" if details.get('entregue', False) else "Não"
                    estado_status = details.get('estado', 'N/A')
                    checklist_items.append({"Item": item, "Entregue": entregue_status, "Estado": estado_status})
                
                st.table(pd.DataFrame(checklist_items))
            else:
                st.info("Não há detalhes de checklist registados para esta devolução.")

