# ALTRepo Server (clickhouse database)

ALTRepo Server is a jquery interface for the repository database of ALT
distribution. ALTRepo allows users to get the necessary information 
regards to the repository by GET requests.

The following types of queries are currently implemented:

#### /package_info

Returns main or full (if full option is true) information on the 
requested package.

Request parameters:

* name - package name
* version - package version
* release - package release
* disttag - package disttag
* buildtime - package buildtime (><=)
* source - show source packages only (true, false)
* arch - package arch
* branch - name of repository
* packager - maintainer of package
* packager_email - maintainer's email
* sha1 - package sha1
* full - show full package information (true, false)

#### /misconflict_packages

Returns a list of binary packages with intersecting files and no 
conflict with a given package.

Request parameters:

* pkg_ls * - name or list of binary package
* task ** - task id
* branch (* - for pkg_ls only) - name of repository
* arch - package architectures

#### /package_by_file

Returns a list of binary packages that contain the specified file.
It is possible to set the full file name, file name mask, md5 of file.

Request parameters:

* file * - file name, can be set as a file name mask
(ex. file='/usr/bin/*')
* md5 ** - file md5
* branch * - name of repository
* arch - package architecture

#### /package_files

Show list of files by current sha1 of package.

Request parameters:

* sha1 * - package sha1

#### /dependent_packages

Returns a list of source packages whose binary packages depend on the
given package.

Request parameters:

* name * - name of binary package
* branch * - repository name

#### /what_depends_src

The function search build dependencies of package, list packages or
packages from task. Also function can also use such parameters like as
leaf, searching depth.

Request parameters:

* name * - package or list of packages
* task ** - task id (can't used with 'name')
* branch (* - for pkg_ls only) - name of repository
* arch - package architectures
* leaf - show assembly dependency chain
* deep - sets the sorting depth (ex.: deep=1 (also 2, 3))
* dptype - type of package for sorting (source, binary, both)
* reqfilter - package or packages (binary) for filter result by dependency
* reqfilterbysrc - package or packages (source) for filter result by 
dependency
* finitepkg - show only topological tree leaves

#### /unpackaged_dirs

Returns unpacked directories of the specified maintainer in the
specified repository.

Request parameters:

* pkgr * - packager name
* pkgset * - repository name
* arch - architecture of packages

#### /repo_compare

Returns a list of differences in the source package base of specified
repositories.

Request parameters:

* assign1 * - name of repository
* assing2 * - name of compared repository

#### /find_pkgset

Returns a list of binary packages for the given source package names.

Request parameters:

* name * - package name or list of packages
* task ** - number of task

#### /build_dependency_set

Return a list of all binary packages which use for build input package.

Request parameters:

* pkg_ls * - package or list of packages
* task ** - task id
* branch (* - for name only) - name of repository
* arch - architecture

#### /packages

Returns a list of all packages of the repository in json format.

Request parameters:

* pkgset * - name of repository
* pkgtype - type of package (source, binary, both)
* arch - architecture(s) of packages

\* - require parameters

** - replacement require parameters

## Dependencies

* python3-module-flask
* python3-module-clickhouse-driver
* python3-module-rpm
* python3-module-numpy
* python3-module-gunicorn
* python3-module-flask-cors

## Components

* libs/* - special modules for working with mathematics, data,
data structure are using in the application
* sql.d/* - dirs with .sql files for query manager
* tests/* - tests of project
* altrepo-server - executable file to run the project
* app.py - main module of application, processes requests
* db_connection.py - module of database connection
* logic_server.py - contains the base class of the server (backend for app)
* paths.py - provides of namespace for using in application
* querymgr.py - module for sql query manager
* run_app.py - module for launching the application and processing
input parameters
* run_test.py - parallel request tests
* test_data - data for request test
* utils.py - contains auxiliary functions used by the main module

## Starting application

Best to use a bunch of nginx and gunicorn servers to run.

First step

	git clone `git_project_repository`
	git checkout `last_tag_or_master`

### Simple example of nginx setting

Make file

	/etc/nginx/sites-available.d/altrepo_server.conf 

..with next content

    server {
        listen PORT;
        server_name HOST;
        
        root /PATH/TO/altrepo_server;
        
        access_log /PATH/TO/logs/access.log;
        error_log /PATH/TO/logs/error.log;
        
        location / {
            proxy_set_header X-Forward-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $http_host;
            proxy_redirect off;
            if (!-f $request_filename) {
                proxy_pass http://127.0.0.1:8000;
                break;
            }
        }
    }

..make symlink

	/etc/nginx/sites-enabled.d/altrepo_server.conf
	->
	/etc/nginx/sites-available.d/altrepo_server.conf

### Configuration file of database

Path to default configuration file

	/etc/altrepo_server/dbconfig.conf

but you can override it use option --config for launch application.

Configuration file usually contains next sections

	[DataBase]
    HOST = 10.0.0.1        # database host
    NAME = database_name   # database name
    TRY_NUMBERS = 5        # number of connection attempts
    TRY_TIMEOUT = 5        # attempts timeout
    USER = test            # database user
    PASSWORD = test        # database password

    [Application]
    HOST = 127.0.0.1    # application host
    PORT = 5000         # port
    PROCESSES = 1       # number of worker processes

    [Other]
    LOGFILE = /home/`user`/altrepo_server.log   # path to logfile

Also you can set launch options use keys. For more information use -h.

### Starting application

For start application using module run_app. For set app configuration
can be using config file ex.:

    ./altrepo-server --config /path/to/config/file.conf

or use launch keys, for more information

    ./altrepo-server --help

Start application from git catalog

    ./altrepo-server `allow_options` &

..after the application will run in the background.

## Examples of query

The response from the server is returned as json data, for their 
formatted mapping is convenient to use jq utility.

#### /package_info

	curl "http://localhost/package_info?name=glibc&branch=Sisyphus" | jq
	curl "http://localhost/package_info?name=glibc&branch=Sisyphus&full=true" | jq

#### /misconflict_packages

	curl "http://localhost/misconflict_packages?pkg_ls=postgresql10&branch=p8" | jq

#### /package_by_file

	curl "http://localhost/package_by_file?file=/usr/bin/less&branch=c8.1" | jq
	curl "http://localhost/package_by_file?file='/etc/sysconfig/c*'&branch=Sisyphus" | jq

#### /package_files

	curl "http://localhost/package_files?sha1=ad8b637c1e6c6e22e8aac42ed1c997658a1e9913" | jq

#### /dependent_packages

	curl "http://localhost/dependent_packages?name=systemd&branch=p8" | jq

#### /what_depends_src

	curl "http://localhost/what_depends_src?name=python-module-setuptools&branch=Sisyphus" | jq
	curl "http://localhost/what_depends_src?name=ocaml&branch=Sisyphus&deep=2" | jq
	curl "http://localhost/what_depends_src?name=ocaml&branch=Sisyphus&leaf=dune" | jq

#### /unpackaged_dirs

    curl "http://localhost/unpackaged_dirs?pkgr=rider&pkgset=p9" | jq

#### /repo_compare

    curl "http://localhost/repo_compare?assign1=p9&assign2=Sisyphus" | jq

#### /find_pkgset
    curl "http://127.0.0.1:5000/find_pkgset?srcpkg_ls=glibc,python" | jq

#### /build_dependency_set
    curl "http://127.0.0.1:5000/build_dependency_set?name=python-module-zope.interface&branch=sisyphus" | jq
    curl "http://127.0.0.1:5000/build_dependency_set?task=250679&arch=i586" | jq
