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
* version
* release
* disttag
* buildtime (><=)
* source - show source packages (true, false)
* arch
* branch
* packager
* sha1
* full (true, false)

#### /misconflict_packages

Returns a list of binary packages with intersecting files and no 
conflict with a given package.

Request parameters:

* pkg_ls * - name or list of binary package
* task ** - task id
* branch * (* - only 'pkg_ls')
* arch

#### /package_by_file

Returns a list of binary packages that contain the specified file.
It is possible to set the full file name, file name mask, md5 of file.

Request parameters:

* file * - file name, can be set as a file name mask
(ex. file='/usr/bin/*')
* md5 ** - file md5
* arch
* branch *

#### /package_files

Show list of files by current sha1 of package.

Request parameters:

* sha1 * - package sha1

#### /dependent_packages

Returns a list of source packages whose binary packages depend on the
given package.

Request parameters:

* name * - name of binary package
* branch *

#### /what_depends_src

Returns a list of source packages whose binary packages build will fail
after removal specified package from the repository.

Request parameters:

* name * - name of source package
* task ** - task id (can't used with 'name')
* branch * (* - only 'name')
* arch
* leaf - show assembly dependency chain
* deep - sets the sorting depth (ex.: deep=1 (also 2, 3))
* reqfilter - package for filter result by dependency
* finitepkg - show only topological tree leaves

#### /repo_compare

Returns a list of differences in the source package base of specified
repositories.

* assign1 * - name of repository
* assing2 * - name of compared repository

\* - require parameters

** - replacement require parameters

## Dependencies

* python3-module-flask
* python3-module-numpy
* python3-module-clickhouse-driver
* python3-module-urllib3
* python3-module-rpm

## Components

* app.py - main module of application, processes requests
* logic_server - contains the base class of the server (backend for app)
* db_connection.py - module of database connection
* utils.py - contains auxiliary functions used by the main module
* paths.py - provides of namespace for using in application
* tests/* - tests of project
* fake_mirror.py - creates a repository structure and fills it with a
specified number packages (used for test queries)
* deps_sorting - module for sorting dependencies (topological sorting)
* conflict_filter - filter for package conflicts by provides (uses
version comparison)

## Starting application

Best to use a bunch of nginx and gunicorn servers to run.

First step

	git clone http://git.altlinux.org/people/mrdrew/private/altrepo_server.git
	git checkout `last_tag`

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
    Host = 10.0.0.1        # database host
    Name = database_name   # database name

    [Application]
    Host = 127.0.0.1    # application host
    Port = 5000         # port
    Processes = 1       # number of worker processes

    [Other]
    LogFiles = /home/mrdrew/altrepo_server.log

Also you can set launch options use keys. For more information use -h.

### Starting application

For start application using module run_app. For set app configuration
can be using config file ex.:

    /usr/bin/python3 run_app.py --config /path/to/config/file.conf

or use launch keys, for more information

    /usr/bin/python3 run_app.py --help

Start application from git catalog

    /usr/bin/python3 run_app.py `allow_options` &

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

#### /repo_compare
    curl "http://localhost/repo_compare?assign1=p9&assign2=Sisyphus" | jq
