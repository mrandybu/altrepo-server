import sys
import utils
from paths import namespace
from gunicorn.app.wsgiapp import run


def start():
    launch_props = [
        ('DATABASE_HOST', str), ('DATABASE_NAME', str), ('DEFAULT_HOST', str),
        ('DEFAULT_PORT', int), ('WORKER_PROCESSES', str), ('LOG_FILE', str)
    ]

    pars_args = [
        ('--host', str, None, 'host to start application'),
        ('--port', int, None, 'port to start application'),
        ('--dbhost', str, None, 'database host'),
        ('--dbname', str, None, 'database name'),
        ('--config', str, namespace.CONFIG_FILE, 'namespace to db config file'),
        ('--prcs', str, None, 'number of worker processes'),
        ('--logs', str, None, 'namespace to log files'),
    ]

    parser = utils.make_argument_parser(pars_args)

    config = utils.read_config(parser.config)

    if config:
        params = {
            'DataBase': [
                ('Host', namespace.DATABASE_HOST),
                ('Name', namespace.DATABASE_NAME)
            ],
            'Application': [
                ('Host', namespace.DEFAULT_HOST),
                ('Port', namespace.DEFAULT_PORT),
                ('Processes', namespace.WORKER_PROCESSES)
            ],
            'Other': [('LogFiles', namespace.LOG_FILE)]
        }

        val_list = []
        for section, items in params.items():
            for line in items:
                try:
                    value = config.get(section, line[0])
                except:
                    value = line[1]

                val_list.append(value)

        for i in range(len(val_list)):
            namespace.__setattr__(
                launch_props[i][0], launch_props[i][1](val_list[i])
            )

    parser_keys = ['dbhost', 'dbname', 'host', 'port', 'prcs', 'logs']

    for i in range(len(parser_keys)):
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


if __name__ == '__main__':
    start()
