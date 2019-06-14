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
        self.package_params = [
            'sha1header', 'subtask', 'name', 'version', 'release', 'epoch',
            'serial_', 'buildtime', 'buildhost', 'size', 'archivesize',
            'rpmversion', 'cookie', 'sourcepackage', 'disttag', 'sourcerpm',
            'filename', 'sha1srcheader'
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

        config = utils.read_config(paths.DB_CONFIG_FILE)
        section = 'DBParams'
        self.db_connection = {
            'dbname': config.get(section, 'DataBaseName'),
            'user': config.get(section, 'User'),
            'password': config.get(section, 'Password'),
            'host': config.get(section, 'Host'),
        }

    def _get_connection(self):
        return DBConnection(dbconn_struct=self.db_connection)

    @func_time(logger)
    def send_request(self):
        db_connection = self._get_connection()
        db_connection.db_query = self.request_line

        return db_connection.send_request()

    # select date one day earlier than current
    def get_last_date(self):
        current_date = "SELECT datetime_release::date FROM AssigmentName " \
                       "{} ORDER BY datetime_release::date DESC LIMIT 1"

        self.request_line = current_date.format(
            "WHERE datetime_release::date < (SELECT datetime_release::date "
            "FROM AssigmentName ORDER BY datetime_release::date DESC LIMIT 1)"
        )

        logger.debug(self.request_line)

        status, response = self.send_request()
        if status is False:
            return response

        if len(response) == 0:
            self.request_line = current_date.format(None)

            logger.debug(self.request_line)

            status, response = self.send_request()
            if status is False:
                return response

        return response[0][0]

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

        return value

    def check_input_params(self, binary_only=False):
        # check arch
        parch = self.get_one_value('arch', 's')
        if parch and parch not in ['aarch64', 'armh', 'i586',
                                   'noarch', 'x86_64', 'x86_64-i586']:
            return utils.json_str_error('Unknown arch of package!')

        # check branch
        pbranch = self.get_one_value('branch', 's')
        if pbranch and pbranch not in ['p7', 'p8', 'Sisyphus']:
            return utils.json_str_error('Unknown branch!')

        # check package params
        pname = self.get_one_value('name', 's')
        if pname:
            default_req = "SELECT p.name FROM Package p"
            args = "p.name = '{}'".format(pname)

            pversion = self.get_one_value('version', 's')
            if pversion:
                args = "{} AND p.version = '{}'".format(args, pversion)

            if pbranch:
                extra_params = \
                    "INNER JOIN Assigment a ON a.package_id = p.id " \
                    "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id"

                default_req = "{} {}".format(default_req, extra_params)
                args = "{} AND an.name = '{}'".format(args, pbranch)

            if binary_only:
                args = "{} AND sourcepackage IS FALSE".format(args)

            self.request_line = "{} WHERE {}".format(default_req, args)

            status, response = self.send_request()
            if status is False:
                return response

            if len(response) == 0:
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
                                arg = "{} IS TRUE"
                            elif value.lower() == 'false':
                                arg = "{} IS FALSE"
                        if type_ == 't':
                            arg = "{} = {}"

                    if value:
                        arg = arg.format(rname, value)
                        if len(params_list) > 0:
                            arg = "AND {}".format(arg)

                        params_list.append(arg)

        if len(params_list) == 0:
            return False

        return params_list

    @staticmethod
    def url_logging():
        logger.info(unquote(request.url))

    def get_last_version(self, name, branch):
        self.request_line = \
            "SELECT MAX(p.version) FROM Package p " \
            "INNER JOIN Assigment a ON a.package_id = p.id " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}' " \
            "AND an.datetime_release::date = '{dt}'" \
            "".format(name=name, branch=branch, dt=self.get_last_date())

        logger.debug(self.request_line)

        status, response = self.send_request()
        if status is False:
            return False, response

        return True, response[0][0]


