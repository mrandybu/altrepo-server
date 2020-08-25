SELECT pkghash
FROM last_depends
WHERE dpname IN
    (SELECT dpname
     FROM Depends
     WHERE pkghash IN
         (SELECT pkghash
          FROM last_packages_with_source
          WHERE sourcepkgname IN
              (SELECT *
               FROM {tmp_table})
            AND assigment_name = %(branch)s
            AND arch IN ('x86_64',
                         'noarch')
            AND name NOT LIKE '%%-debuginfo')
       AND dptype = 'provide')
  AND assigment_name = %(branch)s
  AND dptype = 'require'
  AND sourcepackage IN %(sfilter)s