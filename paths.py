import getpass


class BasePathNamespace:
    PROJECT_NAME = "altrepo_server"
    DB_CONFIG_FILE = "/etc/{}/dbconfig.conf".format(PROJECT_NAME)
    LOG_FILE = "/home/{}/{}.log".format(getpass.getuser(), PROJECT_NAME)


paths = BasePathNamespace()
