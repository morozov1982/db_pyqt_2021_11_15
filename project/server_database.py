from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import mapper, sessionmaker
from datetime import datetime

from common.variables import SERVER_DATABASE


class ServerStorage:
    class AllUsers:
        def __init__(self, username):
            self.id = None
            self.name = username
            self.last_login = datetime.now()

    class ActiveUsers:
        def __init__(self, user_id, ip_address, port, login_time):
            self.id = None
            self.user = user_id
            self.ip_address = ip_address
            self.port = port
            self.login_time = login_time

    class LoginHistory:
        def __init__(self, name, date, ip, port):
            self.id = None
            self.name = name
            self.date_time = date
            self.ip = ip
            self.port = port

    def __init__(self):
        self.db_engine = create_engine(SERVER_DATABASE, echo=False, pool_recycle=7200)
        self.metadata = MetaData()

        users_table = Table('Users', self.metadata,
                            Column('id', Integer, primary_key=True),
                            Column('name', String, unique=True),
                            Column('last_login', DateTime))

        active_users_table = Table('Active_users', self.metadata,
                                   Column('id', Integer, primary_key=True),
                                   Column('user', ForeignKey('Users.id'), unique=True),
                                   Column('ip_address', String),
                                   Column('port', Integer),
                                   Column('login_time', DateTime))

        user_login_history = Table('Login_history', self.metadata,
                                   Column('id', Integer, primary_key=True),
                                   Column('name', ForeignKey('Users.id')),
                                   Column('date_time', DateTime),
                                   Column('ip', String),
                                   Column('port', String))

        self.metadata.create_all(self.db_engine)

        mapper(self.AllUsers, users_table)
        mapper(self.ActiveUsers, active_users_table)
        mapper(self.LoginHistory, user_login_history)

        Session = sessionmaker(bind=self.db_engine)
        self.session = Session()

        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    def user_login(self, username, ip_address, port):
        print(f'Зашёл пользователь: {username, ip_address, port}')
        res = self.session.query(self.AllUsers).filter_by(name=username)

        if res.count():
            user = res.first()
            user.last_login = datetime.now()
        else:
            user = self.AllUsers(username)
            self.session.add(user)
            self.session.commit()

        new_active_user = self.ActiveUsers(user.id, ip_address, port, datetime.now())
        self.session.add(new_active_user)

        history = self.LoginHistory(user.id, datetime.now(), ip_address, port)
        self.session.add(history)

        self.session.commit()

    def user_logout(self, username):
        user = self.session.query(self.AllUsers).filter_by(name=username).first()
        self.session.query(self.ActiveUsers).filter_by(user=user.id).delete()
        self.session.commit()

    def users_list(self):
        query = self.session.query(
            self.AllUsers.name,
            self.AllUsers.last_login,
        )
        return query.all()

    def active_users_list(self):
        query = self.session.query(
            self.AllUsers.name,
            self.ActiveUsers.ip_address,
            self.ActiveUsers.port,
            self.ActiveUsers.login_time,
        ).join(self.AllUsers)
        print(f'Список активных пользователей: {query.all()}')
        return query.all()

    def login_history(self, username=None):
        query = self.session.query(self.AllUsers.name,
                                   self.LoginHistory.date_time,
                                   self.LoginHistory.ip,
                                   self.LoginHistory.port,
                                   ).join(self.AllUsers)
        if username:
            query = query.filter(self.AllUsers.name == username)
        return query.all()


if __name__ == '__main__':
    test_db = ServerStorage()
    test_db.user_login('wasya', '192.168.0.10', 7777)
    test_db.user_login('masya', '192.168.0.20', 7778)
    print(test_db.active_users_list())
    test_db.user_logout('masya')
    print(test_db.active_users_list())
    test_db.login_history('masya')
    test_db.login_history('wasya')
    print(test_db.users_list())
