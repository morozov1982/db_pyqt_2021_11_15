"""
2. Написать функцию host_range_ping() для перебора ip-адресов из заданного диапазона.
Меняться должен только последний октет каждого адреса.
По результатам проверки должно выводиться соответствующее сообщение.
"""
from ipaddress import ip_address

from task_1 import is_ip, host_ping


def is_int(data):
    try:
        int(data)
        return True
    except ValueError:
        return False


def host_range_ping(start_ip='8.8.8.8', num_hosts=5):
    ip_list = []
    if is_ip(start_ip) and is_int(num_hosts):
        last_octet = int(start_ip.split('.')[-1])

        for i in range(num_hosts):
            if last_octet+i > 254:
                break
            ip_list.append(str(ip_address(start_ip) + i))
    return host_ping(ip_list)


if __name__ == '__main__':
    host_range_ping()
    host_range_ping('192.168.0.1', 10)
    # host_range_ping('hello')
    # host_range_ping('1.2.3.4')
    # host_range_ping('1.2.3.4', 10)
    # is_int('data')


# Узел 8.8.8.8 доступен
# Узел 8.8.8.9 недоступен
# Узел 8.8.8.10 недоступен
# Узел 8.8.8.11 недоступен
# Узел 8.8.8.12 недоступен
# Узел 192.168.0.1 доступен
# Узел 192.168.0.2 недоступен
# Узел 192.168.0.3 недоступен
# Узел 192.168.0.4 недоступен
# Узел 192.168.0.5 недоступен
# Узел 192.168.0.6 недоступен
# Узел 192.168.0.7 доступен
# Узел 192.168.0.8 недоступен
# Узел 192.168.0.9 недоступен
# Узел 192.168.0.10 недоступен
