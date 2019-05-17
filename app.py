from flask import Flask, request, json
from db_connection import DBConnection
from utils import get_logger, read_config, json_str_error
from paths import paths

app = Flask(__name__)
logger = get_logger(__name__)


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

        config = read_config(paths.DB_CONFIG_FILE)
        section = 'DBParams'
        db_connection = {
            'dbname': config.get(section, 'DataBaseName'),
            'user': config.get(section, 'User'),
            'password': config.get(section, 'Password'),
            'host': config.get(section, 'Host'),
        }
        self.db = DBConnection(dbconn_struct=db_connection)

    def send_request(self):
        self.db.db_query = self.request_line
        return self.db.send_request()

    @staticmethod
    def convert_to_json(keys, values):
        js = {}

        for i in range(len(values)):
            js[i] = dict([(keys[j], values[i][j])
                          for j in range(len(values[i]))])

        return json.dumps(js)

    def get_last_date_record(self):
        self.request_line = "SELECT datetime_release FROM AssigmentName " \
                            "ORDER BY id DESC LIMIT 1"

        status, response = self.send_request()
        if status is False:
            return response

        return response[0][0]

    def add_extra_package_params(self, extra_package_params):
        return self.package_params + extra_package_params

    @staticmethod
    def get_one_value(param):
        value = request.args.get(param)
        return value

    def check_input_params(self):
        # check arch
        parch = self.get_one_value('arch')
        if parch and parch not in ['aarch64', 'armh', 'i586',
                                   'noarch', 'x86_64', 'x86_64-i586']:
            return json_str_error('Unknown arch of package!')

        # check branch
        pbranch = self.get_one_value('branch')
        if pbranch and pbranch not in ['p7', 'p8', 'Sisyphus']:
            return json_str_error('Unknown branch!')

        # check package params
        pname = self.get_one_value('name')
        if pname:
            default_req = "SELECT p.name FROM Package p"
            args = "p.name = '{}'".format(pname)

            pversion = self.get_one_value('version')
            if pversion:
                args = "{} AND p.version = '{}'".format(args, pversion)

            if pbranch:
                extra_params = \
                    "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
                    "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id"

                default_req = "{} {}".format(default_req, extra_params)
                args = "{} AND an.name = '{}'".format(args, pbranch)

            self.request_line = "{} WHERE {}".format(default_req, args)

            status, response = self.send_request()
            if status is False:
                return response

            if len(response) == 0:
                message = "Package with input parameters is not in the " \
                          "repository."
                logger.info(message)
                return json_str_error(message)

        return True

    def get_values_by_params(self, input_params):
        params_list = []

        for param in input_params:
            value = self.get_one_value(param)

            notempty = input_params[param].get('notempty')
            if not value and notempty is True:
                return False

            action = input_params[param].get('action')

            if value or action:
                arg = "{} = '{}'"
                rname = input_params[param].get('rname')
                type_ = input_params[param].get('type')

                if action:
                    arg = action
                else:
                    if type_ == 'i':
                        if type(value) is not int:
                            return False
                        arg = "{} {}"
                    if type_ == 'b':
                        if value.lower() == 'true':
                            arg = "{} IS NULL"
                        elif value.lower() == 'false':
                            arg = "{} IS NOT NULL"
                        else:
                            return False
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
    def join_tuples(tuple_list):
        return tuple([tuple_[0] for tuple_ in tuple_list])


