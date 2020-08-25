SELECT pkg.pkghash
FROM last_packages
WHERE name IN ({pkgs})
  AND assigment_name = '{branch}'
  AND sourcepackage = 1
