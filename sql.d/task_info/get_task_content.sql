SELECT sourcepkg_hash,
       groupUniqArray(hshs)
FROM
  (SELECT sourcepkg_hash,
          arrayJoin(pkgs) AS hshs
   FROM Tasks
   WHERE task_id = {id})
WHERE hshs IN
    (SELECT arrayJoin(*)
     FROM
       (SELECT groupArray(arrayJoin(pkgs))
        FROM Tasks
        WHERE task_id = {id}
          AND notEmpty(pkgs)
        GROUP BY try,
                 iteration
        ORDER BY try DESC,iteration DESC
        LIMIT 1))
GROUP BY sourcepkg_hash