@app.route('/package_info')
def package_info():
    logger.info(request.url)

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime')
    if buildtime_value and buildtime_value not in ['>', '<', '=']:
        buildtime_action = "{} = {}"

    date_value = server.get_one_value('date')
    if date_value is None:
        date_value = "{} = '{}'".format('{}', server.get_last_date_record())
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
        logger.info(message)
        return json_str_error(message)

    server.request_line = \
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id WHERE " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    status, response = server.send_request()
    if status is False:
        return response

    json_retval = json.loads(server.convert_to_json(
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

        status, response = server.send_request()
        if status is False:
            return response

        json_retval[elem]['files'] = server.join_tuples(response)

        # package properties
        prop_list = [('Require', 'requires'), ('Conflict', 'conflicts'),
                     ('Obsolete', 'obsoletes'), ('Provide', 'provides')]

        for prop in prop_list:
            server.request_line = "SELECT name, version FROM {table} " \
                                  "WHERE package_sha1 = '{sha1}'" \
                                  "".format(table=prop[0], sha1=package_sha1)

            status, response = server.send_request()
            if status is False:
                return response

            json_retval[elem][prop[1]] = server.join_tuples(response)

    return json.dumps(json_retval)


@app.route('/misconflict_packages')
def conflict_packages():
    logger.info(request.url)

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name')
    pbranch = server.get_one_value('branch')

    if not pname or not pbranch:
        message = 'Error in request arguments.'
        logger.info(message)
        return json_str_error(message)

    # version
    pversion = server.get_one_value('version')
    if not pversion:
        server.request_line = \
            "SELECT MAX(p.version) FROM Package p " \
            "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}'" \
            "".format(name=pname, branch=pbranch)

        status, response = server.send_request()
        if status is False:
            return response

        pversion = response[0][0]

    # files
    pfiles = server.get_one_value('files')
    if not pfiles:
        server.request_line = \
            "SELECT DISTINCT f.filename, p.arch, f.filemd5 FROM Package p " \
            "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
            "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}' " \
            "AND p.version = '{version}'" \
            "".format(name=pname, branch=pbranch, version=pversion)

        status, response = server.send_request()
        if status is False:
            return response

        pfiles = response

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
        "WHERE (f.filename, p.arch) IN {files} " \
        "AND f.filemd5 NOT IN {filemd5} " \
        "AND CAST(f.filemode AS VARCHAR) NOT LIKE '1%' " \
        "AND p.name != '{name}' AND p.sourcerpm IS NOT NULL " \
        "AND an.name = '{branch}' AND an.datetime_release = '{date}'" \
        "".format(files=pfiles, filemd5=md5files, name=pname,
                  branch=pbranch, date=server.get_last_date_record())

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

            status, response = server.send_request()
            if status is False:
                return response

            files = server.join_tuples(response)

            result_packages.append((package[0],
                                    "{}-{}".format(package[1], package[2]),
                                    package[3], files))

    return server.convert_to_json(['name', 'version', 'arch', 'files'],
                                  result_packages)


@app.route('/package_by_file')
def package_by_file():
    logger.info(request.url)

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    input_params = {
        'file': {
            'rname': 'f.filename',
            'type': 's',
            'action': None,
            'notempty': True,
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
        logger.info(message)
        return json_str_error(message)

    server.request_line = \
        "SELECT DISTINCT p.name, p.version, an.name FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE {args}".format(args=" ".join(params_values))

    status, response = server.send_request()
    if status is False:
        return response

    return server.convert_to_json(['name', 'version', 'branch'], response)


@app.route('/package_files')
def package_files():
    logger.info(request.url)

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1')

    server.request_line = \
        "SELECT DISTINCT f.filename FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "WHERE p.sourcerpm IS NOT NULL " \
        "AND p.sha1header = '{sha1}'".format(sha1=sha1)

    status, response = server.send_request()
    if status is False:
        return response

    js = {
        'sha1': sha1,
        'files': server.join_tuples(response),
    }

    return json.dumps(js)


@app.route('/dependent_packages')
def dependent_packages():
    logger.info(request.url)

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
        logger.info(message)
        return json_str_error(message)

    server.request_line = \
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Require r ON r.package_sha1 = p.sha1header " \
        "WHERE sourcerpm IS NULL AND " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    status, response = server.send_request()
    if status is False:
        return response

    return server.convert_to_json(server.add_extra_package_params(
        ['packager', 'branch', 'date']), response)


@app.errorhandler(404)
def page_404(e):
    return json_str_error("Page not found!")


server = LogicServer()

if __name__ == '__main__':
    app.run()
