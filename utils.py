import os
import json
import time
import logging
import datetime
import argparse
import requests
import configparser
from bs4 import BeautifulSoup
from collections import defaultdict

from paths import namespace


def get_logger(name):
    logging.basicConfig(format=u'%(levelname)-8s [%(asctime)s] %(message)s',
                        level=logging.DEBUG, filename=namespace.LOG_FILE)
    logger = logging.getLogger(name)

    return logger


def exception_to_logger(exception):
    return exception.args[0].split('\n')[0]


def read_config(config_file):
    config = configparser.ConfigParser(inline_comment_prefixes="#")

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


def print_statusbar(message_list):
    types = {
        'i': "[INFO]",
        'w': "[WARNING]",
        'd': "[DEBUG]",
        'e': "[ERROR]",
    }

    for msg in message_list:
        print("[ALTREPO SERVER]{type_}: {msg}"
              "".format(type_=types[msg[1]], msg=msg[0]))


def make_argument_parser(arg_list, desc=None):
    parser = argparse.ArgumentParser(description=desc)

    for arg in arg_list:
        parser.add_argument(arg[0], type=arg[1], default=arg[2], help=arg[3])

    return parser.parse_args()


# convert tuple or list of tuples to dict by set keys
def tuplelist_to_dict(tuplelist, num):
    result_dict = defaultdict(list)
    for tuple_ in tuplelist:
        count = tuple_[1] if num == 1 else tuple_[1:num + 1]

        if isinstance(count, tuple):
            result_dict[tuple_[0]] += [elem for elem in count]
        elif isinstance(count, list):
            result_dict[tuple_[0]] += count
        else:
            result_dict[tuple_[0]].append(count)

    return result_dict


def remove_duplicate(list_):
    return list(set(list_))


def get_helper(helper):
    return json.dumps(helper, sort_keys=False)


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


class HtmlParser:
    def __init__(self, search_tag, bad_list):
        self.search_tag = search_tag
        self.bad_list = bad_list

    def parse_html(self, url):
        response = requests.get(url)
        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.content, 'lxml')

        for tag in soup.find_all(self.search_tag):
            if tag.text not in self.bad_list:
                response = requests.get(os.path.join(url, tag.text))
                if response.status_code != 200:
                    return False

                return response.content.decode()
