SELECT DISTINCT pkgname
FROM last_depends
WHERE dpname IN
    (SELECT dpname
     FROM last_depends
     WHERE pkgname = '{pkg}'
       AND dptype = 'provide'
       AND assigment_name = %(branch)s
       AND sourcepackage = 0
       AND arch IN %(archs)s)
  AND dptype = 'require'
  AND assigment_name = %(branch)s
  AND sourcepackage IN (0,
                        1)
  AND pkgname IN
    (SELECT DISTINCT name
     FROM
       (SELECT DISTINCT name
        FROM last_packages_with_source
        WHERE sourcepkgname IN
            (SELECT *
             FROM {tmp_table})
          AND assigment_name = %(branch)s
          AND sourcepackage = 0
          AND arch IN %(archs)s
          AND name NOT LIKE '%%-debuginfo'
        UNION ALL SELECT name
        FROM Package
        WHERE name IN
            (SELECT *
             FROM {tmp_table})))
