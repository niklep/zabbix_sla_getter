# -*- coding: utf-8 -*-
"""

"""
import datetime
import requests
import warnings
import logging
try:
    import settings
except ImportError:
    exit("COPY settings.py.default to settings.py AND set variables inside")

warnings.filterwarnings('ignore')
AUTH_TOKEN = ""
log = logging.getLogger("sla")

def configure_logging():
    log.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter("%(levelname)s - %(message)s")
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(settings.LOG_FILE_NAME)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%d-%m-%Y %H:%M")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.ERROR)

    if settings.DEBUG:
        log.addHandler(stream_handler)
    log.addHandler(file_handler)


def login():
    user_login_post = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {
            "user": settings.USER,
            "password": settings.PASSWORD
        },
        "id": 1
    }
    try:
        response_user_login = requests.post(settings.URL, json=user_login_post, verify=False).json()
        auth_token = response_user_login['result']
        return auth_token
    except Exception as ex:
        log.critical("Login error: %s", str(ex))
        exit(f'Login error: {str(ex)}')


def logout():
    user_logout_post = {
        "jsonrpc": "2.0",
        "method": "user.logout",
        "params": [],
        "id": 1,
        "auth": AUTH_TOKEN
    }
    try:
        response_user_logout = requests.post(settings.URL, json=user_logout_post, verify=False).json()
    except Exception as ex:
        log.critical("Logout error: %s", str(ex))
    else:
        if 'error' in response_user_logout.keys():
            log.critical("Logout error: %s", str(response_user_logout['error']))
        else:
            log.info("Logout successfully")
    exit()


def get_all_sla_list():
    """
    Функция возвращает перечень всех объектов SLA. В интерфейсе Zabbix это называется Услуги
    :return: list
    """
    req_get_sla_list = {
        "jsonrpc": "2.0",
        "method": "service.get",
        "params": {
            "output": "extend"
        },
        "auth": AUTH_TOKEN,
        "id": 1
    }
    try:
        sla_list = requests.post(settings.URL, json=req_get_sla_list, verify=False).json()
        # events_count = len(response_trigger_get['result'])
        return sla_list["result"]
        # parent_id = get_iogv_parent_sla_id()
        # print(sla_list[0])
    except Exception as ex:
        log.error("Get all SLA list error: %s", str(ex))
        logout()


def get_iogv_parent_sla_id(sla_list):
    """
    Функция возвращает id SLA услуги, название которой указано в конфиг файле - PARENT_SLA_NAME
    :param sla_list: список всех SLA услуг (результат функции get_all_sla_list)
    :return: int, если услуга найдена, иначе None
    """
    for sla in sla_list:
        if sla["name"] == settings.PARENT_SLA_NAME:
            return sla["serviceid"]
    return None


def get_iogv_sla_list(parent_id):
    """
    Функция возвращает словарь. Ключи - id'шники SLA услуг, значения - имена этих услуг.
    Родитель этих услуг - указанная в конфиге услуга PARENT_SLA_NAME
    :param parent_id: id услуги, детей которой мы ищем
    :return: dictonary. Пары id - names
    """
    res = {}
    req_get_child_sla = {
        "jsonrpc": "2.0",
        "method": "service.get",
        "params": {
            "output": "extend",
            "parentids": [parent_id]
        },
        "auth": AUTH_TOKEN,
        "id": 1
    }
    try:
        child_sla_list = requests.post(settings.URL, json=req_get_child_sla, verify=False).json()
        iogv_sla_list = child_sla_list["result"]
        #print(iogv_sla_list)
        for iogv_sla in iogv_sla_list:
            sla_id = int(iogv_sla["serviceid"])
            sla_name = iogv_sla["name"]
            res[sla_id] = sla_name
        return res
    except Exception as ex:
        log.error("Get IOGV SLA list error: %s", str(ex))
        logout()


def get_iogv_sla_status(iogv_sla_list):
    req_get_child_sla_status = {
        "jsonrpc": "2.0",
        "method": "service.getsla",
        "params": {
            "serviceids": list(iogv_sla_list.keys()),
            "intervals": [
            {
                "from": get_start_timestamp(),
                "to": get_finish_timestamp()
            }
        ]
        },
        "auth": AUTH_TOKEN,
        "id": 1
    }
    try:
        iogv_sla_status = requests.post(settings.URL, json=req_get_child_sla_status, verify=False).json()
        res = iogv_sla_status["result"]
        return res
    except Exception as ex:
        log.error("Get IOGV SLA status error: %s", str(ex))
        logout()


def make_output_result(iogv_ids_names, iogv_sla_status):
    try:
        with open(settings.OUTPUT_FILE_NAME, 'w', encoding="utf8") as file:
            # make_header()
            for id, name in iogv_ids_names.items():
                iogv_str = make_iogv_str(id, name, iogv_sla_status)
                file.write(iogv_str + "\n")
    except FileNotFoundError as fnf_exc:
        log.error("Ошибка. Неверный путь к файлу: %s", str(fnf_exc))
    except PermissionError as perm_exc:
        log.error("Ошибка. Недостаточно прав: %s", str(perm_exc))
    except IOError as io_exc:
        log.error("Ошибка ввода/вывода: %s", str(io_exc))
    except Exception as exc:
        log.error("Непредвиденная ошибка: %s", str(exc))


def make_iogv_str(id, name, iogv_list):
    sla_value = iogv_list[str(id)]["sla"][0]["sla"]
    return f'{name} - {round(sla_value,4)}'


def get_start_timestamp():
    if settings.PERIOD == "MONTH":
        current_month = datetime.datetime.today().timetuple()[1]
        if current_month < 10:
            current_month = f'0{current_month}'
        current_year = datetime.datetime.today().timetuple()[0]
        date_str_format = f'01/{current_month}/{current_year}'
        start_timestamp = int(datetime.datetime.strptime(date_str_format, '%d/%m/%Y').strftime("%s"))
        return start_timestamp


def get_finish_timestamp():
    return int(datetime.datetime.now().timestamp())


if __name__ == '__main__':
    configure_logging()
    AUTH_TOKEN = login()
    sla_list = get_all_sla_list()
    parent_id = get_iogv_parent_sla_id(sla_list)
    if parent_id:
        iogv_sla_list = get_iogv_sla_list(parent_id)
        iogv_sla_status = get_iogv_sla_status(iogv_sla_list)
        make_output_result(iogv_sla_list, iogv_sla_status)

    logout()
