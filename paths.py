import getpass


class BasePathNamespace:
    PROJECT_NAME = "altrepo_server"
    DB_CONFIG_FILE = "config.conf".format(PROJECT_NAME)
    LOG_FILE = "{}.log".format(getpass.getuser(), PROJECT_NAME)


paths = BasePathNamespace()
