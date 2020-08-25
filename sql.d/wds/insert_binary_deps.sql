INSERT INTO {tmp_req} (pkgname,
                       reqname)
SELECT sourcepkgname,
       Bin.sourcepkgname
FROM
  (SELECT sourcepkgname,
          name AS pkgname,
          Bin.sourcepkgname
   FROM last_packages_with_source
   INNER JOIN
     (SELECT pkgname,
             sourcepkgname
      FROM
        (SELECT DISTINCT pkgname,
                         Prv.pkgname AS dpname,
                         Src.sourcepkgname
         FROM
           (SELECT pkgname,
                   dpname,
                   Prv.pkgname
            FROM
              (SELECT DISTINCT pkgname,
                               dpname
               FROM last_depends
               WHERE pkgname IN
                   (SELECT DISTINCT name
                    FROM last_packages_with_source
                    WHERE sourcepkgname IN
                        (SELECT *
                         FROM {tmp_table})
                      AND assigment_name = %(branch)s
                      AND arch IN %(archs)s
                      AND name NOT LIKE '%%-debuginfo')
                 AND dptype = 'require'
                 AND assigment_name = %(branch)s
                 AND arch IN %(archs)s
                 AND sourcepackage = 0) AS BinPkgDeps
            INNER JOIN
              (SELECT dpname,
                      pkgname
               FROM last_depends
               WHERE dptype = 'provide'
                 AND assigment_name = %(branch)s
                 AND sourcepackage = 0
                 AND arch IN %(archs)s) AS Prv USING dpname) AS BinPkgProvDeps
         INNER JOIN
           (SELECT name AS dpname,
                   sourcepkgname
            FROM last_packages_with_source
            WHERE assigment_name = %(branch)s
              AND arch IN %(archs)s) Src USING dpname)) AS Bin USING pkgname
   WHERE assigment_name = %(branch)s
     AND arch IN %(archs)s)
