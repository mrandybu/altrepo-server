SELECT pkg.pkghash
FROM last_packages
WHERE name IN
    (SELECT DISTINCT name
     FROM Package
     WHERE pkghash IN %(hshs)s
       AND name NOT LIKE '%%-debuginfo')
  AND assigment_name IN
    (SELECT branch
     FROM Tasks
     WHERE task_id = %(id)s
     LIMIT 1)
  AND sourcepackage = 0
  AND arch IN ('x86_64',
               'x86_64-i586',
               'i586')