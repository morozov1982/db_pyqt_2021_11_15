import dis


class ClientVerifier(type):
    """ Метакласс, выполняющий базовую проверку класса «Клиент» """

    def __init__(self, clsname, bases, clsdict):
        methods = []

        for key, value in clsdict.items():
            try:
                instructions = dis.get_instructions(value)
            except TypeError:
                pass
            else:
                for instr in instructions:
                    if instr.opname == 'LOAD_GLOBAL' and instr.argval not in methods:
                        methods.append(instr.argval)

        for method in ('accept', 'listen', 'socket'):
            if method in methods:
                raise TypeError(f'В классе вызван запрещённый метод {method}')

        # Долго не мог определить почему не работает, спасибо  @log ;-)
        if 'get_message' in methods or 'send_message' in methods:
            pass
        else:
            raise TypeError('Отсутствуют вызовы функций, работающих с сокетами')
        type.__init__(self, clsname, bases, clsdict)


class ServerVerifier(type):
    """ Метакласс, выполняющий базовую проверку класса «Сервер» """

    def __init__(self, clsname, bases, clsdict):
        methods = []
        attributes = []

        for key, value in clsdict.items():
            try:
                instructions = dis.get_instructions(value)
            except TypeError:
                pass
            else:
                for instruction in instructions:
                    if instruction.opname == 'LOAD_GLOBAL' and instruction.argval not in methods:
                        methods.append(instruction.argval)
                    if instruction.opname == 'LOAD_ATTR' and instruction.argval not in attributes:
                        attributes.append(instruction.argval)

        if 'connect' in methods:
            raise TypeError('Использование метода connect недопустимо в серверном классе')
        if not ('SOCK_STREAM' in attributes and 'AF_INET' in attributes):
            raise TypeError('Некорректная инициализация сокета')

        super().__init__(clsname, bases, clsdict)
