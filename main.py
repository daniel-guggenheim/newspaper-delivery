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
from bs4 import BeautifulSoup

SUNDAY: int = 6
TIMEZONE = pytz.timezone("Europe/Zurich")


def download_pdf(pdf_url: str, session: requests.Session, timeout=(5, 20)):
    try:
        # Download pdf and handle timeout
        logging.info("Download pdf file from {}".format(pdf_url))
        pdf_response = session.get(pdf_url, timeout=timeout)
    except requests.exceptions.Timeout as e:
        logging.error("Request timed out: {}.".format(timeout))
        logging.error(e)
        logging.info("Starting new request with double timeout.")
        return download_pdf(pdf_url, session, timeout=(timeout[0] * 2, timeout[1] * 2))

    logging.info(f"Received a response of type {pdf_response.headers.get('Content-Type')} and a file of size {pdf_response.headers.get('Content-Length')} bytes.")

    # Handling response
    if not pdf_response.ok:
        logging.error("Impossible to download pdf from 'Le Temps'. Error code is {}.".format(pdf_response.status_code))
        logging.error("pdf_response.content:")
        logging.error(pdf_response.content)
        pdf_response.raise_for_status()

    logging.info("Pdf downloaded successfully")
    return pdf_response.content


def login_to_website(session):
    logging.info("Login to LeTemps website.")
    # First, extract the auth / connection tokens
    connection_page = session.get("https://www.letemps.ch/compte/connexion")
    soup = BeautifulSoup(connection_page.content, 'html.parser')

    # Step 2: Extract the authenticity_token
    token_input = soup.find('input', {'name': 'authenticity_token'})
    if token_input is not None:
        authenticity_token = token_input['value']
    else:
        raise Exception("Could not find the authenticity_token")

    # # Step 2: Extract the hash_cash => needs to do some work for it..
    # hash_cash_input = soup.find('input', {'name': 'hashcash'})
    # if hash_cash_input:
    #     hash_cash = hash_cash_input['value']
    # else:
    #     raise Exception("Could not find the authenticity_token")

    login_headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "fr",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "pragma": "no-cache",
        "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "upgrade-insecure-requests": "1"
    }

    login_data = {
        "utf8": "✓",
        "authenticity_token": authenticity_token,
        "hashcash": "1:18:230819:www.letemps.ch::4coa516uue:114137",  # probably can't work long...
        "user[email]": configuration['username_letemps'],
        "user[password]": configuration['password_letemps'],
        "user[remember_me]": "1",
        "commit": "Connexion"
    }
    login_url = "https://www.letemps.ch/compte/connexion"

    logging.info("Login to LeTemps at {}".format(login_url))
    login_response = session.post(login_url, headers=login_headers, data=login_data, allow_redirects=True, timeout=30)
    login_response.raise_for_status()


def find_pdf_url(input_date: datetime.date, base_url: str, session: requests.Session):
    # Convert input_date to French day name, day, and month name
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                 "août", "septembre", "octobre", "novembre", "décembre"]
    days_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

    input_weekday = days_fr[input_date.weekday()]
    input_day = str(input_date.day)
    input_month = months_fr[input_date.month - 1]

    # Fetch the webpage
    fetch_url = base_url + "/pdf"
    logging.info(f"Will attempt to fetch the webpage {fetch_url} to find the pdf url.")
    response = session.get(fetch_url)
    response.raise_for_status()

    # Parse the webpage
    soup = BeautifulSoup(response.content, 'html.parser')
    logging.info(f"Will attempt to parse webpage to find pdf url with dates {input_weekday}, {input_day}, {input_month}")

    # Find the article with the desired date
    articles = soup.find_all('article', class_='print_edition-tps')
    logging.info(f"Found {len(articles)} article elements to parse")

    for article in articles:
        article_text = article.get_text()
        if input_weekday in article_text and input_day in article_text and input_month in article_text:  # we check that the date corresponds
            logging.info(f"Found the correct article.")
            pdf_link = article.find('a', string=lambda text: text and "pdf" in text.lower())  # we look for PDF inside the <a> tag
            if pdf_link:
                logging.info(f"Found the downloadable pdf link: {pdf_link}")

                return base_url + pdf_link['href']

    logging.error(f"Did not find any downloaded pdf link in the page")
    raise Exception(f"Did not find any downloaded pdf link in the page {fetch_url} with dates {input_weekday}, {input_day}, {input_month}")


def download_pdf_with_config(download_date):
    with requests.Session() as session:
        try:
            login_to_website(session)
            pdf_url = find_pdf_url(download_date, "https://www.letemps.ch", session)
            return download_pdf(pdf_url, session)
        except Exception as e:
            logging.error("Exception while trying to download PDF from LeTemps.")
            logging.exception(e)
            raise e


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
    body = "Bonjour,\n\nVoici l'édition du jour du journal Le Temps ({}) en PDF.\n\nA bientôt,\nSystème automatique d'envoi".format(
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
