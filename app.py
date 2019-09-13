from urllib.parse import unquote
from flask import Flask, request, json
from collections import defaultdict
from db_connection import DBConnection
import utils
from utils import func_time
from paths import paths
from deps_sorting import SortList

app = Flask(__name__)
logger = utils.get_logger(__name__)


class LogicServer:
    def __init__(self, request_line=None):
        self.known_branches = ['c8.1', 'p8', 'p7', 'p9', 'Sisyphus', 'c8']
        self.known_archs = ['x86_64', 'noarch', 'x86_64-i586', 'armh', 'arm',
                            'i586', 'pentium4', 'athlon', 'pentium3', 'i686',
                            'armv5tel', 'k6', 'aarch64', 'ppc64le', 'e2kv4',
                            'e2k', 'mipsel']
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
                    'name': 'name of binary package',
                    'branch': '',
                    'version': '',
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
            if param == 'name' or param == 'file':
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


@app.route('/package_info')
@func_time(logger)
def package_info():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime', 'i')
    if buildtime_value and buildtime_value not in ['>', '<', '=']:
        buildtime_action = "{} = {}"

    pbranch = server.get_one_value('branch', 's')

    intput_params = {
        'sha1': {
            'rname': 'pkgcs',
            'type': 's',
            'action': None,
            'notenpty': False,
        },
        'name': {
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'version': {
            'rname': 'version',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'release': {
            'rname': 'release',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'arch': {
            'rname': 'arch',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'disttag': {
            'rname': 'disttag',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'buildtime': {
            'rname': 'buildtime',
            'type': 'i',
            'action': buildtime_action,
            'notempty': False,
        },
        'source': {
            'rname': 'sourcepackage',
            'type': 'b',
            'action': None,
            'notempty': False,
        },
        'packager': {
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(intput_params)
    if params_values is False:
        return json.dumps(server.helper(request.path))

    full = bool(server.get_one_value('full', 'b'))

    output_params = [
        'pkgcs', 'packager', 'packager_email', 'name',
        'arch', 'version', 'release', 'epoch', 'buildtime',
        'sourcepackage', 'sourcerpm', 'filename',
    ]
    if full:
        output_params = server.package_params

    server.request_line = \
        "SELECT pkg.pkghash, {p_params} FROM last_packages WHERE " \
        "{p_values} {branch}".format(
            p_params=", ".join(output_params),
            p_values=" ".join(params_values),
            branch='{}'
        )

    if pbranch:
        server.request_line = server.request_line.format(
            "AND assigment_name = %(branch)s"
        )
    else:
        server.request_line = server.request_line.format('')

    server.request_line = (server.request_line, {'branch': pbranch})

    status, response = server.send_request()
    if status is False:
        return response

    json_retval = json.loads(
        utils.convert_to_json(['pkghash'] + output_params, response)
    )

    if full:

        pkghashs = utils.join_tuples(response)

        # files
        server.request_line = (
            "SELECT pkghash, filename FROM File WHERE pkghash IN %(pkghshs)s",
            {'pkghshs': pkghashs}
        )

        status, response = server.send_request()
        if status is False:
            return response

        files_dict = utils.tuplelist_to_dict(response, 1)

        # depends
        server.request_line = (
            "SELECT pkghash, dptype, dpname, dpversion FROM last_depends "
            "WHERE pkghash IN %(pkghshs)s", {'pkghshs': pkghashs}
        )

        status, response = server.send_request()
        if status is False:
            return response

        depends_dict = utils.tuplelist_to_dict(response, 3)

        for elem in json_retval:
            pkghash = json_retval[elem]['pkghash']

            json_retval[elem]['files'] = files_dict[pkghash]

            prop_dict_values = utils.tuplelist_to_dict(depends_dict[pkghash], 2)

            for prop in ['require', 'conflict', 'obsolete', 'provide']:
                if prop in prop_dict_values.keys():
                    json_retval[elem][prop + 's'] = [
                        nv[0] + " " + nv[1] for nv in prop_dict_values[prop]
                    ]

    # remove pkghash from result
    for value in json_retval.values():
        value.pop('pkghash', None)

    return json.dumps(json_retval, sort_keys=False)


@app.route('/misconflict_packages')
@func_time(logger)
def conflict_packages():
    server.url_logging()

    check_params = server.check_input_params(source=0)
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    pbranch = server.get_one_value('branch', 's')

    if not pname or not pbranch:
        return json.dumps(server.helper(request.path))

    server.request_line = (
        "SELECT arch FROM last_packages WHERE name = %(name)s AND "
        "sourcepackage = 0 AND assigment_name = %(branch)s",
        {'name': pname, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    real_parchs = [arch[0] for arch in response]

    allowed_archs = real_parchs
    if 'noarch' in allowed_archs:
        allowed_archs = server.known_archs

    parchs = server.get_one_value('arch', 's')
    if parchs:
        parchs = parchs.split(',')

        if 'noarch' in parchs:
            allowed_archs = tuple(allowed_archs)
        else:
            add_archs = []
            for arch in parchs:
                if arch in allowed_archs:
                    add_archs.append(arch)

            allowed_archs = add_archs

    if len(allowed_archs) == 0:
        return utils.json_str_error(
            'The package does not have the specified architectures'
        )

    # detect version
    pversion = server.get_one_value('version', 's')
    if not pversion:
        status, pversion = server.get_last_version(pname, pbranch)
        if status is False:
            return pversion

    # packages with ident files
    server.request_line = (
        "SELECT pkghash, filename FROM File WHERE hashname IN (SELECT "
        "hashname FROM File WHERE pkghash IN (SELECT pkghash FROM "
        "last_packages WHERE name = %(name)s AND assigment_name = %(branch)s "
        "AND sourcepackage = 0 AND arch IN %(arch)s) AND fileclass != "
        "'directory') AND pkghash NOT IN (SELECT pkghash FROM last_packages "
        "WHERE name = %(name)s) AND pkghash NOT IN (SELECT pkghash FROM "
        "last_depends WHERE dpname = %(name)s AND dptype = 'conflict' AND "
        "assigment_name = %(branch)s AND sourcepackage = 0 AND (dpversion "
        "LIKE %(vers)s OR dpversion LIKE %(vers_epoch)s OR dpversion = '')) "
        "AND pkghash NOT IN (SELECT pkghash FROM last_packages WHERE name IN "
        "(SELECT DISTINCT dpname FROM last_depends WHERE pkgname = %(name)s "
        "AND assigment_name = %(branch)s AND dptype = 'conflict' AND arch IN "
        "%(arch)s) AND assigment_name = %(branch)s AND sourcepackage = 0 AND "
        "arch IN %(arch)s)",
        {'name': pname, 'branch': pbranch, 'vers': "{}%".format(pversion),
         'vers_epoch': "%:{}%".format(pversion), 'arch': tuple(allowed_archs)}
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    hsh_files_dict = defaultdict(list)
    for pkg in response:
        hsh_files_dict[pkg[0]].append(pkg[1])

    server.request_line = (
        "SELECT pkghash, name, version, release, arch, assigment_name "
        "FROM last_packages WHERE pkghash IN %(hashs)s AND assigment_name = "
        "%(branch)s AND sourcepackage = 0 AND arch IN %(arch)s",
        {'hashs': tuple(hsh_files_dict.keys()), 'branch': pbranch,
         'arch': tuple(allowed_archs)}
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    for package in response:
        idx = response.index(package)
        package = list(package)
        package.append(hsh_files_dict[package[0]])
        response[idx] = package[1:]

    result_list = []
    for package in response:
        name, archs = package[0], []
        for arch in response:
            if arch[0] == name:
                archs.append(arch[3])

        result = [
            package[0], package[1], package[2], archs, package[4], package[5]
        ]

        if result not in result_list:
            result_list.append(result)

    return utils.convert_to_json(['name', 'version', 'release', 'archs', 'branch',
                                  'files_with_conflict'], result_list)


@app.route('/package_by_file')
@func_time(logger)
def package_by_file():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    file = server.get_one_value('file', 'r')
    md5 = server.get_one_value('md5', 's')

    if len([param for param in [file, md5] if param]) != 1:
        return json.dumps(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        return utils.json_str_error('Branch require parameter!')

    arch = server.get_one_value('arch', 's')
    if arch:
        arch = (arch, 'noarch')
    else:
        arch = server.known_archs

    pkghash = \
        "SELECT pkg.pkghash FROM last_packages WHERE " \
        "assigment_name = %(branch)s AND arch IN %(arch)s"

    base_query = \
        "SELECT pkghash{in_} FROM File WHERE pkghash IN ({pkghash}) AND " \
        "{param}".format(in_='{}', pkghash=pkghash, param='{}')

    if file:
        elem, query = file, "filename LIKE %(elem)s"
    else:
        elem, query = md5, "filemd5 = %(elem)s"

    server.request_line = (
        base_query.format(', filename', query),
        {'branch': pbranch, 'arch': tuple(arch), 'elem': elem}
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    ids_filename_dict = utils.tuple_to_dict(response)

    pkghashs = tuple([key for key in ids_filename_dict.keys()])

    server.request_line = (
        "SELECT pkghash, pkgcs, name, version, release, disttag, arch, "
        "assigment_name FROM last_packages WHERE sourcepackage = 0 AND "
        "pkghash IN %(hashs)s AND assigment_name = %(branch)s",
        {'hashs': pkghashs, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    output_values = []
    for package in response:
        package += (ids_filename_dict[package[0]],)
        output_values.append(package[1:])

    output_params = ['pkgcs', 'name', 'version', 'release',
                     'disttag', 'arch', 'branch', 'files']

    return utils.convert_to_json(output_params, tuple(output_values))


@app.route('/package_files')
@func_time(logger)
def package_files():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1', 's')
    if not sha1:
        return json.dumps(server.helper(request.path))

    server.request_line = (
        "SELECT filename FROM File WHERE pkghash = murmurHash3_64(%(sha1)s)",
        {'sha1': sha1}
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return utils.json_str_error(
            "Files not found by sha1 '{}'".format(sha1)
        )

    js = {
        'sha1': sha1,
        'files': [file[0] for file in response],
    }

    return json.dumps(js, sort_keys=False)


@app.route('/dependent_packages')
@func_time(logger)
def dependent_packages():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    if not pname:
        return json.dumps(server.helper(request.path))

    pversion = server.get_one_value('version', 's')
    if pversion:
        pversion = \
            "AND (dpversion LIKE %(vers)s OR dpversion LIKE %(vers_epoch)s " \
            "OR dpversion = '')"
    else:
        pversion = ''

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        message = 'Branch is required parameter.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = (
        "SELECT DISTINCT name, version, release, epoch, serial_, filename "
        "AS sourcerpm, assigment_name, groupUniqArray(binary_arch) FROM "
        "last_packages INNER JOIN (SELECT sourcerpm, arch AS binary_arch "
        "FROM last_packages WHERE name IN (SELECT DISTINCT pkgname FROM "
        "last_depends WHERE dpname = %(name)s {vers} AND "
        "assigment_name = %(branch)s AND sourcepackage = 0) AND "
        "assigment_name = %(branch)s AND sourcepackage = 0) USING sourcerpm "
        "WHERE assigment_name = %(branch)s AND sourcepackage = 1 GROUP BY "
        "(name, version, release, epoch, serial_, filename AS sourcerpm, "
        "assigment_name)".format(vers=pversion),
        {'vers': "{}%".format(pversion), 'vers_epoch': "%:{}%".format(pversion),
         'name': pname, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    js_keys = ['name', 'version', 'release', 'epoch', 'serial', 'sourcerpm',
               'branch', 'archs']

    return utils.convert_to_json(js_keys, response)


@app.route('/what_depends_src')
@func_time(logger)
def broken_build():
    check_params = server.check_input_params(source=1)
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    task_id = server.get_one_value('task', 'i')

    message = None
    if pname and task_id:
        message = "Only one parameter 'name' or 'task'."
    elif not pname and not task_id:
        message = "'name' or 'task' is require parameters."

    if message:
        logger.debug(message)
        return utils.json_str_error(message)

    pbranch = server.get_one_value('branch', 's')
    if pname and not pbranch:
        return json.dumps(server.helper(request.path))

    arch = server.get_one_value('arch', 's')
    if arch:
        arch = [arch]
        if 'noarch' not in arch:
            arch.append('noarch')

    leaf = server.get_one_value('leaf', 's')
    if leaf and task_id:
        return utils.json_str_error("'leaf' may be using with 'name' only.")

    if task_id:
        # branch name
        server.request_line = (
            "SELECT DISTINCT branch FROM Tasks WHERE task_id = %(id)s",
            {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        pbranch = response[0][0]

        server.request_line = (
            "SELECT pkgs FROM Tasks WHERE task_id = %(id)s", {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        pkgs_hsh = ()
        for tp_package in response:
            for package in tp_package[0]:
                pkgs_hsh += (package,)

        # src packages from task
        server.request_line = (
            "SELECT DISTINCT name FROM Package WHERE filename IN (SELECT "
            "DISTINCT sourcerpm FROM Package WHERE pkghash IN %(pkghshs)s)"
            "", {'pkghshs': pkgs_hsh}
        )

        status, response = server.send_request()
        if status is False:
            return response

        input_pkgs = utils.join_tuples(response)

    else:
        input_pkgs = (pname,)

    deep_level = server.get_one_value('deep', 'i')
    if not deep_level:
        deep_level = 1

    base_query = \
        "SELECT DISTINCT pkgname FROM last_depends WHERE dpname IN " \
        "(SELECT name FROM last_packages_with_source WHERE " \
        "sourcepkgname IN %(pkgs)s AND assigment_name = %(branch)s AND " \
        "arch IN ('x86_64', 'noarch') AND name NOT LIKE '%%-debuginfo') " \
        "AND assigment_name = %(branch)s AND sourcepackage = 1 AND " \
        "dptype = 'require' AND pkgname NOT LIKE '%%-debuginfo' UNION ALL " \
        "SELECT arrayJoin(%(union)s)"

    deep_wrapper = \
        "SELECT DISTINCT pkgname FROM last_depends WHERE dpname IN " \
        "(SELECT DISTINCT name FROM last_packages_with_source WHERE " \
        "sourcepkgname IN ({b_q}) AND assigment_name = %(branch)s AND " \
        "arch IN ('x86_64', 'noarch') AND name NOT LIKE '%%-debuginfo') " \
        "AND assigment_name = %(branch)s AND dptype = 'require' AND " \
        "sourcepackage = 1".format(b_q='{b_q}')

    if deep_level == 1:
        server.request_line = base_query
    else:

        if deep_level > 3:
            return utils.json_str_error("Deep cannot exceed 3")

        server.request_line = \
            "SELECT DISTINCT pkgname FROM ({} UNION ALL {})".format(
                deep_wrapper.format(b_q=base_query), base_query
            )

        if deep_level == 3:
            pre_query = server.request_line

            server.request_line = \
                "SELECT DISTINCT pkgname FROM ({} UNION ALL {})".format(
                    deep_wrapper.format(b_q=server.request_line), pre_query
                )

    server.request_line = (
        server.request_line,
        {'union': list(input_pkgs), 'pkgs': input_pkgs, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    # get requires
    requires_list = ['']
    for require in response:
        requires_list.append(require[0])

    server.request_line = (
        "SELECT DISTINCT BinDeps.pkgname, arrayFilter(x -> (x != "
        "BinDeps.pkgname AND notEmpty(x)), groupUniqArray(sourcepkgname)) "
        "AS srcarray FROM (SELECT DISTINCT BinDeps.pkgname, name AS "
        "pkgname, sourcepkgname FROM last_packages_with_source INNER JOIN "
        "(SELECT DISTINCT BinDeps.pkgname, pkgname FROM (SELECT DISTINCT "
        "BinDeps.pkgname, pkgname, dpname FROM last_depends INNER JOIN "
        "(SELECT DISTINCT pkgname, dpname FROM last_depends WHERE pkgname "
        "IN %(pkgs)s AND assigment_name = %(branch)s AND dptype = 'require' "
        "AND sourcepackage = 1) AS BinDeps USING dpname WHERE "
        "assigment_name = %(branch)s AND dptype = 'provide' AND "
        "sourcepackage = 0 AND arch IN ('x86_64', 'noarch'))) USING "
        "pkgname WHERE assigment_name = %(branch)s ORDER BY sourcepkgname "
        "ASC UNION ALL SELECT arrayJoin(%(union)s), '', '') WHERE "
        "sourcepkgname IN %(pkgs)s GROUP BY BinDeps.pkgname ORDER BY "
        "length(srcarray)",
        {'union': list(input_pkgs), 'pkgs': tuple(requires_list),
         'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    name_reqs_dict = {}
    for elem in response:
        reqs = [req for req in elem[1] if req != '']
        name_reqs_dict[elem[0]] = reqs

    name_reqs_dict_cleanup = name_reqs_dict

    if leaf:
        if leaf not in name_reqs_dict_cleanup.keys():
            return utils.json_str_error(
                "Package '{}' not in dependencies list.".format(leaf)
            )
        else:
            leaf_deps = name_reqs_dict_cleanup[leaf]

    sort = SortList(name_reqs_dict_cleanup, pname)
    circle_deps, sorted_list = sort.sort_list()

    cleanup_circle_deps = []
    for dp in circle_deps:
        if dp[1] != pname:
            cleanup_circle_deps.append(dp)

    circle_deps = cleanup_circle_deps

    circle_deps_dict = {}
    for c_dep in circle_deps:
        if c_dep[0] not in circle_deps_dict.keys():
            circle_deps_dict[c_dep[0]] = []
        circle_deps_dict[c_dep[0]].append(c_dep[1])

    for name, deps in circle_deps_dict.items():
        if name in deps:
            deps.remove(name)
        for pac in sorted_list:
            if pac == name:
                sorted_list[sorted_list.index(pac)] = (pac, deps)

    result_dict = {}
    for package in sorted_list:
        if isinstance(package, tuple):
            result_dict[package[0]] = package[1]
        else:
            result_dict[package] = []

    if leaf:
        result_dict_leaf = defaultdict(list)
        result_dict_leaf[pname] = []

        for package, c_deps in result_dict.items():
            if package in leaf_deps:
                if c_deps:
                    for dep in c_deps:
                        if dep in leaf_deps:
                            result_dict_leaf[package].append(dep)
                else:
                    result_dict_leaf[package] = []

        result_dict_leaf[leaf] = []

        result_dict = result_dict_leaf

    sorted_pkgs = tuple(result_dict.keys())

    server.request_line = (
        "SELECT DISTINCT SrcPkg.name, SrcPkg.version, SrcPkg.release, "
        "SrcPkg.epoch, SrcPkg.serial_, sourcerpm AS filename, "
        "assigment_name, groupUniqArray(arch) FROM last_packages "
        "INNER JOIN (SELECT name, version, release, epoch, serial_, "
        "filename, assigment_name FROM last_packages WHERE name IN "
        "%(pkgs)s AND assigment_name = %(branch)s AND sourcepackage = 1) "
        "AS SrcPkg USING filename WHERE assigment_name = %(branch)s AND "
        "sourcepackage = 0 GROUP BY (SrcPkg.name, SrcPkg.version, "
        "SrcPkg.release, SrcPkg.epoch, SrcPkg.serial_, filename, "
        "assigment_name)",
        {'pkgs': sorted_pkgs, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    # add circle requires in package info
    pkg_info_list = []
    for info in response:
        for pkg, c_deps in result_dict.items():
            if info[0] == pkg:
                pkg_info_list.append(info + (c_deps,))

    # sort pkg info list
    sorted_dict = {}
    for pkg in pkg_info_list:
        if task_id:
            if pkg[0] not in input_pkgs:
                sorted_dict[sorted_pkgs.index(pkg[0])] = pkg
        else:
            sorted_dict[sorted_pkgs.index(pkg[0])] = pkg

    sorted_dict = list(dict(sorted(sorted_dict.items())).values())

    js_keys = ['name', 'version', 'release', 'epoch', 'serial_', 'sourcerpm',
               'branch', 'archs', 'cycle']

    return utils.convert_to_json(js_keys, sorted_dict)


@app.errorhandler(404)
def page_404(e):
    helper = {
        'Valid queries': {
            '/package_info': 'information about given package',
            '/misconflict_packages': 'binary packages with intersecting '
                                     'files and no conflict with a given package',
            '/package_by_file': 'binary packages that contain the specified file',
            '/package_files': 'files by current sha1 of package',
            '/dependent_packages': 'source packages whose binary packages '
                                   'depend on the given package',
            '/what_depends_src': 'binary packages with build dependency on a '
                                 'given package',
        }
    }
    return json.dumps(helper)


server = LogicServer()
server.init()

if __name__ == '__main__':
    app.run()
