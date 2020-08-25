INSERT INTO {tmp_table}
SELECT DISTINCT name
FROM Package
WHERE (filename IN
         (SELECT DISTINCT if(sourcepackage = 1, filename, sourcerpm) AS sourcerpm
          FROM Package
          WHERE pkghash IN
              (SELECT DISTINCT pkghash
               FROM last_depends
               WHERE dpname IN
                   (SELECT dpname
                    FROM Depends
                    WHERE pkghash IN
                        (SELECT pkghash
                         FROM last_packages_with_source
                         WHERE sourcepkgname IN %(pkgs)s
                           AND assigment_name = %(branch)s
                           AND arch IN ('x86_64',
                                        'noarch')
                           AND name NOT LIKE '%%-debuginfo')
                      AND dptype = 'provide')
                 AND assigment_name = %(branch)s
                 AND sourcepackage IN %(sfilter)s
                 AND dptype = 'require'
                 AND pkgname NOT LIKE '%%-debuginfo' )))
  AND sourcepackage = 1
UNION ALL
SELECT arrayJoin(%(union)s)