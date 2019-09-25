import sys
import utils
from paths import paths
from gunicorn.app.wsgiapp import run


def start():
    default_host = '127.0.0.1'
    default_port = 5000

    parser_args = [
        ('--host', str, default_host, 'host to start application'),
        ('--port', int, default_port, 'port to start application'),
        ('--config', str, paths.DB_CONFIG_FILE, 'path to db config file'),
        ('--logs', str, paths.LOG_FILE, 'path to log files'),
    ]

    parser = utils.make_argument_parser(parser_args)

    paths.DB_CONFIG_FILE = parser.config
    paths.LOG_FILE = parser.logs

    sys.argv = [
        sys.argv[0], '-b', '{}:{:d}'.format(default_host, default_port),
        '-w', '4', 'app:app'
    ]

    run()


if __name__ == '__main__':
    start()
