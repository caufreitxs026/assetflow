import streamlit as st
import pandas as pd
from datetime import datetime
from auth import show_login_form, logout
from sqlalchemy import text
from weasyprint import HTML

# --- Autenticação ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

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
        <span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span>
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

# --- DADOS DA LOGO ---
# A logo é guardada como uma string Base64 para ser embutida diretamente no PDF.
# CORREÇÃO: Usando aspas triplas (""") para evitar erros de sintaxe com a string longa.
LOGO_BASE64_STRING = """data:image/png;base64,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"

Meu código atual pages/6_Gerar_Documentos.py:

import streamlit as st
import pandas as pd
from datetime import datetime
from auth import show_login_form
from sqlalchemy import text
from weasyprint import HTML

# --- Autenticação ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("app.py")

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
        <span class="logo-asset">ASSET</span><span class="logo-flow">FLOW</span>
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

# --- Funções do DB ---
def get_db_connection():
    return st.connection("supabase", type="sql")

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
            h.id,
            h.data_movimentacao,
            a.numero_serie,
            c.nome_completo
        FROM
            historico_movimentacoes h
        JOIN
            LatestMovements lm ON h.aparelho_id = lm.aparelho_id AND h.data_movimentacao = lm.last_move_date
        JOIN
            aparelhos a ON h.aparelho_id = a.id
        JOIN
            status s ON a.status_id = s.id
        LEFT JOIN
            colaboradores c ON h.colaborador_id = c.id
        WHERE
            s.nome_status = 'Em uso'
            AND c.id IS NOT NULL
        ORDER BY
            h.data_movimentacao DESC;
    """
    df = conn.query(query)
    return df.to_dict('records')

@st.cache_data(ttl=30)
def buscar_dados_termo(mov_id):
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

def gerar_pdf_termo(dados, checklist_data):
    """Gera o PDF a partir de um template HTML usando WeasyPrint."""
    
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
            
            .header {{ text-align: center; margin-bottom: 20px; }}
            h1 {{ color: #003366; font-size: 16pt; margin: 0; padding-top: 10px; }}
            
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
            
            .signature {{ margin-top: 25px; text-align: center; }} 
            .signature-line {{ border-top: 1px solid #000; width: 350px; margin: 0 auto; padding-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>TERMO DE RESPONSABILIDADE</h1>
        </div>
        <div class="section">
            <div class="section-title">DADOS DA MOVIMENTAÇÃO</div>
            <table class="info-table">
                <tr><td>CÓDIGO DO COLABORADOR:</td><td>{dados.get('codigo_colaborador', '')}</td></tr>
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

# --- UI ---
st.title("Gerar Termo de Responsabilidade")

try:
    movimentacoes = carregar_movimentacoes_entrega()

    if not movimentacoes:
        st.info("Nenhuma movimentação de 'Em uso' encontrada para gerar termos.")
    else:
        mov_dict = {f"{m['data_movimentacao'].strftime('%d/%m/%Y %H:%M')} - {m['nome_completo']} (S/N: {m['numero_serie']})": m['id'] for m in movimentacoes}
        
        st.subheader("1. Selecione a Movimentação")
        mov_selecionada_str = st.selectbox(
            "Selecione a entrega para gerar o termo:", 
            options=list(mov_dict.keys()), 
            index=None, 
            placeholder="Selecione uma movimentação..."
        )
        
        if mov_selecionada_str:
            mov_id = mov_dict[mov_selecionada_str]
            dados_termo_original = buscar_dados_termo(mov_id)

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
                    opcoes_estado = ["NOVO", "BOM", "REGULAR", "AVARIADO"]
                    
                    cols = st.columns(2)
                    for i, item in enumerate(itens_checklist):
                        with cols[i % 2]:
                            entregue = st.checkbox(f"{item}", value=True, key=f"entregue_{item}_{mov_id}")
                            estado = st.selectbox(f"Estado de {item}", options=opcoes_estado, key=f"estado_{item}_{mov_id}")
                            checklist_data[item] = {'entregue': entregue, 'estado': estado}

                    submitted = st.form_submit_button("Gerar PDF", use_container_width=True, type="primary")
                    if submitted:
                        pdf_bytes = gerar_pdf_termo(dados_termo_editaveis, checklist_data)
                        
                        safe_name = "".join(c for c in dados_termo_editaveis.get('nome_completo', 'termo') if c.isalnum() or c in " ").rstrip()
                        pdf_filename = f"Termo_{safe_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        
                        st.session_state['pdf_para_download'] = {"data": pdf_bytes, "filename": pdf_filename}
                        st.rerun()
    
    if 'pdf_para_download' in st.session_state and st.session_state['pdf_para_download']:
        pdf_info = st.session_state.pop('pdf_para_download')
        st.download_button(
            label="PDF Gerado! Clique para Baixar",
            data=pdf_info['data'],
            file_name=pdf_info['filename'],
            mime="application/pdf",
            use_container_width=True
        )

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página: {e}")
    st.info("Verifique se o banco de dados está inicializado e se há movimentações do tipo 'Em uso' registadas.")

