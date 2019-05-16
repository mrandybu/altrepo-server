import logging
import configparser
import json
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
