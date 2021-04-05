import requests
import logging
import pytz
from datetime import datetime
# import locale # not supported on Google Cloud Functions
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate
from config import config_vars as configuration

SUNDAY: int = 6
TIMEZONE = pytz.timezone("Europe/Zurich")


def download_pdf(pdf_url, login_url, login_data, timeout=(5, 20)):
    logging.info("Connecting to LeTemps website to download pdf.")
    with requests.Session() as session:
        try:
            logging.info("Login to LeTemps at {}".format(login_url))
            login_response = session.post(login_url, data=login_data, timeout=30)

            # Download pdf and handle timeout
            logging.info("Download pdf file from {}".format(pdf_url))
            try:
                pdf_response = session.get(pdf_url, timeout=timeout)
            except requests.exceptions.Timeout as e:
                logging.error("Request timed out: {}.".format(timeout))
                logging.error(e)
                logging.info("Starting new request with double timeout.")
                return download_pdf(pdf_url, login_url, login_data, timeout=(timeout[0] * 2, timeout[1] * 2))

            # Handling response
            if not pdf_response.ok:
                logging.error("Impossible to download pdf from 'Le Temps'. Error code is {}.".format(
                    pdf_response.status_code))
                logging.error("login_response.content:")
                logging.error(login_response.content)
                logging.error("pdf_response.content:")
                logging.error(pdf_response.content)
                pdf_response.raise_for_status()
        except Exception as e:
            logging.error("Exception while trying to download PDF from LeTemps.")
            logging.exception(e)
            raise e
    logging.info("Pdf downloaded successfully")
    return pdf_response.content


def download_pdf_with_config(download_date):
    today_str = download_date.strftime('%Y%m%d')
    pdf_url = "https://www.letemps.ch/pdf/{}/download".format(today_str)
    login_url = 'https://www.letemps.ch/user/login?destination=/'
    login_data = {
        "name": configuration['username_letemps'],
        "pass": configuration['password_letemps'],
        "form_build_id": configuration['form_build_id_letemps'],
        "form_id": "user_login_form",
        "op": "Se connecter",
    }
    return download_pdf(pdf_url, login_url, login_data)


def create_email(subject, body):
    logging.debug("Creating email")
    msg = MIMEMultipart()
    msg['From'] = configuration['send_from']
    msg['To'] = ', '.join(configuration['send_to'])
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(body))
    return msg


def attach_to_email(msg, file, attachement_name):
    # Add pdf file as attachement to email
    logging.debug("Attaching file to email")
    part = MIMEApplication(file, Name=attachement_name)
    part['Content-Disposition'] = 'attachment; filename="{}"'.format(attachement_name)
    msg.attach(part)


def send_email(server_address, port, send_from, send_to, email_password, email_content):
    logging.info("Connecting to '{}' at port {}".format(server_address, port))
    with smtplib.SMTP_SSL(server_address, port) as server:
        ehlo = server.ehlo()
        logging.info("[{}] {}".format(ehlo[0], ehlo[1].decode('unicode_escape').replace('\n', ' - ')))
        logging.info("Logging with user {}".format(send_from))
        server.login(send_from, email_password)
        logging.info("Sending email to {}".format(send_to))
        server.sendmail(send_from, send_to, email_content.as_string())
        logging.info("Email sent successfully!")


def run_app(download_date):
    # Email text
    subject = "Le Temps - {}".format(download_date.strftime('%d.%m.%Y'))
    body = "Bonjour,\n\nVoici l'édition du jour du journal Le Temps ({}) en PDF.\n\nA bientôt,\nSystème automatique d'envoi par Daniel Guggenheim".format(
        download_date.strftime('%A, %d.%m.%Y'))
    attachement_name = 'le_temps_{}.pdf'.format(download_date.strftime('%Y_%m_%d'))

    # Run app
    pdf = download_pdf_with_config(download_date)
    msg = create_email(subject, body)
    attach_to_email(msg, pdf, attachement_name)
    send_email(configuration['email_server_address'], configuration['email_port'], configuration['send_from'],
               configuration['send_to'], configuration['email_password'], msg)


def main(data, context):
    """
    Triggered from a message on a Cloud Pub/Sub topic
    :param data: (dict) Event payload.
    :param context: (google.cloud.functions.Context) Metadata for the event.
    :return:
    """
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(funcName)s %(levelname)s %(message)s')
    # locale.setlocale(locale.LC_TIME, "fr-CH")
    now = datetime.now(TIMEZONE)

    # No episod on Sunday
    if now.weekday() == SUNDAY:
        logging.info(f'It is Sunday ({now}). No edition will be downloaded today.')
    else:
        logging.info(f'It is not Sunday ({now}). Will try to download the daily edition.')
        run_app(now)


if __name__ == "__main__":
    main('data', 'context')
