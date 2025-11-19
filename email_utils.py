import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
from auth import show_login_form, logout
from sqlalchemy import text
# ATENÇÃO: Adicionamos 'montar_layout_base' à importação
from email_utils import enviar_email, montar_layout_base 

# --- Verificação de Autenticação ---
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
        logout()
    st.markdown("---")
    # Adicione o footer da barra lateral se desejar

# --- Funções de Banco de Dados ---
def get_db_connection():
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=30)
def carregar_aparelhos_em_uso():
    conn = get_db_connection()
    # Query ajustada para buscar também marca_id e modelo_id
    query = """
        WITH UltimaMovimentacao AS (
            SELECT
                h.aparelho_id, h.colaborador_id,
                ROW_NUMBER() OVER(PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao DESC) as rn
            FROM historico_movimentacoes h
        )
        SELECT
            a.id as aparelho_id, a.numero_serie, 
            mo.id as modelo_id, mo.nome_modelo, 
            ma.id as marca_id, ma.nome_marca,
            c.id as colaborador_id, c.nome_completo as colaborador_nome, c.codigo as colaborador_codigo, s.nome_setor as colaborador_setor
        FROM aparelhos a
        JOIN status st ON a.status_id = st.id
        LEFT JOIN UltimaMovimentacao um ON a.id = um.aparelho_id AND um.rn = 1
        LEFT JOIN colaboradores c ON um.colaborador_id = c.id
        LEFT JOIN setores s ON c.setor_id = s.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        WHERE st.nome_status = 'Em uso' AND c.id IS NOT NULL AND c.status = 'Ativo' -- Garante que o colaborador está ativo
        ORDER BY c.nome_completo;
    """
    df = conn.query(query)
    return df.to_dict('records')

def processar_devolucao(aparelho_id, colaborador_id, nome_colaborador_devolveu, checklist_data, destino_final, observacoes):
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.begin()
            localizacao = ""
            data_movimentacao_atual = datetime.now() # Guarda a data exata
            
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

            query_hist = text("""
                INSERT INTO historico_movimentacoes 
                (data_movimentacao, aparelho_id, colaborador_id, status_id, localizacao_atual, observacoes, checklist_devolucao, colaborador_snapshot)
                VALUES (:data, :ap_id, NULL, :status_id, :loc, :obs, :checklist, :col_snap)
            """)
            s.execute(query_hist, {
                "data": data_movimentacao_atual, "ap_id": aparelho_id, "status_id": novo_status_id,
                "loc": localizacao, "obs": observacoes, "checklist": checklist_json, 
                "col_snap": nome_colaborador_devolveu
            })

            s.execute(text("UPDATE aparelhos SET status_id = :status_id WHERE id = :ap_id"), 
                      {"status_id": novo_status_id, "ap_id": aparelho_id})

            if destino_final == "Enviar para Manutenção":
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
            
            # Retorna dados úteis para o e-mail
            return True, novo_status_nome, data_movimentacao_atual
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar a devolução: {e}")
        return False, None, None


