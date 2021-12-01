from datetime import datetime

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import mapper, sessionmaker


class ClientDatabase:
    class KnownUsers:
        def __init__(self, user):
            self.id = None
            self.username = user

    class MessageHistory:
        def __init__(self, from_user, to_user, message):
            self.id = None
            self.from_user = from_user
            self.to_user = to_user
            self.message = message
            self.date = datetime.now()

    class Contacts:
        def __init__(self, contact):
            self.id = None
            self.name = contact

    def __init__(self, name):
        self.db_engine = create_engine(f'sqlite:///client_{name}.db3', echo=False, pool_recycle=7200,
                                       connect_args={'check_same_thread': False})
        self.metadata = MetaData()

        # Известные пользователи
        users = Table('known_users', self.metadata,
                      Column('id', Integer, primary_key=True),
                      Column('username', String))

        # История сообщений
        history = Table('message_history', self.metadata,
                        Column('id', Integer, primary_key=True),
                        Column('from_user', String),
                        Column('to_user', String),
                        Column('message', Text),
                        Column('date', DateTime))

        # Контакты
        contacts = Table('contacts', self.metadata,
                         Column('id', Integer, primary_key=True),
                         Column('name', String, unique=True))

        self.metadata.create_all(self.db_engine)

        # Отображения
        mapper(self.KnownUsers, users)
        mapper(self.MessageHistory, history)
        mapper(self.Contacts, contacts)

        Session = sessionmaker(bind=self.db_engine)
        self.session = Session()

        self.session.query(self.Contacts).delete()
        self.session.commit()

    # Добавляет контакт
    def add_contact(self, contact):
        if not self.session.query(self.Contacts).filter_by(name=contact).count():
            contact_row = self.Contacts(contact)
            self.session.add(contact_row)
            self.session.commit()

    # Удаляет контакт
    def remove_contact(self, contact):
        self.session.query(self.Contacts).filter_by(name=contact).delete()

    # Добавляет известных пользователей
    def add_users(self, users_list):
        self.session.query(self.KnownUsers).delete()

        for user in users_list:
            user_row = self.KnownUsers(user)
            self.session.add(user_row)
        self.session.commit()

    # Сохраняет сообщения
    def save_message(self, from_user, to_user, message):
        message_row = self.MessageHistory(from_user, to_user, message)
        self.session.add(message_row)
        self.session.commit()

    # Возвращает контакты
    def get_contacts(self):
        return [contact[0] for contact in self.session.query(self.Contacts.name).all()]

    # Список известных пользователей
    def get_users(self):
        return [user[0] for user in self.session.query(self.KnownUsers.username).all()]

    # Проверка наличия пользователя в известных
    def check_user(self, user):
        if self.session.query(self.KnownUsers).filter_by(username=user).count():
            return True
        else:
            return False

    # Проверка наличия пользователя в контактах
    def check_contact(self, contact):
        if self.session.query(self.Contacts).filter_by(name=contact).count():
            return True
        else:
            return False

    # История переписки
    def get_history(self, from_whom=None, to_whom=None):
        query = self.session.query(self.MessageHistory)
        if from_whom:
            query = query.filter_by(from_user=from_whom)
        if to_whom:
            query = query.filter_by(to_user=to_whom)
        return [(hist_row.from_user, hist_row.to_user, hist_row.message, hist_row.date) for hist_row in query.all()]


if __name__ == '__main__':
    test_db = ClientDatabase('wasya')
    for contact in ['masya', 'beaver', 'ipsum']:
        test_db.add_contact(contact)
    test_db.add_contact('someone')

    test_db.add_users(['test1', 'test2', 'test3', 'test4', 'test5'])
    test_db.save_message('test1', 'test2', f'Привет! я тестовое сообщение, время: {datetime.now()}!')
    test_db.save_message('test2', 'test1', f'Привет! я другое тестовое сообщение, время: {datetime.now()}!')

    print(test_db.get_contacts())
    print(test_db.get_users())
    print(test_db.check_user('test1'))
    print(test_db.check_user('test10'))
    print(test_db.get_history('test2'))
    print(test_db.get_history(to_whom='test2'))
    print(test_db.get_history('test3'))
    test_db.remove_contact('someone')
    print(test_db.get_contacts())
