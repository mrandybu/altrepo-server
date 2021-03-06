#!/usr/bin/env python3

import os
import ast
import sys
import time
import argparse
import threading
import urllib.request
from http.client import RemoteDisconnected
from configparser import NoSectionError, NoOptionError

sys.path.append(os.path.dirname(os.path.realpath(__file__))
                .replace('/tests/request_test', ''))

import utils
from paths import namespace


class AppRequestTest(threading.Thread):
    global_lock = threading.Lock()

    def __init__(self, urls=None):
        super(AppRequestTest, self).__init__()
        self.urls = urls
        self.args = self.__parse_arguments()

    @staticmethod
    def __get_app_params():
        config = utils.read_config(namespace.CONFIG_FILE)
        if config:
            try:
                host = config.get('Application', 'Host')
                port = config.get('Application', 'Port')
                return host, port
            except (NoSectionError, NoOptionError):
                pass

        return '127.0.0.1', 5000

    def __parse_arguments(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--datafile', type=str, default='test_data',
                            help='path to file with testing data')
        parser.add_argument(
            '--reqname', type=str, help='run a test with a specific request'
        )
        parser.add_argument('-s', action='store_true', help='https connection')
        parser.add_argument(
            '--host', type=str, default=self.__get_app_params()[0],
            help='host where application started'
        )
        parser.add_argument(
            '--port', type=int, default=self.__get_app_params()[1],
            help='application port'
        )
        parser.add_argument(
            '--threads', type=int, default=1, help='number of threads'
        )
        parser.add_argument(
            '--to-file', type=str, help='write test results to file'
        )

        return parser.parse_args()

    def __make_url(self, query):
        protocol = 'http' if not self.args.s else 'https'
        url = '{pr}://{host}:{port}/{req}'.format(
            pr=protocol, host=self.args.host, port=self.args.port, req=query
        )
        return url

    def get_one_value(self, url_name):
        try:
            with open(self.args.datafile, 'r') as fd:
                for line in fd:
                    if line.startswith(url_name):
                        return self.__make_url(line.split()[1].strip())
        except (FileNotFoundError, IsADirectoryError):
            print("Error in input file. Check it and try again.")
            sys.exit(1)

        print("Query `{}` no in data file.".format(url_name))
        sys.exit(1)

    def url_pool_generator(self):
        try:
            with open(self.args.datafile, 'r') as fd:
                while True:
                    line = fd.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line and not line.startswith('#'):
                        yield self.__make_url(line.split()[1].strip())
        except (FileNotFoundError, IsADirectoryError):
            print("Error in input file. Check it and try again.")
            sys.exit(1)

    def run(self) -> None:
        for url in self.urls:
            query_time = None
            try:
                start = time.time()
                response = urllib.request.urlopen(url)
                query_time = time.time() - start
                length = len(ast.literal_eval(response.read().decode()))
            except RemoteDisconnected:
                length = '`empty response`'

            message = '{} : length {}'.format(url, length)
            if self.args.threads == 1 and query_time:
                message += ' : time {}'.format(round(query_time, 2))

            if self.args.to_file:
                AppRequestTest.global_lock.acquire()
                with open(self.args.to_file, 'a+') as fd:
                    fd.write('{}\n'.format(message))
                AppRequestTest.global_lock.release()

            print(message)


def create_threads():
    app_rt = AppRequestTest()
    pool = [app_rt.get_one_value(app_rt.args.reqname)] if app_rt.args.reqname \
        else [i for i in app_rt.url_pool_generator()]

    n = round(len(pool) / app_rt.args.threads)
    chunks = [pool[i:i + n] for i in range(0, len(pool), n)]

    for chunk in chunks:
        test_thread = AppRequestTest(urls=chunk)
        test_thread.start()


if __name__ == '__main__':
    create_threads()
