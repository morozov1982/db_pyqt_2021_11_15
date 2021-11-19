"""
1. Написать функцию host_ping(), в которой с помощью утилиты ping
будет проверяться доступность сетевых узлов.
Аргументом функции является список, в котором каждый сетевой узел
должен быть представлен именем хоста или ip-адресом.
В функции необходимо перебирать ip-адреса и проверять
их доступность с выводом соответствующего сообщения
(«Узел доступен», «Узел недоступен»). При этом ip-адрес
сетевого узла должен создаваться с помощью функции ip_address().
"""
from ipaddress import ip_address
from pprint import pprint
from subprocess import Popen, PIPE


def is_ip(ip):
    try:
        ip_address(ip)
        return True
    except ValueError:
        return False


def host_ping(ip_list, timeout=500, requests=1):  # прислушался к советам преподавателя и добавил timeout и requests
    pinged_hosts = {'reached': [], 'unreachable': []}
    for ip in ip_list:
        if not is_ip(ip):
            continue
        process = Popen(f'ping {ip} -w {timeout} -n {requests}', shell=False, stdout=PIPE)
        process.wait()

        if process.returncode == 0:
            pinged_hosts['reached'].append(ip)
            print(f'Узел {ip} доступен')
        else:
            pinged_hosts['unreachable'].append(ip)
            print(f'Узел {ip} недоступен')
    return pinged_hosts


if __name__ == '__main__':
    ips = ['192.168.1.1', '192.168.0.1', '8.8.8.8', '0.1.2.3', 'hello world!', '1234', 'google.kz']
    result_dict = host_ping(ips)
    pprint(result_dict)  # решил тоже здесь попробовать

# Узел 192.168.1.1 недоступен
# Узел 192.168.0.1 доступен
# Узел 8.8.8.8 доступен
# Узел 0.1.2.3 недоступен
# {'reached': ['192.168.0.1', '8.8.8.8'],
# 'unreachable': ['192.168.1.1', '0.1.2.3']}
