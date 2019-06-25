# ALTRepo Server

ALTRepo Server is a jquery interface for the repository database of ALT
distribution. ALTRepo allows users to get the necessary information regards
to the repository by GET requests.

The following types of queries are currently implemented:

#### /package_info

Returns full information on the requested package.

Request parameters:

* name * - package name
* version
* release
* arch
* disttag
* buildtime (><=)
* source - show source packages (true, false)
* branch
* date (ex. date=2019-06-21)
* packager

#### /misconflict_packages

Returns a list of binary packages with intersecting files and no conflict
with a given package.

Request parameters:

* name * - name of binary package
* branch *
* version

#### /package_by_file

Returns a list of binary packages that contain the specified file.
It is possible to set the full file name, file name mask, md5 of file.

Request parameters:

* file - file name, can be set as a file name mask (ex. file='/usr/bin/%')
* md5 - file md5

#### /package_files

Show list of files by current sha1 of package.

Request parameters:

* sha1 * - package sha1

#### /dependent_packages

Returns a list of source packages whose binary packages depend on the
given package.

Request parameters:

* name - name of binary package
* version
* branch

#### /what_depends_src

Returns a list of binary packages whose build will fail after removal
specified package from the repository.

Request parameters:

* name - name of source package
* branch *

\* - require parameters

## Dependencies

* python3-module-flask
* python3-module-numpy
* python3-module-psycopg2

## Components

* app.py - main module of application, contains the base class of the server
and processes requests
* db_connection.py - module of database connection
* utils.py - contains auxiliary functions used by the main module
* paths.py - provides of namespace for using in application
* tests/* - tests of project
* fake_mirror.py - creates a repository structure and fills it with a
specified number packages (used for test queries)

## Starting application

Best to use a bunch of nginx and gunicorm servers to run.

First step

	git clone http://git.altlinux.org/people/mrdrew/private/altrepo_server.git

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

Make file

	/etc/altrepo_server/dbconfig.conf

..with next content

	[DBParams]
	DataBaseName = DB name
	User = DB username
	Password = DB password
	Host = DB host

### Starting application

Start application from git catalog

	gunicorn.py3 app:app &

..after the application will run in the background.

## Examples of query

The response from the server is returned as json data, for their formatted
mapping is convenient to use jq utility.

#### /package_info

	curl "http://apphost/package_info?name=glibc&branch=Sisyphus" | jq

#### /misconflict_packages

	curl "http://apphost/misconflict_packages?name=postgresql10&branch=p8" | jq

#### /package_by_file

	curl "http://apphost/package_by_file?file=/usr/bin/less&branch=c8.1" | jq
	curl "http://apphost/package_by_file?file='/etc/sysconfig/c%'&branch=Sisyphus" | jq

#### /package_files

	curl "http://apphost/package_files?sha1=ad8b637c1e6c6e22e8aac42ed1c997658a1e9913" | jq

#### /dependent_packages

	curl "http://apphost/dependent_packages?name=systemd&branch=p8" | jq

#### /what_depends_src

	curl "http://apphost/what_depends_src?name=python-module-setuptools&branch=Sisyphus" | jq