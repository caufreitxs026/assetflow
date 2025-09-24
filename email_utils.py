import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def enviar_email_de_redefinicao(destinatario_email, destinatario_nome, token):
    """
    Envia um e-mail para o utilizador com um link para redefinir a sua senha.
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

    # --- ALTERAÇÃO AQUI ---
    # Constrói a URL da página de redefinição com o endereço de produção real.
    app_url = "https://assetfl0w.streamlit.app/Resetar_Senha" 
    reset_link = f"{app_url}?token={token}"

    # Corpo do e-mail em texto puro e HTML
    text = f"""
    Olá, {destinatario_nome},

    Recebemos um pedido para redefinir a sua senha no sistema AssetFlow.
    Copie e cole o seguinte link no seu navegador para criar uma nova senha:
    {reset_link}

    Este link é válido por 15 minutos. Se você não solicitou esta alteração, por favor, ignore este e-mail.

    Atenciosamente,
    Equipe AssetFlow
    """

    html = f"""
    <html>
    <body>
        <p>Olá, <strong>{destinatario_nome}</strong>,</p>
        <p>Recebemos um pedido para redefinir a sua senha no sistema AssetFlow.</p>
        <p>Clique no botão abaixo para criar uma nova senha. O link é válido por <strong>15 minutos</strong>.</p>
        <a href="{reset_link}" style="background-color: #003366; color: white; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-family: sans-serif;">
            Redefinir Senha
        </a>
        <p>Se você não consegue clicar no botão, copie e cole o seguinte link no seu navegador:</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>Se você não solicitou esta alteração, por favor, ignore este e-mail.</p>
        <br>
        <p>Atenciosamente,<br>Equipe AssetFlow</p>
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

