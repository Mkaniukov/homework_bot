from http import HTTPStatus
import logging
import os
import telegram
import time
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'practicum_token': PRACTICUM_TOKEN,
        'telegram_token': TELEGRAM_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if value is None:
            logging.critical(f'{key} не найден')
            return False
    logging.info('Токены найдены')
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logging.error('Ошибка при отправке сообщения')
    else:
        logging.debug('Сообщение успешно отправлено')
    pass


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            response.raise_for_status()
        logging.info('Ответ на запрос к API: 200 OK')
        return response.json()
    except requests.exceptions.RequestException:
        message = f'Ошибка при запросе к API: {response.status_code}'
        raise requests.exceptions.RequestException(message)


def check_response(response):
    """Проверяем ответ API на соответствие документации."""
    if isinstance(response, dict):
        if 'homeworks' in response:
            if isinstance(response.get('homeworks'), list):
                return response.get('homeworks')
            raise TypeError('API возвращает не список.')
        raise KeyError('Не найден ключ homeworks.')
    raise TypeError('API возвращает не словарь.')


def parse_status(homework):
    """Проверка статуса домашней работы."""
    status = homework.get('status')
    if status is None:
        raise TypeError
    if status not in HOMEWORK_VERDICTS:
        raise TypeError
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise TypeError
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        logging.error('Неизвестный статус работы')
        return None
    return ('Изменился статус проверки работы '
            f'"{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        while True:
            try:
                """Запрос к API."""
                response_result = get_api_answer(timestamp)
                """Проверка ответа."""
                homeworks = check_response(response_result)
                logging.info("Список домашних работ получен")
                """Если есть обновления, то отправить сообщение в Telegram."""
                if len(homeworks) > 0:
                    send_message(bot, parse_status(homeworks[0]))
                    """Дата последнего обновления."""
                    timestamp = response_result['current_date']
                else:
                    logging.info("Новые задания не обнаружены")
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                logging.error(message)
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
