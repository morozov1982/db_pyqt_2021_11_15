from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import mapper, sessionmaker
from datetime import datetime


class ServerStorage:
    """
    Класс-оболочка для работы с базой данных сервера.
    Использует SQLite базу данных, реализован с помощью
    SQLAlchemy ORM и применён классический подход.
    """
    class AllUsers:
        """Класс-отображение таблицы всех пользователей."""
        def __init__(self, username, password_hash):
            self.id = None
            self.name = username
            self.last_login = datetime.now()
            self.password_hash = password_hash
            self.pubkey = None

    class ActiveUsers:
        """Класс-отображение таблицы активных пользователей."""
        def __init__(self, user_id, ip_address, port, login_time):
            self.id = None
            self.user = user_id
            self.ip_address = ip_address
            self.port = port
            self.login_time = login_time

    class LoginHistory:
        """Класс-отображение таблицы истории входов."""
        def __init__(self, name, date, ip, port):
            self.id = None
            self.name = name
            self.date_time = date
            self.ip = ip
            self.port = port

    class UsersContacts:
        """Класс-отображение таблицы контактов пользователей."""
        def __init__(self, user, contact):
            self.id = None
            self.user = user
            self.contact = contact

    class UsersHistory:
        """Класс-отображение таблицы истории действий."""
        def __init__(self, user):
            self.id = None
            self.user = user
            self.sent = 0
            self.accepted = 0

    def __init__(self, path):
        self.db_engine = create_engine(f'sqlite:///{path}', echo=False, pool_recycle=7200,
                                       connect_args={'check_same_thread': False})
        self.metadata = MetaData()

        # Пользователи
        users_table = Table('Users', self.metadata,
                            Column('id', Integer, primary_key=True),
                            Column('name', String, unique=True),
                            Column('last_login', DateTime),
                            Column('password_hash', String),
                            Column('pubkey', Text))

        # Активные пользователи
        active_users_table = Table('Active_users', self.metadata,
                                   Column('id', Integer, primary_key=True),
                                   Column('user', ForeignKey('Users.id'), unique=True),
                                   Column('ip_address', String),
                                   Column('port', Integer),
                                   Column('login_time', DateTime))

        # История входов
        user_login_history = Table('Login_history', self.metadata,
                                   Column('id', Integer, primary_key=True),
                                   Column('name', ForeignKey('Users.id')),
                                   Column('date_time', DateTime),
                                   Column('ip', String),
                                   Column('port', String))

        # Контакты пользователей
        contacts = Table('Contacts', self.metadata,
                         Column('id', Integer, primary_key=True),
                         Column('user', ForeignKey('Users.id')),
                         Column('contact', ForeignKey('Users.id')))

        # История пользователей
        users_history_table = Table('History', self.metadata,
                                    Column('id', Integer, primary_key=True),
                                    Column('user', ForeignKey('Users.id')),
                                    Column('sent', Integer),
                                    Column('accepted', Integer))

        self.metadata.create_all(self.db_engine)

        mapper(self.AllUsers, users_table)
        mapper(self.ActiveUsers, active_users_table)
        mapper(self.LoginHistory, user_login_history)
        mapper(self.UsersContacts, contacts)
        mapper(self.UsersHistory, users_history_table)

        Session = sessionmaker(bind=self.db_engine)
        self.session = Session()

        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    def user_login(self, username, ip_address, port, key):
        """
        Метод выполняющийся при входе пользователя, записывает в базу факт входа.
        Обновляет открытый ключ пользователя при его изменении.
        """
        res = self.session.query(self.AllUsers).filter_by(name=username)

        if res.count():
            user = res.first()
            user.last_login = datetime.now()
            if user.pubkey != key:
                user.pubkey = key
        else:
            raise ValueError('Пользователь не зарегистрирован')

        new_active_user = self.ActiveUsers(user.id, ip_address, port, datetime.now())
        self.session.add(new_active_user)

        history = self.LoginHistory(user.id, datetime.now(), ip_address, port)
        self.session.add(history)

        self.session.commit()

    def add_user(self, name, password_hash):
        """
        Метод регистрации пользователя.
        Принимает имя и хэш пароля, создаёт запись в таблице статистики.
        """
        user_row = self.AllUsers(name, password_hash)
        self.session.add(user_row)
        self.session.commit()
        history_row = self.UsersHistory(user_row.id)
        self.session.add(history_row)
        self.session.commit()

    def remove_user(self, name):
        """Метод удаляющий пользователя из базы."""
        user = self.session.query(self.AllUsers).filter_by(name=name).first()
        self.session.query(self.ActiveUsers).filter_by(user=user.id).delete()
        self.session.query(self.LoginHistory).filter_by(name=user.id).delete()
        self.session.query(self.UsersContacts).filter_by(user=user.id).delete()
        self.session.query(self.UsersContacts).filter_by(contact=user.id).delete()
        self.session.query(self.UsersHistory).filter_by(user=user.id).delete()
        self.session.query(self.AllUsers).filter_by(name=name).delete()
        self.session.commit()

    def get_hash(self, name):
        """Метод получения хэша пароля пользователя."""
        user = self.session.query(self.AllUsers).filter_by(name=name).first()
        return user.password_hash

    def get_pubkey(self, name):
        """Метод получения публичного ключа пользователя."""
        user = self.session.query(self.AllUsers).filter_by(name=name).first()
        return user.pubkey

    def check_user(self, name):
        """Метод проверяющий существование пользователя."""
        if self.session.query(self.AllUsers).filter_by(name=name).count():
            return True
        return False

    def user_logout(self, username):
        """Метод фиксирующий отключение пользователя."""
        user = self.session.query(self.AllUsers).filter_by(name=username).first()
        self.session.query(self.ActiveUsers).filter_by(user=user.id).delete()
        self.session.commit()

    def users_list(self):
        """Метод возвращающий список известных пользователей со временем последнего входа."""
        query = self.session.query(self.AllUsers.name, self.AllUsers.last_login)
        return query.all()

    def active_users_list(self):
        """Метод возвращающий список активных пользователей."""
        query = self.session.query(self.AllUsers.name, self.ActiveUsers.ip_address, self.ActiveUsers.port,
                                   self.ActiveUsers.login_time).join(self.AllUsers)
        return query.all()

    def login_history(self, username=None):
        """Метод возвращающий историю входов."""
        query = self.session.query(self.AllUsers.name,
                                   self.LoginHistory.date_time,
                                   self.LoginHistory.ip,
                                   self.LoginHistory.port
                                   ).join(self.AllUsers)
        if username:
            query = query.filter(self.AllUsers.name == username)
        return query.all()

    def process_message(self, sender, recipient):
        """Метод записывающий в таблицу статистики факт передачи сообщения."""
        sender = self.session.query(self.AllUsers).filter_by(name=sender).first().id
        recipient = self.session.query(self.AllUsers).filter_by(name=recipient).first().id
        sender_row = self.session.query(self.UsersHistory).filter_by(user=sender).first()
        sender_row.sent += 1
        recipient_row = self.session.query(self.UsersHistory).filter_by(user=recipient).first()
        recipient_row.accepted += 1

        self.session.commit()

    def add_contact(self, user, contact):
        """Метод добавления контакта для пользователя."""
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()

        if not contact or self.session.query(self.UsersContacts).filter_by(user=user.id, contact=contact.id).count():
            return

        contact_row = self.UsersContacts(user.id, contact.id)
        self.session.add(contact_row)
        self.session.commit()

    def remove_contact(self, user, contact):
        """Метод удаления контакта пользователя."""
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()

        if not contact:
            return

        self.session.query(self.UsersContacts).filter(self.UsersContacts.user == user.id,
                                                      self.UsersContacts.contact == contact.id).delete()
        self.session.commit()

    def get_contacts(self, username):
        """Метод возвращающий список контактов пользователя."""
        user = self.session.query(self.AllUsers).filter_by(name=username).one()

        query = self.session.query(self.UsersContacts, self.AllUsers.name).filter_by(user=user.id). \
            join(self.AllUsers, self.UsersContacts.contact == self.AllUsers.id)

        return [contact[1] for contact in query.all()]

    def message_history(self):
        """Метод возвращающий статистику сообщений."""
        query = self.session.query(
            self.AllUsers.name,
            self.AllUsers.last_login,
            self.UsersHistory.sent,
            self.UsersHistory.accepted
        ).join(self.AllUsers)

        return query.all()


if __name__ == '__main__':
    test_db = ServerStorage('server_base.db3')
    # test_db.user_login('wasya', '192.168.0.10', 7777)
    # test_db.user_login('masya', '192.168.0.20', 7778)
    # print(test_db.active_users_list())
    # test_db.user_logout('masya')
    # print(test_db.active_users_list())
    # test_db.login_history('masya')
    # test_db.login_history('wasya')
    # print(test_db.users_list())

    test_db.add_contact('wasya', 'masya')
    test_db.add_contact('masya', 'wasya')

    print(test_db.get_contacts('masya'))
    print(test_db.get_contacts('wasya'))

    test_db.remove_contact('masya', 'wasya')

    print(test_db.get_contacts('masya'))
    print(test_db.get_contacts('wasya'))

    # test_db.process_message('masya', 'wasya')
    print(test_db.message_history())
