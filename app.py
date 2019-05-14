from flask import Flask, request, json
from db_request import DBRequest

app = Flask(__name__)


class LogicServer:
    _db_connection = {
        'dbname': 'alter_altrepo',
        'user': 'underwit',
        'password': '1',
        'host': '10.88.13.7',
    }

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

    def send_request(self):
        db = DBRequest()

        conn = db.get_connection(self._db_connection)
        if conn is False:
            return False

        result = db.send_request(conn, self.request_line)
        if result is False:
            return False

        db.close_connection(conn)

        return result

    @staticmethod
    def convert_to_json(keys, values):
        js = {}

        for i in range(len(values)):
            js[i] = dict([(keys[j], values[i][j])
                          for j in range(len(values[i]))])

        return json.dumps(js)

    def get_last_date_record(self):
        request_line_tmp = self.request_line
        self.request_line = "SELECT datetime_release FROM AssigmentName " \
                            "ORDER BY id DESC LIMIT 1"

        result = self.send_request()

        self.request_line = request_line_tmp

        if result is not False:
            return result[0][0]

    def add_extra_package_params(self, extra_package_params):
        self.package_params += extra_package_params

    @staticmethod
    def get_one_value(param):
        value = request.args.get(param)
        return value

    def check_input_params(self):
        # check arch
        parch = self.get_one_value('arch')
        if parch and parch not in ['aarch64', 'armh', 'i586',
                                   'noarch', 'x86_64', 'x86_64-i586']:
            return 'Unknown arch of package!'

        # check branch
        pbranch = self.get_one_value('branch')
        if pbranch and pbranch not in ['p7', 'p8', 'Sisyphus']:
            return 'Unknown branch!'

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

            if not self.request_line:
                return "Package with params not exists!"

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

                if arg:
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
    server = LogicServer()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime')
    if buildtime_value:
        if buildtime_value not in ['>', '<', '=']:
            buildtime_action = "{} = {}"

    date_value = server.get_one_value('date')
    if date_value is None:
        date_value = "{} IN (SELECT datetime_release FROM AssigmentName " \
                     "ORDER BY datetime_release DESC LIMIT 1)"
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
        return 'Request params error..('

    server.request_line = \
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id WHERE " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    response = server.send_request()
    if response is False:
        return 'Request error..('

    server.add_extra_package_params(['packager', 'branch', 'date', 'files',
                                     'requires', 'conflicts', 'obsoletes',
                                     'provides'])

    json_retval = json.loads(
        server.convert_to_json(server.package_params, response)
    )

    for elem in json_retval:
        package_sha1 = json_retval[elem]['sha1header']

        # files
        server.request_line = \
            "SELECT filename FROM File WHERE package_sha1 = '{}'" \
            "".format(package_sha1)

        files = server.send_request()
        if files is False:
            return 'Request error..('

        json_retval[elem]['files'] = server.join_tuples(files)

        p_list = [('Require', 'requires'), ('Conflict', 'conflicts'),
                  ('Obsolete', 'obsoletes'), ('Provide', 'provides')]

        for pl in p_list:
            server.request_line = "SELECT name, version FROM {table} " \
                                  "WHERE package_sha1 = '{sha1}'" \
                                  "".format(table=pl[0], sha1=package_sha1)

            response = server.send_request()
            if response is False:
                return 'Request error..('

            json_retval[elem][pl[1]] = server.join_tuples(response)

    return json.dumps(json_retval)


if __name__ == '__main__':
    app.run()
