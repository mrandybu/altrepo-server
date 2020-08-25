SELECT name,
       version,
       release,
       epoch,
       groupUniqArray(arch)
FROM last_packages
WHERE name IN %(pkgs)s
  AND assigment_name = %(branch)s
  AND sourcepackage = 0
  AND arch IN %(arch)s
GROUP BY (name,
          version,
          release,
          epoch)
