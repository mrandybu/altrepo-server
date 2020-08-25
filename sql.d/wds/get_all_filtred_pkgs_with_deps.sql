SELECT DISTINCT pkgname,
                arrayFilter(x -> (x != pkgname
                                  AND notEmpty(x)), groupUniqArray(reqname)) AS arr
FROM package_dependency
WHERE reqname IN
    (SELECT ''
     UNION ALL SELECT pkgname
     FROM package_dependency)
GROUP BY pkgname
ORDER BY arr
