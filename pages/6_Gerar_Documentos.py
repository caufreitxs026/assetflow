import streamlit as st
import pandas as pd
from datetime import datetime
from auth import show_login_form, logout
from sqlalchemy import text
from weasyprint import HTML, CSS

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
    if st.button("Logout", key="sidebar_logout_button"):
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

# --- Funções do DB e Auxiliares ---
def get_db_connection():
    return st.connection("supabase", type="sql")

@st.cache_data(ttl=3600)
def carregar_logo_base64():
    """Lê a string Base64 da logo a partir de um ficheiro para manter o código limpo."""
    try:
        with open("logo.b64", "r") as f:
            return f.read()
    except FileNotFoundError:
        st.error("Ficheiro 'logo.b64' não encontrado. Por favor, crie o ficheiro com o código Base64 da sua logo.")
        return ""

@st.cache_data(ttl=30)
def carregar_movimentacoes_entrega():
    conn = get_db_connection()
    query = """
        WITH LatestMovements AS (
            SELECT
                aparelho_id,
                MAX(data_movimentacao) as last_move_date
            FROM
                historico_movimentacoes
            GROUP BY
                aparelho_id
        )
        SELECT
            h.id, h.data_movimentacao, a.numero_serie, c.nome_completo
        FROM historico_movimentacoes h
        JOIN LatestMovements lm ON h.aparelho_id = lm.aparelho_id AND h.data_movimentacao = lm.last_move_date
        JOIN aparelhos a ON h.aparelho_id = a.id
        JOIN status s ON a.status_id = s.id
        LEFT JOIN colaboradores c ON h.colaborador_id = c.id
        WHERE s.nome_status = 'Em uso' AND c.id IS NOT NULL AND c.status = 'Ativo'
        ORDER BY h.data_movimentacao DESC;
    """
    df = conn.query(query)
    return df.to_dict('records')

@st.cache_data(ttl=30)
def buscar_dados_completos(mov_id):
    conn = get_db_connection()
    query = """
        SELECT
            c.nome_completo, c.cpf, s.nome_setor, c.gmail, c.codigo as codigo_colaborador,
            ma.nome_marca, mo.nome_modelo, a.imei1, a.imei2, a.numero_serie,
            h.id as protocolo, h.data_movimentacao
        FROM historico_movimentacoes h
        JOIN colaboradores c ON h.colaborador_id = c.id
        JOIN setores s ON c.setor_id = s.id
        JOIN aparelhos a ON h.aparelho_id = a.id
        JOIN modelos mo ON a.modelo_id = mo.id
        JOIN marcas ma ON mo.marca_id = ma.id
        WHERE h.id = :mov_id;
    """
    result_df = conn.query(query, params={"mov_id": mov_id})
    return result_df.to_dict('records')[0] if not result_df.empty else None

@st.cache_data(ttl=60)
def carregar_setores_nomes():
    conn = get_db_connection()
    df = conn.query("SELECT nome_setor FROM setores ORDER BY nome_setor;")
    return df['nome_setor'].tolist()


