SELECT DISTINCT Pkg.pkgname,
                extract(filename, '^(.+)/([^/]+)$') AS dir,
                Pkg.version,
                Pkg.release,
                Pkg.epoch,
                Pkg.packager,
                Pkg.packager_email,
                groupUniqArray(Pkg.arch)
FROM File
         LEFT JOIN (
    SELECT pkghash,
           name as pkgname,
           version,
           release,
           epoch,
           disttag,
           packager_email,
           packager,
           arch
    FROM Package) AS Pkg USING pkghash
WHERE empty(fileclass)
  AND (pkghash IN (SELECT pkghash
                   FROM last_packages
                   WHERE (assigment_name = %(branch)s)
                     AND packager_email
                       LIKE %(email)s
                     AND (sourcepackage = 0)
                     AND (arch IN %(archs)s)))
  AND (hashdir NOT IN (SELECT hashname
                       FROM File
                       WHERE (fileclass =
                              'directory')
                         AND (pkghash IN (SELECT pkghash
                                          FROM last_packages
                                          WHERE (assigment_name = %(branch)s)
                                            AND (sourcepackage = 0)
                                            AND (arch IN
                                                 %(archs)s)))))
GROUP BY (Pkg.pkgname, dir, Pkg.version, Pkg.release,
          Pkg.epoch, Pkg.packager, Pkg.packager_email)
ORDER BY packager_email