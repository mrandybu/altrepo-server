import re
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
        self.clickhouse_host = self._get_config('ClickHouse', 'Host')
        self.clickhouse_name = self._get_config('ClickHouse', 'DBName', False)

    @staticmethod
    def init():
        utils.print_statusbar(
            "Using configuration file: {}".format(paths.DB_CONFIG_FILE), 'i'
        )

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

    @func_time(logger)
    def send_request(self):
        db_connection = self._get_connection()
        db_connection.db_query = self.request_line

        return db_connection.send_request()

    # FIXME need fix according new db struct
    def get_last_repo_id(self, pbranch=None, date=None):

        default_query = \
            "SELECT toString(id) FROM AssigmentName " \
            "WHERE complete = 1 {args} ORDER BY datetime_release DESC LIMIT 1"

        branch_id = {}
        for branch in self.known_branches:
            args = "AND name = '{}'".format(branch)
            if date:
                args = "{} AND toDate(datetime_release) = '{}'" \
                       "".format(args, date)

            self.request_line = default_query.format(args=args)

            status, response = self.send_request()
            if status is False:
                return response

            if len(response) > 0:
                branch_id[branch] = response[0][0]

        if pbranch:
            if pbranch in branch_id:
                # always return a tuple to use 'IN' everywhere
                return utils.normalize_tuple((branch_id[pbranch],))

            return ()

        return tuple([branch for branch in branch_id.values()])

    def add_extra_package_params(self, extra_package_params):
        return self.package_params + extra_package_params

    @staticmethod
    def get_one_value(param, type_):
        value = request.args.get(param)

        if value:
            # fix err when package name contains '+'
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
                if value.lower() not in ['true', 'false']:
                    value = False
            # type for using pattern in /package_by_file
            if type_ == 'r':
                value = [el for el in value.split("'") if el][0]

        return value

    def check_input_params(self, binary_only=False, date=None):
        # check arch
        parch = self.get_one_value('arch', 's')
        if parch and parch not in ['aarch64', 'armh', 'i586',
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

        # logger.debug(self.request_line)

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
    date_value = server.get_one_value('date', 's')

    last_repo_id = server.get_last_repo_id(pbranch, date_value)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

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
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    full = bool(server.get_one_value('full', 'b'))

    output_params = [
        'pkgcs', 'packager', 'packager_email', 'name',
        'arch', 'version', 'release', 'epoch', 'buildtime',
        'sourcepackage', 'sourcerpm', 'filename',
    ]
    if full:
        output_params = server.package_params

    server.request_line = \
        "SELECT {p_params} FROM Package WHERE pkgcs IN " \
        "(SELECT pkgcs FROM Assigment WHERE uuid IN {repo_ids}) AND {p_values}" \
        "".format(
            p_params=", ".join(output_params),
            repo_ids=last_repo_id,
            p_values=" ".join(params_values)
        )

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    json_retval = json.loads(
        utils.convert_to_json(output_params, response)
    )

    if full:

        sha1_list = utils.normalize_tuple(utils.join_tuples(response))

        # files
        server.request_line = \
            "SELECT pkgcs, filename FROM File WHERE pkgcs IN {}".format(sha1_list)

        status, response = server.send_request()
        if status is False:
            return response

        files_dict = utils.tuplelist_to_dict(response, 1)

        # depends
        server.request_line = \
            "SELECT pkgcs, dptype, name, version FROM Depends WHERE pkgcs IN {}" \
            "".format(sha1_list)

        status, response = server.send_request()
        if status is False:
            return response

        depends_dict = utils.tuplelist_to_dict(response, 3)

        for elem in json_retval:
            pkgcs = json_retval[elem]['pkgcs']

            json_retval[elem]['files'] = files_dict[pkgcs]

            prop_dict_values = utils.tuplelist_to_dict(depends_dict[pkgcs], 2)

            for prop in ['require', 'conflict', 'obsolete', 'provide']:
                if prop in prop_dict_values.keys():
                    json_retval[elem][prop + 's'] = [
                        nv[0] + " " + nv[1] for nv in prop_dict_values[prop]
                    ]

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
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    last_repo_id = server.get_last_repo_id(pbranch)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

    # input package sha1
    server.request_line = \
        "SELECT max(pkgcs) FROM last_packages WHERE name = '{name}' AND " \
        "assigment_name = '{branch}' AND sourcepackage = 0" \
        "".format(name=pname, branch=pbranch)

    status, response = server.send_request()
    if status is False:
        return response

    input_pkgcs = response[0][0]

    # detect version
    pversion = server.get_one_value('version', 's')
    if not pversion:
        status, pversion = server.get_last_version(pname, pbranch)
        if status is False:
            return pversion

    # package without conflicts
    server.request_line = \
        "SELECT MAX(pkgcs), name, version FROM last_packages WHERE pkgcs IN (" \
        "SELECT DISTINCT pkgcs FROM File WHERE filename IN (" \
        "SELECT filename FROM File WHERE fileclass != 'directory' AND " \
        "pkgcs = '{pkgcs}') AND pkgcs NOT IN (" \
        "SELECT pkgcs FROM Depends WHERE dptype = 'conflict' AND dpname = '{name}' " \
        "AND (dpversion LIKE '{vers}-%' OR dpversion LIKE '%:{vers}-%' OR " \
        "dpversion LIKE ''))) AND name != '{name}' AND sourcepackage = 0 AND " \
        "assigment_name = '{branch}' GROUP BY (name, version)" \
        "".format(pkgcs=input_pkgcs, name=pname, vers=pversion, branch=pbranch)

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    packages_without_conflicts = response

    # input package conflict
    server.request_line = \
        "SELECT dpname, dpversion FROM Depends WHERE dptype = 'conflict' " \
        "AND pkgcs = '{}'".format(input_pkgcs)

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

    # input package files
    server.request_line = \
        "SELECT filename FROM File WHERE pkgcs = '{}'".format(input_pkgcs)

    status, response = server.send_request()
    if status is False:
        return response

    input_package_files = utils.normalize_tuple(utils.join_tuples(response))

    # input package archs
    server.request_line = \
        "SELECT DISTINCT arch FROM Package " \
        "WHERE (name, version) = ('{}', '{}')".format(pname, pversion)

    status, response = server.send_request()
    if status is False:
        return response

    input_package_archs = utils.join_tuples(response)

    # add archs, files to result list
    for package in result_packages:
        # conflict files
        server.request_line = \
            "SELECT filename FROM File WHERE pkgcs = '{}' AND filename IN {}" \
            "".format(package[0], input_package_files)

        status, response = server.send_request()
        if status is False:
            return response

        conflict_files = utils.join_tuples(response)

        # archs of conflict packages
        server.request_line = \
            "SELECT DISTINCT arch FROM Package WHERE " \
            "(name, version) = ('{}', '{}')".format(package[1], package[2])

        status, response = server.send_request()
        if status is False:
            return response

        archs = []
        for arch in response:
            if arch[0] in input_package_archs or arch[0] == 'noarch':
                archs.append(arch[0])

        result_packages[result_packages.index(package)] = (
            package[1], package[2], archs, conflict_files
        )

    return utils.convert_to_json(['name', 'version', 'archs', 'files'],
                                 result_packages)


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
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        return utils.json_str_error('Branch require parameter!')

    last_repo_id = server.get_last_repo_id(pbranch)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

    base_query = "SELECT pkgcs{in_} FROM File WHERE pkgcs IN " \
                 "(SELECT pkgcs FROM Assigment WHERE uuid IN {ids}) " \
                 "AND {param}".format(in_='{}', ids=last_repo_id, param='{}')

    if file:
        query = "filename LIKE '{}'".format(file)
    else:
        query = "filemd5 = '{}'".format(md5)

    pkgcs_query = base_query.format('', query)

    server.request_line = base_query.format(', filename', query)

    status, response = server.send_request()
    if status is False:
        return response

    ids_filename_dict = utils.tuple_to_dict(response)

    server.request_line = \
        "SELECT pkgcs, name, version, release, disttag, arch FROM Package " \
        "WHERE sourcepackage = 0 AND pkgcs IN ({})".format(pkgcs_query)

    status, response = server.send_request()
    if status is False:
        return response

    output_values = []
    for package in response:
        package += (ids_filename_dict[package[0]], pbranch)
        output_values.append(package)

    output_params = ['pkgcs', 'name', 'version', 'release',
                     'disttag', 'arch', 'files', 'branch']

    return utils.convert_to_json(output_params, tuple(output_values))


@app.route('/package_files')
@func_time(logger)
def package_files():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1', 's')
    if sha1 is False:
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = "SELECT filename FROM File WHERE pkgcs = '{sha1}'" \
                          "".format(sha1=sha1)

    # logger.debug(server.request_line)

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
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': True,
        },
        'version': {
            'rname': 'version',
            'type': 's',
            'action': action,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    pbranch = server.get_one_value('branch', 's')

    last_repo_id = server.get_last_repo_id(pbranch)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

    server.request_line = \
        "SELECT DISTINCT sourcerpm FROM Package WHERE pkgcs IN " \
        "(SELECT pkgcs FROM Assigment WHERE uuid IN {}) AND pkgcs IN " \
        "(SELECT pkgcs FROM Depends WHERE {})" \
        "".format(last_repo_id, " ".join(params_values))

    status, response = server.send_request()
    if status is False:
        return response

    source_package_fullname = []
    for fullname in response:
        if fullname[0]:
            reg = re.compile("(.*)-([0-9.]+)-(alt.*).src.rpm")
            source_package_fullname.append(re.findall(reg, fullname[0])[0])

    if not source_package_fullname:
        return json.dumps({})

    server.request_line = \
        "SELECT {p_params} FROM Package WHERE " \
        "(name, version, release) IN {nvr} AND sourcepackage = 1 " \
        "AND pkgcs IN (SELECT pkgcs FROM Assigment WHERE uuid IN {uuids})" \
        "".format(
            p_params=", ".join(server.package_params),
            nvr=tuple(source_package_fullname),
            uuids=last_repo_id
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

    input_params = {
        'branch': {
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': True,
        },
    }

    params_values = server.get_values_by_params(input_params, True)
    if params_values is False:
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

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

    pbranch = params_values['branch']
    arch = server.get_one_value('arch', 's')

    if pname:
        status, pversion = server.get_last_version(pname, pbranch)
        if status is False:
            return pversion

    last_repo_id = server.get_last_repo_id(pbranch)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

    # allowed packages sha1
    allowed_pkgcs = "SELECT pkgcs FROM Assigment WHERE uuid IN {}" \
                    "".format(last_repo_id)

    if pname:
        server.request_line = \
            "SELECT T1.name, T1.version, T2.archs FROM " \
            "(SELECT concat(name, '-', version, '-', release, '.src.rpm') " \
            "AS sourcerpm, name, version FROM Package WHERE sourcepackage = 1 " \
            "AND pkgcs IN (SELECT DISTINCT pkgcs FROM Depends WHERE name IN " \
            "(SELECT DISTINCT name FROM Package WHERE sourcerpm LIKE " \
            "'{name}-{vers}-%.src.rpm' AND pkgcs IN ({ids})) AND " \
            "(version LIKE '{vers}-%' OR version = '') AND pkgcs IN " \
            "({ids}))) T1, (SELECT sourcerpm, groupUniqArray(arch) AS archs " \
            "FROM Package WHERE sourcerpm IN (SELECT " \
            "concat(name, '-', version, '-', release, '.src.rpm') FROM Package " \
            "WHERE sourcepackage = 1 AND pkgcs IN (SELECT DISTINCT pkgcs FROM " \
            "Depends WHERE name IN (SELECT DISTINCT name FROM Package WHERE " \
            "sourcerpm LIKE '{name}-{vers}-%.src.rpm' AND pkgcs IN ({ids})) AND " \
            "(version LIKE '{vers}-%' OR version = '') AND pkgcs IN ({ids}))) " \
            "GROUP BY (sourcerpm)) T2 WHERE T2.sourcerpm = T1.sourcerpm".format(
                name=pname, vers=pversion, ids=allowed_pkgcs
            )
    else:
        # binary packages in task
        server.request_line = "SELECT pkgs FROM Tasks WHERE id = {}".format(task_id)

        status, response = server.send_request()
        if status is False:
            return response

        binary_packages = ()
        for tp_package in response:
            for package in tp_package[0]:
                binary_packages += (package,)

        binary_packages = utils.normalize_tuple(binary_packages)

        server.request_line = \
            "SELECT DISTINCT concat(name, '-', 'version', '-', release) " \
            "FROM Package WHERE pkgcs IN (SELECT pkgcs FROM Depends " \
            "WHERE name IN (SELECT name FROM Package WHERE pkgcs IN {bp}))" \
            "".format(bp=binary_packages)

        if arch:
            server.request_line += " AND arch = '{}'".format(arch)

    status, response = server.send_request()
    if status is False:
        return response

    for elem in response:
        add = elem + (pbranch,)
        if task_id and arch:
            add += (arch,)

        response[response.index(elem)] = add

    if pname:
        js_keys = ['name', 'version', 'archs', 'branch']
    else:
        js_keys = ['name', 'branch']
        if arch:
            js_keys.append('arch')

    return utils.convert_to_json(js_keys, response)


@app.errorhandler(404)
def page_404(e):
    return utils.json_str_error("Page not found!")


server = LogicServer()
server.init()

if __name__ == '__main__':
    app.run()
