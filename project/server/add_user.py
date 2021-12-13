from binascii import hexlify
from hashlib import pbkdf2_hmac

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, \
    QMessageBox, QApplication


class RegisterUser(QDialog):
    """Класс диалог регистрации пользователя на сервере."""

    def __init__(self, db, server):
        super().__init__()

        self.db = db
        self.server = server

        self.setWindowTitle('Регистрация')
        self.setFixedSize(175, 183)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.label_username = QLabel('Введите имя пользователя:', self)
        self.label_username.move(10, 10)
        self.label_username.setFixedSize(150, 15)

        self.client_name = QLineEdit(self)
        self.client_name.setFixedSize(154, 20)
        self.client_name.move(10, 30)

        self.label_password = QLabel('Введите пароль:', self)
        self.label_password.move(10, 55)
        self.label_password.setFixedSize(150, 15)

        self.client_password = QLineEdit(self)
        self.client_password.setFixedSize(154, 20)
        self.client_password.move(10, 75)
        self.client_password.setEchoMode(QLineEdit.Password)
        self.label_conf = QLabel('Введите подтверждение:', self)
        self.label_conf.move(10, 100)
        self.label_conf.setFixedSize(150, 15)

        self.client_conf = QLineEdit(self)
        self.client_conf.setFixedSize(154, 20)
        self.client_conf.move(10, 120)
        self.client_conf.setEchoMode(QLineEdit.Password)

        self.btn_ok = QPushButton('Сохранить', self)
        self.btn_ok.move(10, 150)
        self.btn_ok.clicked.connect(self.save_data)

        self.btn_cancel = QPushButton('Выход', self)
        self.btn_cancel.move(90, 150)
        self.btn_cancel.clicked.connect(self.close)

        self.messages = QMessageBox()

        self.show()

    def save_data(self):
        """
        Метод проверки правильности ввода
        и сохранения в базу нового пользователя.
        """
        if not self.client_name.text():
            self.messages.critical(
                self, 'Ошибка', 'Не указано имя пользователя')
            return
        elif self.client_password.text() != self.client_conf.text():
            self.messages.critical(
                self, 'Ошибка', 'Введённые пароли не совпадают')
            return
        elif self.db.check_user(self.client_name.text()):
            self.messages.critical(
                self, 'Ошибка', 'Пользователь уже существует')
            return
        else:
            # Генерируем хэш пароля, соль - логин в нижнем регистре
            password_bytes = self.client_password.text().encode('utf-8')
            print(password_bytes)
            salt = self.client_name.text().lower().encode('utf-8')
            print(salt)
            password_hash = pbkdf2_hmac(
                'sha512', password_bytes, salt, 10000)
            print(password_hash)
            self.db.add_user(
                self.client_name.text(), hexlify(password_hash))
            self.messages.information(
                self, 'Успех', 'Пользователь успешно зарегистрирован')
            self.server.service_update_lists()
            self.close()


if __name__ == '__main__':
    app = QApplication([])
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
    dial = RegisterUser(None)
    app.exec_()
