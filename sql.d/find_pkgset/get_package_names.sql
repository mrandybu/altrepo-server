SELECT DISTINCT name
FROM Package
WHERE filename IN
    (SELECT DISTINCT sourcerpm
     FROM Package
     WHERE pkghash IN
         (SELECT arrayJoin(pkgs)
          FROM Tasks
          WHERE task_id = %(task_id)s)
       AND name NOT LIKE '%%-debuginfo')