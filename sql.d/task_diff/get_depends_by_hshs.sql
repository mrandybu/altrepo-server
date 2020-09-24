SELECT name,
       dptype,
       arch,
       groupUniqArray(dpname)
FROM Package
INNER JOIN
  (SELECT DISTINCT pkghash,
                   dpname,
                   dptype
   FROM Depends
   WHERE pkghash IN %(hshs)s
     AND dptype IN ('provide',
                    'require',
                    'obsolete',
                    'conflict')) AS Deps USING pkghash
WHERE name NOT LIKE '%%-debuginfo'
  AND arch IN ('x86_64',
               'x86_64-i586',
               'i586')
GROUP BY name,
         arch,
         dptype