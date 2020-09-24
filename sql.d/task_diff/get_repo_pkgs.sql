SELECT pkg.pkghash
FROM last_packages
WHERE name IN
    (SELECT DISTINCT name
     FROM Package
     WHERE pkghash IN %(hshs)s
       AND name NOT LIKE '%%-debuginfo')
  AND assigment_name = 'Sisyphus'
  AND sourcepackage = 0
  AND arch IN ('x86_64',
               'x86_64-i586',
               'i586')