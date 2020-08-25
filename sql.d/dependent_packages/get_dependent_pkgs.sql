SELECT DISTINCT name,
                version,
                release,
                epoch,
                serial_,
                filename AS sourcerpm,
                assigment_name,
                groupUniqArray(binary_arch)
FROM last_packages
INNER JOIN
  (SELECT sourcerpm,
          arch AS binary_arch
   FROM last_packages
   WHERE name IN
       (SELECT DISTINCT pkgname
        FROM last_depends
        WHERE dpname IN
            (SELECT dpname
             FROM last_depends
             WHERE pkgname = %(name)s
               AND dptype = 'provide'
               AND assigment_name = %(branch)s
               AND sourcepackage = 0)
          AND assigment_name = %(branch)s
          AND sourcepackage = 0)
     AND assigment_name = %(branch)s
     AND sourcepackage = 0) AS SrcPkg USING sourcerpm
WHERE assigment_name = %(branch)s
  AND sourcepackage = 1
GROUP BY (name,
          version,
          release,
          epoch,
          serial_,
          filename AS sourcerpm,
          assigment_name)