@st.cache_data(ttl=30)
def carregar_historico_devolucoes(start_date=None, end_date=None, ns_search=None, colaborador_search=None):
    conn = get_db_connection()
    # --- Query Aprimorada ---
    # Busca mais dados para permitir o reenvio do e-mail com informações completas
    query = """
        WITH HistoricoComNomePrevio AS (
            SELECT
                h.id, h.data_movimentacao, h.aparelho_id, h.status_id, h.localizacao_atual,
                h.observacoes, h.checklist_devolucao, h.colaborador_snapshot,
                LAG(h.colaborador_id) OVER (PARTITION BY h.aparelho_id ORDER BY h.data_movimentacao) as prev_colaborador_id
            FROM historico_movimentacoes h
        )
        SELECT
            h_prev.id, h_prev.data_movimentacao,
            ma.nome_marca, mo.nome_modelo,
            a.numero_serie,
            h_prev.colaborador_snapshot AS colaborador_devolveu,
            c.codigo as colaborador_codigo,
            s_colab.nome_setor as colaborador_setor,
            s_ap.nome_status AS destino_final,
            h_prev.localizacao_atual, h_prev.observacoes, h_prev.checklist_devolucao
        FROM HistoricoComNomePrevio h_prev
        JOIN aparelhos a ON h_prev.aparelho_id = a.id
        JOIN status s_ap ON h_prev.status_id = s_ap.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        LEFT JOIN colaboradores c ON h_prev.prev_colaborador_id = c.id
        LEFT JOIN setores s_colab ON c.setor_id = s_colab.id
    """
    params = {}
    conditions = ["h_prev.checklist_devolucao IS NOT NULL"] # Condição base para ser uma devolução

    if start_date:
        conditions.append("CAST(h_prev.data_movimentacao AS DATE) >= :start_date")
        params['start_date'] = start_date
    if end_date:
        conditions.append("CAST(h_prev.data_movimentacao AS DATE) <= :end_date")
        params['end_date'] = end_date
    if ns_search:
        conditions.append("a.numero_serie ILIKE :ns_search")
        params['ns_search'] = f"%{ns_search}%"
    if colaborador_search:
        conditions.append("h_prev.colaborador_snapshot ILIKE :colab_search")
        params['colab_search'] = f"%{colaborador_search}%"

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY h_prev.data_movimentacao DESC"
    
    df = conn.query(query, params=params)
    
    if not df.empty:
        # Cria a coluna 'aparelho' para exibição
        df['aparelho'] = df['nome_marca'] + ' ' + df['nome_modelo']
        # Processa o JSON do checklist
        df['checklist_detalhes'] = df['checklist_devolucao'].apply(
            lambda x: json.loads(x) if isinstance(x, str) and x.strip() else (x if isinstance(x, dict) else {})
        )
    return df

