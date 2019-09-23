import logging
import configparser
import json
import time
import datetime
from paths import paths


def get_logger(name):
    logging.basicConfig(format=u'%(levelname)-8s [%(asctime)s] %(message)s',
                        level=logging.DEBUG, filename=paths.LOG_FILE)
    logger = logging.getLogger(name)

    return logger


def exception_to_logger(exception):
    return exception.args[0].split('\n')[0]


def read_config(config_file):
    config = configparser.ConfigParser()

    if config.read(config_file):
        return config

    return False


# return error message as json format
def json_str_error(error):
    return json.dumps({'Error': error})


def convert_to_json(keys, values, sort=False):
    js = {}

    for i in range(len(values)):
        js[i] = dict([(keys[j], values[i][j])
                      for j in range(len(values[i]))])

        for key in js[i]:
            if key == 'date':
                js[i]['date'] = datetime.datetime.strftime(
                    js[i]['date'], '%Y-%m-%d %H:%M:%S'
                )

    return json.dumps(js, sort_keys=sort)


def join_tuples(tuple_list):
    return tuple([tuple_[0] for tuple_ in tuple_list])


def print_statusbar(message, type_):
    types = {
        'i': "[INFO]",
        'w': "[WARNING]",
        'd': "[DEBUG]",
        'e': "[ERROR]",
    }
    print("[ALTREPO SERVER]{type_}: {msg}"
          "".format(type_=types[type_], msg=message))


# convert tuple or list of tuples to dict by set keys
def tuplelist_to_dict(tuplelist, num):
    result_dict = {}
    for tuple_ in tuplelist:
        if tuple_[0] not in result_dict.keys():
            result_dict[tuple_[0]] = []

        if num == 1:
            count = tuple_[1]
        else:
            count = tuple_[1:num + 1]

        for elem in count:
            result_dict[tuple_[0]].append(elem)

    return result_dict


def remove_duplicate(list_):
    return list(set(list_))


def func_time(logger):
    def decorator(function):
        def wrapper(*args, **kwargs):
            start = time.time()
            resuls = function(*args, **kwargs)
            logger.info(
                "Time {} is {}".format(function.__name__, time.time() - start)
            )
            return resuls

        wrapper.__name__ = function.__name__
        return wrapper

    return decorator
