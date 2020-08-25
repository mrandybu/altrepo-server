SELECT DISTINCT name
FROM last_packages_with_source
WHERE sourcepkgname = %(srcpkg)s
  AND assigment_name = %(branch)s
  AND arch IN ('x86_64',
               'noarch')
  AND name NOT LIKE '%%debuginfo'