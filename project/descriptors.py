import ipaddress
import logging

logger = logging.getLogger('server')


class Port:
    def __set__(self, instance, value):
        if not 1023 < value < 65536:
            logger.critical(
                f'Попытка запуска сервера с указанием неподходящего порта: {value}. Допустимы адреса с 1024 до 65535.')
            exit(1)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name


class Addr():
    def __set__(self, instance, value):
        if value:
            try:
                ip = ipaddress.ip_address(value)
            except ValueError as e:
                logger.critical(f'Неверный ip адрес: {e}')
                exit(1)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name
