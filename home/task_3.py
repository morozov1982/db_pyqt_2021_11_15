"""
Написать функцию host_range_ping_tab(), возможности которой основаны на функции из примера 2.
Но в данном случае результат должен быть итоговым по всем ip-адресам, представленным в табличном формате
(использовать модуль tabulate). Таблица должна состоять из двух колонок
"""

from tabulate import tabulate
from task_2 import host_range_ping


def host_range_ping_tab(start_ip='8.8.8.8', num_hosts=5):
    pinged_hosts = host_range_ping(start_ip, num_hosts)
    tabulated_res = tabulate(pinged_hosts, headers='keys', tablefmt='pipe')
    return tabulated_res


if __name__ == "__main__":
    tab = host_range_ping_tab()
    print("=" * 29)
    print(tab)
    print("=" * 29)


# Узел 8.8.8.8 доступен
# Узел 8.8.8.9 недоступен
# Узел 8.8.8.10 недоступен
# Узел 8.8.8.11 недоступен
# Узел 8.8.8.12 недоступен
# =============================
# | reached   | unreachable   |
# |:----------|:--------------|
# | 8.8.8.8   | 8.8.8.9       |
# |           | 8.8.8.10      |
# |           | 8.8.8.11      |
# |           | 8.8.8.12      |
# =============================
