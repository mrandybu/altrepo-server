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
   WHERE pkghash IN
       (SELECT arrayJoin(pkgs)
        FROM Tasks
        WHERE task_id = {id}
          AND (try,
               iteration) IN
            (SELECT max(try),
                    argMax(iteration, try)
             FROM Tasks
             WHERE task_id = {id}))
     AND dptype IN ('provide',
                    'require',
                    'obsolete',
                    'conflict')) AS Deps USING pkghash
WHERE name NOT LIKE '%-debuginfo'
  AND arch IN ('x86_64',
               'x86_64-i586',
               'i586')
GROUP BY name,
         arch,
         dptype
