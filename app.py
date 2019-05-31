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
            'sha1header', 'subtask', 'name', 'arch', 'version', 'release',
            'epoch', 'serial_', 'summary', 'description', 'changelog',
            'buildtime', 'buildhost', 'size', 'distribution', 'vendor', 'gif',
            'xpm', 'license', 'group_', 'source', 'patch', 'url', 'os',
            'prein', 'postin', 'preun', 'postun', 'icon', 'archivesize',
            'rpmversion', 'preinprog', 'postinprog', 'preunprog', 'postunprog',
            'buildarchs', 'verifyscript', 'verifyscriptprog', 'cookie',
            'prefixes', 'instprefixes', 'sourcepackage', 'optflags', 'disturl',
            'payloadformat', 'payloadcompressor', 'payloadflags', 'platform',
            'disttag', 'sourcerpm', 'filename',
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
        self.db = DBConnection(dbconn_struct=self.db_connection)
        self.last_date = self._get_last_date_record()

    @func_time(logger)
    def send_request(self):
        self.db.db_query = self.request_line
        return self.db.send_request()

    # select date one day earlier than current
    def _get_last_date_record(self):
        current_date = "SELECT datetime_release FROM AssigmentName " \
                       "ORDER BY id DESC LIMIT 1"

        self.request_line = \
            "SELECT datetime_release FROM AssigmentName " \
            "WHERE datetime_release NOT IN ({}) ORDER BY id DESC LIMIT 1" \
            "".format(current_date)

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
                    "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
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
            "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}' " \
            "AND an.datetime_release = '{dt}'" \
            "".format(name=name, branch=branch, dt=self.last_date)

        logger.debug(self.request_line)

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

    date_value = server.get_one_value('date', 's')
    if date_value is None:
        date_value = "{} = '{}'".format('{}', server.last_date)
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
            'rname': 'p.sourcepackage',
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
            'rname': 'an.datetime_release',
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

    # TODO make user files input, maybe later..
    # files
    server.request_line = \
        "SELECT DISTINCT f.filename, p.arch, f.filemd5 FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE p.name = '{name}' AND an.name = '{branch}' " \
        "AND p.version = '{version}'" \
        "".format(name=pname, branch=pbranch, version=pversion)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    pfiles = response

    if len(pfiles) == 0:
        return '{}'

    md5files = tuple([file[2] for file in pfiles])
    if len(md5files) < 2:
        md5files += ('',)

    pfiles = tuple([(file[0], file[1]) for file in pfiles])
    if len(pfiles) < 2:
        pfiles += (('', ''),)

    # packages with ident files
    server.request_line = \
        "SELECT DISTINCT p.name, p.version, p.release, p.arch, p.sha1header " \
        "FROM Package p INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE p.sourcepackage IS FALSE AND p.name != '{name}' " \
        "AND an.name = '{branch}' AND an.datetime_release = '{date}' " \
        "AND f.filemd5 NOT IN {filemd5} AND (f.filename, p.arch) IN {files} " \
        "AND CAST(f.filemode AS VARCHAR) NOT LIKE '1%'" \
        "".format(files=pfiles, filemd5=md5files, name=pname,
                  branch=pbranch, date=server.last_date)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    packages_with_ident_files = [(el[0], "{}-{}".format(el[1], el[2]), el[3])
                                 for el in response]

    # conflicts input package
    server.request_line = \
        "SELECT DISTINCT c.name, c.version, p.arch FROM Package p " \
        "INNER JOIN Conflict c ON c.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE p.name = '{name}' AND p.version = '{version}' " \
        "AND an.name = '{branch}'" \
        "".format(name=pname, version=pversion, branch=pbranch)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    packages_without_conflict = []

    for package in packages_with_ident_files:
        if package[2] == 'noarch':
            for conflict in response:
                conflict = (conflict[0], conflict[1])

                if (package[0], package[1]) != conflict and \
                        (package[0], '') != conflict:
                    packages_without_conflict.append(package)
        else:
            if package not in response and \
                    (package[0], '', package[2]) not in response:
                packages_without_conflict.append(package)

    result_packages = []

    for package in packages_without_conflict:
        package = (package[0], package[1].split("-")[0],
                   package[1].split("-")[1], package[2])

        # conflicts found packages
        server.request_line = \
            "SELECT DISTINCT c.name, c.version, p.arch FROM Package p " \
            "INNER JOIN Conflict c ON c.package_sha1 = p.sha1header " \
            "INNER JOIN Assigment a ON a.package_sha1 = sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE (p.name, p.version, p.release, p.arch) = {nvr} " \
            "AND an.name = '{branch}'" \
            "".format(nvr=package, branch=pbranch)

        logger.debug(server.request_line)

        status, response = server.send_request()
        if status is False:
            return response

        ind = False
        for conflict in response:
            if (pname, pversion) == (conflict[0], conflict[1]) or \
                    (pname, '') == (conflict[0], conflict[1]):
                ind = True
                break

        # conflict files
        if ind is False:
            server.request_line = \
                "SELECT DISTINCT f.filename FROM Package p " \
                "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
                "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
                "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
                "WHERE (p.name, p.version, p.release, p.arch) = {nvr} " \
                "AND an.name = '{branch}' AND (f.filename, p.arch) IN {files}" \
                "".format(nvr=package, branch=pbranch, files=pfiles)

            logger.debug(server.request_line)

            status, response = server.send_request()
            if status is False:
                return response

            files = utils.join_tuples(response)

            result_packages.append((package[0],
                                    "{}-{}".format(package[1], package[2]),
                                    package[3], files))

    return utils.convert_to_json(['name', 'version', 'arch', 'files'],
                                 result_packages)


@app.route('/package_by_file')
@func_time(logger)
def package_by_file():
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
        "WHERE an.datetime_release = '{date}' AND {args}" \
        "".format(args=" ".join(params_values),
                  date=server.last_date)

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
        "WHERE p.sourcepackage IS FALSE " \
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

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    input_params = {
        'name': {
            'rname': 'r.name',
            'type': 's',
            'action': None,
            'notempty': False,
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
        'date': {
            'rname': 'an.datetime_release',
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
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Require r ON r.package_sha1 = p.sha1header " \
        "WHERE p.sourcepackage IS TRUE AND " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

    return utils.convert_to_json(server.add_extra_package_params(
        ['packager', 'branch', 'date']), response)


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
        "SELECT DISTINCT p.name, p.arch FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE an.name = '{branch}' AND an.datetime_release = '{dt}' " \
        "AND p.sourcerpm LIKE '{name}-{version}-%'" \
        "".format(name=pname, version=pversion, branch=pbranch,
                  dt=server.last_date)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

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
        "INNER JOIN Require r ON r.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE p.sourcepackage IS TRUE AND an.name = '{branch}' " \
        "AND an.datetime_release = '{dt}' AND r.name IN {bp} " \
        "AND (r.version = '' OR r.version LIKE '{vers}-%')" \
        "".format(branch=pbranch, dt=server.last_date, bp=binary_packages,
                  vers=pversion)

    logger.debug(server.request_line)

    status, response = server.send_request()
    if status is False:
        return response

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
        "SELECT DISTINCT p.name, p.arch, p.sourcerpm FROM Package p " \
        "WHERE p.sourcerpm IN {}".format(source_names_tuple)

    logger.debug(server.request_line)

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
