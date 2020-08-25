SELECT arrayJoin(*)
FROM
  (SELECT groupArray(arrayJoin(pkgs))
   FROM Tasks
   WHERE task_id = %(task)d
     AND notEmpty(pkgs)
   GROUP BY try,
            iteration
   ORDER BY try DESC,iteration DESC
   LIMIT 1)
