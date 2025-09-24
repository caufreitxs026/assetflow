import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

def enviar_email_de_redefinicao(destinatario_email, destinatario_nome, token):
    """
    Envia um e-mail com um layout profissional para o utilizador redefinir a sua senha.
    Utiliza as credenciais armazenadas nos secrets do Streamlit.
    """
    try:
        # Carrega as credenciais do ficheiro secrets.toml
        sender_email = st.secrets["email_credentials"]["sender_email"]
        sender_password = st.secrets["email_credentials"]["sender_password"]
    except KeyError:
        st.error("Credenciais de e-mail não configuradas nos secrets do Streamlit. A funcionalidade de redefinição de senha está desativada.")
        return False

    # Monta a mensagem do e-mail
    message = MIMEMultipart("alternative")
    message["Subject"] = "AssetFlow - Redefinição de Senha"
    message["From"] = f"AssetFlow <{sender_email}>"
    message["To"] = destinatario_email

    # --- CORREÇÃO FINAL AQUI ---
    # Simplificamos o nome da página para evitar erros de interpretação do Streamlit.
    # O ficheiro agora deve chamar-se 'pages/Resetar_Senha.py'.
    app_url = "https://assetfl0w.streamlit.app/Resetar_Senha" 
    reset_link = f"{app_url}?token={token}"

    # Corpo do e-mail em texto puro (para clientes de e-mail que não suportam HTML)
    text = f"""
    Olá, {destinatario_nome},

    Recebemos uma solicitação para redefinir a senha da sua conta no AssetFlow.
    Para criar uma nova senha, copie e cole o seguinte link no seu navegador:
    {reset_link}

    Por segurança, este link irá expirar em 15 minutos. Se não foi você quem solicitou, pode ignorar este e-mail com segurança.

    Atenciosamente,
    Equipe AssetFlow
    """

    # Corpo do e-mail em HTML com a logo e um design melhorado
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Redefinição de Senha</title>
    </head>
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #ffffff; color: #333;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e0e0e0;">
            <div style="padding: 20px; text-align: center; border-bottom: 1px solid #eeeeee; background-color: #000;">
                <div style="font-family: 'Courier New', monospace; font-size: 28px; font-weight: bold;">
                    <span style="color: #FFFFFF; text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7);">ASSET</span><span style="color: #E30613; text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7);">FLOW</span>
                </div>
            </div>
            <div style="padding: 30px;">
                <h2 style="color: #003366;">Redefinição de Senha Solicitada</h2>
                <p>Olá, <strong>{destinatario_nome}</strong>,</p>
                <p>Recebemos uma solicitação para redefinir a senha da sua conta no AssetFlow. Se não foi você, pode ignorar este e-mail com segurança.</p>
                <p>Para criar uma nova senha, clique no botão abaixo. Por segurança, este link irá expirar em <strong>15 minutos</strong>.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" target="_blank" style="background-color: #003366; color: #ffffff; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-weight: bold;">Redefinir a Minha Senha</a>
                </div>
                <p style="font-size: 12px; color: #888888;">Se o botão não funcionar, copie e cole o seguinte link no seu navegador:</p>
                <p style="font-size: 12px; color: #888888; word-break: break-all;">{reset_link}</p>
            </div>
            <div style="background-color: #f9f9f9; padding: 20px; font-size: 12px; color: #888888; text-align: center; border-top: 1px solid #eeeeee;">
                <p>&copy; {datetime.now().year} AssetFlow. Todos os direitos reservados.</p>
                <p>Este é um e-mail automático, por favor não responda.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Anexa as partes de texto e HTML à mensagem
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    message.attach(part1)
    message.attach(part2)

    # Conecta-se ao servidor SMTP do Gmail e envia o e-mail
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, destinatario_email, message.as_string())
        return True
    except Exception as e:
        # Fornece um erro mais detalhado no log do Streamlit para debugging
        print(f"Falha ao enviar e-mail: {e}")
        st.error(f"Falha ao conectar-se ao servidor de e-mail. Verifique as credenciais e as configurações de segurança da conta Gmail.")
        return False

