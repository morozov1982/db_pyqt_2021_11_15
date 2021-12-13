from base64 import b64encode, b64decode
from json import JSONDecodeError
import sys
from logging import getLogger


from Cryptodome.Cipher import PKCS1_OAEP
from Cryptodome.PublicKey import RSA
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor
from PyQt5.QtWidgets import QMainWindow, qApp, QMessageBox

sys.path.append('../')
from client.del_contact import DelContactDialog
from client.add_contact import AddContactDialog
from client.client_ui import Ui_MainClientWindow
from common.errors import ServerError
from common.variables import MESSAGE_TEXT, SENDER

logger = getLogger('client')


class ClientMainWindow(QMainWindow):
    """
    Класс - основное окно пользователя.
    Содержит всю основную логику работы клиентского модуля.
    Конфигурация окна создана в QTDesigner
    и загружается из конвертированого файла client_ui.py
    """

    def __init__(self, db, transport, keys):
        super().__init__()
        self.db = db
        self.transport = transport

        # объект - дешифорвщик сообщений с предзагруженным ключём
        self.decrypter = PKCS1_OAEP.new(keys)

        self.ui = Ui_MainClientWindow()
        self.ui.setupUi(self)

        self.ui.menu_exit.triggered.connect(qApp.exit)

        self.ui.btn_send.clicked.connect(self.send_message)

        self.ui.btn_add_contact.clicked.connect(self.add_contact_window)
        self.ui.menu_add_contact.triggered.connect(self.add_contact_window)

        self.ui.btn_remove_contact.clicked.connect(self.delete_contact_window)
        self.ui.menu_del_contact.triggered.connect(self.delete_contact_window)

        self.contacts_model = None
        self.history_model = None
        self.messages = QMessageBox()
        self.current_chat = None
        self.current_chat_key = None
        self.encryptor = None

        self.ui.list_messages.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)
        self.ui.list_messages.setWordWrap(True)

        self.ui.list_contacts.doubleClicked.connect(self.select_active_user)

        self.clients_list_update()
        self.set_disabled_input()
        self.show()

    def set_disabled_input(self):
        """Метод делающий поля ввода неактивными"""
        self.ui.label_new_message.setText(
            'Для выбора получателя дважды кликните на его имя '
            'в списке контактов')
        self.ui.text_message.clear()
        if self.history_model:
            self.history_model.clear()

        self.ui.btn_clear.setDisabled(True)
        self.ui.btn_send.setDisabled(True)
        self.ui.text_message.setDisabled(True)

        self.encryptor = None
        self.current_chat = None
        self.current_chat_key = None

    def history_list_update(self):
        """
        Метод заполняющий соответствующий QListView историей переписки
        с текущим собеседником.
        """
        lst = sorted(self.db.get_history(self.current_chat),
                     key=lambda item: item[3])

        if not self.history_model:
            self.history_model = QStandardItemModel()
            self.ui.list_messages.setModel(self.history_model)

        self.history_model.clear()

        length = len(lst)
        start_index = 0
        if length > 20:
            start_index = length - 20

        for i in range(start_index, length):
            item = lst[i]
            if item[1] == "in":
                mess = QStandardItem(
                    f'Входящее от {item[3].replace(microsecond=0)}:\n '
                    f'{item[2]}')
                mess.setEditable(False)
                mess.setBackground(QBrush(QColor(255, 213, 213)))
                mess.setTextAlignment(Qt.AlignLeft)
                self.history_model.appendRow(mess)
            else:
                mess = QStandardItem(
                    f'Исходящее от {item[3].replace(microsecond=0)}:\n '
                    f'{item[2]}')
                mess.setEditable(False)
                mess.setTextAlignment(Qt.AlignRight)
                mess.setBackground(QBrush(QColor(204, 255, 204)))
                self.history_model.appendRow(mess)

            self.ui.list_messages.scrollToBottom()

    def select_active_user(self):
        """Метод обработчик события двойного клика по списку контактов."""
        self.current_chat = self.ui.list_contacts.currentIndex().data()
        self.set_active_user()

    def set_active_user(self):
        """Метод активации чата с собеседником."""
        try:
            self.current_chat_key = self.transport.key_request(
                self.current_chat)
            logger.debug(f'Загружен открытый ключ для {self.current_chat}')

            if self.current_chat_key:
                self.encryptor = PKCS1_OAEP.new(
                    RSA.import_key(self.current_chat_key))

        except (OSError, JSONDecodeError):
            self.current_chat_key = None
            self.encryptor = None
            logger.debug(f'Не удалось получить ключ для {self.current_chat}')

        if not self.current_chat_key:
            self.messages.warning(self, 'Ошибка',
                                  'Для выбранного пользователя '
                                  'нет ключа шифрования')
            return

        self.ui.label_new_message.setText(
            f'Введите сообщение для {self.current_chat}:')
        self.ui.btn_clear.setDisabled(False)
        self.ui.btn_send.setDisabled(False)
        self.ui.text_message.setDisabled(False)

        self.history_list_update()

    def clients_list_update(self):
        """Метод обновляющий список контактов."""
        contacts_list = self.db.get_contacts()
        self.contacts_model = QStandardItemModel()
        for i in sorted(contacts_list):
            item = QStandardItem(i)
            item.setEditable(False)
            self.contacts_model.appendRow(item)
        self.ui.list_contacts.setModel(self.contacts_model)

    def add_contact_window(self):
        """Метод создающий окно - диалог добавления контакта"""
        # global select_dialog
        select_dialog = AddContactDialog(self.transport, self.db)
        select_dialog.btn_ok.clicked.connect(
            lambda: self.add_contact_action(select_dialog))
        select_dialog.show()

    def add_contact_action(self, item):
        """Метод обработчк нажатия кнопки «Добавить»"""
        new_contact = item.selector.currentText()
        self.add_contact(new_contact)
        item.close()

    def add_contact(self, new_contact):
        """
        Метод добавляющий контакт в серверную и клиентсткую базы данных.
        После обновления баз данных обновляет и содержимое окна.
        """
        try:
            self.transport.add_contact(new_contact)
        except ServerError as err:
            self.messages.critical(self, 'Ошибка сервера', err.text)
        except OSError as err:
            if err.errno:
                self.messages.critical(self, 'Ошибка',
                                       'Потеряно соединение с сервером!')
                self.close()
            self.messages.critical(self, 'Ошибка', 'Таймаут соединения!')
        else:
            self.db.add_contact(new_contact)
            new_contact = QStandardItem(new_contact)
            new_contact.setEditable(False)
            self.contacts_model.appendRow(new_contact)
            logger.info(f'Успешно добавлен контакт {new_contact}')
            self.messages.information(self, 'Успех',
                                      'Контакт успешно добавлен')

    def delete_contact_window(self):
        """Метод создающий окно удаления контакта."""
        # global remove_dialog
        remove_dialog = DelContactDialog(self.db)
        remove_dialog.btn_ok.clicked.connect(
            lambda: self.delete_contact(remove_dialog))
        remove_dialog.show()

    def delete_contact(self, item):
        """
        Метод удаляющий контакт из серверной и клиентсткой баз данных.
        После обновления баз данных обновляет и содержимое окна.
        """
        selected = item.selector.currentText()
        try:
            self.transport.remove_contact(selected)
        except ServerError as err:
            self.messages.critical(self, 'Ошибка сервера', err.text)
        except OSError as err:
            if err.errno:
                self.messages.critical(self, 'Ошибка',
                                       'Потеряно соединение с сервером!')
                self.close()
            self.messages.critical(self, 'Ошибка', 'Таймаут соединения!')
        else:
            self.db.del_contact(selected)
            self.clients_list_update()
            logger.info(f'Успешно удалён контакт {selected}')
            self.messages.information(self, 'Успех', 'Контакт успешно удалён')
            item.close()
            # При удалении активного пользователя деактивируем поля ввода
            if selected == self.current_chat:
                self.current_chat = None
                self.set_disabled_input()

    def send_message(self):
        """
        Функция отправки сообщения текущему собеседнику.
        Реализует шифрование сообщения и его отправку.
        """
        message_text = self.ui.text_message.toPlainText()
        self.ui.text_message.clear()
        if not message_text:
            return

        # Шифруем сообщение ключом получателя и упаковываем в base64
        message_text_encrypted = self.encryptor.encrypt(
            message_text.encode('utf8'))
        message_text_encrypted_base64 = b64encode(
            message_text_encrypted)

        try:
            self.transport.send_message(
                self.current_chat,
                message_text_encrypted_base64.decode('ascii'))
        except ServerError as err:
            self.messages.critical(self, 'Ошибка', err.text)
        except OSError as err:
            if err.errno:
                self.messages.critical(self, 'Ошибка',
                                       'Потеряно соединение с сервером!')
                self.close()
            self.messages.critical(self, 'Ошибка', 'Таймаут соединения!')
        except (ConnectionResetError, ConnectionAbortedError):
            self.messages.critical(self, 'Ошибка',
                                   'Потеряно соединение с сервером!')
            self.close()
        else:
            self.db.save_message(self.current_chat, 'out', message_text)
            logger.debug(f'Отправлено сообщение для {self.current_chat}: '
                         f'{message_text}')
            self.history_list_update()

    @pyqtSlot(dict)
    def message(self, message):
        """
        Слот обработчик поступаемых сообщений.
        Выполняет дешифровку поступаемых сообщений и их сохранение
        в истории сообщений. Запрашивает пользователя если пришло сообщение
        не от текущего собеседника.
        При необходимости меняет собеседника.
        """

        encrypted_message = b64decode(message[MESSAGE_TEXT])

        try:
            decrypted_message = self.decrypter.decrypt(encrypted_message)
        except (ValueError, TypeError):
            self.messages.warning(self, 'Ошибка',
                                  'Не удалось декодировать сообщение.')
            return

        self.db.save_message(
            self.current_chat, 'in', decrypted_message.decode('utf-8'))

        sender = message[SENDER]
        if sender == self.current_chat:
            self.history_list_update()
        else:
            if self.db.check_contact(sender):
                if self.messages.question(
                        self,
                        'Новое сообщение',
                        f'Получено новое сообщение от {sender}, '
                        f'открыть чат с ним?',
                        QMessageBox.No) == QMessageBox.Yes:
                    self.current_chat = sender
                    self.set_active_user()
            else:
                print('NO')
                if self.messages.question(
                        self,
                        'Новое сообщение',
                        f'Получено новое сообщение от {sender}.\n '
                        f'Данного пользователя нет в вашем контакт-листе.\n '
                        f'Добавить в контакты и открыть чат с ним?',
                        QMessageBox.Yes,
                        QMessageBox.No) == QMessageBox.Yes:
                    self.add_contact(sender)
                    self.current_chat = sender
                    self.db.save_message(
                        self.current_chat,
                        'in',
                        decrypted_message.decode('utf-8'))
                    self.set_active_user()

    @pyqtSlot()
    def connection_lost(self):
        """
        Слот обработчик потери соеднинения с сервером.
        Выдаёт окно предупреждение и завершает работу приложения.
        """
        self.messages.warning(self, 'Сбой соединения',
                              'Потеряно соединение с сервером')
        self.close()

    @pyqtSlot()
    def sig_205(self):
        """Слот выполняющий обновление баз данных по команде сервера."""
        if self.current_chat and not self.db.check_user(self.current_chat):
            self.messages.warning(self, 'Сочувствую',
                                  'Данный собеседник был удалён с сервера.')
            self.set_disabled_input()
            self.current_chat = None
        self.clients_list_update()

    def make_connection(self, trans_obj):
        """Метод обеспечивающий соединение сигналов и слотов."""
        trans_obj.new_message.connect(self.message)
        trans_obj.connection_lost.connect(self.connection_lost)
        trans_obj.message_205.connect(self.sig_205)
