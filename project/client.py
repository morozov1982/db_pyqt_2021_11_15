import json
import socket
import sys
import time
import argparse
import logging
import threading

import logs.config_client_log
from decos import log
from common.variables import ACTION, EXIT, TIME, ACCOUNT_NAME, MESSAGE, SENDER, DESTINATION, MESSAGE_TEXT, PRESENCE, \
    USER, RESPONSE, ERROR, DEFAULT_IP_ADDRESS, DEFAULT_PORT, GET_CONTACTS, LIST_INFO, ADD_CONTACT, USERS_REQUEST, \
    REMOVE_CONTACT
from common.utils import send_message, get_message
from errors import IncorrectDataRecivedError, ReqFieldMissingError, ServerError
from metaclasses import ClientVerifier
from client_database import ClientDatabase

# Инициализация клиентского логера
logger = logging.getLogger('client')

sock_lock = threading.Lock()
db_lock = threading.Lock()


# Класс формировки и отправки сообщений на сервер и взаимодействия с пользователем
class ClientSender(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, account_name, sock, db):
        self.account_name = account_name
        self.sock = sock
        self.db = db
        super().__init__()

    # Функция создаёт словарь с сообщением о выходе
    # @log  # Ох как я из-за этого намучился
    def create_exit_message(self):
        return {
            ACTION: EXIT,
            TIME: time.time(),
            ACCOUNT_NAME: self.account_name
        }

    # Функция запрашивает кому отправить сообщение и само сообщение, и отправляет полученные данные на сервер
    # @log  # Ох как я из-за этого намучился
    def create_message(self):
        to = input('Введите получателя сообщения: ')
        message = input('Введите сообщение для отправки: ')

        # Существует ли получатель
        with db_lock:
            if not self.db.check_user(to):
                logger.error(f'Попытка отправить сообщение незарегистрированому получателю: {to}')
                return

        message_dict = {
            ACTION: MESSAGE,
            SENDER: self.account_name,
            DESTINATION: to,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        logger.debug(f'Сформирован словарь сообщения: {message_dict}')

        with db_lock:
            self.db.save_message(self.account_name, to, message)

        with sock_lock:
            try:
                send_message(self.sock, message_dict)
                logger.info(f'Отправлено сообщение для пользователя {to}')
            except OSError as err:
                if err.errno:
                    logger.critical('Потеряно соединение с сервером!')
                    exit(1)
                else:
                    logger.error('Не удалось передать сообщениею Таймаут соединения')

    # Функция выводящяя справку по использованию
    def print_help(self):
        print('=' * 52)
        print('Поддерживаемые команды:')
        print('=' * 23)
        print('message - отправить сообщение. Кому и текст будет запрошены отдельно')
        print('history - история сообщений')
        print('contacts - список контактов')
        print('edit - редактирование списка контактов')
        print('help - вывести подсказки по командам')
        print('exit - выход из программы')
        print('=' * 25)

    # История сообщений
    def print_history(self):
        inp = input('in - показать входящие сообщения,\n'
                    'out - исходящие,\n'
                    'нажать Enter - все.\n>>> ')
        with db_lock:
            if inp == 'in':
                history_list = self.db.get_history(to_whom=self.account_name)
                for message in history_list:
                    print(f'\nСообщение от пользователя: {message[0]} от {message[3]}:\n{message[2]}')
            elif inp == 'out':
                history_list = self.db.get_history(from_whom=self.account_name)
                for message in history_list:
                    print(f'\nСообщение пользователю: {message[1]} от {message[3]}:\n{message[2]}')
            else:
                history_list = self.db.get_history()
                for message in history_list:
                    print(f'\nСообщение от пользователя: {message[0]}, '
                          f'пользователю {message[1]} от {message[3]}\n{message[2]}')

    # Изменение контактов
    def edit_contacts(self):
        inp = input('Для удаления введите - del, для добавления - add: ')
        if inp == 'del':
            edit = input('Введите имя удаляемного контакта: ')
            with db_lock:
                if self.db.check_contact(edit):
                    self.db.del_contact(edit)
                else:
                    logger.error('Попытка удаления несуществующего контакта!')
        elif inp == 'add':
            edit = input('Введите имя создаваемого контакта: ')
            if self.db.check_user(edit):
                with db_lock:
                    self.db.add_contact(edit)
                with sock_lock:
                    try:
                        add_contact(self.sock, self.account_name, edit)
                    except ServerError:
                        logger.error('Не удалось отправить информацию на сервер!')

    # Функция взаимодействия с пользователем, запрашивает команды, отправляет сообщения
    # @log  # Ох как я из-за этого намучился
    def run(self):
        self.print_help()
        while True:
            command = input('Введите команду: ')
            if command == 'message':
                self.create_message()
            elif command == 'help':
                self.print_help()
            elif command == 'exit':
                with sock_lock:
                    try:
                        send_message(self.sock, self.create_exit_message())
                    except:
                        pass
                    print('Завершение соединения.')
                    logger.info('Завершение работы по команде пользователя.')
                time.sleep(0.5)
                break

            elif command == 'contacts':
                with db_lock:
                    contacts_list = self.db.get_contacts()
                for contact in contacts_list:
                    print(contact)

            elif command == 'edit':
                self.edit_contacts()

            elif command == 'history':
                self.print_history()

            else:
                print('Команда не распознана, попробойте снова. help - вывести поддерживаемые команды.')


# Класс-приёмник сообщений с сервера. Принимает сообщения, выводит в консоль
class ClientReader(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, account_name, sock, db):
        self.account_name = account_name
        self.sock = sock
        self.db = db
        super().__init__()

    # Основной цикл приёмника сообщений, принимает сообщения, выводит в консоль.
    # Завершается при потере соединения
    # @log  # Ох как я из-за этого намучился
    def run(self):
        while True:
            time.sleep(1)
            with sock_lock:
                try:
                    message = get_message(self.sock)
                except IncorrectDataRecivedError:
                    logger.error(f'Не удалось декодировать полученное сообщение!')
                except OSError as err:
                    if err.errno:
                        logger.critical(f'Потеряно соединение с сервером!')
                        break
                except (ConnectionError, ConnectionAbortedError, ConnectionResetError, json.JSONDecodeError):
                    logger.critical(f'Потеряно соединение с сервером!')
                    break
                else:
                    if ACTION in message and message[ACTION] == MESSAGE and SENDER in message and DESTINATION in message \
                            and MESSAGE_TEXT in message and message[DESTINATION] == self.account_name:
                        print(f'\nПолучено сообщение от пользователя {message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                        with db_lock:
                            try:
                                self.db.save_message(message[SENDER], self.account_name, message[MESSAGE_TEXT])
                            except:
                                logger.error('Ошибка взаимодействия с базой данных')

                        logger.info(f'Получено сообщение от пользователя {message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                    else:
                        logger.error(f'Получено некорректное сообщение с сервера: {message}')


# Функция генерирует запрос о присутствии клиента
@log
def create_presence(account_name):
    out = {
        ACTION: PRESENCE,
        TIME: time.time(),
        USER: {
            ACCOUNT_NAME: account_name
        }
    }
    logger.debug(f'Сформировано {PRESENCE} сообщение для пользователя {account_name}')
    return out


# Функция разбирает ответ сервера на сообщение о присутствии,
# возращает 200 если все ОК или генерирует исключение при ошибке
@log
def process_response_ans(message):
    logger.debug(f'Разбор приветственного сообщения от сервера: {message}')
    if RESPONSE in message:
        if message[RESPONSE] == 200:
            return '200 : OK'
        elif message[RESPONSE] == 400:
            raise ServerError(f'400 : {message[ERROR]}')
    raise ReqFieldMissingError(RESPONSE)


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


def contacts_list_request(sock, name):
    logger.debug(f'Запрос контактов для пользователся {name}')
    req = {
        ACTION: GET_CONTACTS,
        TIME: time.time(),
        USER: name
    }
    logger.debug(f'Сформирован запрос {req}')
    send_message(sock, req)
    ans = get_message(sock)
    logger.debug(f'Получен ответ {ans}')
    if RESPONSE in ans and ans[RESPONSE] == 202:
        return ans[LIST_INFO]
    else:
        raise ServerError


def add_contact(sock, username, contact):
    logger.debug(f'Создание контакта {contact}')
    req = {
        ACTION: ADD_CONTACT,
        TIME: time.time(),
        USER: username,
        ACCOUNT_NAME: contact
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        pass
    else:
        raise ServerError('Ошибка создания контакта')
    print('Контакт создан')


def user_list_request(sock, username):
    logger.debug(f'Запрос списка известных пользователей {username}')
    req = {
        ACTION: USERS_REQUEST,
        TIME: time.time(),
        ACCOUNT_NAME: username
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 202:
        return ans[LIST_INFO]
    else:
        raise ServerError


def remove_contact(sock, username, contact):
    logger.debug(f'Создание контакта {contact}')
    req = {
        ACTION: REMOVE_CONTACT,
        TIME: time.time(),
        USER: username,
        ACCOUNT_NAME: contact
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        pass
    else:
        raise ServerError('Ошибка удаления контакта')
    print('Контакт удалён')


def db_load(sock, db, username):
    try:
        users_list = user_list_request(sock, username)
    except ServerError:
        logger.error('Ошибка запроса списка известных пользователей')
    else:
        db.add_users(users_list)

    try:
        contacts_list = contacts_list_request(sock, username)
    except ServerError:
        logger.error('Ошибка запроса списка контактов')
    else:
        for contact in contacts_list:
            db.add_contact(contact)


def main():
    # Сообщаем о запуске
    print('Консольный месседжер. Клиентский модуль.')

    # Загружаем параметы коммандной строки
    server_address, server_port, client_name = arg_parser()

    # Если имя пользователя не было задано, необходимо запросить пользователя.
    if not client_name:
        client_name = input('Введите имя пользователя: ')
    else:
        print(f'Клиентский модуль запущен с именем: {client_name}')

    logger.info(
        f'Запущен клиент с парамертами: адрес сервера: {server_address}, '
        f'порт: {server_port}, имя пользователя: {client_name}')

    # Инициализация сокета и сообщение серверу о нашем появлении
    try:
        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        transport.settimeout(1)

        transport.connect((server_address, server_port))
        send_message(transport, create_presence(client_name))
        answer = process_response_ans(get_message(transport))
        logger.info(f'Установлено соединение с сервером. Ответ сервера: {answer}')
        print(f'Установлено соединение с сервером. Имя пользователя: {client_name}')  # для удобства
    except json.JSONDecodeError:
        logger.error('Не удалось декодировать полученную JSON строку.')
        exit(1)
    except ServerError as error:
        logger.error(f'При установке соединения сервер вернул ошибку: {error.text}')
        exit(1)
    except ReqFieldMissingError as missing_error:
        logger.error(f'В ответе сервера отсутствует необходимое поле {missing_error.missing_field}')
        exit(1)
    except (ConnectionRefusedError, ConnectionError):
        logger.critical(
            f'Не удалось подключиться к серверу {server_address}:{server_port}, '
            f'конечный компьютер отверг запрос на подключение.')
        exit(1)
    else:
        db = ClientDatabase(client_name)
        db_load(transport, db, client_name)

        # Если соединение с сервером установлено корректно, запускаем поток взаимодействия с пользователем
        module_sender = ClientSender(client_name, transport, db)
        module_sender.daemon = True
        module_sender.start()
        logger.debug('Запущены процессы')

        # затем запускаем поток - приёмник сообщений
        module_receiver = ClientReader(client_name, transport, db)
        module_receiver.daemon = True
        module_receiver.start()

        # Watchdog основной цикл, если один из потоков завершён, то значит или потеряно соединение
        # или пользователь ввёл exit. Поскольку все события обработываются в потоках,
        # достаточно просто завершить цикл.
        while True:
            time.sleep(1)
            if module_receiver.is_alive() and module_sender.is_alive():
                continue
            break


if __name__ == '__main__':
    main()