# --- FUNÇÃO ATUALIZADA: Usando montar_layout_base ---
def gerar_conteudo_email_devolucao(dados_aparelho, checklist_data, destino_final, observacoes, data_devolucao):
    assunto = f"Devolução do aparelho - {dados_aparelho.get('colaborador_nome', 'N/A')}"

    # Monta as linhas da tabela de checklist em HTML
    checklist_rows = ""
    if isinstance(checklist_data, dict):
        for item, details in checklist_data.items():
            entregue = "Sim" if details.get('entregue', False) else "Não"
            estado = details.get('estado', 'N/A')
            checklist_rows += f"""
            <tr>
                <td style="padding: 6px; border-bottom: 1px solid #eeeeee; font-family: Arial, sans-serif; font-size: 13px; color: #333;">{item}</td>
                <td style="padding: 6px; border-bottom: 1px solid #eeeeee; font-family: Arial, sans-serif; font-size: 13px; color: #333;">{entregue}</td>
                <td style="padding: 6px; border-bottom: 1px solid #eeeeee; font-family: Arial, sans-serif; font-size: 13px; color: #333;">{estado}</td>
            </tr>
            """

    checklist_html_table = f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
        <thead>
            <tr bgcolor="#f2f2f2">
                <th align="left" style="padding: 8px; border-bottom: 2px solid #cccccc; font-family: Arial, sans-serif; font-size: 13px; color: #333;">Item</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #cccccc; font-family: Arial, sans-serif; font-size: 13px; color: #333;">Entregue</th>
                <th align="left" style="padding: 8px; border-bottom: 2px solid #cccccc; font-family: Arial, sans-serif; font-size: 13px; color: #333;">Estado</th>
            </tr>
        </thead>
        <tbody>
            {checklist_rows}
        </tbody>
    </table>
    """

    # Constrói o "miolo" do e-mail que será injetado no template base
    # Usamos tabelas em vez de divs e margins para compatibilidade com Outlook
    miolo_html = f"""
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; padding-bottom: 5px; border-bottom: 2px solid #003366;">
            Relatório de Devolução de Ativo
        </td>
    </tr>
    <tr><td height="15" style="font-size:0px; line-height:0px;">&nbsp;</td></tr>
    
    <tr>
        <td style="font-family: Arial, sans-serif; font-size: 14px; color: #333333;">
            <strong>Data da Devolução:</strong> {data_devolucao.strftime('%d/%m/%Y %H:%M')}
        </td>
    </tr>
    <tr><td height="25" style="font-size:0px; line-height:0px;">&nbsp;</td></tr>

    <!-- Seção Colaborador -->
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; padding-bottom: 5px;">
            Dados do Colaborador
        </td>
    </tr>
    <tr>
        <td style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.6;">
            <strong>Nome Completo:</strong> {dados_aparelho.get('colaborador_nome', 'N/A')}<br/>
            <strong>Código:</strong> {dados_aparelho.get('colaborador_codigo', 'N/A')}<br/>
            <strong>Função (Setor):</strong> {dados_aparelho.get('colaborador_setor', 'N/A')}
        </td>
    </tr>
    <tr><td height="20" style="font-size:0px; line-height:0px;">&nbsp;</td></tr>

    <!-- Seção Aparelho -->
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; padding-bottom: 5px;">
            Dados do Aparelho
        </td>
    </tr>
    <tr>
        <td style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.6;">
            <strong>Aparelho:</strong> {dados_aparelho.get('nome_marca', '')} {dados_aparelho.get('nome_modelo', '')}<br/>
            <strong>N°/S do Aparelho:</strong> {dados_aparelho.get('numero_serie', 'N/A')}
        </td>
    </tr>
    <tr><td height="20" style="font-size:0px; line-height:0px;">&nbsp;</td></tr>

    <!-- Seção Informações -->
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; padding-bottom: 5px;">
            Informações da Devolução
        </td>
    </tr>
    <tr>
        <td style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.6;">
            <strong>Destino Final do Aparelho:</strong> {destino_final}<br/>
            <strong>Observações:</strong> {observacoes if observacoes else 'Nenhuma observação registada.'}
        </td>
    </tr>
    <tr><td height="20" style="font-size:0px; line-height:0px;">&nbsp;</td></tr>

    <!-- Seção Checklist -->
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; padding-bottom: 10px;">
            Detalhes do Checklist da Devolução
        </td>
    </tr>
    <tr>
        <td>
            {checklist_html_table}
        </td>
    </tr>
    """
    
    # Usa a função base para envolver o miolo na estrutura compatível com Outlook
    html_completo = montar_layout_base(assunto, miolo_html)

    # Texto puro como fallback
    corpo_texto = f"""
    Relatório de Devolução de Ativo

    Data da Devolução: {data_devolucao.strftime('%d/%m/%Y %H:%M')}

    Dados do Colaborador:
    Nome Completo: {dados_aparelho.get('colaborador_nome', 'N/A')}
    Código: {dados_aparelho.get('colaborador_codigo', 'N/A')}
    Função (Setor): {dados_aparelho.get('colaborador_setor', 'N/A')}

    Dados do Aparelho:
    Aparelho: {dados_aparelho.get('nome_marca', '')} {dados_aparelho.get('nome_modelo', '')}
    N°/S do Aparelho: {dados_aparelho.get('numero_serie', 'N/A')}

    Informações da Devolução:
    Destino Final do Aparelho: {destino_final}
    Observações: {observacoes if observacoes else 'Nenhuma observação registada.'}

    Checklist: (Ver e-mail em HTML para tabela formatada)
    """
    
    return assunto, html_completo, corpo_texto

# --- Interface Principal ---
st.title("Fluxo de Devolução e Triagem")
st.markdown("---")

try:
    option = st.radio(
        "Selecione a operação:",
        ("Registar Devolução", "Histórico de Devoluções"),
        horizontal=True,
        label_visibility="collapsed",
        key="devolucoes_tab_selector"
    )
    st.markdown("---")

    # --- Lógica para controlar a exibição do formulário de e-mail ---
    if 'devolucao_concluida' not in st.session_state:
        st.session_state.devolucao_concluida = False
    
    if option == "Registar Devolução":
        # Se a devolução NÃO foi concluída, mostra o formulário normal
        if not st.session_state.devolucao_concluida:
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
                    
                    st.markdown("---")
                    st.subheader("2. Realize a Inspeção e Decida o Destino Final")
                    with st.form("form_devolucao"):
                        st.markdown("##### Checklist de Devolução")
                        
                        checklist_data_input = {}
                        itens_checklist = ["Tela", "Carcaça", "Bateria", "Botões", "USB", "Chip", "Carregador", "Cabo USB", "Capa", "Película"]
                        opcoes_estado = ["Bom", "Riscado", "Quebrado", "Faltando", "Permanece"]
                        
                        cols = st.columns(2)
                        for i, item in enumerate(itens_checklist):
                            with cols[i % 2]:
                                entregue = st.checkbox(f"{item}", value=True, key=f"entregue_{item}_{aparelho_selecionado_data['aparelho_id']}")
                                estado = st.selectbox(f"Estado de {item}", options=opcoes_estado, key=f"estado_{item}_{aparelho_selecionado_data['aparelho_id']}", label_visibility="collapsed")
                                checklist_data_input[item] = {'entregue': entregue, 'estado': estado}
                        
                        observacoes_input = st.text_area("Observações Gerais da Devolução", placeholder="Ex: Tela com risco profundo no canto superior direito.")
                        
                        st.markdown("---")
                        st.markdown("##### Destino Final do Aparelho")
                        destino_final_input = st.radio(
                            "Selecione o destino do aparelho após a inspeção:",
                            ["Devolver ao Estoque", "Enviar para Manutenção", "Baixar/Inutilizado"],
                            horizontal=True, key="destino_final"
                        )

                        submitted = st.form_submit_button("Processar Devolução", use_container_width=True, type="primary")
                        if submitted:
                            sucesso, novo_status, data_mov = processar_devolucao(
                                aparelho_selecionado_data['aparelho_id'], 
                                aparelho_selecionado_data['colaborador_id'], 
                                aparelho_selecionado_data['colaborador_nome'], 
                                checklist_data_input, 
                                destino_final_input, 
                                observacoes_input
                            )
                            if sucesso:
                                st.session_state.devolucao_concluida = True
                                # Guarda os dados necessários para o e-mail
                                st.session_state.email_data = {
                                    "dados_aparelho": aparelho_selecionado_data,
                                    "checklist_data": checklist_data_input,
                                    "destino_final": destino_final_input,
                                    "observacoes": observacoes_input,
                                    "data_devolucao": data_mov,
                                    "novo_status": novo_status
                                }
                                st.cache_data.clear()
                                st.rerun() # Recarrega para mostrar a secção de e-mail

        # Se a devolução FOI concluída, mostra a secção de e-mail opcional
        else:
            if 'email_data' in st.session_state:
                email_data = st.session_state.email_data
                st.success(f"Devolução processada com sucesso! Novo status do aparelho: {email_data['novo_status']}.")
                if email_data['destino_final'] == "Enviar para Manutenção":
                     st.info("Uma Ordem de Serviço preliminar foi aberta. Aceda à página 'Manutenções' para adicionar o fornecedor e outros detalhes.")

                st.markdown("---")
                st.subheader("3. Notificação por E-mail (Opcional)")
                
                enviar_agora = st.checkbox("Enviar e-mail de notificação desta devolução?")
                
                if enviar_agora:
                    destinatarios_str = st.text_area("Destinatários (separados por vírgula):", placeholder="exemplo1@email.com, exemplo2@email.com")
                    
                    if st.button("Enviar E-mail de Notificação", type="primary", use_container_width=True):
                        if destinatarios_str:
                            destinatarios_list = [email.strip() for email in destinatarios_str.split(',') if email.strip()]
                            if destinatarios_list:
                                with st.spinner("A gerar e enviar o e-mail..."):
                                    assunto, corpo_html, corpo_texto = gerar_conteudo_email_devolucao(
                                        email_data['dados_aparelho'], 
                                        email_data['checklist_data'], 
                                        email_data['destino_final'], 
                                        email_data['observacoes'],
                                        email_data['data_devolucao']
                                    )
                                    if enviar_email(destinatarios_list, assunto, corpo_html, corpo_texto):
                                        st.success("E-mail de notificação enviado com sucesso!")
                                        # Limpa o estado após o envio
                                        del st.session_state.email_data
                                        st.session_state.devolucao_concluida = False
                                        # Aguarda um pouco para o utilizador ver a mensagem antes de limpar
                                        st.write("A recarregar a página...")
                                        import time
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error("Falha ao enviar o e-mail.")
                            else:
                                st.warning("Por favor, insira pelo menos um endereço de e-mail válido.")
                        else:
                            st.warning("Por favor, insira os endereços de e-mail dos destinatários.")
                
                # Botão para concluir sem enviar e-mail
                if st.button("Concluir (sem enviar e-mail)", use_container_width=True):
                    del st.session_state.email_data
                    st.session_state.devolucao_concluida = False
                    st.rerun()

    elif option == "Histórico de Devoluções":
        st.subheader("Histórico Completo de Devoluções")
        
        st.markdown("<h6>Filtros do Histórico</h6>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Período de:", value=None, format="DD/MM/YYYY", key="hist_start")
            data_fim = st.date_input("Até:", value=None, format="DD/MM/YYYY", key="hist_end")
        with col2:
            ns_filtro = st.text_input("Pesquisar por N/S do Aparelho:")
            colaborador_filtro = st.text_input("Pesquisar por Colaborador (devolveu por):")
        historico_df = carregar_historico_devolucoes(
            start_date=data_inicio, 
            end_date=data_fim,
            ns_search=ns_filtro,
            colaborador_search=colaborador_filtro
        )
        
        if historico_df.empty:
            st.warning("Nenhum registo de devolução encontrado para os filtros selecionados.")
        else:
            df_para_exibir = historico_df.drop(columns=['id', 'checklist_devolucao', 'checklist_detalhes'], errors='ignore').copy()
            df_para_exibir.rename(columns={
                'data_movimentacao': 'Data da Devolução', 'aparelho': 'Aparelho',
                'numero_serie': 'N/S do Aparelho', 'colaborador_devolveu': 'Devolvido por',
                'destino_final': 'Destino Final', 'localizacao_atual': 'Localização Pós-Devolução',
                'observacoes': 'Observações'
            }, inplace=True)
            
            st.markdown("<h6>Resultados</h6>", unsafe_allow_html=True)
            st.dataframe(df_para_exibir, use_container_width=True, hide_index=True, column_config={
                "Data da Devolução": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
            })

            st.markdown("---")
            st.markdown("<h5>Detalhes do Checklist da Devolução</h5>", unsafe_allow_html=True)

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

                    # --- NOVA SECÇÃO DE REENVIO DE E-MAIL ---
                    st.markdown("---")
                    with st.expander("Reenviar Notificação por E-mail"):
                        with st.form(key=f"form_reenviar_{selected_id}", clear_on_submit=True):
                            destinatarios_str = st.text_area("Destinatários (separados por vírgula):", placeholder="exemplo1@email.com, exemplo2@email.com")
                            submit_reenvio = st.form_submit_button("Enviar E-mail", use_container_width=True)
                            
                            if submit_reenvio:
                                if destinatarios_str:
                                    destinatarios_list = [email.strip() for email in destinatarios_str.split(',') if email.strip()]
                                    if destinatarios_list:
                                        with st.spinner("A gerar e reenviar o e-mail..."):
                                            # Prepara o dicionário de dados do aparelho
                                            dados_aparelho_email = {
                                                'colaborador_nome': linha_selecionada_data['colaborador_devolveu'],
                                                'colaborador_codigo': linha_selecionada_data.get('colaborador_codigo', 'N/A'),
                                                'colaborador_setor': linha_selecionada_data.get('colaborador_setor', 'N/A'),
                                                'nome_marca': linha_selecionada_data['nome_marca'],
                                                'nome_modelo': linha_selecionada_data['nome_modelo'],
                                                'numero_serie': linha_selecionada_data['numero_serie']
                                            }
                                            
                                            assunto, corpo_html, corpo_texto = gerar_conteudo_email_devolucao(
                                                dados_aparelho_email,
                                                checklist_info,
                                                linha_selecionada_data['destino_final'],
                                                linha_selecionada_data['observacoes'],
                                                linha_selecionada_data['data_movimentacao']
                                            )
                                            
                                            if enviar_email(destinatarios_list, assunto, corpo_html, corpo_texto):
                                                st.success("E-mail de notificação reenviado com sucesso!")
                                            else:
                                                st.error("Falha ao reenviar o e-mail.")
                                    else:
                                        st.warning("Por favor, insira pelo menos um endereço de e-mail válido.")
                                else:
                                    st.warning("Por favor, insira os endereços de e-mail dos destinatários.")

                else:
                    st.info("Não há detalhes de checklist registados para esta devolução.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página de devoluções: {e}")
    st.info("Verifique se o banco de dados está a funcionar corretamente.")
