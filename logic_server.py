import time
from flask import request, g
from urllib.parse import unquote

import utils
from utils import func_time
from paths import namespace
from db_connection import DBConnection

logger = utils.get_logger(__name__)


class LogicServer:
    def __init__(self):
        # make configuration before app start
        self._init()

        # base constant values
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

    # init method, starts before application starts
    @staticmethod
    def _init():
        info_list = [
            ("Configuration file: {}".format(namespace.CONFIG_FILE), 'i'),
            ("DataBase host: {} name: {} user: {}"
             "".format(namespace.DATABASE_HOST, namespace.DATABASE_NAME,
                       namespace.DATABASE_USER), 'i'
             ),
            ("Logging file: {}".format(namespace.LOG_FILE), 'i'),
            ("Application host: {}:{}"
             "".format(namespace.DEFAULT_HOST, namespace.DEFAULT_PORT), 'i'),
        ]

        utils.print_statusbar(info_list)

    @staticmethod
    def helper(query):
        helper = {
            '/package_info': {
                '##### /package_info arguments #####': {
                    'name': 'search by name of the package',
                    'version': 'search by version',
                    'release': 'search by release',
                    'disttag': 'search by disttag',
                    'buildtime': 'time in integer UNIX time format',
                    'source': 'enable source packages (true, false)',
                    'arch': 'search by arch',
                    'branch': 'search by branch',
                    'packager': 'search by packager name',
                    'packager_email': 'search by packager name',
                    'sha1': 'search by sha1 of the package',
                    'full': 'full package info (true, default:false)',
                }
            },
            '/misconflict_packages': {
                '##### /misconflict_packages arguments #####': {
                    'pkg_ls *': 'name or list of binary packages',
                    'task **': 'task id (not use with `pkg_ls`)',
                    'branch *': 'require for `pkg_ls` only',
                    'arch': 'allowed set multiple archs (arch=x86_64,i586)',
                }
            },
            '/package_by_file': {
                '##### /package_by_file arguments #####': {
                    'file *': "file name, can be set as a file name mask "
                              "(ex. file='/usr/bin/*')",
                    'md5 **': 'file md5 (without `file` only)',
                    'branch *': 'name of repository',
                    'arch': 'allowed set multiple archs (arch=x86_64,i586)',
                }
            },
            '/package_files': {
                '##### /package_files arguments #####': {
                    'sha1 *': 'package sha1',
                }
            },
            '/dependent_packages': {
                '##### /dependent_packages arguments #####': {
                    'name *': 'name of binary package',
                    'branch *': 'name of repository',
                }
            },
            '/what_depends_src': {
                '##### /what_depends_src arguments #####': {
                    'name *': 'name of source package',
                    'task **': 'task id (can\'t used with `name`)',
                    'branch *': 'require for `name` only',
                    'arch': 'allowed set multiple archs (arch=x86_64,i586)',
                    'leaf': 'show assembly dependency chain',
                    'deep': 'sets the sorting depth',
                    'dptype': 'type of package for sorting (source, binary, '
                              'both)',
                    'reqfilter': 'package or packages (binary) for filter result '
                                 'by dependency',
                    'reqfilterbysrc': 'package or packages (source) for filter '
                                      'result by dependency',
                    'finitepkg': 'show only topological tree leaves',
                }
            },
            '/unpackaged_dirs': {
                '##### /unpackaged_dirs arguments #####': {
                    'pkgr *': 'packager name',
                    'pkgset *': 'name of branch',
                    'arch': 'allowed set multiple archs (arch=x86_64,i586)',
                },
            },
            '/repo_compare': {
                '##### /repo_compare arguments #####': {
                    'pkgset1 *': 'name of repository',
                    'pkgset2 *': 'name of compared repository',
                },
            },
            '/find_pkgset': {
                '##### /find_pkgset arguments #####': {
                    'name *': 'source package name. Multiple packages must '
                              'be comma separated. '
                              'Example: name=curl,ocaml,php7',
                    'task **': 'number of girar task, example: task=239070',
                }
            },
            '/build_dependency_set': {
                '##### /build_dependency_set arguments #####': {
                    'pkg_ls *': 'package or list of packages (source)',
                    'task **': 'task id (can\'t used with `name`)',
                    'branch *': 'require for `name` only',
                    'arch': 'allowed set multiple archs (arch=x86_64,i586)',
                }
            },
            '/packages': {
                '##### /packages arguments #####': {
                    'pkgset *': 'branch name (require argument)',
                    'pkgtype': 'type of packages (source, binary, both)',
                    'arch': 'allowed set multiple archs (arch=x86_64,i586)',
                }
            },
            '/task_info': {
                '##### /task_info arguments #####': {
                    'task *': 'task id',
                }
            },
            '/task_diff': {
                '##### /task_diff arguments #####': {
                    'task *': 'task id',
                }
            },
        }

        return helper[query]

    @staticmethod
    def get_one_value(param, type_, is_=None):
        value = request.args.get(param)

        if value:
            # fixed err when package name contains '+'
            if is_ == 'pkg_name':
                value = value.replace(' ', '+')

                if param == 'file':
                    value = value.replace('*', '%')

            if is_ == 'repo_name':
                value = value.lower()
                if value == 'sisyphus':
                    value = 'Sisyphus'

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
                    value = 0
                else:
                    value = 1
            # type for using pattern in /package_by_file
            if type_ == 'r':
                value = [el for el in value.split("'") if el][0]

        return value

    # get values of input parameters as dict
    def get_dict_values(self, list_of_params):
        values_dict = {}
        for param in list_of_params:
            is_ = None
            if len(param) > 2:
                is_ = param[2]

            value = self.get_one_value(param[0], param[1], is_)
            values_dict[param[0]] = value

        return values_dict

    # FIXME update method according last changes
    def check_input_params(self, source=None):
        if not request.args:
            return utils.get_helper(server.helper(request.path))

        # check arch
        parchs = self.get_one_value('arch', 's')
        if parchs:
            for arch in parchs.split(','):
                if arch and arch not in server.known_archs:
                    return utils.json_str_error('Unknown arch of package!')

        # check branch
        pbranch = self.get_one_value('branch', 's', 'repo_name')
        if pbranch and pbranch not in self.known_branches:
            return utils.json_str_error('Unknown branch!')

        # check package params
        pname = self.get_one_value('name', 's', 'pkg_name')

        def check_package():
            default_req = "SELECT name FROM last_packages"
            args = "name = %(name)s"

            pversion = self.get_one_value('version', 's')
            if pversion:
                args = "{} AND version = %(vers)s".format(args)

            if pbranch:
                args = "{} AND assigment_name = %(branch)s".format(args)

            if source in (0, 1):
                args = "{} AND sourcepackage = %(source)d".format(args)

            g.connection.request_line = "{} WHERE {}".format(default_req, args)

            g.connection.request_line = (
                g.connection.request_line,
                {'name': pname, 'vers': pversion, 'branch': pbranch,
                 'source': source}
            )

            status, response = g.connection.send_request()
            if status is False:
                return response

            if not response:
                return False

            return True

        pkg_ls = self.get_one_value('pkg_ls', 's', 'pkg_name')

        if pname:
            pkg_ls = pname

        if pname or pkg_ls:
            for pname in pkg_ls.split(','):
                if not check_package():
                    message = "Package(s) with input parameters is not in the " \
                              "repository."
                    logger.debug(message)
                    return utils.json_str_error(message)

        return True

    # get values of input parameters by structure of parameters
    def get_values_by_params(self, input_params, values_only=False):
        params_list = []
        if values_only:
            params_list = {}

        for param in input_params:
            type_ = input_params[param].get('type')

            is_ = None
            if 'is_' in input_params[param]:
                is_ = input_params[param]['is_']

            value = self.get_one_value(param, type_, is_)
            if value is False:
                return value

            notempty = input_params[param].get('notempty')
            if not value and notempty is True:
                return False

            action = input_params[param].get('action')

            if value is not None or action:
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
                            if value == 1:
                                arg = "{} = 1"
                            elif value == 0:
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


server = LogicServer()


class Connection:

    def __init__(self, request_line=None):
        self.request_line = request_line
        self.db_connection = DBConnection(
            namespace.DATABASE_HOST, namespace.DATABASE_NAME,
            namespace.DATABASE_USER, namespace.DATABASE_PASS
        )

    @func_time(logger)
    def send_request(self, trace=False):
        rl = self.request_line
        if isinstance(rl, tuple):
            rl = rl[0]

        if bool(rl) is False:
            return False, 'SQL query not found in query manager.'

        status = self.db_connection.connection_status
        if not status:
            for try_ in range(namespace.TRY_CONNECTION_NUMBER):
                logger.debug(
                    'Attempt to connect to the database #{}'.format(try_)
                )

                status = self.db_connection.make_connection()
                if status:
                    break

                time.sleep(namespace.TRY_TIMEOUT)

        if status:
            self.db_connection.db_query = self.request_line
            return self.db_connection.send_request(trace)
        else:
            return False, 'Database connection error.'

    def drop_connection(self):
        if self.db_connection:
            self.db_connection.disconnect()
            logger.debug('Connection closed.')
