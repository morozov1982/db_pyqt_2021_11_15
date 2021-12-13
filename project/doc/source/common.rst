Common package
=================================================

Пакет общих утилит, использующихся в разных модулях проекта.


Скрипт decos.py
---------------

.. automodule:: common.decos
    :members:


Скрипт descriptors.py
---------------------

.. autoclass:: common.descriptors.Port
    :members:

.. autoclass:: common.descriptors.Addr
    :members:


Скрипт errors.py
----------------

.. autoclass:: common.errors.ServerError
    :members:


Скрипт metaclasses.py
---------------------

.. autoclass:: common.metaclasses.ClientVerifier
    :members:

.. autoclass:: common.metaclasses.ServerVerifier
    :members:


Скрипт utils.py
---------------------

common.utils **send_message** (sock, message)

    Функция приёма сообщений от удалённых компьютеров.
    Принимает сообщения в формате JSON, декодирует полученное сообщение
    и проверяет, что получен словарь.

common.utils **get_message** (client)

    Функция отправки словарей через сокет.
    Кодирует словарь в формат JSON и отправляет через сокет.


Скрипт utils.py
---------------

Содержит разные глобальные переменные проекта.