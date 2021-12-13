from logging import Formatter, StreamHandler, INFO, FileHandler, getLogger
import sys
import os.path

sys.path.append('../')
from common.variables import LOGGING_LEVEL

# создаём формировщик логов (formatter):
client_formatter = Formatter(
    '%(asctime)s %(levelname)s %(filename)s %(message)s')

# Подготовка имени файла для логирования
path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'client.log')

# создаём потоки вывода логов
steam = StreamHandler(sys.stderr)
steam.setFormatter(client_formatter)
steam.setLevel(INFO)
log_file = FileHandler(path, encoding='utf8')
log_file.setFormatter(client_formatter)

# создаём регистратор и настраиваем его
logger = getLogger('client')
logger.addHandler(steam)
logger.addHandler(log_file)
logger.setLevel(LOGGING_LEVEL)

# отладка
if __name__ == '__main__':
    logger.critical('Test critical event')
    logger.error('Test error event')
    logger.debug('Test debug event')
    logger.info('Test info event')
