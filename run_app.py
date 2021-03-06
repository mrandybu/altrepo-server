import sys
from collections import defaultdict
from gunicorn.app.wsgiapp import run

import utils
from paths import namespace


def start():
    launch_props = [
        ('DATABASE_HOST', str), ('DATABASE_NAME', str),
        ('TRY_CONNECTION_NUMBER', int), ('TRY_TIMEOUT', int),
        ('DATABASE_USER', str), ('DATABASE_PASS', str),
        ('DEFAULT_HOST', str), ('DEFAULT_PORT', int),
        ('WORKER_PROCESSES', str), ('LOG_FILE', str)
    ]

    pars_args = [
        ('--host', str, None, 'host to start application'),
        ('--port', int, None, 'port to start application'),
        ('--dbhost', str, None, 'database host'),
        ('--dbname', str, None, 'database name'),
        ('--dbuser', str, None, 'database user'),
        ('--config', str, namespace.CONFIG_FILE, 'namespace to db config file'),
        ('--prcs', str, None, 'number of worker processes'),
        ('--logs', str, None, 'namespace to log files'),
    ]

    parser = utils.make_argument_parser(pars_args)

    config = utils.read_config(parser.config)

    if config:

        args_dict = defaultdict(dict)
        for section in config.sections():
            for option in config.options(section):
                args_dict[section.lower()][option] = config.get(section, option)

        params = {
            'database': [
                ('host', namespace.DATABASE_HOST),
                ('name', namespace.DATABASE_NAME),
                ('try_numbers', namespace.TRY_CONNECTION_NUMBER),
                ('try_timeout', namespace.TRY_TIMEOUT),
                ('user', namespace.DATABASE_USER),
                ('password', namespace.DATABASE_PASS)
            ],
            'application': [
                ('host', namespace.DEFAULT_HOST),
                ('port', namespace.DEFAULT_PORT),
                ('processes', namespace.WORKER_PROCESSES)
            ],
            'other': [('logfiles', namespace.LOG_FILE)]
        }

        val_list = []
        for section, items in params.items():
            for line in items:
                value = args_dict.get(section)
                val_list.append(value.get(line[0]) if value else line[1])

        for i in range(len(val_list)):
            if val_list[i]:
                namespace.__setattr__(
                    launch_props[i][0], launch_props[i][1](val_list[i])
                )

    parser_keys = [
        'dbhost', 'dbname', '', '', 'dbuser', '', 'host', 'port', 'prcs', 'logs'
    ]

    for i in range(len(parser_keys)):
        if parser.__contains__(parser_keys[i]):
            pars_val = parser.__getattribute__(parser_keys[i])

            if pars_val:
                namespace.__setattr__(
                    launch_props[i][0], launch_props[i][1](pars_val)
                )

    sys.argv = [
        sys.argv[0], '-b', '{}:{:d}'.format(namespace.DEFAULT_HOST,
                                            namespace.DEFAULT_PORT),
        '-w', namespace.WORKER_PROCESSES, 'app:app'
    ]

    run()
