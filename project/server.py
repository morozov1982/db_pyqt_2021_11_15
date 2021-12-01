import argparse
import configparser
import logging
import os.path
import select
import socket
import sys
import threading

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

import logs.config_server_log
from decos import log
from common.variables import DEFAULT_PORT, MAX_CONNECTIONS, DESTINATION, ACTION, USER, ACCOUNT_NAME, PRESENCE, TIME, \
    RESPONSE_200, RESPONSE_400, ERROR, MESSAGE, SENDER, MESSAGE_TEXT, EXIT, GET_CONTACTS, RESPONSE_202, LIST_INFO, \
    ADD_CONTACT, REMOVE_CONTACT, USERS_REQUEST
from common.utils import get_message, send_message
from metaclasses import ServerVerifier
from descriptors import Port, Addr
from practice.server_gui import create_stat_model

from server_database import ServerStorage

# Инициализация логирования сервера
from server_gui import MainWindow, gui_create_model, HistoryWindow, ConfigWindow

logger = logging.getLogger('server')

# Флаг: подключён новый пользователь
new_connection = False
con_flag_lock = threading.Lock()


# Парсер аргументов коммандной строки
@log
def arg_parser(default_port, default_address):
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', default=default_port, type=int, nargs='?')
    parser.add_argument('-a', default=default_address, nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    listen_address = namespace.a
    listen_port = namespace.p

    return listen_address, listen_port


# Основной класс сервера
class Server(threading.Thread, metaclass=ServerVerifier):
    addr = Addr()
    port = Port()

    def __init__(self, listen_address, listen_port, db):
        # Параметры подключения
        self.addr = listen_address
        self.port = listen_port

        # БД сервера
        self.db = db

        # список клиентов, очередь сообщений
        self.clients = []
        self.messages = []

        # Словарь, содержащий имена пользователей и соответствующие им сокеты
        self.names = dict()

        super().__init__()

    def init_socket(self):
        logger.info(
            f'Запущен сервер, порт для подключений: {self.port}, '
            f'адрес с которого принимаются подключения: {self.addr}. '
            f'Если адрес не указан, принимаются соединения с любых адресов.')
        # Готовим сокет
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.addr, self.port))
        self.sock.settimeout(0.5)

        # Слушаем порт
        self.sock.listen()  # MAX_CONNECTIONS)

    # Обработчик сообщений от клиентов, принимает словарь - сообщение от клиента, проверяет корректность,
    # отправляет словарь-ответ в случае необходимости
    # @log
    def process_client_message(self, message, client):
        global new_connection
        logger.debug(f'Разбор сообщения от клиента: {message}')
        # Если это сообщение о присутствии, принимаем и отвечаем
        if ACTION in message and message[ACTION] == PRESENCE and TIME in message and USER in message:
            # Если такой пользователь ещё не зарегистрирован, регистрируем,
            # иначе отправляем ответ и завершаем соединение
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                client_ip, client_port = client.getpeername()
                self.db.user_login(message[USER][ACCOUNT_NAME], client_ip, client_port)
                send_message(client, RESPONSE_200)
                with con_flag_lock:
                    new_connection = True
            else:
                response = RESPONSE_400
                response[ERROR] = 'Имя пользователя уже занято'
                send_message(client, response)
                self.clients.remove(client)
                client.close()
            return
        # Если это сообщение, то добавляем его в очередь сообщений. Ответ не требуется
        elif ACTION in message and message[ACTION] == MESSAGE and DESTINATION in message and TIME in message \
                and SENDER in message and MESSAGE_TEXT in message and self.names[message[SENDER]] == client:
            self.messages.append(message)
            self.db.process_message(message[SENDER], message[DESTINATION])
            return
        # При входе клиента
        elif ACTION in message and message[ACTION] == EXIT and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            self.db.user_logout(message[ACCOUNT_NAME])
            logger.info(f'Клиент {message[ACCOUNT_NAME]} корректно отключился от сервера!')

            self.clients.remove(self.names[message[ACCOUNT_NAME]])
            self.names[message[ACCOUNT_NAME]].close()
            del self.names[message[ACCOUNT_NAME]]

            with con_flag_lock:
                new_connection = True

            return

        # При запросе контакт-листа
        elif ACTION in message and message[ACTION] == GET_CONTACTS and USER in message and \
                self.names[message[USER]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = self.db.get_contacts(message[USER])
            send_message(client, response)

        # При добавлении контакта
        elif ACTION in message and message[ACTION] == ADD_CONTACT and ACCOUNT_NAME in message and USER in message \
                and self.names[message[USER]] == client:
            self.db.add_contact(message[USER], message[ACCOUNT_NAME])
            send_message(client, RESPONSE_200)

        # При удалении контакта
        elif ACTION in message and message[ACTION] == REMOVE_CONTACT and ACCOUNT_NAME in message and USER in message \
                and self.names[message[USER]] == client:
            self.db.remove_contact(message[USER], message[ACCOUNT_NAME])
            send_message(client, RESPONSE_200)

        # ПРи запросе известных пользователей
        elif ACTION in message and message[ACTION] == USERS_REQUEST and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = [user[0] for user in self.db.users_list()]
            send_message(client, response)

        # Иначе отдаём Bad request
        else:
            response = RESPONSE_400
            response[ERROR] = 'Запрос некорректен'
            send_message(client, response)
            return

    # Функция адресной отправки сообщения определённому клиенту.
    # Принимает словарь сообщение, список зарегистрированых пользователей и слушающие сокеты.
    # Ничего не возвращает
    # @log
    def process_message(self, message, listen_socks):
        if message[DESTINATION] in self.names and self.names[message[DESTINATION]] in listen_socks:
            send_message(self.names[message[DESTINATION]], message)
            logger.info(f'Отправлено сообщение пользователю {message[DESTINATION]} от пользователя {message[SENDER]}.')
        elif message[DESTINATION] in self.names and self.names[message[DESTINATION]] not in listen_socks:
            raise ConnectionError
        else:
            logger.error(
                f'Пользователь {message[DESTINATION]} не зарегистрирован на сервере, отправка сообщения невозможна.')

    def run(self):
        # Инициализация сокета
        self.init_socket()

        while True:
            # Ждём подключения, если таймаут вышел, ловим исключение
            try:
                client, client_address = self.sock.accept()
            except OSError:
                pass
            else:
                logger.info(f'Установлено соедение с ПК {client_address}')
                self.clients.append(client)

            recv_data_lst = []
            send_data_lst = []
            err_lst = []
            # Проверяем на наличие ждущих клиентов
            try:
                if self.clients:
                    recv_data_lst, send_data_lst, err_lst = select.select(self.clients, self.clients, [], 0)
            except OSError as e:
                logger.error(f'Ошибка работы с сокетами: {e}')

            # принимаем сообщения и если ошибка, исключаем клиента
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(get_message(client_with_message), client_with_message)
                    except OSError:
                        logger.info(f'Клиент {client_with_message.getpeername()} отключился от сервера.')

                        for name in self.names:
                            if self.names[name] == client_with_message:
                                self.db.user_logout(name)
                                del self.names[name]
                                break
                        self.clients.remove(client_with_message)

            # Если есть сообщения, обрабатываем каждое
            for message in self.messages:
                try:
                    self.process_message(message, send_data_lst)
                except (ConnectionAbortedError, ConnectionError, ConnectionResetError, ConnectionRefusedError):
                    logger.info(f'Связь с клиентом с именем {message[DESTINATION]} была потеряна')
                    self.clients.remove(self.names[message[DESTINATION]])
                    self.db.user_logout(message[DESTINATION])
                    del self.names[message[DESTINATION]]
            self.messages.clear()


def print_help():
    print('Поддерживаемые комманды:')
    print('users - список известных пользователей')
    print('connected - список подключенных пользователей')
    print('loghist - история входов пользователя')
    print('exit - завершение работы сервера.')
    print('help - вывод справки по поддерживаемым командам')


def main():
    config = configparser.ConfigParser()
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config.read(f"{dir_path}/{'server.ini'}")

    # Загрузка параметров командной строки, если нет параметров, то задаём значения по умоланию
    listen_address, listen_port = arg_parser(config['SETTINGS']['default_port'], config['SETTINGS']['listen_address'])

    db = ServerStorage(os.path.join(config['SETTINGS']['db_path'], config['SETTINGS']['db_file']))

    # Создание экземпляра класса - сервера
    server = Server(listen_address, listen_port, db)
    server.daemon = True
    server.start()

    # Графическое окружение сервера
    server_app = QApplication(sys.argv)
    main_window = MainWindow()

    main_window.statusBar().showMessage('Сервер работает')
    main_window.active_clients_table.setModel(gui_create_model(db))
    main_window.active_clients_table.resizeColumnsToContents()
    main_window.active_clients_table.resizeRowsToContents()

    # Обновляет список подключённых, проверяет флаг подключения и, есели надо, обновляет список
    def list_update():
        global new_connection
        if new_connection:
            main_window.active_clients_table.setModel(gui_create_model(db))
            main_window.active_clients_table.resizeColumnsToContents()
            main_window.active_clients_table.resizeRowsToContents()
            with con_flag_lock:
                new_connection = False

    # Создаёт окно со статистикой клиентов
    def show_statistics():
        global stat_window
        stat_window = HistoryWindow()
        stat_window.history_table.setModel(create_stat_model(db))
        stat_window.history_table.resizeColumnsToContents()
        stat_window.history_table.resizeRowsToContents()
        stat_window.show()

    # Создаёт окно с настройками сервера
    def server_config():
        global config_window
        config_window = ConfigWindow()
        config_window.db_path.insert(config['SETTINGS']['db_path'])
        config_window.db_file.insert(config['SETTINGS']['db_file'])
        config_window.port.insert(config['SETTINGS']['default_port'])
        config_window.ip.insert(config['SETTINGS']['listen_address'])
        config_window.save_btn.clicked.connect(save_server_config)

    # Сохраняет настройки
    def save_server_config():
        global config_window
        message = QMessageBox()
        config['SETTINGS']['db_path'] = config_window.db_path.text()
        config['SETTINGS']['db_file'] = config_window.db_file.text()
        try:
            port = int(config_window.port.text())
        except ValueError:
            message.warning(config_window, 'Ошибка!', 'Порт должен быть числом!')
        else:
            config['SETTINGS']['listen_address'] = config_window.ip.text()
            if 1023 < port < 65536:
                config['SETTINGS']['default_port'] = str(port)

                with open('server.ini', 'w') as conf:
                    config.write(conf)
                    message.information(config_window, 'OK', 'Настройки успешно сохранены!')
            else:
                message.warning(config_window, 'Ошибка!', 'Порт должен быть от 1024 до 65536')

    # Обновляет список клиентов раз в секунду
    timer = QTimer()
    timer.timeout.connect(list_update)
    timer.start(1000)

    # Связываем кнопки с процедурами
    main_window.refresh_btn.triggered.connect(list_update)
    main_window.show_history_btn.triggered.connect(show_statistics)
    main_window.config_btn.triggered.connect(server_config)

    server_app.exec_()


if __name__ == '__main__':
    main()
