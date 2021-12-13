import hmac
from binascii import hexlify, a2b_base64
from json import JSONDecodeError
from logging import getLogger
from os import urandom
from select import select
from threading import Thread
from socket import socket, AF_INET, SOCK_STREAM

from common.descriptors import Addr, Port
from common.utils import get_message, send_message
from common.variables import MAX_CONNECTIONS, DESTINATION, SENDER, ACTION, \
    PRESENCE, TIME, USER, MESSAGE, MESSAGE_TEXT, RESPONSE_200, RESPONSE_400, \
    ERROR, EXIT, ACCOUNT_NAME, GET_CONTACTS, RESPONSE_202, LIST_INFO, \
    ADD_CONTACT, REMOVE_CONTACT, USERS_REQUEST, PUBLIC_KEY_REQUEST, \
    RESPONSE_511, DATA, RESPONSE, PUBLIC_KEY, RESPONSE_205
from common.decos import login_required


# Инициализация логирования сервера
logger = getLogger('server')


# Основной класс сервера
class MessageProcessor(Thread):
    """
    Основной класс сервера.
    Принимает содинения, словари - пакеты от клиентов,
    обрабатывает поступающие сообщения.
    Работает в качестве отдельного потока.
    """
    addr = Addr()
    port = Port()

    def __init__(self, listen_address, listen_port, db):
        # Параметры подключения
        self.addr = listen_address
        self.port = listen_port

        # БД сервера
        self.db = db

        # Сокет, через который будет осуществляться работа
        self.sock = None

        # список клиентов
        self.clients = []

        # Сокеты
        self.listen_sockets = None
        self.error_sockets = None

        # Флаг продолжения работы
        self.running = True

        # Словарь, содержащий имена пользователей и соответствующие им сокеты
        self.names = dict()

        super().__init__()

    def init_socket(self):
        """Метод инициализатор сокета."""

        logger.info(
            f'Запущен сервер, порт для подключений: {self.port}, '
            f'адрес с которого принимаются подключения: {self.addr}. '
            f'Если адрес не указан, принимаются соединения с любых адресов.')
        # Готовим сокет
        transport = socket(AF_INET, SOCK_STREAM)
        transport.bind((self.addr, self.port))
        transport.settimeout(0.5)

        # Слушаем порт
        self.sock = transport
        self.sock.listen(MAX_CONNECTIONS)

    @login_required
    def process_client_message(self, message, client):
        """Метод отбработчик поступающих сообщений."""

        logger.debug(f'Разбор сообщения от клиента: {message}')

        # Если это сообщение о присутствии, принимаем и отвечаем
        if ACTION in message and message[ACTION] == PRESENCE \
                and TIME in message and USER in message:
            # Вызываем функцию авторизации
            self.authorize_user(message, client)

        # Если это сообщение, то отправляем его получателю
        elif ACTION in message and message[ACTION] == MESSAGE \
                and DESTINATION in message and TIME in message \
                and SENDER in message and MESSAGE_TEXT in message \
                and self.names[message[SENDER]] == client:
            if message[DESTINATION] in self.names:
                self.db.process_message(message[SENDER], message[DESTINATION])
                self.process_message(message)
                try:
                    send_message(client, RESPONSE_200)
                except OSError:
                    self.remove_client(client)
            else:
                response = RESPONSE_400
                response[ERROR] = 'Пользователь не зарегистрирован на сервере'
                try:
                    send_message(client, response)
                except OSError:
                    pass
            return

        # При выходе клиента
        elif ACTION in message and message[ACTION] == EXIT \
                and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            self.remove_client(client)

        # При запросе контакт-листа
        elif ACTION in message and message[ACTION] == GET_CONTACTS \
                and USER in message and \
                self.names[message[USER]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = self.db.get_contacts(message[USER])
            try:
                send_message(client, response)
            except OSError:
                self.remove_client(client)

        # При добавлении контакта
        elif ACTION in message and message[ACTION] == ADD_CONTACT \
                and ACCOUNT_NAME in message and USER in message \
                and self.names[message[USER]] == client:
            self.db.add_contact(message[USER], message[ACCOUNT_NAME])
            try:
                send_message(client, RESPONSE_200)
            except OSError:
                self.remove_client(client)

        # При удалении контакта
        elif ACTION in message and message[ACTION] == REMOVE_CONTACT \
                and ACCOUNT_NAME in message and USER in message \
                and self.names[message[USER]] == client:
            self.db.remove_contact(message[USER], message[ACCOUNT_NAME])
            try:
                send_message(client, RESPONSE_200)
            except OSError:
                self.remove_client(client)

        # При запросе известных пользователей
        elif ACTION in message and message[ACTION] == USERS_REQUEST \
                and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = [user[0] for user in self.db.users_list()]
            try:
                send_message(client, response)
            except OSError:
                self.remove_client(client)

        # При запросе публичного ключа пользователя
        elif ACTION in message and message[ACTION] == PUBLIC_KEY_REQUEST \
                and ACCOUNT_NAME in message:
            response = RESPONSE_511
            response[DATA] = self.db.get_pubkey(message[ACCOUNT_NAME])
            # если пользователь никогда не логинился
            if response[DATA]:
                try:
                    send_message(client, response)
                except OSError:
                    self.remove_client(client)
            else:
                response = RESPONSE_400
                response[ERROR] = 'Для данного пользователя ' \
                                  'нет публичного ключа'
                try:
                    send_message(client, response)
                except OSError:
                    self.remove_client(client)

        # Иначе отдаём Bad request
        else:
            response = RESPONSE_400
            response[ERROR] = 'Запрос некорректен'
            try:
                send_message(client, response)
            except OSError:
                self.remove_client(client)

    def process_message(self, message):
        """Метод отправки сообщения клиенту."""

        if message[DESTINATION] in self.names \
                and self.names[message[DESTINATION]] in self.listen_sockets:
            try:
                send_message(self.names[message[DESTINATION]], message)
                logger.info(f'Отправлено сообщение пользователю '
                            f'{message[DESTINATION]} '
                            f'от пользователя {message[SENDER]}.')
            except OSError:
                self.remove_client(message[DESTINATION])
        elif message[DESTINATION] in self.names \
                and self.names[message[DESTINATION]] not in self.listen_sockets:
            logger.error(f'Связь с клиентом {message[DESTINATION]} '
                         f'была потеряна. '
                         f'Соединение закрыто, доставка невозможна.')
            self.remove_client(self.names[message[DESTINATION]])
        else:
            logger.error(f'Пользователь {message[DESTINATION]} '
                         f'не зарегистрирован на сервере, '
                         f'отправка сообщения невозможна.')

    def run(self):
        """Метод основной цикл потока."""

        self.init_socket()

        while self.running:
            # Ждём подключения, если таймаут вышел, ловим исключение
            try:
                client, client_address = self.sock.accept()
            except OSError:
                pass
            else:
                logger.info(f'Установлено соедение с ПК {client_address}')
                client.settimeout(5)
                self.clients.append(client)

            recv_data_lst = []
            send_data_lst = []
            err_lst = []
            # Проверяем на наличие ждущих клиентов
            try:
                if self.clients:
                    recv_data_lst, self.listen_sockets, self.error_sockets = select(
                        self.clients, self.clients, [], 0)
            except OSError as e:
                logger.error(f'Ошибка работы с сокетами: {e.errno}')

            # принимаем сообщения и если ошибка, исключаем клиента
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(
                            get_message(client_with_message),
                            client_with_message)
                    except (OSError, JSONDecodeError, TypeError) as err:
                        logger.debug('Получены данне о клиентском исключени.',
                                     exc_info=err)
                        self.remove_client(client_with_message)

    def remove_client(self, client):
        """
        Метод обработчик клиента с которым прервана связь.
        Ищет клиента и удаляет его из списков и базы.
        """
        logger.info(f'Клиент {client.getpeername()} отключился от сервера.')
        for name in self.names:
            if self.names[name] == client:
                self.db.user_logout(name)
                del self.names[name]
                break
        self.clients.remove(client)
        client.close()

    def authorize_user(self, message, sock):
        """Метод реализующий авторизцию пользователей."""
        logger.debug(f'Начало авторизации {message[USER]}')

        # Если имя пользователя уже занято, возвращаем 400
        if message[USER][ACCOUNT_NAME] in self.names.keys():
            response = RESPONSE_400
            response[ERROR] = 'Имя пользователя уже занято'

            try:
                logger.debug(f'Имя пользователя занято, отправка {response}')
                send_message(sock, response)
            except OSError:
                logger.debug('OS Error')
            self.clients.remove(sock)
            sock.close()

        # Зарегистрирован ли пользователь на сервере
        elif not self.db.check_user(message[USER][ACCOUNT_NAME]):
            response = RESPONSE_400
            response[ERROR] = 'Пользователь не зарегистрирован'

            try:
                logger.debug(f'Неизвестное имя пользователя, '
                             f'отправка {response}')
                send_message(sock, response)
            except OSError:
                pass
            self.clients.remove(sock)
            sock.close()

        else:
            logger.debug('Корректное имя пользователя, начало проверка пароля')
            message_auth = RESPONSE_511
            random_str = hexlify(urandom(64))
            message_auth[DATA] = random_str.decode('ascii')
            hash_ = hmac.new(
                self.db.get_hash(message[USER][ACCOUNT_NAME]),
                random_str, 'MD5')
            digest = hash_.digest()
            logger.debug(f'Сообщение аутентификации - {message_auth}')

            try:
                send_message(sock, message_auth)
                ans = get_message(sock)
            except OSError as err:
                logger.debug('Ошибка аутентификации, данные:', exc_info=err)
                sock.close()
                return

            client_digest = a2b_base64(ans[DATA])

            if RESPONSE in ans and ans[RESPONSE] == 511 \
                    and hmac.compare_digest(digest, client_digest):
                self.names[message[USER][ACCOUNT_NAME]] = sock
                client_ip, client_port = sock.getpeername()

                try:
                    send_message(sock, RESPONSE_200)
                except OSError:
                    self.remove_client(message[USER][ACCOUNT_NAME])

                self.db.user_login(
                    message[USER][ACCOUNT_NAME],
                    client_ip,
                    client_port,
                    message[USER][PUBLIC_KEY])

            else:
                response = RESPONSE_400
                response[ERROR] = 'Неверный пароль'

                try:
                    send_message(sock, response)
                except OSError:
                    pass

                self.clients.remove(sock)
                sock.close()

    def service_update_lists(self):
        """Метод реализующий отправку сервисного сообщения 205 клиентам."""
        for client in self.names:
            try:
                send_message(self.names[client], RESPONSE_205)
            except OSError:
                self.remove_client(self.names[client])
