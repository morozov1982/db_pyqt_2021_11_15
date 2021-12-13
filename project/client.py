import os.path
from os import urandom
from sys import argv
from argparse import ArgumentParser
from logging import getLogger

from Cryptodome.PublicKey import RSA
from PyQt5.QtWidgets import QApplication, QMessageBox

import logs.config_client_log
from common.decos import log
from common.variables import DEFAULT_IP_ADDRESS, DEFAULT_PORT
from common.errors import ServerError
from client.database import ClientDatabase
from client.transport import ClientTransport
from client.main_window import ClientMainWindow
from client.start_dialog import UserNameDialog

# Инициализация клиентского логера
logger = getLogger('client')


# Парсер аргументов коммандной строки
@log
def arg_parser():
    """
    Парсер аргументов командной строки, возвращает кортеж из 4 элементов:
    адрес сервера, порт, имя пользователя, пароль.
    Выполняет проверку на корректность номера порта.
    """
    parser = ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADDRESS, nargs='?')
    parser.add_argument('port', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-n', '--name', default=None, nargs='?')
    parser.add_argument('-p', '--password', default='', nargs='?')
    namespace = parser.parse_args(argv[1:])
    server_address = namespace.addr
    server_port = namespace.port
    client_name = namespace.name
    client_password = namespace.password

    # проверим подходящий номер порта
    if not 1023 < server_port < 65536:
        logger.critical(
            f'Попытка запуска клиента с неподходящим номером порта: '
            f'{server_port}. Допустимы адреса с 1024 до 65535. '
            f'Клиент завершается.')
        exit(1)

    return server_address, server_port, client_name, client_password


if __name__ == '__main__':
    # Загружаем параметы коммандной строки
    server_address, server_port, client_name, client_password = arg_parser()
    logger.debug('Аргументы загружены')

    client_app = QApplication(argv)

    start_dialog = UserNameDialog()
    # Если имя пользователя не было задано, то запросим его
    if not client_name or not client_password:
        client_app.exec_()
        # Если пользователь ввёл имя и нажал OK,
        # то сохраняем введённое имя и удаляем объект или выходим
        if start_dialog.ok_pressed:
            client_name = start_dialog.client_name.text()
            client_password = start_dialog.client_password.text()
            logger.debug(f'Используются: ПОЛЬЗОВАТЕЛЬ = {client_name}, '
                         f'ПАРОЛЬ = {client_password}.')
        else:
            exit(0)

    logger.info(
        f'Запущен клиент с парамертами: адрес сервера: {server_address}, '
        f'порт: {server_port}, имя пользователя: {client_name}')

    dir_path = os.path.dirname(os.path.realpath(__file__))
    key_file = os.path.join(dir_path, f'{client_name}.key')

    if not os.path.exists(key_file):
        keys = RSA.generate(2048, urandom)
        with open(key_file, 'wb') as key:
            key.write(keys.export_key())
    else:
        with open(key_file, 'rb') as key:
            keys = RSA.import_key(key.read())

    logger.debug('Ключи успешно загружены')

    db = ClientDatabase(client_name)

    try:
        transport = ClientTransport(server_port, server_address, db,
                                    client_name, client_password, keys)
        logger.debug("Транспорт готов")
    except ServerError as err:
        message = QMessageBox()
        message.critical(start_dialog, 'Ошибка сервера', err.text)
        exit(1)
    transport.setDaemon(True)
    transport.start()

    # Удалим объект диалога за ненадобностью
    del start_dialog

    # GUI
    main_window = ClientMainWindow(db, transport, keys)
    main_window.make_connection(transport)
    main_window.setWindowTitle(f'Чат программа Alpha-релиз - {client_name}')
    client_app.exec_()

    transport.transport_shutdown()
    transport.join()
