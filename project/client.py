import sys
import argparse
import logging

from PyQt5.QtWidgets import QApplication

import logs.config_client_log
from common.decos import log
from common.variables import DEFAULT_IP_ADDRESS, DEFAULT_PORT
from common.errors import ServerError
from client.database import ClientDatabase
from client.transport import ClientTransport
from client.main_window import ClientMainWindow
from client.start_dialog import UserNameDialog

# Инициализация клиентского логера
logger = logging.getLogger('client')


# Парсер аргументов коммандной строки
@log
def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADDRESS, nargs='?')
    parser.add_argument('port', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-n', '--name', default=None, nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    server_address = namespace.addr
    server_port = namespace.port
    client_name = namespace.name

    # проверим подходящий номер порта
    if not 1023 < server_port < 65536:
        logger.critical(
            f'Попытка запуска клиента с неподходящим номером порта: {server_port}. '
            f'Допустимы адреса с 1024 до 65535. Клиент завершается.')
        exit(1)

    return server_address, server_port, client_name


if __name__ == '__main__':
    # Загружаем параметы коммандной строки
    server_address, server_port, client_name = arg_parser()

    client_app = QApplication(sys.argv)

    # Если имя пользователя не было задано, то запросим его
    if not client_name:
        start_dialog = UserNameDialog()
        client_app.exec_()
        # Если пользователь ввёл имя и нажал OK, то сохраняем введённое имя и удаляем объект или выходим
        if start_dialog.ok_pressed:
            client_name = start_dialog.client_name.text()
            del start_dialog
        else:
            exit(0)

    logger.info(
        f'Запущен клиент с парамертами: адрес сервера: {server_address}, '
        f'порт: {server_port}, имя пользователя: {client_name}')

    db = ClientDatabase(client_name)

    try:
        transport = ClientTransport(server_port, server_address, db, client_name)
    except ServerError as err:
        print(err.text)
        exit(1)
    transport.setDaemon(True)
    transport.start()

    # GUI
    main_window = ClientMainWindow(db, transport)
    main_window.make_connection(transport)
    main_window.setWindowTitle(f'Чат программа Alpha-релиз - {client_name}')
    client_app.exec_()

    transport.transport_shutdown()
    transport.join()
