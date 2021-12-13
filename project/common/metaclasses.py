from dis import get_instructions


class ClientVerifier(type):
    """
    Метакласс, проверяющий что в результирующем классе нет серверных вызовов
    таких как: accept, listen.
    Также проверяется, что сокет не создаётся внутри конструктора класса.
    """

    def __init__(cls, clsname, bases, clsdict):
        methods = []

        for func in clsdict:
            try:
                instructions = get_instructions(clsdict[func])
            except TypeError:
                pass
            else:
                for instr in instructions:
                    if instr.opname == 'LOAD_GLOBAL' \
                            and instr.argval not in methods:
                        methods.append(instr.argval)

        for method in ('accept', 'listen', 'socket'):
            if method in methods:
                raise TypeError(f'В классе вызван запрещённый метод {method}')

        # Долго не мог определить почему не работает, спасибо  @log ;-)
        if 'get_message' in methods or 'send_message' in methods:
            pass
        else:
            raise TypeError(
                'Отсутствуют вызовы функций, работающих с сокетами')
        super().__init__(clsname, bases, clsdict)


class ServerVerifier(type):
    """
    Метакласс, проверяющий что в результирующем классе нет клиентских вызовов
    таких как: connect.
    Также проверяется, что серверный сокет является TCP
    и работает по IPv4 протоколу.
    """

    def __init__(cls, clsname, bases, clsdict):
        methods = []
        attrs = []

        for func in clsdict:
            try:
                instructions = get_instructions(clsdict[func])
            except TypeError:
                pass
            else:
                for instruction in instructions:
                    if instruction.opname == 'LOAD_GLOBAL' \
                            and instruction.argval not in methods:
                        methods.append(instruction.argval)
                    if instruction.opname == 'LOAD_ATTR' \
                            and instruction.argval not in attrs:
                        attrs.append(instruction.argval)

        if 'connect' in methods:
            raise TypeError(
                'Использование метода connect недопустимо в серверном классе')
        if not ('SOCK_STREAM' in attrs and 'AF_INET' in attrs):
            raise TypeError('Некорректная инициализация сокета')

        super().__init__(clsname, bases, clsdict)
