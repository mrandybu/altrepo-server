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
            'payloadflags', 'platform'
        ]
        self.packageinfo_params = [
            'summary', 'description', 'changelog', 'distribution', 'vendor',
            'gif', 'xpm', 'license', 'group_', 'source', 'patch', 'url',
            'os', 'prein', 'postin', 'preun', 'postun', 'icon', 'preinprog',
            'postinprog', 'preunprog', 'postunprog', 'buildarchs',
            'verifyscript', 'verifyscriptprog', 'prefixes', 'instprefixes',
            'optflags', 'disturl', 'payloadformat', 'payloadcompressor',
            'payloadflags', 'platform'
        ]
        self.request_line = request_line

        section = 'DBParams'
        self.db_connection = {
            'dbname': self._get_config(section, 'DataBaseName'),
            'user': self._get_config(section, 'User'),
            'password': self._get_config(section, 'Password'),
            'host': self._get_config(section, 'Host'),
        }
        self.clickhouse_host = self._get_config('ClickHouse', 'Host')

    @staticmethod
    def _get_config(section, field):
        config = utils.read_config(paths.DB_CONFIG_FILE)
        if config is False:
            raise Exception("Unable read config file.")

        try:
            return config.get(section, field)
        except:
            raise Exception("No needed section or field in config file.")

    def _get_connection(self):
        return DBConnection(dbconn_struct=self.db_connection,
                            clickhouse_host=self.clickhouse_host)

    @func_time(logger)
    def send_request(self, clickhouse=False):
        db_connection = self._get_connection()
        db_connection.db_query = self.request_line

        return db_connection.send_request(clickhouse)

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

            status, response = self.send_request(clickhouse=True)
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
            default_req = "SELECT name FROM Package"
            args = "name = '{}'".format(pname)

            pversion = self.get_one_value('version', 's')
            if pversion:
                args = "{} AND version = '{}'".format(args, pversion)

            args = \
                "{} AND pkgcs IN (SELECT pkgcs FROM Assigment WHERE uuid IN {})" \
                "".format(args, self.get_last_repo_id(pbranch, date))

            if binary_only:
                args = "{} AND sourcepackage = 0".format(args)

            self.request_line = "{} WHERE {}".format(default_req, args)

            status, response = self.send_request(clickhouse=True)
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
            "SELECT p.version FROM Package p " \
            "INNER JOIN Assigment a ON a.package_id = p.id " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}' " \
            "AND an.id IN {b_id} ORDER BY p.buildtime DESC LIMIT 1" \
            "".format(
                name=name, branch=branch, b_id=self.get_last_repo_id(branch)
            )

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
        'name': {
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': True,
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

    server.request_line = \
        "SELECT {p_params} FROM Package WHERE pkgcs IN " \
        "(SELECT pkgcs FROM Assigment WHERE uuid IN {repo_ids}) AND {p_values}" \
        "".format(
            p_params=", ".join(server.package_params),
            repo_ids=last_repo_id,
            p_values=" ".join(params_values)
        )

    # logger.debug(server.request_line)

    status, response = server.send_request(clickhouse=True)
    if status is False:
        return response

    json_retval = json.loads(
        utils.convert_to_json(server.package_params, response)
    )

    for elem in json_retval:
        package_sha1 = json_retval[elem]['pkgcs']

        # files
        server.request_line = \
            "SELECT filename FROM File WHERE pkgcs = '{}'".format(package_sha1)

        # logger.debug(server.request_line)

        status, response = server.send_request(clickhouse=True)
        if status is False:
            return response

        json_retval[elem]['files'] = utils.join_tuples(response)

        # package properties
        prop_list = [('requires', 'require'), ('conflicts', 'conflict'),
                     ('obsoletes', 'obsolete'), ('provides', 'provide')]

        server.request_line = \
            "SELECT dptype, concat(name, ' ', version) FROM Depends " \
            "WHERE pkgcs = '{}'".format(package_sha1)

        status, response = server.send_request(clickhouse=True)
        if status is False:
            return response

        dict_types = {
            'require': [], 'conflict': [], 'obsolete': [], 'provide': [],
        }

        for type_ in response:
            for prop in prop_list:
                if type_[0] == prop[1]:
                    dict_types[prop[1]].append(type_[1])

        for prop in prop_list:
            json_retval[elem][prop[0]] = dict_types[prop[1]]

    return json.dumps(json_retval, sort_keys=False)


@app.route('/misconflict_packages')
@func_time(logger)
def conflict_packages():
    return utils.json_str_error("IN MODERNIZATION..:)")
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

    # version
    pversion = server.get_one_value('version', 's')
    if not pversion:
        status, pversion = server.get_last_version(pname, pbranch)
        if status is False:
            return pversion

    last_repo_id = server.get_last_repo_id(pbranch)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

    default_query = \
        "SELECT DISTINCT {what} FROM Package p " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "{join} WHERE an.id IN {b_id} AND p.sourcepackage IS FALSE AND " \
        "{where}".format(
            what='{what}', join='{join}', b_id=last_repo_id, where='{where}'
        )

    # archs of input package
    server.request_line = default_query.format(
        what="ar.value",
        where="p.name = '{name}' AND p.version = '{vers}'"
              "".format(name=pname, vers=pversion),
        join="INNER JOIN Arch ar ON ar.id = p.arch_id",
    )

    status, response = server.send_request()
    if status is False:
        return response

    with_archs = ''

    archs = tuple([arch[0] for arch in response])
    if not archs:
        message = "Architectures for {} not found in database.".format(pname)
        return utils.json_str_error(message)

    if len(archs) == 1:
        archs += ('',)
    if archs[0] != 'noarch':
        with_archs = "AND ar.value IN {}".format(archs)

    # input package files
    server.request_line = default_query.format(
        what="p.id, p.buildtime",
        where="p.name = '{name}' AND p.version = '{vers}' "
              "ORDER BY p.buildtime DESC LIMIT 1"
              "".format(name=pname, vers=pversion),
        join='',
    )

    status, response = server.send_request()
    if status is False:
        return response

    package_id = response[0][0]

    server.request_line = \
        "SELECT DISTINCT filename FROM File WHERE fileclass != 'directory' " \
        "AND package_id = {}".format(package_id)

    status, response = server.send_request(clickhouse=True)
    if status is False:
        return response

    input_package_files = tuple([file[0] for file in response])
    if not input_package_files:
        return utils.json_str_error("Package has no files.")
    if len(input_package_files) == 1:
        input_package_files += ('',)

    server.request_line = \
        "SELECT DISTINCT package_id, filename FROM File WHERE filename IN {}" \
        "".format(input_package_files)

    status, response = server.send_request(clickhouse=True)
    if status is False:
        return response

    id_filename_dict = utils.tuple_to_dict(response)

    ids = tuple(id_ for id_ in id_filename_dict.keys())
    if len(ids) == 1:
        ids += (-1,)

    # package with ident files
    server.request_line = default_query.format(
        what="p.id, p.name, p.version, ar.value",
        where="p.name != '{name}' {with_archs} "
              "AND p.id IN {ids}"
              "".format(name=pname, with_archs=with_archs, ids=ids),
        join="INNER JOIN Arch ar ON ar.id = p.arch_id"
    )

    status, response = server.send_request()
    if status is False:
        return response

    packages_with_ident_files = [
        (package[0], package[1], package[2], package[3]) for package in response
    ]

    # input package conflicts
    server.request_line = default_query.format(
        what="c.name, c.version",
        where="p.name = '{name}' AND p.version = '{vers}'"
              "".format(name=pname, vers=pversion),
        join="INNER JOIN Conflict c ON c.package_id = p.id",
    )

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    input_package_conflicts = [
        (conflict[0], conflict[1].split('-')[0]) for conflict in response
    ]

    ident_package_without_conflicts = []
    for ident_package in packages_with_ident_files:

        i_p = (ident_package[1], ident_package[2], ident_package[3])

        # ident package conflicts
        server.request_line = default_query.format(
            what="c.name, c.version",
            where="(p.name, p.version, ar.value) = {i_p} "
                  "".format(i_p=i_p),
            join="INNER JOIN Arch ar ON ar.id = p.arch_id "
                 "INNER JOIN Conflict c ON c.package_id = p.id",
        )

        # logger.debug(server.request_line)

        status, response = server.send_request()
        if status is False:
            return response

        ident_package_conflicts = [
            (conflict[0], conflict[1].split('-')[0]) for conflict in response
        ]

        if (pname, pversion) not in ident_package_conflicts \
                and (pname, '') not in ident_package_conflicts:
            if (ident_package[0], ident_package[1]) not in \
                    input_package_conflicts and (ident_package[0], '') \
                    not in input_package_conflicts:
                ident_package += (tuple(id_filename_dict[ident_package[0]]),)

                ident_package_without_conflicts.append(ident_package)

    misconflicts = []
    for _, name, version, _, files in ident_package_without_conflicts:
        archs = [package[3] for package in ident_package_without_conflicts
                 if (package[1], package[2]) == (name, version)]

        result_tuple = (name, version, archs, files)

        if result_tuple not in misconflicts:
            misconflicts.append(result_tuple)

    return utils.convert_to_json(['name', 'version', 'archs', 'files'],
                                 misconflicts)


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

    base_query = "SELECT pkgcs, filename FROM File WHERE pkgcs IN " \
                 "(SELECT pkgcs FROM Assigment WHERE uuid IN {}) AND {}" \
                 "".format(last_repo_id, '{}')

    if file:
        query = "filename LIKE '{}'".format(file)
    else:
        query = "filemd5 = '{}'".format(md5)

    server.request_line = base_query.format(query)

    status, response = server.send_request(clickhouse=True)
    if status is False:
        return response

    ids_filename_dict = utils.tuple_to_dict(response)

    ids = utils.normalize_tuple(utils.join_tuples(response))

    server.request_line = \
        "SELECT pkgcs, name, version, release, disttag, arch FROM Package " \
        "WHERE sourcepackage = 0 AND pkgcs IN {}".format(ids)

    status, response = server.send_request(clickhouse=True)
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

    status, response = server.send_request(clickhouse=True)
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
    return utils.json_str_error("IN MODERNIZATION..:)")
    server.url_logging()

    check_params = server.check_input_params(binary_only=True)
    if check_params is not True:
        return check_params

    pversion = server.get_one_value('version', 's')
    if pversion:
        action = "{} LIKE '{}%'"
    else:
        action = None

    input_params = {
        'name': {
            'rname': 'r.name',
            'type': 's',
            'action': None,
            'notempty': True,
        },
        'version': {
            'rname': 'r.version',
            'type': 's',
            'action': action,
            'notempty': False,
        },
        'branch': {
            'rname': 'an.name',
            'type': 's',
            'action': None,
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
        "SELECT DISTINCT p.sourcerpm FROM Package p " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Require r ON r.package_id = p.id " \
        "WHERE an.id IN {b_id} AND ".format(
            b_id=last_repo_id) + " ".join(params_values)

    status, response = server.send_request()
    if status is False:
        return response

    source_package_fullname = []
    for fullname in response:
        if fullname[0]:
            reg = re.compile("(.*)-([0-9.]+)-(alt.*).src.rpm")
            source_package_fullname.append(re.findall(reg, fullname[0])[0])

    if not source_package_fullname:
        return json.dumps('{}')

    pbranch = server.get_one_value('branch', 's')
    if pbranch:
        pbranch = "AND an.name = '{}'".format(pbranch)
    else:
        pbranch = ''

    server.request_line = \
        "SELECT p.{}, pi.{}, pr.name, an.name, an.datetime_release::date " \
        "FROM Package p INNER JOIN PackageInfo pi ON pi.package_id = p.id " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "WHERE (p.name, p.version, p.release) IN {nvr} " \
        "AND p.sourcepackage IS TRUE " \
        "AND an.id IN {b_id} {branch}" \
        "".format(
            ", p.".join(server.package_params),
            ", pi.".join(server.packageinfo_params),
            nvr=tuple(source_package_fullname),
            b_id=last_repo_id,
            branch=pbranch,
        )

    status, response = server.send_request()
    if status is False:
        return response

    return utils.convert_to_json(
        server.add_extra_package_params(
            server.packageinfo_params + ['packager', 'branch', 'date']
        ),
        response
    )


@app.route('/what_depends_src')
@func_time(logger)
def broken_build():
    return utils.json_str_error("IN MODERNIZATION..:)")
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    input_params = {
        'name': {
            'rname': 'r.name',
            'type': 's',
            'action': None,
            'notempty': True,
        },
        'branch': {
            'rname': 'an.name',
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

    pname = params_values['name']
    pbranch = params_values['branch']

    status, pversion = server.get_last_version(pname, pbranch)
    if status is False:
        return pversion

    last_repo_id = server.get_last_repo_id(pbranch)
    if not last_repo_id:
        message = 'No records of branch with current date.'
        return utils.json_str_error(message)

    # binary packages of input package
    server.request_line = \
        "SELECT DISTINCT p.name, ar.value FROM Package p " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Arch ar ON ar.id = p.arch_id " \
        "WHERE an.name = '{branch}' AND an.id IN {b_id} " \
        "AND p.sourcerpm LIKE '{name}-{version}-%'".format(
            name=pname, version=pversion, branch=pbranch, b_id=last_repo_id
        )

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    input_package_archs_list = list(
        set([package[1] for package in response])
    )

    binary_packages = tuple([package[0] for package in response])
    if len(binary_packages) < 2:
        binary_packages += ('',)

    # packages with require on binary
    server.request_line = \
        "SELECT DISTINCT p.sha1header, p.name, p.version, " \
        "p.release, an.name FROM Package p " \
        "INNER JOIN Require r ON r.package_id = p.id " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE p.sourcepackage IS TRUE AND an.name = '{branch}' " \
        "AND an.id IN {b_id} AND r.name IN {bp} " \
        "AND (r.version = '' OR r.version LIKE '{vers}-%')".format(
            branch=pbranch, b_id=last_repo_id,
            bp=binary_packages, vers=pversion
        )

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    req_src_packages = response

    # source package name
    source_names_tuple = ()
    for package in req_src_packages:
        source_name = ("{}-{}-{}.src.rpm".format(
            package[1], package[2], package[3]),
        )
        req_src_packages[req_src_packages.index(package)] += source_name
        source_names_tuple += source_name

    if len(source_names_tuple) < 2:
        source_names_tuple += ('',)

    # binary package with req on input
    server.request_line = \
        "SELECT DISTINCT p.name, ar.value, p.sourcerpm FROM Package p " \
        "INNER JOIN Arch ar ON ar.id = p.arch_id WHERE p.sourcerpm IN {}" \
        "".format(source_names_tuple)

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    binary_packages_with_arch = response

    # add archs to binary packages
    source_name_archs_list = []
    for package in binary_packages_with_arch:
        archs = [bp[1] for bp in binary_packages_with_arch
                 if bp[2] == package[2]]

        source_name_archs = (package[2], set(archs))
        if source_name_archs not in source_name_archs_list:
            source_name_archs_list.append(source_name_archs)

    # add archs to source packages
    sources_with_archs = []
    for package in req_src_packages:
        mod_package = (package[1], package[2], package[4])

        for source in source_name_archs_list:
            if source[0] == package[5]:
                broken_archs = []

                for arch in source[1]:
                    if arch == 'noarch' or arch in input_package_archs_list:
                        broken_archs.append(arch)

                if 'noarch' in broken_archs and len(broken_archs) > 1:
                    broken_archs.remove('noarch')

                mod_package += (broken_archs,)

        sources_with_archs.append(mod_package)

    return utils.convert_to_json(
        ['name', 'version', 'branch', 'archs'], sources_with_archs
    )


@app.errorhandler(404)
def page_404(e):
    return utils.json_str_error("Page not found!")


server = LogicServer()

if __name__ == '__main__':
    app.run()
