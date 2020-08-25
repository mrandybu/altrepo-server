SELECT DISTINCT sourcepkg_hash
FROM Tasks
WHERE task_id = %(task)d
  AND (try,
       iteration) IN
    (SELECT max(try),
            argMax(iteration, try)
     FROM Tasks
     WHERE task_id = %(task)d)
