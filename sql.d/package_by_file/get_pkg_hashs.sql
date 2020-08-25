SELECT pkg.pkghash
FROM last_packages
WHERE assigment_name = %(branch)s
  AND arch IN %(arch)s
