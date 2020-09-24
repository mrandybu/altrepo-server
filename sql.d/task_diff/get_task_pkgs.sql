SELECT pkghash
FROM Package
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
  AND arch IN ('x86_64',
               'x86_64-i586',
               'i586')