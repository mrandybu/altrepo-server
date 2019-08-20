import re
from urllib.parse import unquote
from flask import Flask, request, json
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
                            "(ex. file='/usr/bin/%')",
                    'md5': 'file md5',
                    'arch': '',
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
                    'sort': '/beta/ for sort by dependencies',
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
    def send_request(self):
        db_connection = self._get_connection()
        db_connection.db_query = self.request_line

        return db_connection.send_request()

    @staticmethod
    def get_one_value(param, type_):
        value = request.args.get(param)

        if value:
            # fixed err when package name contains '+'
            if param == 'name':
                value = value.replace(' ', '+')

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

    def check_input_params(self, binary_only=False):
        if not request.args:
            return json.dumps(server.helper(request.path))

        # check arch
        parchs = self.get_one_value('arch', 's')
        if parchs:
            for arch in parchs.split(','):
                if arch and arch not in ['aarch64', 'armh', 'i586',
                                         'noarch', 'x86_64', 'x86_64-i586']:
                    return utils.json_str_error('Unknown arch of package!')

        # check branch
        pbranch = self.get_one_value('branch', 's')
        if pbranch and pbranch not in self.known_branches:
            return utils.json_str_error('Unknown branch!')

        # check package params
        pname = self.get_one_value('name', 's')
        if pname:
            default_req = "SELECT name FROM last_packages"
            args = "name = '{}'".format(pname)

            pversion = self.get_one_value('version', 's')
            if pversion:
                args = "{} AND version = '{}'".format(args, pversion)

            if pbranch:
                args = "{} AND assigment_name = '{branch}'" \
                       "".format(args, branch=pbranch)

            if binary_only:
                args = "{} AND sourcepackage = 0".format(args)

            self.request_line = "{} WHERE {}".format(default_req, args)

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
        self.request_line = \
            "SELECT version FROM last_packages WHERE name = '{name}' AND " \
            "assigment_name = '{branch}'".format(name=name, branch=branch)

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
            "AND assigment_name = '{}'".format(pbranch)
        )
    else:
        server.request_line = server.request_line.format('')

    status, response = server.send_request()
    if status is False:
        return response

    json_retval = json.loads(
        utils.convert_to_json(['pkghash'] + output_params, response)
    )

    if full:

        pkghashs = utils.normalize_tuple(utils.join_tuples(response))

        # files
        server.request_line = \
            "SELECT pkghash, filename FROM File WHERE pkghash IN {}" \
            "".format(pkghashs)

        status, response = server.send_request()
        if status is False:
            return response

        files_dict = utils.tuplelist_to_dict(response, 1)

        # depends
        server.request_line = \
            "SELECT pkghash, dptype, dpname, dpversion FROM last_depends " \
            "WHERE pkghash IN {}".format(pkghashs)

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

    check_params = server.check_input_params(binary_only=True)
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    pbranch = server.get_one_value('branch', 's')

    if not pname or not pbranch:
        return json.dumps(server.helper(request.path))

    allowed_archs = ('noarch',)
    parchs = server.get_one_value('arch', 's')
    if parchs:
        for arch in parchs.split(','):
            if arch not in allowed_archs:
                allowed_archs += (arch,)
    else:
        allowed_archs += ('x86_64',)

    # input package sha1 hash
    server.request_line = \
        "SELECT pkg.pkghash FROM last_packages WHERE name = '{name}' AND " \
        "assigment_name = '{branch}' AND sourcepackage = 0 AND arch IN " \
        "{archs}".format(name=pname, branch=pbranch, archs=allowed_archs)

    status, response = server.send_request()
    if status is False:
        return response

    input_pkghash = response[0][0]

    # detect version
    pversion = server.get_one_value('version', 's')
    if not pversion:
        status, pversion = server.get_last_version(pname, pbranch)
        if status is False:
            return pversion

    # package without conflicts
    server.request_line = \
        "SELECT pkg.pkghash, name, version FROM last_packages WHERE " \
        "pkg.pkghash IN (SELECT DISTINCT pkghash FROM File WHERE hashname " \
        "IN (SELECT hashname FROM File WHERE fileclass != 'directory' AND " \
        "pkghash = {pkghash}) AND pkghash NOT IN (SELECT pkghash FROM " \
        "Depends WHERE dptype = 'conflict' AND dpname = '{name}' AND " \
        "(dpversion LIKE '{vers}-%' OR dpversion LIKE '%:{vers}-%' OR " \
        "dpversion LIKE ''))) AND name != '{name}' AND sourcepackage = 0 " \
        "AND assigment_name = '{branch}' AND arch IN {arch}".format(
            pkghash=input_pkghash, name=pname, vers=pversion, branch=pbranch,
            arch=allowed_archs
        )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    packages_without_conflicts = response

    # input package conflict
    server.request_line = \
        "SELECT dpname, dpversion FROM Depends WHERE dptype = 'conflict' " \
        "AND pkghash = {}".format(input_pkghash)

    status, response = server.send_request()
    if status is False:
        return response

    input_package_conflicts = response

    # remove release from version
    for conflict in input_package_conflicts:
        input_package_conflicts[input_package_conflicts.index(conflict)] = \
            (conflict[0], conflict[1].split('-')[0])

    result_packages = []
    for package in packages_without_conflicts:
        if (package[1], '') not in input_package_conflicts \
                and (package[1], package[2]) not in input_package_conflicts:
            result_packages.append(package)

    # add archs, files to result list
    f_result_packages = []
    for package in result_packages:
        # conflict files
        server.request_line = \
            "SELECT filename FROM File WHERE pkghash = {} AND hashname IN " \
            "(SELECT hashname FROM File WHERE pkghash = {})" \
            "".format(package[0], input_pkghash)

        status, response = server.send_request()
        if status is False:
            return response

        conflict_files = utils.join_tuples(response)

        # archs of conflict packages
        server.request_line = \
            "SELECT DISTINCT arch FROM last_packages WHERE " \
            "(name, version) = ('{}', '{}')".format(package[1], package[2])

        status, response = server.send_request()
        if status is False:
            return response

        archs = []
        for arch in response:
            if arch[0] in allowed_archs:
                archs.append(arch[0])

        f_package = (package[1], package[2], archs, conflict_files)

        if f_package not in f_result_packages:
            f_result_packages.append(f_package)

    return utils.convert_to_json(['name', 'version', 'archs', 'files'],
                                 f_result_packages)


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
        arch = "AND arch IN {}".format((arch, 'noarch'))
    else:
        arch = ''

    pkghash = \
        "SELECT pkg.pkghash FROM last_packages WHERE " \
        "assigment_name = '{branch}' {arch}".format(branch=pbranch, arch=arch)

    base_query = \
        "SELECT pkghash{in_} FROM File WHERE pkghash IN ({pkghash}) AND " \
        "{param}".format(in_='{}', pkghash=pkghash, param='{}')

    if file:
        query = "filename LIKE '{}'".format(file)
    else:
        query = "filemd5 = '{}'".format(md5)

    server.request_line = base_query.format(', filename', query)

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    ids_filename_dict = utils.tuple_to_dict(response)

    pkghashs = utils.normalize_tuple([key for key in ids_filename_dict.keys()])

    server.request_line = \
        "SELECT pkghash, pkgcs, name, version, release, disttag, arch, " \
        "assigment_name FROM last_packages WHERE sourcepackage = 0 AND " \
        "pkghash IN {} AND assigment_name = '{}'".format(pkghashs, pbranch)

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

    server.request_line = \
        "SELECT filename FROM File WHERE pkghash IN (SELECT pkghash FROM " \
        "Package WHERE pkgcs = '{sha1}')".format(sha1=sha1)

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

    pversion = server.get_one_value('version', 's')
    if pversion:
        action = "{} LIKE '{}%'"
    else:
        action = None

    input_params = {
        'name': {
            'rname': 'dpname',
            'type': 's',
            'action': None,
            'notempty': True,
        },
        'version': {
            'rname': 'dpversion',
            'type': 's',
            'action': action,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        return json.dumps(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        message = 'Branch is required parameter.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = \
        "SELECT DISTINCT sourcerpm, epoch, serial_, disttag FROM " \
        "last_packages WHERE pkg.pkghash IN (SELECT pkghash FROM " \
        "Depends WHERE {args}) AND assigment_name = '{branch}'" \
        "".format(branch=pbranch, args=" ".join(params_values))

    status, response = server.send_request()
    if status is False:
        return response

    source_package_fullname = []
    for fullname in response:
        if fullname[0]:
            reg = re.compile("(.*)-([0-9.]+)-(alt.*).src.rpm")
            source_package_fullname.append(
                re.findall(reg, fullname[0])[0] + fullname[1:]
            )

    if not source_package_fullname:
        return json.dumps({})

    server.request_line = \
        "SELECT {p_params} FROM last_packages WHERE (name, version, release, " \
        "epoch, serial_, disttag) IN {nvr} AND sourcepackage = 1 AND " \
        "assigment_name = '{branch}'".format(
            p_params=", ".join(server.package_params),
            nvr=utils.normalize_tuple(tuple(source_package_fullname)),
            branch=pbranch,
        )

    status, response = server.send_request()
    if status is False:
        return response

    return utils.convert_to_json(server.package_params, response)


@app.route('/what_depends_src')
@func_time(logger)
def broken_build():
    check_params = server.check_input_params()
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

    if pname:
        status, pversion = server.get_last_version(pname, pbranch)
        if status is False:
            return pversion

    if pname:
        server.request_line = \
            "SELECT DISTINCT name, version, release, epoch, serial_ " \
            "FROM last_packages WHERE name IN (SELECT DISTINCT pkgname FROM " \
            "last_depends WHERE dpname IN (SELECT DISTINCT name FROM " \
            "last_packages WHERE sourcerpm IN (SELECT filename FROM " \
            "last_packages WHERE name IN (SELECT DISTINCT pkgname FROM " \
            "last_depends WHERE dpname IN (SELECT DISTINCT name FROM " \
            "last_packages WHERE sourcerpm IN (SELECT filename FROM " \
            "last_packages WHERE name = '{name}' AND sourcepackage = 1 AND " \
            "assigment_name = '{branch}') AND assigment_name = '{branch}' " \
            "AND name NOT LIKE '%-debuginfo') AND sourcepackage = 1 AND " \
            "assigment_name = '{branch}') AND assigment_name = '{branch}' " \
            "AND sourcepackage = 1) AND name NOT LIKE '%-debuginfo' AND " \
            "assigment_name = '{branch}') AND sourcepackage = 1 AND " \
            "assigment_name = '{branch}') AND sourcepackage = 1 AND " \
            "assigment_name = '{branch}'".format(name=pname, branch=pbranch)
    else:
        # binary packages in task
        server.request_line = \
            "SELECT pkgs FROM Tasks WHERE task_id = {}".format(task_id)

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return json.dumps({})

        binary_packages = ()
        for tp_package in response:
            for package in tp_package[0]:
                binary_packages += (package,)

        binary_packages = utils.normalize_tuple(binary_packages)

        server.request_line = \
            "SELECT DISTINCT concat(name, '-', version, '-', release) AS " \
            "fullname, epoch, serial_, disttag, assigment_name, " \
            "groupUniqArray(arch) FROM last_packages WHERE pkg.pkghash IN (" \
            "SELECT pkghash FROM Depends WHERE dpname IN (SELECT name FROM " \
            "Package WHERE pkghash IN {bp})) AND assigment_name IN (" \
            "SELECT branch FROM Tasks WHERE task_id = {task_id}) {arch} AND " \
            "pkg.pkghash NOT IN {bp} GROUP BY (fullname, epoch, serial_, " \
            "disttag, assigment_name)".format(
                bp=binary_packages, branch=pbranch, arch='{arch}', task_id=task_id
            )

        if arch:
            server.request_line = server.request_line.format(
                arch="AND arch = '{}'".format(arch)
            )
        else:
            server.request_line = server.request_line.format(arch='')

    status, response = server.send_request()
    if status is False:
        return response

    sort = server.get_one_value('sort', 'b')
    if sort:
        server.request_line = \
            "SELECT Dps.pkgname, groupUniqArray(sourcepkgname) FROM " \
            "last_packages_with_source LEFT JOIN (SELECT * FROM last_depends " \
            "WHERE assigment_name = '{branch}' AND pkgname NOT LIKE " \
            "'%-debuginfo' AND dptype = 'require' AND sourcepackage = 1) AS " \
            "Dps ON Dps.dpname = name WHERE name NOT LIKE '%-debuginfo' AND " \
            "assigment_name = '{branch}' AND sourcepkghash IN (SELECT DISTINCT " \
            "pkghash FROM last_depends WHERE assigment_name = '{branch}' AND " \
            "arch IN ('x86_64', 'noarch') AND dptype = 'require' AND " \
            "sourcepackage = 1 AND dpname IN (SELECT DISTINCT name FROM " \
            "last_packages_with_source WHERE sourcepkgname IN (SELECT DISTINCT " \
            "pkgname FROM last_depends WHERE dpname IN (SELECT name FROM " \
            "last_packages_with_source WHERE assigment_name = '{branch}' AND " \
            "sourcepkgname = '{pkgname}' AND arch IN ('x86_64', 'noarch') AND " \
            "name NOT LIKE '%-debuginfo') AND assigment_name = '{branch}' AND " \
            "arch IN ('x86_64', 'noarch') AND dptype = 'require' AND " \
            "sourcepackage = 0 AND pkgname NOT LIKE '%-debuginfo' UNION ALL " \
            "SELECT name FROM last_packages WHERE assigment_name = '{branch}' " \
            "AND name = '{pkgname}' AND arch IN ('x86_64', 'noarch') AND " \
            "sourcepackage = 1) AND assigment_name = '{branch}' AND arch IN " \
            "('x86_64', 'noarch') AND name NOT LIKE '%-debuginfo') UNION ALL " \
            "SELECT pkghash FROM last_packages WHERE assigment_name = '{branch}' " \
            "AND name = '{pkgname}' AND arch IN ('x86_64', 'noarch') AND " \
            "sourcepackage = 1) AND arch IN ('x86_64', 'noarch') AND " \
            "assigment_name = '{branch}' AND pkgname != '' GROUP BY Dps.pkgname" \
            "".format(branch=pbranch, pkgname=pname)

        status, response = server.send_request()

        name_reqs_dict = {}
        for elem in response:
            reqs = [req for req in elem[1] if req != '']
            name_reqs_dict[elem[0]] = reqs

        sort = SortList(name_reqs_dict, pname)
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
            for pac in sorted_list:
                if pac == name:
                    sorted_list[sorted_list.index(pac)] = (pac, deps)

        result_dict = {}
        for package in sorted_list:
            if isinstance(package, tuple):
                result_dict[package[0]] = package[1]
            else:
                result_dict[package] = []

        return json.dumps(result_dict, sort_keys=False)

    if pname:
        js_keys = ['name', 'version', 'release', 'epoch', 'serial_', 'branch']

        for package in response:
            response[response.index(package)] = package + (pbranch,)
    else:
        js_keys = ['fullname', 'epoch', 'serial_', 'disttag', 'branch', 'archs']

    return utils.convert_to_json(js_keys, response)


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
