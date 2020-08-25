SELECT pkghash,
       name
FROM last_packages
WHERE name IN %(pkgs)s
  AND assigment_name = %(branch)s
  AND sourcepackage = 0
  AND arch IN %(arch)s