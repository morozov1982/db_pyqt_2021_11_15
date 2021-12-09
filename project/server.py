import argparse
import configparser
import logging
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

import logs.config_server_log
from common.decos import log
from common.variables import DEFAULT_PORT
from server.database import ServerStorage
from server.core import MessageProcessor
from server.main_window import MainWindow


# Инициализация логирования сервера
logger = logging.getLogger('server')


# Парсер аргументов коммандной строки
@log
def arg_parser(default_port, default_address):
    """Парсер аргументов коммандной строки."""
    logger.debug(f'Инициализация парсера аргументов коммандной строки: {sys.argv}')
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', default=default_port, type=int, nargs='?')
    parser.add_argument('-a', default=default_address, nargs='?')
    parser.add_argument('--no_gui', action='store_true')
    namespace = parser.parse_args(sys.argv[1:])
    listen_address = namespace.a
    listen_port = namespace.p
    gui_flag = namespace.no_gui
    logger.debug('Аргументы успешно загружены')

    return listen_address, listen_port, gui_flag


@log
def config_load():
    """Парсер конфигурационного ini-файла."""
    config = configparser.ConfigParser()
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config.read(f"{dir_path}/{'server.ini'}")
    if 'SETTINGS' not in config:
        config.add_section('SETTINGS')
        config.set('SETTINGS', 'default_port', str(DEFAULT_PORT))
        config.set('SETTINGS', 'listen_Address', '')
        config.set('SETTINGS', 'db_path', '')
        config.set('SETTINGS', 'db_file', 'server_base.db3')
    return config


@log
def main():
    """Основная функция"""
    config = config_load()

    # Загрузка параметров командной строки, если нет параметров, то задаём значения по умоланию
    listen_address, listen_port, gui_flag = arg_parser(
        config['SETTINGS']['default_port'], config['SETTINGS']['listen_address'])

    db = ServerStorage(os.path.join(config['SETTINGS']['db_path'], config['SETTINGS']['db_file']))

    # Создание экземпляра класса - сервера
    server = MessageProcessor(listen_address, listen_port, db)
    server.daemon = True
    server.start()

    # Если указан параметр без GUI, то запускаем простой обработчик консольного ввода, иначе запускаем GUI
    if gui_flag:
        while True:
            command = input('Введите exit для завершения работы сервера: ')
            if command == 'exit':
                server.running = False
                server.join()
                break
    else:
        # Создаём графическое окуружение для сервера:
        server_app = QApplication(sys.argv)
        server_app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
        main_window = MainWindow(db, server, config)

        # Запускаем GUI
        server_app.exec_()

        # По закрытию окон останавливаем обработчик сообщений
        server.running = False


if __name__ == '__main__':
    main()
