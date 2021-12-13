from ipaddress import ip_address
from logging import getLogger
from sys import argv


if argv[0].find('client') == -1:
    logger = getLogger('server')
else:
    logger = getLogger('client')


class Port:
    """
    Класс - дескриптор для номера порта.
    Позволяет использовать только порты с 1023 по 65536.
    При попытке установить неподходящий номер порта генерирует исключение.
    """

    def __set__(self, instance, value):
        if not 1023 < value < 65536:
            logger.critical(
                f'Попытка запуска сервера с указанием неподходящего порта:'
                f'{value}. Допустимы адреса с 1024 до 65535.')
            raise TypeError('Некорректрый номер порта')
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name


class Addr:
    """
    Класс - дескриптор для номера порта.
    При попытке установить неподходящий IP-адрес генерирует исключение.
    """

    def __set__(self, instance, value):
        if value:
            try:
                ip = ip_address(value)
            except ValueError as e:
                logger.critical(f'Неверный ip адрес: {e}')
                exit(1)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name
