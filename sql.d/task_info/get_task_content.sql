SELECT sourcepkg_hash,
       status,
       subtask,
       concat(toString(try), '.', toString(iteration)) AS ti,
       groupUniqArray(arrayJoin(pkgs))
FROM Tasks
WHERE task_id = {id}
  AND (try,
       iteration) IN
    (SELECT max(try),
            argMax(iteration, try)
     FROM Tasks
     WHERE task_id = {id})
GROUP BY sourcepkg_hash,
         status,
         subtask,
         ti