def gerar_pdf_termo(dados, checklist_data, logo_string):
    """Gera o PDF do Termo de Responsabilidade a partir de um template HTML."""
    
    data_mov = dados.get('data_movimentacao')
    if isinstance(data_mov, str):
        try:
            data_formatada = datetime.strptime(data_mov, '%d/%m/%Y %H:%M').strftime('%d/%m/%Y %H:%M')
        except ValueError:
            data_formatada = data_mov 
    elif isinstance(data_mov, datetime):
        data_formatada = data_mov.strftime('%d/%m/%Y %H:%M')
    else:
        data_formatada = "N/A"
    
    dados['data_movimentacao_formatada'] = data_formatada

    checklist_html = ""
    for item, detalhes in checklist_data.items():
        entregue_str = 'SIM' if detalhes['entregue'] else 'NÃO'
        estado_str = detalhes['estado']
        checklist_html += f"<tr><td>{item}</td><td>{entregue_str}</td><td>{estado_str}</td></tr>"

    texto_termos_resumido = """
    Declaro receber o equipamento descrito para uso profissional, sendo responsável pela sua guarda e conservação. 
    Comprometo-me a devolvê-lo nas mesmas condições em que o recebi. Danos por mau uso serão de minha responsabilidade 
    (Art. 462, § 1º da CLT). Autorizo o uso dos meus dados para este fim, de acordo com a LGPD.
    """

    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 1cm; }}
            body {{ font-family: Arial, sans-serif; font-size: 10pt; line-height: 1.3; color: #333; }}
            
            .header {{ 
                text-align: center; 
                margin-bottom: 20px;
                padding-top: 40px;
            }}
            h1 {{ color: #003366; font-size: 16pt; margin: 0; }}

            .logo {{
                position: absolute;
                top: 0cm;
                left: 0.2cm; 
                width: 150px; 
            }}
            
            .section {{ margin-bottom: 8px; }}
            .section-title {{ background-color: #003366; color: white; padding: 4px 8px; font-weight: bold; font-size: 11pt; border-radius: 4px;}}
            
            .info-table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
            .info-table td {{ padding: 3px; border: none; }}
            .info-table td:first-child {{ font-weight: bold; width: 25%; }}
            
            .checklist-table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
            .checklist-table th, .checklist-table td {{ border-bottom: 1px solid #ddd; padding: 4px; text-align: left; }}
            .checklist-table th {{ background-color: #f2f2f2; text-align: center; border-bottom: 2px solid #ccc;}}
            .checklist-table td:nth-child(2), .checklist-table td:nth-child(3) {{ text-align: center; }}
            
            .disclaimer {{ font-size: 8pt; text-align: justify; margin-top: 5px; padding: 0 5px; }}
            
            .signature {{ margin-top: 95px; text-align: center; }} 
            .signature-line {{ border-top: 1px solid #000; width: 350px; margin: 0 auto; padding-top: 5px; }}
        </style>
    </head>
    <body>
        <img src="{logo_string}" class="logo">
        <div class="header">
            <h1>TERMO DE RESPONSABILIDADE</h1>
        </div>
        <div class="section">
            <div class="section-title">DADOS DA MOVIMENTAÇÃO</div>
            <table class="info-table">
                <tr><td>CÓDIGO:</td><td>{dados.get('codigo_colaborador', '')}</td></tr>
                <tr><td>DATA:</td><td>{dados.get('data_movimentacao_formatada', '')}</td></tr>
            </table>
        </div>
        <div class="section">
            <div class="section-title">DADOS DO COLABORADOR</div>
            <table class="info-table">
                <tr><td>NOME:</td><td>{dados.get('nome_completo', '')}</td></tr>
                <tr><td>CPF:</td><td>{dados.get('cpf', '')}</td></tr>
                <tr><td>SETOR:</td><td>{dados.get('nome_setor', '')}</td></tr>
            </table>
        </div>
        <div class="section">
            <div class="section-title">DADOS DO EQUIPAMENTO</div>
            <table class="info-table">
                <tr><td>TIPO:</td><td>SMARTPHONE</td></tr>
                <tr><td>MARCA:</td><td>{dados.get('nome_marca', '')}</td></tr>
                <tr><td>MODELO:</td><td>{dados.get('nome_modelo', '')}</td></tr>
                <tr><td>NÚMERO DE SÉRIE:</td><td>{dados.get('numero_serie', '')}</td></tr>
                <tr><td>IMEI 1:</td><td>{dados.get('imei1', '')}</td></tr>
                <tr><td>IMEI 2:</td><td>{dados.get('imei2', '')}</td></tr>
            </table>
        </div>
        <div class="section">
            <div class="section-title">CHECKLIST DE ITENS ENTREGUES</div>
            <table class="checklist-table">
                <thead><tr><th>ITEM</th><th>ENTREGUE</th><th>ESTADO</th></tr></thead>
                <tbody>{checklist_html}</tbody>
            </table>
        </div>
        <div class="section">
            <div class="section-title">TERMOS E CONDIÇÕES</div>
            <p class="disclaimer">{texto_termos_resumido}</p>
        </div>
        <div class="signature">
            <div class="signature-line">{dados.get('nome_completo', '')}</div>
        </div>
    </body>
    </html>
    """
    
    pdf_bytes = HTML(string=html_string).write_pdf()
    return pdf_bytes

def gerar_pdf_etiqueta(dados, logo_string):
    """Gera o PDF da Etiqueta a partir de um template HTML."""
    data_formatada = dados.get('data_movimentacao').strftime('%d/%m/%Y') if dados.get('data_movimentacao') else "N/A"

    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: 100mm 40mm;
                margin: 0;
            }}
            body {{
                font-family: Arial, sans-serif;
                font-size: 7.5pt;
                color: #000;
                margin: 0;
                padding: 3mm;
                box-sizing: border-box;
                line-height: 1.1; /* Linha mais compacta */
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding-bottom: 1.5mm;
                border-bottom: 1px solid #000;
                margin-bottom: 1.5mm; /* Adiciona espaço após a linha */
            }}
            .logo {{
                width: 30mm;
                height: auto;
                position: relative;
                top: -2mm; /* Move a logo um pouco para cima */
            }}
            .date {{
                font-size: 8pt;
                font-weight: bold;
            }}
            .content {{
                display: flex;
                width: 100%;
            }}
            .column {{
                width: 50%;
                padding-right: 2mm;
            }}
            .column:last-child {{
                padding-right: 0;
                padding-left: 2mm;
                border-left: 1px solid #ccc;
            }}
            .field {{
                margin-bottom: 1.2mm; /* Ajusta o espaçamento entre os campos */
            }}
            .field-label {{
                font-weight: bold;
                display: block;
                font-size: 6.5pt;
                margin-bottom: 0.1mm; /* Espaço mínimo entre label e valor */
                text-transform: uppercase; /* Deixa os rótulos em maiúsculas */
            }}
            .field-value {{
                font-size: 7.5pt;
                word-wrap: break-word;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <img src="{logo_string}" class="logo">
            <span class="date">{data_formatada}</span>
        </div>
        <div class="content">
            <div class="column">
                <div class="field"><span class="field-label">N°/S:</span><span class="field-value">{dados.get('numero_serie', '')}</span></div>
                <div class="field"><span class="field-label">MODELO:</span><span class="field-value">{dados.get('nome_marca', '')} {dados.get('nome_modelo', '')}</span></div>
                <div class="field"><span class="field-label">IMEI 1:</span><span class="field-value">{dados.get('imei1', '')}</span></div>
                <div class="field"><span class="field-label">IMEI 2:</span><span class="field-value">{dados.get('imei2', '')}</span></div>
            </div>
            <div class="column">
                <div class="field"><span class="field-label">FUNCAO:</span><span class="field-value">{dados.get('nome_setor', '')}</span></div>
                <div class="field"><span class="field-label">CÓDIGO:</span><span class="field-value">{dados.get('codigo_colaborador', '')}</span></div>
                <div class="field"><span class="field-label">NOME:</span><span class="field-value">{dados.get('nome_completo', '')}</span></div>
                <div class="field"><span class="field-label">GMAIL:</span><span class="field-value">{dados.get('gmail', '')}</span></div>
            </div>
        </div>
    </body>
    </html>
    """
    
    pdf_bytes = HTML(string=html_string).write_pdf()
    return pdf_bytes

# --- UI PRINCIPAL COM RADIO BUTTONS ---
st.title("Geração de Documentos")
st.markdown("---")

option = st.radio(
    "Selecione a operação:",
    ("Termo de Responsabilidade", "Gerar Etiquetas"),
    horizontal=True,
    label_visibility="collapsed",
    key="docs_selector"
)
st.markdown("---")

try:
    if option == "Termo de Responsabilidade":
        st.header("Gerar Termo de Responsabilidade")
        movimentacoes = carregar_movimentacoes_entrega()

        if not movimentacoes:
            st.info("Nenhuma movimentação de 'Em uso' encontrada para gerar termos.")
        else:
            mov_dict_termo = {f"{m['data_movimentacao'].strftime('%d/%m/%Y %H:%M')} - {m['nome_completo']} (S/N: {m['numero_serie']})": m['id'] for m in movimentacoes}
            
            st.subheader("1. Selecione a Movimentação")
            mov_selecionada_str_termo = st.selectbox(
                "Selecione a entrega para gerar o termo:", 
                options=list(mov_dict_termo.keys()), 
                index=None, 
                placeholder="Selecione uma movimentação...",
                key="termo_select"
            )
            
            if mov_selecionada_str_termo:
                mov_id_termo = mov_dict_termo[mov_selecionada_str_termo]
                dados_termo_original = buscar_dados_completos(mov_id_termo)

                if dados_termo_original:
                    st.markdown("---")
                    st.subheader("2. Confira e Edite as Informações (Checkout)")

                    with st.form("checkout_form"):
                        dados_termo_editaveis = dados_termo_original.copy()

                        dados_termo_editaveis['codigo_colaborador'] = st.text_input("Código do Colaborador", value=dados_termo_original.get('codigo_colaborador', ''))
                        data_str = dados_termo_original['data_movimentacao'].strftime('%d/%m/%Y %H:%M')
                        dados_termo_editaveis['data_movimentacao'] = st.text_input("Data", value=data_str)
                        
                        st.markdown("##### Dados do Colaborador")
                        dados_termo_editaveis['nome_completo'] = st.text_input("Nome", value=dados_termo_original['nome_completo'])
                        dados_termo_editaveis['cpf'] = st.text_input("CPF", value=dados_termo_original['cpf'])
                        
                        setores_options = carregar_setores_nomes()
                        try:
                            current_sector_index = setores_options.index(dados_termo_original['nome_setor'])
                        except (ValueError, IndexError):
                            current_sector_index = 0
                        dados_termo_editaveis['nome_setor'] = st.selectbox("Setor", options=setores_options, index=current_sector_index)
                        
                        dados_termo_editaveis['gmail'] = st.text_input("Email", value=dados_termo_original.get('gmail', ''))

                        st.markdown("##### Dados do Smartphone")
                        dados_termo_editaveis['numero_serie'] = st.text_input("N/S", value=dados_termo_original.get('numero_serie', ''))
                        dados_termo_editaveis['imei1'] = st.text_input("IMEI 1", value=dados_termo_original.get('imei1', ''))
                        dados_termo_editaveis['imei2'] = st.text_input("IMEI 2", value=dados_termo_original.get('imei2', ''))
                        
                        st.markdown("---")
                        st.subheader("3. Preencha o Checklist")
                        
                        checklist_data = {}
                        itens_checklist = ["Tela", "Carcaça", "Bateria", "Botões", "USB", "Chip", "Carregador", "Cabo USB", "Capa", "Película"]
                        opcoes_estado = ["NOVO", "BOM", "REGULAR", "AVARIADO", "JÁ DISPÕE"]
                        
                        cols = st.columns(2)
                        for i, item in enumerate(itens_checklist):
                            with cols[i % 2]:
                                entregue = st.checkbox(f"{item}", value=True, key=f"entregue_{item}_{mov_id_termo}")
                                estado = st.selectbox(f"Estado de {item}", options=opcoes_estado, key=f"estado_{item}_{mov_id_termo}")
                                checklist_data[item] = {'entregue': entregue, 'estado': estado}

                        submitted = st.form_submit_button("Gerar PDF do Termo", use_container_width=True, type="primary")
                        if submitted:
                            logo_string = carregar_logo_base64()
                            if logo_string:
                                pdf_bytes = gerar_pdf_termo(dados_termo_editaveis, checklist_data, logo_string)
                                
                                safe_name = "".join(c for c in dados_termo_editaveis.get('nome_completo', 'termo') if c.isalnum() or c in " ").rstrip()
                                pdf_filename = f"Termo_{safe_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                                
                                st.session_state['pdf_para_download'] = {"data": pdf_bytes, "filename": pdf_filename, "type": "termo"}
                                st.rerun()

    elif option == "Gerar Etiquetas":
        st.header("Gerar Etiqueta do Ativo")
        movimentacoes_etiqueta = carregar_movimentacoes_entrega() # Reutiliza a mesma função

        if not movimentacoes_etiqueta:
            st.info("Nenhuma movimentação de 'Em uso' encontrada para gerar etiquetas.")
        else:
            mov_dict_etiqueta = {f"{m['data_movimentacao'].strftime('%d/%m/%Y %H:%M')} - {m['nome_completo']} (S/N: {m['numero_serie']})": m['id'] for m in movimentacoes_etiqueta}

            st.subheader("Selecione a Movimentação")
            mov_selecionada_str_etiqueta = st.selectbox(
                "Selecione a entrega para gerar a etiqueta:", 
                options=list(mov_dict_etiqueta.keys()), 
                index=None, 
                placeholder="Selecione uma movimentação...",
                key="etiqueta_select"
            )

            if mov_selecionada_str_etiqueta:
                mov_id_etiqueta = mov_dict_etiqueta[mov_selecionada_str_etiqueta]
                dados_etiqueta = buscar_dados_completos(mov_id_etiqueta)

                if dados_etiqueta:
                    # Mostra um preview dos dados
                    st.write("Dados para a etiqueta:")
                    st.json({
                        "N°/S": dados_etiqueta.get('numero_serie', ''),
                        "MODELO": f"{dados_etiqueta.get('nome_marca', '')} {dados_etiqueta.get('nome_modelo', '')}",
                        "NOME": dados_etiqueta.get('nome_completo', ''),
                        "FUNÇÃO": dados_etiqueta.get('nome_setor', '')
                    })

                    if st.button("Gerar PDF da Etiqueta", use_container_width=True, type="primary"):
                        logo_string = carregar_logo_base64()
                        if logo_string:
                            pdf_bytes = gerar_pdf_etiqueta(dados_etiqueta, logo_string)
                            
                            safe_ns = "".join(c for c in dados_etiqueta.get('numero_serie', 'etiqueta') if c.isalnum()).rstrip()
                            pdf_filename = f"Etiqueta_{safe_ns}_{datetime.now().strftime('%Y%m%d')}.pdf"
                            
                            st.session_state['pdf_para_download'] = {"data": pdf_bytes, "filename": pdf_filename, "type": "etiqueta"}
                            st.rerun()

    # Lógica de download unificada fora das abas
    if 'pdf_para_download' in st.session_state and st.session_state['pdf_para_download']:
        pdf_info = st.session_state.pop('pdf_para_download')
        doc_type = pdf_info.get("type", "documento").capitalize()
        st.download_button(
            label=f"{doc_type} Gerado! Clique para Baixar",
            data=pdf_info['data'],
            file_name=pdf_info['filename'],
            mime="application/pdf",
            use_container_width=True
        )

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página: {e}")
    st.info("Verifique se o banco de dados está inicializado e se há movimentações do tipo 'Em uso' registadas.")
