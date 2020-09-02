import os
import getpass


class BasePathNamespace:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    # configuration parameters
    PROJECT_NAME = "altrepo_server"
    CONFIG_FILE = "/etc/{}/dbconfig.conf".format(PROJECT_NAME)
    LOG_FILE = "/home/{}/{}.log".format(getpass.getuser(), PROJECT_NAME)
    # application launch parameters
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 5000
    WORKER_PROCESSES = '1'
    # database parameters
    DATABASE_HOST = ''
    DATABASE_NAME = ''
    TRY_CONNECTION_NUMBER = 5
    TRY_TIMEOUT = 5
    DATABASE_USER = 'default'
    DATABASE_PASS = ''


namespace = BasePathNamespace()
