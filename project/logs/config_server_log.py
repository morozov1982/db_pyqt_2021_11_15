import sys
from logging import Formatter, StreamHandler, INFO, handlers, getLogger
import os.path

sys.path.append('../')
from common.variables import LOGGING_LEVEL

# создаём формировщик логов (formatter):
server_formatter = Formatter(
    '%(asctime)s %(levelname)s %(filename)s %(message)s')

# Подготовка имени файла для логирования
path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'server.log')

# создаём потоки вывода логов
steam = StreamHandler(sys.stderr)
steam.setFormatter(server_formatter)
steam.setLevel(INFO)
log_file = handlers.TimedRotatingFileHandler(
    path, encoding='utf8', interval=1, when='D')
log_file.setFormatter(server_formatter)

# создаём регистратор и настраиваем его
logger = getLogger('server')
logger.addHandler(steam)
logger.addHandler(log_file)
logger.setLevel(LOGGING_LEVEL)

# отладка
if __name__ == '__main__':
    logger.critical('Test critical event')
    logger.error('Test error event')
    logger.debug('Test debug event')
    logger.info('Test info event')
