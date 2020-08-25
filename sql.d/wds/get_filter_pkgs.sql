SELECT DISTINCT sourcepkgname
FROM last_packages_with_source
WHERE name IN
    (SELECT DISTINCT *
     FROM ({base_query}))
  AND assigment_name = %(branch)s
  AND arch IN %(archs)s
