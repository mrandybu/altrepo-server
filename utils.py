import logging
import configparser
import json
import time
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


def json_str_error(error):
    return json.dumps({'Error': error})


def convert_to_json(keys, values):
    js = {}

    for i in range(len(values)):
        js[i] = dict([(keys[j], values[i][j])
                      for j in range(len(values[i]))])

    return json.dumps(js)


def join_tuples(tuple_list):
    return tuple([tuple_[0] for tuple_ in tuple_list])


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
