SELECT name,
       version,
       release,
       Df.name,
       Df.version,
       Df.release
FROM
  (SELECT name,
          version,
          release
   FROM last_packages
   WHERE assigment_name = %(pkgset1)s
     AND sourcepackage = 1
     AND (name,
          version,
          release) NOT IN
       (SELECT name,
               version,
               release
        FROM last_packages
        WHERE assigment_name = %(pkgset2)s
          AND sourcepackage = 1)
     AND name IN
       (SELECT name
        FROM last_packages
        WHERE assigment_name = %(pkgset2)s
          AND sourcepackage = 1)) AS PkgSet2
INNER JOIN
  (SELECT name,
          version,
          release
   FROM last_packages
   WHERE assigment_name = %(pkgset2)s
     AND sourcepackage = 1) AS Df USING name
UNION ALL
SELECT name,
       version,
       release,
       '',
       '',
       ''
FROM last_packages
WHERE assigment_name = %(pkgset1)s
  AND sourcepackage = 1
  AND name NOT IN
    (SELECT name
     FROM last_packages
     WHERE assigment_name = %(pkgset2)s
       AND sourcepackage = 1)