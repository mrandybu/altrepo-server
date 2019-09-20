from urllib.parse import unquote
from flask import Flask, request, json
from db_connection import DBConnection
import utils
from utils import func_time
from paths import paths

app = Flask(__name__)
logger = utils.get_logger(__name__)


class LogicServer:
    def __init__(self, request_line=None):
        self.known_branches = ['c8.1', 'p8', 'p7', 'p9', 'Sisyphus', 'c8']
        self.known_archs = ['x86_64', 'noarch', 'x86_64-i586', 'armh', 'arm',
                            'i586', 'pentium4', 'athlon', 'pentium3', 'i686',
                            'armv5tel', 'k6', 'aarch64', 'ppc64le', 'e2kv4',
                            'e2k', 'mipsel']
        self.default_archs = ['x86_64', 'i586', 'aarch64', 'armh', 'ppc64le',
                              'noarch']
        self.package_params = [
            'pkgcs', 'packager', 'packager_email', 'name', 'arch', 'version',
            'release', 'epoch', 'serial_', 'buildtime', 'buildhost', 'size',
            'archivesize', 'rpmversion', 'cookie', 'disttag', 'sourcerpm',
            'filename', 'sha1srcheader', 'summary', 'description', 'changelog',
            'distribution', 'vendor', 'gif', 'xpm', 'license', 'group_', 'url',
            'os', 'prein', 'postin', 'preun', 'postun', 'icon', 'preinprog',
            'postinprog', 'preunprog', 'postunprog', 'buildarchs',
            'verifyscript', 'verifyscriptprog', 'prefixes', 'instprefixes',
            'optflags', 'disturl', 'payloadformat', 'payloadcompressor',
            'payloadflags', 'platform',
        ]
        self.request_line = request_line

        # db params
        self.clickhouse_host = self._get_config('ClickHouse', 'Host')
        self.clickhouse_name = self._get_config('ClickHouse', 'DBName', False)

    # init method, starts before application starts
    @staticmethod
    def init():
        utils.print_statusbar(
            "Using configuration file: {}".format(paths.DB_CONFIG_FILE), 'i'
        )

    @staticmethod
    def helper(query):
        helper = {
            '/package_info': {
                '##### /package_info arguments #####': {
                    'name': '',
                    'version': '',
                    'release': '',
                    'disttag': '',
                    'buildtime': '><=',
                    'source': 'show source packages (true, false)',
                    'branch': '',
                    'packager': '',
                    'sha1': '',
                    'full': 'full package info',
                }
            },
            '/misconflict_packages': {
                '##### /misconflict_packages argunents #####': {
                    'pkg_ls': 'name or list of binary packages',
                    'task': "task id (not use with 'pkg_ls')",
                    'branch': '',
                    'arch': '',
                }
            },
            '/package_by_file': {
                '##### /package_by_file arguments #####': {
                    'file': "file name, can be set as a file name mask "
                            "(ex. file='/usr/bin/*')",
                    'md5': 'file md5',
                    'arch': '',
                    'branch': '',
                }
            },
            '/package_files': {
                '##### /package_files arguments #####': {
                    'sha1': 'package sha1',
                }
            },
            '/dependent_packages': {
                '##### /dependent_packages arguments #####': {
                    'name': 'name of binary package',
                    'version': '',
                    'branch': '',
                }
            },
            '/what_depends_src': {
                '##### /what_depends_src arguments #####': {
                    'name': 'name of source package',
                    'task': "task id (can't used with 'name')",
                    'branch': '',
                    'sort': 'for sort by dependencies',
                    'leaf': "show assembly dependency chain (only with 'sort')",
                    'deep': 'sets the sorting depth',
                }
            },
            '/unpackaged_dirs': {
                '##### /what_depends_src arguments #####': {
                    'pkgr': '',
                    'pkgset': '',
                    'arch': '',
                }
            }
        }

        return helper[query]

    @staticmethod
    def _get_config(section, field, req=True):
        config = utils.read_config(paths.DB_CONFIG_FILE)
        if config is False:
            raise Exception("Unable read config file.")

        try:
            return config.get(section, field)
        except:
            if req:
                raise Exception("No needed section or field in config file.")
            else:
                pass

    def _get_connection(self):
        return DBConnection(clickhouse_host=self.clickhouse_host,
                            clickhouse_name=self.clickhouse_name)

    # measures the execution time of func
    @func_time(logger)
    def send_request(self, trace=False):
        db_connection = self._get_connection()
        db_connection.db_query = self.request_line

        return db_connection.send_request(trace)

    @staticmethod
    def get_one_value(param, type_):
        value = request.args.get(param)

        if value:
            # fixed err when package name contains '+'
            if param in ['name', 'file', 'pkg_ls']:
                value = value.replace(' ', '+')

                if param == 'file':
                    value = value.replace('*', '%')

            if type_ == 's':
                value = value.split("'")[0]
            if type_ == 'i':
                try:
                    value = int(value)
                except:
                    value = False
            if type_ == 'b':
                b_value = value.lower()
                if b_value not in ['true', 'false'] or b_value == 'false':
                    value = False
                else:
                    value = True
            # type for using pattern in /package_by_file
            if type_ == 'r':
                value = [el for el in value.split("'") if el][0]

        return value

    def get_dict_values(self, list_of_params):
        values_dict = {}
        for param in list_of_params:
            value = self.get_one_value(param[0], param[1])
            values_dict[param[0]] = value

        return values_dict

    def check_input_params(self, source=None):
        if not request.args:
            return json.dumps(server.helper(request.path))

        # check arch
        parchs = self.get_one_value('arch', 's')
        if parchs:
            for arch in parchs.split(','):
                if arch and arch not in server.known_archs:
                    return utils.json_str_error('Unknown arch of package!')

        # check branch
        pbranch = self.get_one_value('branch', 's')
        if pbranch and pbranch not in self.known_branches:
            return utils.json_str_error('Unknown branch!')

        # check package params
        pname = self.get_one_value('name', 's')
        if pname:
            default_req = "SELECT name FROM last_packages"
            args = "name = %(name)s"

            pversion = self.get_one_value('version', 's')
            if pversion:
                args = "{} AND version = %(vers)s".format(args)

            if pbranch:
                args = "{} AND assigment_name = %(branch)s".format(args)

            if source in (0, 1):
                args = "{} AND sourcepackage = %(source)d".format(args)

            self.request_line = "{} WHERE {}".format(default_req, args)

            self.request_line = (
                self.request_line,
                {'name': pname, 'vers': pversion, 'branch': pbranch,
                 'source': source}
            )

            status, response = self.send_request()
            if status is False:
                return response

            if not response:
                message = "Package with input parameters is not in the " \
                          "repository."
                logger.debug(message)
                return utils.json_str_error(message)

        return True

    def get_values_by_params(self, input_params, values_only=False):
        params_list = []
        if values_only:
            params_list = {}

        for param in input_params:
            type_ = input_params[param].get('type')

            value = self.get_one_value(param, type_)
            if value is False:
                return value

            notempty = input_params[param].get('notempty')
            if not value and notempty is True:
                return False

            action = input_params[param].get('action')

            if value or action:
                if values_only:
                    params_list[param] = value
                else:
                    arg = "{} = '{}'"
                    rname = input_params[param].get('rname')

                    if action:
                        arg = action
                    else:
                        if type_ == 'i':
                            arg = "{} {}"
                        if type_ == 'b':
                            if value.lower() == 'true':
                                arg = "{} = 1"
                            elif value.lower() == 'false':
                                arg = "{} = 0"
                        if type_ == 't':
                            arg = "{} = {}"

                    arg = arg.format(rname, value)
                    if len(params_list) > 0:
                        arg = "AND {}".format(arg)

                    params_list.append(arg)

        if not params_list:
            return False

        return params_list

    @staticmethod
    def url_logging():
        logger.info(unquote(request.url))

    def get_last_version(self, name, branch):
        self.request_line = (
            "SELECT version FROM last_packages WHERE name = %(name)s AND "
            "assigment_name = %(branch)s", {'name': name, 'branch': branch}
        )

        status, response = self.send_request()
        if status is False:
            return False, response

        return True, response[0][0]


server = LogicServer()
server.init()