import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

def montar_layout_base(titulo_cabecalho, conteudo_html_interno):
    """
    Encapsula o conteúdo do e-mail numa estrutura de tabelas HTML robusta
    compatível com Outlook Desktop e Webmail.
    """
    return f"""
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <title>{titulo_cabecalho}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f2f2f2;">
        <!-- Tabela Mãe (Fundo Geral) -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f2f2f2;">
            <tr>
                <td align="center" style="padding: 20px 0 20px 0;">
                    <!-- Tabela Filha (O Cartão Centralizado - Largura Fixa 600px) -->
                    <table border="0" cellpadding="0" cellspacing="0" width="600" style="border-collapse: collapse; background-color: #ffffff; border: 1px solid #dddddd;">
                        
                        <!-- Cabeçalho Preto com Logo -->
                        <tr>
                            <td align="center" bgcolor="#000000" style="padding: 20px 0 20px 0;">
                                <span style="font-family: 'Courier New', Courier, monospace; font-size: 28px; font-weight: bold; color: #FFFFFF;">
                                    ASSET<span style="color: #E30613;">FLOW</span>
                                </span>
                            </td>
                        </tr>

                        <!-- Conteúdo Principal -->
                        <tr>
                            <td bgcolor="#ffffff" style="padding: 30px 30px 30px 30px;">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                    {conteudo_html_interno}
                                </table>
                            </td>
                        </tr>

                        <!-- Rodapé -->
                        <tr>
                            <td bgcolor="#eeeeee" style="padding: 20px 30px 20px 30px; font-family: Arial, sans-serif; font-size: 12px; color: #888888; text-align: center;">
                                &copy; {datetime.now().year} AssetFlow.<br/>
                                Este é um e-mail automático, por favor não responda.
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

def enviar_email(destinatarios, assunto, corpo_html_completo, corpo_texto=""):
    """
    Envia o e-mail. Nota: espera receber o HTML JÁ PROCESSADO pelo montar_layout_base
    ou um HTML completo.
    """
    try:
        sender_email = st.secrets["email_credentials"]["sender_email"]
        sender_password = st.secrets["email_credentials"]["sender_password"]
    except KeyError:
        st.error("Credenciais de e-mail não configuradas nos secrets do Streamlit.")
        return False

    if not destinatarios:
        st.error("Nenhum destinatário fornecido para o e-mail.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = assunto
    message["From"] = f"AssetFlow <{sender_email}>"
    message["To"] = ", ".join(destinatarios)

    if corpo_texto:
        part1 = MIMEText(corpo_texto, "plain")
        message.attach(part1)
    
    # O corpo_html aqui já deve vir com as tabelas montadas
    part2 = MIMEText(corpo_html_completo, "html")
    message.attach(part2)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, destinatarios, message.as_string())
        return True
    except Exception as e:
        # print(f"Falha ao enviar e-mail: {e}") # Opcional: logs no console
        st.error(f"Falha ao conectar-se ao servidor de e-mail: {e}")
        return False

def enviar_email_de_redefinicao(destinatario_email, destinatario_nome, token):
    """
    Envia o e-mail de redefinição usando a nova estrutura de tabelas.
    """
    assunto = "AssetFlow - Redefinição de Senha"
    app_url = "https://assetfl0w.streamlit.app/Resetar_Senha" 
    reset_link = f"{app_url}?token={token}"

    # Conteúdo interno (apenas o recheio, sem html/body/head)
    miolo_html = f"""
    <tr>
        <td style="color: #003366; font-family: Arial, sans-serif; font-size: 20px; font-weight: bold;">
            Redefinição de Senha
        </td>
    </tr>
    <tr>
        <td height="20" style="font-size:0px; line-height:0px;">&nbsp;</td>
    </tr>
    <tr>
        <td style="color: #333333; font-family: Arial, sans-serif; font-size: 14px; line-height: 20px;">
            Olá, <strong>{destinatario_nome}</strong>,<br/><br/>
            Recebemos uma solicitação para redefinir a senha da sua conta. Se não foi você, ignore este e-mail.
        </td>
    </tr>
    <tr>
        <td height="30" style="font-size:0px; line-height:0px;">&nbsp;</td>
    </tr>
    <tr>
        <td align="center">
            <table border="0" cellpadding="0" cellspacing="0">
                <tr>
                    <td align="center" bgcolor="#003366" style="border-radius: 5px;">
                        <a href="{reset_link}" target="_blank" style="font-size: 16px; font-family: Arial, sans-serif; color: #ffffff; text-decoration: none; padding: 12px 25px; border: 1px solid #003366; display: inline-block; border-radius: 5px; font-weight: bold;">
                            Redefinir Minha Senha
                        </a>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
    <tr>
        <td height="30" style="font-size:0px; line-height:0px;">&nbsp;</td>
    </tr>
    <tr>
        <td style="color: #888888; font-family: Arial, sans-serif; font-size: 12px;">
            O link expira em 15 minutos. Link direto:<br/>
            <a href="{reset_link}" style="color: #003366;">{reset_link}</a>
        </td>
    </tr>
    """

    # Monta o HTML final usando a função base
    html_completo = montar_layout_base("Redefinição de Senha", miolo_html)

    # Texto puro para clientes sem HTML
    corpo_texto = f"""
    Olá, {destinatario_nome},
    Para redefinir sua senha, acesse: {reset_link}
    """

    return enviar_email([destinatario_email], assunto, html_completo, corpo_texto)
