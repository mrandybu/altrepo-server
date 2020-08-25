SELECT DISTINCT assigment_name,
                sourcepkgname,
                toString(any(assigment_date)) AS pkgset_date,
                groupUniqArray(name) AS pkgnames,
                version,
                release,
                any(disttag),
                any(packager_email),
                toString(toDateTime(any(buildtime))) AS buildtime,
                groupUniqArray(arch)
FROM last_packages_with_source
WHERE (sourcepkgname IN %(pkgs)s)
  AND (name NOT LIKE '%%-debuginfo')
GROUP BY assigment_name,
         sourcepkgname,
         version,
         release
ORDER BY pkgset_date DESC