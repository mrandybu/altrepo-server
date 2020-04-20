from flask import Flask, request, json
from logic_server import server
import utils
from utils import func_time, get_helper
from deps_sorting import SortList
from conflict_filter import ConflictFilter

app = Flask(__name__)
logger = utils.get_logger(__name__)


@app.route('/package_info')
@func_time(logger)
def package_info():
    """
    The function of showing information about given package by user parameters.

    Input GET params:
        sha1 - package sha1
        name - package name
        version - package version
        release - package release
        arch - package arch
        disttag - package disttag
        buildtime - package buildtime
        source - show source packages only (true/false)
        packager - maintainer of package
        branch - repository
        full - show full package information

    Output structure:
        `not full option`
        pkgcs
        packager
        packager_email
        name
        arch
        version
        release
        epoch
        buildtime
        sourcepackage
        sourcerpm
        filename
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime', 'i')
    if buildtime_value and buildtime_value not in ['>', '<', '=']:
        buildtime_action = "{} = {}"

    pbranch = server.get_one_value('branch', 's', is_='repo_name')

    input_params = {
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
            'is_': 'pkg_name',
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

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        return get_helper(server.helper(request.path))

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
            "SELECT pkghash, groupUniqArray(filename) FROM File WHERE pkghash "
            "IN %(pkghshs)s GROUP BY pkghash", {'pkghshs': pkghashs}
        )

        status, response = server.send_request()
        if status is False:
            return response

        files_dict = utils.tuplelist_to_dict(response, 1)

        # add empty list if package has no files
        for hsh in pkghashs:
            if hsh not in files_dict:
                files_dict[hsh] = []

        # depends
        server.request_line = (
            "SELECT pkghash, dptype, dpname FROM last_depends WHERE pkghash "
            "IN %(pkghshs)s", {'pkghshs': pkghashs}
        )

        status, response = server.send_request()
        if status is False:
            return response

        depends_dict = utils.tuplelist_to_dict(response, 2)

        depends_struct = {}
        for pkg in depends_dict:
            depend_ls = depends_dict[pkg]

            depends_struct[pkg] = {}

            for i in range(0, len(depend_ls), 2):
                if depend_ls[i] not in depends_struct[pkg]:
                    depends_struct[pkg][depend_ls[i]] = []

                depends_struct[pkg][depend_ls[i]].append(depend_ls[i + 1])

        for elem in json_retval:
            pkghash = json_retval[elem]['pkghash']

            # add files to result structure
            json_retval[elem]['files'] = files_dict[pkghash]

            # add depends to result structure
            for dep in depends_struct[pkghash]:
                json_retval[elem][dep] = depends_struct[pkghash][dep]

    # remove pkghash from result
    for value in json_retval.values():
        value.pop('pkghash', None)

    return json.dumps(json_retval, sort_keys=False)


@app.route('/misconflict_packages')
@func_time(logger)
def conflict_packages():
    """
    The function of searching for conflicting files in packages that do not have
    a conflict.

    Input GET params:
        pkg_ls * - package or list of packages
        task ** - task id
        branch (* - for pkg_ls only) - name of repository
        arch - package architectures

    Output structure:
        input package
        conflict package
        version
        release
        epoch
        architectures
        files with conflict
    """
    server.url_logging()

    check_params = server.check_input_params(source=0)
    if check_params is not True:
        return check_params

    values = server.get_dict_values([
        ('pkg_ls', 's', 'pkg_name'), ('task', 'i'),
        ('branch', 's', 'repo_name'), ('arch', 's')
    ])

    if values['pkg_ls'] and values['task']:
        return utils.json_str_error("One parameter only. ('name'/'task')")

    if not values['pkg_ls'] and not values['task']:
        return utils.json_str_error("'pkg_ls' or 'task' is require parameters.")

    if values['pkg_ls'] and not values['branch']:
        return get_helper(server.helper(request.path))

    if values['arch']:
        allowed_archs = values['arch'].split(',')
        if 'noarch' not in allowed_archs:
            allowed_archs.append('noarch')
    else:
        allowed_archs = server.default_archs

    allowed_archs = tuple(allowed_archs)

    # prepare packages list from Task
    if values['task']:
        # get branch of task
        server.request_line = (
            "SELECT DISTINCT branch FROM Tasks WHERE task_id = %(task)d",
            {'task': values['task']}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error(
                "Task {task} not found!".format(task=values['task'])
            )

        pbranch = response[0][0]

        # get packages of task (hashes)
        server.request_line = (
            "SELECT pkgs FROM Tasks WHERE task_id = %(task)d",
            {'task': values['task']}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error(
                "Error: Packages in task {task} not found!"
                "".format(task=values['task'])
            )

        # joining tuples from response list
        input_pkg_hshs = []
        for block in response:
            for hsh in block[0]:
                input_pkg_hshs.append(hsh)

    # package list without task
    else:
        pkg_ls = tuple(values['pkg_ls'].split(','))
        pbranch = values['branch']

        # get hash for package names
        server.request_line = (
            "SELECT pkghash, name FROM last_packages WHERE name IN %(pkgs)s "
            "AND assigment_name = %(branch)s AND sourcepackage = 0 AND arch "
            "IN %(arch)s", {
                'pkgs': tuple(pkg_ls), 'branch': pbranch, 'arch': allowed_archs
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error(
                "Error: Packages {pkgs} not found in pkgset {branch}!".format(
                    pkgs=pkg_ls, branch=pbranch
                )
            )

        # check the existence of a package by comparing the number of input
        # and selected from database
        if len(set([pkg[1] for pkg in response])) != len(pkg_ls):
            return utils.json_str_error("Error of input data.")

        # form a list of package hashes
        input_pkg_hshs = [pkg[0] for pkg in response]

    # get list of (input package | conflict package | conflict files)
    server.request_line = (
        "SELECT InPkg.pkghash, pkghash, groupUniqArray(filename) FROM (SELECT "
        "pkghash, filename, hashname FROM File WHERE hashname IN (SELECT "
        "hashname FROM File WHERE pkghash IN %(hshs)s AND fileclass != "
        "'directory') AND pkghash IN (SELECT pkghash FROM last_packages WHERE "
        "assigment_name = %(branch)s AND sourcepackage = 0 AND arch IN "
        "%(arch)s AND name NOT IN (SELECT name FROM Package WHERE "
        "pkghash IN %(hshs)s) AND name NOT LIKE '%%-debuginfo')) LEFT JOIN ("
        "SELECT pkghash, hashname FROM File WHERE pkghash IN %(hshs)s) AS "
        "InPkg USING hashname GROUP BY (InPkg.pkghash, pkghash)", {
            'hshs': tuple(input_pkg_hshs), 'branch': pbranch,
            'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    hshs_files = response

    # list of conflicting package pairs
    in_confl_hshs = [(hsh[0], hsh[1]) for hsh in hshs_files]

    # filter conflicts by provides/conflicts
    c_filter = ConflictFilter(pbranch, allowed_archs)

    # check for the presence of the specified conflict each pair
    # if the conflict between the packages in the pair is specified,
    # then add the pair to the list
    filter_ls = []
    for tp_hsh in in_confl_hshs:
        confl_ls = c_filter.detect_conflict(tp_hsh[0], tp_hsh[1])
        for confl in confl_ls:
            if confl not in filter_ls:
                filter_ls.append(confl)

    # get a list of hashes of packages to form a dict of hash-name
    pkg_hshs = utils.remove_duplicate(
        [hsh[0] for hsh in hshs_files] + [hsh[1] for hsh in hshs_files]
    )

    # get package names by hashes
    server.request_line = (
        "SELECT DISTINCT pkghash, name FROM Package WHERE pkghash IN %(pkgs)s "
        "AND sourcepackage = 0 AND arch IN %(arch)s", {
            'pkgs': tuple(pkg_hshs), 'branch': pbranch, 'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    hsh_name_dict = utils.tuplelist_to_dict(response, 1)

    # get names of input packages
    input_packages = []
    for hsh, name in hsh_name_dict.items():
        if hsh in input_pkg_hshs:
            input_packages.append(name)

    input_packages = utils.remove_duplicate(utils.join_tuples(input_packages))

    # convert the hashes into names, put in the first place in the pair
    # the name of the input package, if it is not
    filter_ls_names = []
    for hsh in filter_ls:
        inp_pkg = hsh_name_dict[hsh[1]][0]
        if inp_pkg not in input_packages:
            inp_pkg = hsh_name_dict[hsh[0]][0]
            filter_ls_names.append((inp_pkg, hsh_name_dict[hsh[1]][0]))
        else:
            filter_ls_names.append((inp_pkg, hsh_name_dict[hsh[0]][0]))

    # form the list of tuples (input package | conflict package | conflict files)
    result_list = []
    for pkg in hshs_files:
        pkg = (hsh_name_dict[pkg[0]][0], hsh_name_dict[pkg[1]][0], pkg[2])
        if pkg not in result_list:
            result_list.append(pkg)

    # look for duplicate pairs of packages in the list with different files
    # and join them
    result_list_cleanup = []
    for pkg in result_list:
        files = list(pkg[2])
        for pkg_next in result_list:
            if (pkg[0], pkg[1]) == (pkg_next[0], pkg_next[1]):
                for file in pkg_next[2]:
                    files.append(file)

        files = sorted(utils.remove_duplicate(files))

        pkg = (pkg[0], pkg[1], files)
        if pkg not in result_list_cleanup:
            result_list_cleanup.append(pkg)

    confl_pkgs = utils.remove_duplicate([pkg[1] for pkg in result_list_cleanup])

    # get main information of packages by package hashes
    server.request_line = (
        "SELECT name, version, release, epoch, groupUniqArray(arch) FROM "
        "last_packages WHERE name IN %(pkgs)s AND assigment_name = %(branch)s "
        "AND sourcepackage = 0 AND arch IN %(arch)s GROUP BY (name, version, "
        "release, epoch)", {
            'pkgs': tuple(confl_pkgs), 'branch': pbranch, 'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    # form dict name - package info
    name_info_dict = {}
    for pkg in response:
        name_info_dict[pkg[0]] = pkg[1:]

    # form list of tuples (input pkg | conflict pkg | pkg info | conflict files)
    # and filter it
    result_list_info = []
    for pkg in result_list_cleanup:
        if (pkg[0], pkg[1]) not in filter_ls_names:
            pkg = (pkg[0], pkg[1]) + name_info_dict[pkg[1]] + (pkg[2],)
            result_list_info.append(pkg)

    return utils.convert_to_json(
        ['input_package', 'conflict_package', 'version', 'release', 'epoch',
         'archs', 'files_with_conflict'], result_list_info
    )


@app.route('/package_by_file')
@func_time(logger)
def package_by_file():
    """
    The function of searching binary packages that contain the specified file.

    Input GET params:
        file * - file name or pattern
        md5 ** - file md5
        branch * - repository name
        arch - package architecture

    Output structure:
        pkgcs
        name
        version
        release
        disttag
        arch
        branch
        files
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    file = server.get_one_value('file', 'r', is_='pkg_name')
    md5 = server.get_one_value('md5', 's')

    if len([param for param in [file, md5] if param]) != 1:
        return get_helper(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's', 'repo_name')
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

    ids_filename_dict = utils.tuplelist_to_dict(response, 1)

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
    """
    The function of searching binary packages that contain the specified file.

    Input GET params:
        sha1 - package sha1

    Output structure:
        sha1
        files
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1', 's')
    if not sha1:
        return get_helper(server.helper(request.path))

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
    """
    The function of searching source packages whose binary packages depend on
    the given package.

    Input GET params:
        name * - name of package
        branch * - repository name

    Output structure:
        name
        version
        release
        epoch
        serial
        sourcerpm
        branch
        archs
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's', is_='pkg_name')
    if not pname:
        return get_helper(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's', is_='repo_name')
    if not pbranch:
        message = 'Branch is required parameter.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = (
        "SELECT DISTINCT name, version, release, epoch, serial_, filename "
        "AS sourcerpm, assigment_name, groupUniqArray(binary_arch) FROM "
        "last_packages INNER JOIN (SELECT sourcerpm, arch AS binary_arch FROM "
        "last_packages WHERE name IN (SELECT DISTINCT pkgname FROM last_depends "
        "WHERE dpname IN (SELECT dpname FROM last_depends WHERE pkgname = "
        "%(name)s AND dptype = 'provide' AND assigment_name = %(branch)s AND "
        "sourcepackage = 0) AND assigment_name = %(branch)s AND sourcepackage "
        "= 0) AND assigment_name = %(branch)s AND sourcepackage = 0) USING "
        "sourcerpm WHERE assigment_name = %(branch)s AND sourcepackage = 1 "
        "GROUP BY (name, version, release, epoch, serial_, filename AS "
        "sourcerpm, assigment_name)", {'name': pname, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    js_keys = ['name', 'version', 'release', 'epoch', 'serial', 'sourcerpm',
               'branch', 'archs']

    return utils.convert_to_json(js_keys, response)


@app.route('/what_depends_src')
@func_time(logger)
def what_depends_build():
    """
    The function of searching build dependencies.

    The function search build dependencies of package, list packages or
    packages from task. Also function can also use such parameters like as
    leaf, searching depth.

    Input GET params:
        name * - package or list of packages
        task ** - task id
        branch (* - for pkg_ls only) - name of repository
        arch - package architectures
        leaf - assembly dependency chain
        deep - sorting depth
        dptype - type of package (source, binary, both)
        reqfilter - filter result by dependency by binary pkg
        reqfilterbysrc - filter result by dependency by source pkg
        finitepkg - topological tree leaves

    Output structure:
        name
        version
        release
        epoch
        serial_
        sourcerpm
        branch
        archs
        buildtime
        cycle
        requires
        acl
    """
    server.url_logging()

    check_params = server.check_input_params(source=1)
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's', is_='pkg_name')
    task_id = server.get_one_value('task', 'i')

    # dptype option
    depends_type_to_sql = {
        'source': (1,),
        'binary': (0,),
        'both': (1, 0)
    }

    depends_type = server.get_one_value('dptype', 's')
    if depends_type not in depends_type_to_sql:
        depends_type = 'both'

    sourcef = depends_type_to_sql[depends_type]

    message = None
    if pname and task_id:
        message = "Only one parameter package 'name' or build 'task'."
    elif not pname and not task_id:
        message = "Source package 'name' or build 'task' " \
                  "is require parameters."

    if message:
        logger.debug(message)
        return utils.json_str_error(message)

    pbranch = server.get_one_value('branch', 's', is_='repo_name')
    if pname and not pbranch:
        return get_helper(server.helper(request.path))

    arch = server.get_one_value('arch', 's')
    if arch:
        arch = [arch]
        if 'noarch' not in arch:
            arch.append('noarch')
    else:
        arch = ['x86_64', 'noarch']

    # tree leaf - show only build path between 'name' and 'leaf'
    leaf = server.get_one_value('leaf', 's', 'pkg_name')
    if leaf and task_id:
        return utils.json_str_error("'leaf' may be using with 'name' only.")

    # process this query for task
    if task_id:
        # get the branch name from task
        server.request_line = (
            "SELECT DISTINCT branch FROM Tasks WHERE task_id = %(id)s",
            {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error('Unknown task id.')

        # branch from task
        pbranch = response[0][0]

        # get the packages hashes from Task
        server.request_line = (
            "SELECT pkgs FROM Tasks WHERE task_id = %(id)s", {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        # join list of tuples of tuples
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

    # without task - get the packages name from URL
    else:
        input_pkgs = (pname,)

    # deep level for recursive requires search
    deep_level = server.get_one_value('deep', 'i')
    if not deep_level:
        deep_level = 1

    tmp_table_name = 'tmp_pkg_ls'

    # create tmp table with list of packages
    server.request_line = "CREATE TEMPORARY TABLE {tmp_table} (pkgname String)" \
                          "".format(tmp_table=tmp_table_name)

    status, response = server.send_request()
    if status is False:
        return response

    # base query - first iteration, build requires depth 1
    server.request_line = (
        "INSERT INTO {tmp_table} SELECT DISTINCT name FROM Package WHERE "
        "(filename IN (SELECT DISTINCT if(sourcepackage = 1, filename, "
        "sourcerpm) AS sourcerpm from Package WHERE pkghash IN (SELECT DISTINCT "
        "pkghash FROM last_depends WHERE dpname IN (SELECT dpname FROM Depends "
        "WHERE pkghash IN (SELECT pkghash FROM last_packages_with_source WHERE "
        "sourcepkgname IN %(pkgs)s AND assigment_name = %(branch)s AND arch IN "
        "('x86_64', 'noarch') AND name NOT LIKE '%%-debuginfo') AND dptype = "
        "'provide') AND assigment_name = %(branch)s AND sourcepackage IN "
        "%(sfilter)s AND dptype = 'require' AND pkgname NOT LIKE '%%-debuginfo'"
        "))) AND sourcepackage = 1 UNION ALL SELECT arrayJoin(%(union)s)"
        "".format(tmp_table=tmp_table_name), {
            'sfilter': sourcef, 'pkgs': input_pkgs, 'branch': pbranch,
            'union': list(input_pkgs)
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    max_allowed_depth = 10

    if deep_level > 1:
        if deep_level > max_allowed_depth:
            return utils.json_str_error(
                "Requires Depth cannot exceed {}".format(max_allowed_depth)
            )

        # sql wrapper for increase depth
        deep_wrapper = \
            "SELECT pkghash FROM last_depends WHERE dpname IN (SELECT dpname " \
            "FROM Depends WHERE pkghash IN (SELECT pkghash FROM " \
            "last_packages_with_source WHERE sourcepkgname IN (SELECT * FROM " \
            "{tmp_table}) AND assigment_name = %(branch)s AND arch IN ('x86_64', " \
            "'noarch') AND name NOT LIKE '%%-debuginfo') AND dptype='provide') " \
            "AND assigment_name = %(branch)s AND dptype = 'require' AND " \
            "sourcepackage IN %(sfilter)s".format(tmp_table=tmp_table_name)

        # process depth for every level and add results to pkg_ls
        for i in range(deep_level - 1):
            server.request_line = (
                "INSERT INTO {tmp_table} (pkgname) SELECT DISTINCT * FROM ("
                "SELECT name FROM Package WHERE (filename IN (SELECT DISTINCT "
                "if(sourcepackage = 1, filename, sourcerpm) AS sourcerpm from "
                "Package WHERE pkghash IN ({wrapper}))) AND sourcepackage = 1 "
                "UNION ALL (SELECT * FROM {tmp_table}))".format(
                    wrapper=deep_wrapper, tmp_table=tmp_table_name
                ), {'sfilter': sourcef, 'branch': pbranch}
            )

            status, response = server.send_request()
            if status is False:
                return response

    server.request_line = (
        "SELECT DISTINCT acl_for, groupUniqArray(acl_list) FROM last_acl WHERE "
        "acl_for IN (SELECT pkgname FROM {tmp_table}) AND acl_branch = %(branch)s "
        "GROUP BY acl_for".format(tmp_table=tmp_table_name), {
            'branch': pbranch.lower()
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    # get package acl
    pkg_acl_dict = {}
    for pkg in response:
        pkg_acl_dict[pkg[0]] = pkg[1][0]

    tmp_table_pkg_dep = 'package_dependency'

    # create tmp table package - dependency
    server.request_line = \
        "CREATE TEMPORARY TABLE {} (pkgname String, reqname String)" \
        "".format(tmp_table_pkg_dep)

    status, response = server.send_request()
    if status is False:
        return response

    # get source dependencies
    if depends_type in ['source', 'both']:
        # populate the temporary table with package names and their source
        # dependencies
        server.request_line = (
            "INSERT INTO {tmp_deps} (pkgname, reqname) SELECT DISTINCT "
            "BinDeps.pkgname, sourcepkgname FROM (SELECT DISTINCT BinDeps.pkgname, "
            "name AS pkgname, sourcepkgname FROM last_packages_with_source "
            "INNER JOIN (SELECT DISTINCT BinDeps.pkgname, pkgname FROM (SELECT "
            "DISTINCT BinDeps.pkgname, pkgname, dpname FROM last_depends "
            "INNER JOIN (SELECT DISTINCT pkgname, dpname FROM last_depends "
            "WHERE pkgname IN (SELECT '' UNION ALL SELECT * FROM {tmp_table}) "
            "AND assigment_name = %(branch)s AND dptype = 'require' AND "
            "sourcepackage = 1) AS BinDeps USING dpname WHERE assigment_name = "
            "%(branch)s AND dptype = 'provide' AND sourcepackage = 0 AND arch "
            "IN ('x86_64', 'noarch'))) USING pkgname WHERE assigment_name = "
            "%(branch)s ORDER BY sourcepkgname ASC UNION ALL SELECT arrayJoin("
            "%(pkgs)s), '', '')".format(
                tmp_deps=tmp_table_pkg_dep, tmp_table=tmp_table_name), {
                'branch': pbranch, 'pkgs': list(input_pkgs)
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

    # get binary dependencies
    if depends_type in ['binary', 'both']:
        # populate the temporary table with package names and their binary
        # dependencies
        server.request_line = (
            "INSERT INTO {tmp_req} (pkgname, reqname) SELECT sourcepkgname, "
            "Bin.sourcepkgname FROM (SELECT sourcepkgname, name AS pkgname, "
            "Bin.sourcepkgname FROM last_packages_with_source INNER JOIN ("
            "SELECT pkgname, sourcepkgname FROM (SELECT DISTINCT pkgname, "
            "Prv.pkgname AS dpname, Src.sourcepkgname FROM (SELECT pkgname, "
            "dpname, Prv.pkgname FROM (SELECT DISTINCT pkgname, dpname FROM "
            "last_depends WHERE pkgname IN (SELECT DISTINCT name FROM "
            "last_packages_with_source WHERE sourcepkgname IN (SELECT * FROM "
            "{tmp_table}) AND assigment_name = %(branch)s AND arch IN %(archs)s "
            "AND name NOT LIKE '%%-debuginfo') AND dptype = 'require' AND "
            "assigment_name = %(branch)s AND arch IN %(archs)s AND sourcepackage "
            "= 0) INNER JOIN (SELECT dpname, pkgname FROM last_depends WHERE "
            "dptype = 'provide' AND assigment_name = %(branch)s AND sourcepackage "
            "= 0 AND arch IN %(archs)s) AS Prv USING dpname) INNER JOIN (SELECT "
            "name as dpname, sourcepkgname FROM last_packages_with_source WHERE "
            "assigment_name = %(branch)s AND arch IN %(archs)s) Src USING dpname"
            ")) AS Bin USING pkgname WHERE assigment_name = %(branch)s AND arch "
            "IN %(archs)s)".format(
                tmp_table=tmp_table_name, tmp_req=tmp_table_pkg_dep
            ), {'branch': pbranch, 'archs': tuple(arch)}
        )

        status, response = server.send_request()
        if status is False:
            return response

    # select all filtered package with dependencies
    server.request_line = \
        "SELECT DISTINCT pkgname, arrayFilter(x -> (x != pkgname AND " \
        "notEmpty(x)), groupUniqArray(reqname)) AS arr FROM package_dependency " \
        "WHERE reqname IN (SELECT '' UNION ALL SELECT pkgname FROM " \
        "package_dependency) GROUP BY pkgname ORDER BY arr"

    status, response = server.send_request()
    if status is False:
        return response

    pkgs_to_sort_dict = utils.tuplelist_to_dict(response, 1)

    if not pkgs_to_sort_dict:
        return json.dumps({})

    finitepkg = server.get_one_value('finitepkg', 'b', is_='pkg_name')

    if finitepkg:
        all_dependencies = []
        for pkg, deps in pkgs_to_sort_dict.items():
            for dep in deps:
                if dep not in all_dependencies:
                    all_dependencies.append(dep)

        server.request_line = \
            ("SELECT pkgname FROM {} WHERE pkgname NOT IN %(pkgs)s"
             "".format(tmp_table_name), {'pkgs': tuple(all_dependencies)})

        status, response = server.send_request()
        if status is False:
            return response

        filter_by_tops = utils.join_tuples(response)

    # check leaf, if true, get dependencies of leaf package
    if leaf:
        if leaf not in pkgs_to_sort_dict.keys():
            return utils.json_str_error(
                "Package '{}' not in dependencies list.".format(leaf)
            )

    pkg_ls_with_empty_reqs = []
    for pkg, reqs in pkgs_to_sort_dict.items():
        if not reqs:
            pkg_ls_with_empty_reqs.append(pkg)

    # sort list of dependencies by their dependencies
    sort = SortList(pkgs_to_sort_dict, pname)
    circle_deps, sorted_list = sort.sort_list()

    # create output dict with circle dependency
    result_dict = {}
    for name in sorted_list:
        result_dict[name] = []
        if name in circle_deps:
            result_dict[name] += list(circle_deps[name].keys())

    # if leaf, then select packages from the result list and their cyclic
    # dependencies on which the leaf package and create a dictionary
    if leaf:

        def recursive_search(pkgname, structure):
            for pkg in structure[pkgname]:
                if pkg not in leaf_filter and pkg != pkgname:
                    leaf_filter.append(pkg)
                    recursive_search(pkg, structure)

        leaf_filter = []
        recursive_search(leaf, pkgs_to_sort_dict)

        if leaf not in leaf_filter:
            leaf_filter.append(leaf)

        # filter result dict by leaf packages
        result_dict = {
            key: value for (key, value) in result_dict.items()
            if key in leaf_filter
        }

    # list of result package names
    sorted_pkgs = tuple(result_dict.keys())

    # get output data for sorted package list
    server.request_line = (
        "SELECT DISTINCT SrcPkg.name, SrcPkg.version, SrcPkg.release, "
        "SrcPkg.epoch, SrcPkg.serial_, sourcerpm AS filename, assigment_name, "
        "groupUniqArray(arch), CAST(toDateTime(any(SrcPkg.buildtime)), 'String') "
        "AS buildtime_str FROM last_packages INNER JOIN (SELECT name, version, "
        "release, epoch, serial_, filename, assigment_name, buildtime FROM "
        "last_packages WHERE name IN (SELECT * FROM {tmp_table}) AND "
        "assigment_name = %(branch)s AND sourcepackage = 1) AS SrcPkg USING "
        "filename WHERE assigment_name = %(branch)s AND sourcepackage = 0 "
        "GROUP BY (SrcPkg.name, SrcPkg.version, SrcPkg.release, SrcPkg.epoch, "
        "SrcPkg.serial_, filename, assigment_name)"
        "".format(tmp_table=tmp_table_name), {'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    # form list of packages with it information
    pkg_info_list = []
    for info in response:
        for pkg, c_deps in result_dict.items():
            if info[0] == pkg:
                # add empty list if not acl
                if pkg not in pkg_acl_dict:
                    pkg_acl_dict[pkg] = []

                pkg_info_list.append(
                    info + (c_deps,) + (pkgs_to_sort_dict[pkg],) +
                    (pkg_acl_dict[pkg],)
                )

    # filter result packages list by dependencies
    reqfilter = server.get_dict_values(
        [('reqfilter', 's', 'pkg_name'), ('reqfilterbysrc', 's', 'pkg_name')]
    )

    if None not in reqfilter.values():
        message = "Parameters 'reqfilter' and 'reqfilterbysrc' cannot be " \
                  "used together."
        return utils.json_str_error(message)

    filter_pkgs = None
    if reqfilter['reqfilter'] or reqfilter['reqfilterbysrc']:

        if reqfilter['reqfilter']:
            reqfilter_binpkgs = tuple(reqfilter['reqfilter'].split(','))
        else:
            server.request_line = (
                "SELECT DISTINCT name FROM last_packages_with_source WHERE "
                "sourcepkgname = %(srcpkg)s AND assigment_name = %(branch)s AND "
                "arch IN ('x86_64', 'noarch') AND name NOT LIKE '%%debuginfo'", {
                    'srcpkg': reqfilter['reqfilterbysrc'], 'branch': pbranch
                }
            )

            status, response = server.send_request()
            if status is False:
                return response

            reqfilter_binpkgs = utils.join_tuples(response)

        base_query = \
            "SELECT DISTINCT pkgname FROM last_depends WHERE dpname IN (" \
            "SELECT dpname FROM last_depends WHERE pkgname = '{pkg}' AND " \
            "dptype = 'provide' AND assigment_name = %(branch)s AND " \
            "sourcepackage = 0 AND arch IN %(archs)s) AND dptype = 'require' " \
            "AND assigment_name = %(branch)s AND sourcepackage IN (0, 1) AND " \
            "pkgname IN (SELECT DISTINCT name FROM (SELECT DISTINCT name FROM " \
            "last_packages_with_source WHERE sourcepkgname IN (SELECT * FROM " \
            "{tmp_table}) AND assigment_name = %(branch)s AND sourcepackage = 0 " \
            "AND arch IN %(archs)s AND name NOT LIKE '%%-debuginfo' UNION ALL " \
            "SELECT name FROM Package WHERE name IN (SELECT * FROM {tmp_table})))" \
            "".format(pkg="{pkg}", tmp_table=tmp_table_name)

        if len(reqfilter_binpkgs) == 1:
            base_query = base_query.format(pkg=reqfilter_binpkgs[0])
        else:
            last_query = None
            for pkg in reqfilter_binpkgs:
                if not last_query:
                    last_query = base_query.format(pkg=pkg)

                last_query = "{} AND pkgname IN ({})" \
                             "".format(last_query, base_query.format(pkg=pkg))

            base_query = last_query

        server.request_line = (
            "SELECT DISTINCT sourcepkgname FROM last_packages_with_source WHERE "
            "name IN (SELECT DISTINCT * FROM ({base_query})) AND assigment_name = "
            "%(branch)s AND arch IN %(archs)s".format(base_query=base_query), {
                'branch': pbranch, 'archs': tuple(arch)
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

        filter_pkgs = utils.join_tuples(response)

    # sort pkg info list
    sorted_dict = {}
    for pkg in pkg_info_list:
        if (filter_pkgs and pkg[0] in filter_pkgs) or not filter_pkgs:
            if task_id:
                if pkg[0] not in input_pkgs:
                    sorted_dict[sorted_pkgs.index(pkg[0])] = pkg
            else:
                sorted_dict[sorted_pkgs.index(pkg[0])] = pkg

    sorted_dict = list(dict(sorted(sorted_dict.items())).values())

    if finitepkg:
        sorted_dict = [pkg for pkg in sorted_dict if pkg[0] in filter_by_tops]

    js_keys = ['name', 'version', 'release', 'epoch', 'serial_', 'sourcerpm',
               'branch', 'archs', 'buildtime', 'cycle', 'requires', 'acl']

    return utils.convert_to_json(js_keys, sorted_dict)


@app.route('/unpackaged_dirs')
@func_time(logger)
def unpackaged_dirs():
    """
    The function of searching unpacked directories by maintainer name.

    Input GET params:
        pkgr * - maintainer name
        pkgset * - repository name
        arch - architecture

    Output structure:
        package
        directory
        version
        release
        epoch
        packager
        email
        arch
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    values = server.get_dict_values(
        [('pkgr', 's'), ('pkgset', 's', 'repo_name'), ('arch', 's')]
    )

    if not values['pkgr'] or not values['pkgset']:
        return get_helper(server.helper(request.path))

    parch = server.default_archs
    if values['arch']:
        parch = values['arch'].split(',')
        if 'noarch' not in parch:
            parch.append('noarch')

    server.request_line = (
        "SELECT DISTINCT Pkg.pkgname, extract(filename, '^(.+)/([^/]+)$') AS "
        "dir, Pkg.version, Pkg.release, Pkg.epoch, Pkg.packager, "
        "Pkg.packager_email, groupUniqArray(Pkg.arch) FROM File LEFT JOIN ("
        "SELECT pkghash, name as pkgname, version, release, epoch, disttag, "
        "packager_email, packager, arch FROM Package) AS Pkg USING pkghash "
        "WHERE empty(fileclass) AND (pkghash IN (SELECT pkghash FROM "
        "last_packages WHERE (assigment_name = %(branch)s) AND packager_email "
        "LIKE %(email)s AND (sourcepackage = 0) AND (arch IN %(archs)s))) AND "
        "(hashdir NOT IN (SELECT hashname FROM File WHERE (fileclass = "
        "'directory') AND (pkghash IN (SELECT pkghash FROM last_packages WHERE "
        "(assigment_name = %(branch)s) AND (sourcepackage = 0) AND (arch IN "
        "%(archs)s))))) GROUP BY (Pkg.pkgname, dir, Pkg.version, Pkg.release, "
        "Pkg.epoch, Pkg.packager, Pkg.packager_email) ORDER BY packager_email",
        {
            'branch': values['pkgset'], 'email': '{}@%'.format(values['pkgr']),
            'archs': tuple(parch)
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    js_keys = ['package', 'directory', 'version', 'release', 'epoch',
               'packager', 'email', 'arch']

    return utils.convert_to_json(js_keys, response)


@app.route('/repo_compare')
@func_time(logger)
def repo_compare():
    """
    The function of compare two differences in the package base of specified
    repositories.

    Input GET params:
        pkgset1 * - first repository name for compare
        pkgset2 * - lsat repository name for compare

    Output structure:
        name
        version
        release
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    values = server.get_dict_values([
        ('pkgset1', 's', 'repo_name'), ('pkgset2', 's', 'repo_name')
    ])

    if not values['pkgset1'] or not values['pkgset2']:
        return get_helper(server.helper(request.path))

    server.request_line = (
        "SELECT name, version, release, Df.name, Df.version, Df.release FROM "
        "(SELECT name, version, release FROM last_packages WHERE "
        "assigment_name = %(pkgset1)s AND sourcepackage = 1 AND (name, "
        "version, release) NOT IN (SELECT name, version, release FROM "
        "last_packages WHERE assigment_name = %(pkgset2)s AND "
        "sourcepackage = 1) AND name IN (SELECT name FROM last_packages WHERE "
        "assigment_name = %(pkgset2)s AND sourcepackage = 1)) INNER JOIN "
        "(SELECT name, version, release FROM last_packages WHERE "
        "assigment_name = %(pkgset2)s AND sourcepackage = 1) AS Df USING name "
        "UNION ALL SELECT name, version, release, '', '', '' FROM last_packages "
        "WHERE assigment_name = %(pkgset1)s AND sourcepackage = 1 AND name "
        "NOT IN (SELECT name FROM last_packages WHERE assigment_name = "
        "%(pkgset2)s AND sourcepackage = 1)", {
            'pkgset1': values['pkgset1'], 'pkgset2': values['pkgset2']
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    result_dict = {}
    for i in range(len(response)):
        iter_elem = response[i]
        result_dict[i] = {
            values['pkgset1']: {
                'name': iter_elem[0], 'version': iter_elem[1],
                'release': iter_elem[2]
            },
            values['pkgset2']: {
                'name': iter_elem[3], 'version': iter_elem[4],
                'release': iter_elem[5]
            }
        }

    if not response:
        return json.dumps({})

    return json.dumps(result_dict, sort_keys=False)


@app.route('/find_pkgset')
@func_time(logger)
def find_pkgset():
    """
    The function of compare two differences in the package base of specified
    repositories.

    Input GET params:
        srcpkg_ls - package name or list of packages
        task - number of task

    Output structure:
        branch
        data
        packages
        version
        archs
    """
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    values = server.get_dict_values([
        ('srcpkg_ls', 's', 'pkg_name'), ('task', 'i')
    ])
    if None not in values.values():
        return utils.json_str_error("One parameter only ('srcpkg_ls'/'task').")

    if values['srcpkg_ls']:
        pkg_ls = values['srcpkg_ls'].split(',')
    else:
        server.request_line = (
            "SELECT DISTINCT name FROM Package WHERE filename IN (SELECT "
            "DISTINCT sourcerpm FROM Package WHERE pkghash IN (SELECT "
            "arrayJoin(pkgs) FROM Tasks WHERE task_id = %(task_id)s) AND name "
            "NOT LIKE '%%-debuginfo')", {
                'task_id': values['task']
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

        pkg_ls = utils.join_tuples(response)

    server.request_line = (
        "SELECT assigment_name, pkgset_date, pkgnames, version, "
        "groupUniqArray(arch) FROM (SELECT DISTINCT assigment_name, "
        "toString(any(assigment_date)) AS pkgset_date, groupUniqArray(name) "
        "AS pkgnames, version, arch FROM last_packages_with_source WHERE "
        "(sourcepkgname IN %(pkgs)s) AND (name NOT LIKE '%%-debuginfo') "
        "GROUP BY assigment_name, version, arch ORDER BY pkgset_date DESC) "
        "GROUP BY assigment_name, pkgset_date, pkgnames, version", {
            'pkgs': tuple(pkg_ls)
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    param_ls = ['branch', 'data', 'packages', 'version', 'archs']

    return utils.convert_to_json(param_ls, response)


@app.teardown_request
def drop_connection(connection):
    server.drop_connection()


@app.errorhandler(404)
def page_404(error):
    helper = {
        'Error': error.description,
        'Valid queries': {
            '/package_info': 'information about given package',
            '/misconflict_packages': 'binary packages with intersecting '
                                     'files and no conflict with a given package',
            '/package_by_file': 'binary packages that contain the specified file',
            '/package_files': 'files by current sha1 of package',
            '/dependent_packages': 'source packages whose binary packages '
                                   'depend on the given package',
            '/what_depends_src': 'source packages with build dependency on a '
                                 'given package',
            '/unpackaged_dirs': 'list of unpacked directories',
            '/repo_compare': 'list of differences in the package base of '
                             'specified repositories',
            '/find_pkgset': 'list of binary packages for the given source',
        }
    }
    return json.dumps(helper, sort_keys=False)


if __name__ == '__main__':
    app.run()
