INSERT INTO {tmp_deps} (pkgname,
                        reqname)
SELECT DISTINCT BinDeps.pkgname,
                sourcepkgname
FROM
  (SELECT DISTINCT BinDeps.pkgname,
                   name AS pkgname,
                   sourcepkgname
   FROM last_packages_with_source
   INNER JOIN
     (SELECT DISTINCT BinDeps.pkgname,
                      pkgname
      FROM
        (SELECT DISTINCT BinDeps.pkgname,
                         pkgname,
                         dpname
         FROM last_depends
         INNER JOIN
           (SELECT DISTINCT pkgname,
                            dpname
            FROM last_depends
            WHERE pkgname IN
                (SELECT ''
                 UNION ALL SELECT *
                 FROM {tmp_table})
              AND assigment_name = %(branch)s
              AND dptype = 'require'
              AND sourcepackage = 1) AS BinDeps USING dpname
         WHERE assigment_name = %(branch)s
           AND dptype = 'provide'
           AND sourcepackage = 0
           AND arch IN ('x86_64',
                        'noarch'))) AS pkgs USING pkgname
   WHERE assigment_name = %(branch)s
   ORDER BY sourcepkgname ASC
   UNION ALL SELECT arrayJoin(%(pkgs)s),
                    '',
                    '')