@app.route('/package_info')
@func_time(logger)
def package_info():
    return utils.json_str_error(
        "At the moment, the request is being adapted to the new database structure."
    )

    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime', 'i')
    if buildtime_value and buildtime_value not in ['>', '<', '=']:
        buildtime_action = "{} = {}"

    date_value = server.get_one_value('date', 's')
    if date_value is None:
        date_value = "{} = '{}'".format('{}', server.get_last_date())
    else:
        date_value = None

    intput_params = {
        'name': {
            'rname': 'p.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'version': {
            'rname': 'p.version',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'release': {
            'rname': 'p.release',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'arch': {
            'rname': 'p.arch',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'disttag': {
            'rname': 'p.disttag',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'buildtime': {
            'rname': 'p.buildtime',
            'type': 'i',
            'action': buildtime_action,
            'notempty': False,
        },
        'sourcerpm': {
            'rname': 'p.sourcerpm',
            'type': 'b',
            'action': None,
            'notempty': False,
        },
        'branch': {
            'rname': 'an.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'date': {
            'rname': 'an.datetime_release::date',
            'type': 's',
            'action': date_value,
            'notempty': False,
        },
        'packager': {
            'rname': 'pr.name',
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
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id WHERE " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    json_retval = json.loads(utils.convert_to_json(
        server.add_extra_package_params(
            ['packager', 'branch', 'date', 'files',
             'requires', 'conflicts', 'obsoletes', 'provides']
        ), response))

    for elem in json_retval:
        package_sha1 = json_retval[elem]['sha1header']

        # files
        server.request_line = \
            "SELECT filename FROM File WHERE package_sha1 = '{}'" \
            "".format(package_sha1)

        logger.debug(server.request_line)

        status, response = server.send_request()
        if status is False:
            return response

        json_retval[elem]['files'] = utils.join_tuples(response)

        # package properties
        prop_list = [('Require', 'requires'), ('Conflict', 'conflicts'),
                     ('Obsolete', 'obsoletes'), ('Provide', 'provides')]

        for prop in prop_list:
            server.request_line = "SELECT name, version FROM {table} " \
                                  "WHERE package_sha1 = '{sha1}'" \
                                  "".format(table=prop[0], sha1=package_sha1)

            logger.debug(server.request_line)

            status, response = server.send_request()
            if status is False:
                return response

            json_retval[elem][prop[1]] = utils.join_tuples(response)

    return json.dumps(json_retval)


@app.route('/misconflict_packages')
@func_time(logger)
def conflict_packages():
    return utils.json_str_error(
        "At the moment, the request is being adapted to the new database structure."
    )

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

    repo_date = server.get_last_date()

    default_query = \
        "SELECT DISTINCT {what} FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id {join} " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "WHERE an.name = '{branch}' AND an.datetime_release = '{date}' " \
        "AND {where}".format(what='{what}', branch=pbranch, date=repo_date,
                             where='{where}', join='{join}')

    # input package archs
    server.request_line = default_query.format(
        what="p.arch",
        where="p.name = '{name}' AND p.version = '{vers}' "
              "AND p.sourcerpm IS NOT NULL"
              "".format(name=pname, vers=pversion),
        join=''
    )

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    with_archs = ''

    archs = tuple([arch[0] for arch in response])
    if len(archs) == 0:
        message = "Architectures for {} not found in database.".format(pname)
        return utils.json_str_error(message)

    if len(archs) == 1:
        archs += ('',)
    if archs[0] != 'noarch':
        with_archs = "AND p.arch IN {}".format(archs)

    # input package files
    server.request_line = default_query.format(
        what="f.filename",
        where="p.name = '{name}' AND p.version = '{vers}' "
              "AND p.sourcerpm IS NOT NULL AND f.fileclass != 'directory'"
              "".format(name=pname, vers=pversion),
        join=''
    )

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    input_package_files = tuple([file[0] for file in response])
    if len(input_package_files) == 0:
        return
    if len(input_package_files) == 1:
        input_package_files += ('',)

    # packages with ident files
    server.request_line = default_query.format(
        what="p.name, p.version, p.arch",
        where="p.name != '{name}' {with_archs} AND p.sourcerpm IS NOT NULL AND "
              "f.filename IN {files}"
              "".format(name=pname, with_archs=with_archs,
                        files=input_package_files),
        join=''
    )

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    packages_with_ident_files = [
        (package[0], package[1], package[2]) for package in response
    ]

    # input package conflicts
    server.request_line = default_query.format(
        what="c.name, c.version",
        where="p.name = '{name}' AND p.version = '{vers}' "
              "AND p.sourcerpm IS NOT NULL"
              "".format(name=pname, vers=pversion),
        join="INNER JOIN Conflict c ON c.package_sha1 = p.sha1header"
    )

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    input_package_conflicts = [
        (conflict[0], conflict[1].split('-')[0]) for conflict in response
    ]

    ident_package_without_conflicts = []
    for ident_package in packages_with_ident_files:
        # ident package conflicts
        server.request_line = default_query.format(
            what="c.name, c.version",
            where="(p.name, p.version, p.arch) = {ident_package} "
                  "AND p.sourcerpm IS NOT NULL"
                  "".format(ident_package=ident_package),
            join="INNER JOIN Conflict c ON c.package_sha1 = p.sha1header"
        )

        logger.debug(server.request_line)

        status, response = server.send_request()
        if status is False:
            return response

        ident_package_conflicts = [
            (conflict[0], conflict[1].split('-')[0]) for conflict in response
        ]

        if (pname, pversion) not in ident_package_conflicts \
                and (pname, '') not in ident_package_conflicts:
            if (ident_package[0], ident_package[1]) not in input_package_conflicts \
                    and (ident_package[0], '') not in input_package_conflicts:

                server.request_line = default_query.format(
                    what="f.filename",
                    where="(p.name, p.version, p.arch) = {ident_package} "
                          "AND p.sourcerpm IS NOT NULL "
                          "AND f.fileclass != 'directory'"
                          "".format(ident_package=ident_package),
                    join=''
                )

                logger.debug(server.request_line)

                status, response = server.send_request()
                if status is False:
                    return response

                ident_package_files = tuple([file[0] for file in response])

                intersection_files = []
                for el in input_package_files:
                    if el in ident_package_files:
                        intersection_files.append(el)

                ident_package += (intersection_files,)

                ident_package_without_conflicts.append(ident_package)

    misconflicts = []
    for name, version, _, files in ident_package_without_conflicts:
        archs = [package[2] for package in ident_package_without_conflicts
                 if (package[0], package[1]) == (name, version)]

        result_tuple = (name, version, archs, files)

        if result_tuple not in misconflicts:
            misconflicts.append(result_tuple)

    return utils.convert_to_json(['name', 'version', 'archs', 'files'],
                                 misconflicts)


@app.route('/package_by_file')
@func_time(logger)
def package_by_file():
    return utils.json_str_error(
        "At the moment, the request is being adapted to the new database structure."
    )

    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    file = server.get_one_value('file', 's')
    md5 = server.get_one_value('md5', 's')

    mask = re.findall(re.compile("mask='(.*)'"), unquote(request.url))
    if len(mask) > 0:
        mask = "{} LIKE '{}'".format('{}', mask[0])
    else:
        mask = None

    if len([param for param in [file, md5, mask] if param]) != 1:
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    input_params = {
        'file': {
            'rname': 'f.filename',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'branch': {
            'rname': 'an.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'md5': {
            'rname': 'f.filemd5',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'mask': {
            'rname': 'f.filename',
            'type': 's',
            'action': mask,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = \
        "SELECT DISTINCT p.sha1header, p.name, p.version, p.release, " \
        "p.arch, p.disttag, f.filename, an.name FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE an.datetime_release::date = '{date}' AND {args}" \
        "".format(args=" ".join(params_values),
                  date=server.get_last_date())

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    return utils.convert_to_json(
        ['sha1header', 'name', 'version', 'release', 'arch', 'disttag',
         'file', 'branch'], response
    )


@app.route('/package_files')
@func_time(logger)
def package_files():
    return utils.json_str_error(
        "At the moment, the request is being adapted to the new database structure."
    )

    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1', 's')
    if sha1 is False:
        message = 'Error in request arguments.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = \
        "SELECT DISTINCT f.filename FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "WHERE p.sourcerpm IS NOT NULL " \
        "AND p.sha1header = '{sha1}'".format(sha1=sha1)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    if len(response) == 0:
        return utils.json_str_error(
            "Files not found by sha1 '{}'".format(sha1)
        )

    js = {
        'sha1': sha1,
        'files': utils.join_tuples(response),
    }

    return json.dumps(js)


@app.route('/dependent_packages')
@func_time(logger)
def dependent_packages():
    server.url_logging()

    check_params = server.check_input_params(binary_only=True)
    if check_params is not True:
        return check_params

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
            'action': "{} LIKE '{}%'",
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

    server.request_line = \
        "SELECT DISTINCT p.sourcerpm FROM Package p " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Require r ON r.package_id = p.id " \
        "WHERE an.datetime_release::date = '{date}' " \
        "AND ".format(date=server.get_last_date()) + " ".join(params_values)

    status, response = server.send_request()
    if status is False:
        return response

    source_package_fullname = []
    for fullname in response:
        if fullname[0]:
            reg = re.compile("(.*)-([0-9.]+)-(alt.*).src.rpm")
            source_package_fullname.append(re.findall(reg, fullname[0])[0])

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
        "AND an.datetime_release::date = '{date}' {branch}" \
        "".format(
            ", p.".join(server.package_params),
            ", pi.".join(server.packageinfo_params),
            nvr=tuple(source_package_fullname),
            date=server.get_last_date(),
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

    # binary packages of input package
    server.request_line = \
        "SELECT DISTINCT p.name, ar.name FROM Package p " \
        "INNER JOIN Assigment a ON a.package_id = p.id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Arch ar ON ar.id = p.arch_id " \
        "WHERE an.name = '{branch}' AND an.datetime_release::date = '{date}' " \
        "AND p.sourcerpm LIKE '{name}-{version}-%'" \
        "".format(name=pname, version=pversion, branch=pbranch,
                  date=server.get_last_date())

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    if len(response) == 0:
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
        "AND an.datetime_release::date = '{date}' AND r.name IN {bp} " \
        "AND (r.version = '' OR r.version LIKE '{vers}-%')" \
        "".format(branch=pbranch, date=server.get_last_date(),
                  bp=binary_packages, vers=pversion)

    # logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    if len(response) == 0:
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
        "SELECT DISTINCT p.name, ar.name, p.sourcerpm FROM Package p " \
        "INNER JOIN Arch ar ON ar.id = p.arch_id WHERE p.sourcerpm IN {}" \
        "".format(source_names_tuple)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    binary_packages_with_arch = response

    # FIXME needed optimization
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
                broken_archs = ()

                for arch in source[1]:
                    if arch == 'noarch' or arch in input_package_archs_list:
                        broken_archs += (arch,)

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
