SELECT DISTINCT srchsh,
                groupUniqArray(pkghash)
FROM
  (SELECT pkghash AS srchsh,
          dpname
   FROM Depends
   WHERE pkghash IN ({pkgs})
     AND dptype = 'require') AS sourceDep
INNER JOIN
  (SELECT pkghash,
          dpname
   FROM last_depends
   WHERE dptype = 'provide'
     AND assigment_name = '{branch}'
     AND sourcepackage = 0
     AND arch IN ({archs})) AS binaryDeps USING dpname
GROUP BY srchsh