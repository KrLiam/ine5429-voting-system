
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import os

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_email_credentials(env_path: str = ".env") -> tuple[str, str]:
    load_dotenv(env_path)
    email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not email or not password:
        raise ValueError("EMAIL_ADDRESS or EMAIL_PASSWORD missing in .env")

    return email, password

URL = "https://9rsxq6fr-5000.brs.devtunnels.ms/"
SUBJECT = "INE5429 - Participe da eleição para presidente do Grupo 2"
MESSAGE = "\n".join((
    "Olá! Somos alunos da disciplina de Segurança em Computação (INE5429) do semestre 2025.2. O nosso trabalho em grupo consiste em " +
    "um sistema de votação utilizando criptografia homomórfica. Por isto, estamos conduzindo uma eleição para testar o nosso sistema " +
    "e você foi convidado para ser um eleitor.",
    "",
    "Para isso, basta você acessar o web site abaixo e inserir o token de votação (a string hexadecimal) para realizar o seu voto. " +
    "Atenção ao período de votação é curto e encerra hoje (27/11/2025) às 23:59. O resultado final estará disponível na página após o término da eleição.",
    "",
    f"Link da página: {URL}",
    "",
    "Token:",
    "{}",
    "",
    "",
    "Agradecemos a atenção!",
    "Atenciosamente,",
    "William Kraus e Tiago Siqueira.",
    ""
))

def send_bulk_email(
    sender_email: str,
    sender_password: str,
    recipients: list[str],
    subject: str,
    body: str,
    tokens: list[str],
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
):
    """
    Sends an email to all addresses in `recipients`.
    """

    # Connect to SMTP
    with smtplib.SMTP(smtp_server, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(sender_email, sender_password)

        print("Logged in successfuly")

        # Send individually (recommended) so that bad emails don't break all
        for i, recipient in enumerate(recipients):
            print(f"Sending email to {recipient}")

            message = MIMEMultipart()
            message["From"] = sender_email
            message["Subject"] = subject
            message["To"] = recipient
            message.attach(MIMEText(body.format(tokens[i]), 'plain'))

            smtp.sendmail(sender_email, recipient, message.as_string())


def load_tokens() -> list[str]:
    with open("data/tokens.txt", "rt") as f:
        return f.readlines()

def load_recipients() -> list[str]:
    with open("voter_emails.txt", "rt") as f:
        lines = f.readlines()
        return [line for line in lines if not line.startswith("#")]


def main():
    email, password = load_email_credentials(".env")
    recipients = load_recipients()
    tokens = load_tokens()

    send_bulk_email(
        sender_email=email,
        sender_password=password,
        recipients=recipients,
        subject=SUBJECT,
        body=MESSAGE,
        tokens=tokens,
    )

if __name__ == "__main__":
    main()