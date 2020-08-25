SELECT *
FROM
  (SELECT InPkg.pkghash,
          pkghash,
          files,
          foundpkgname
   FROM
     (SELECT InPkg.pkghash,
             pkghash,
             groupUniqArray(filename) AS files
      FROM
        (SELECT pkghash,
                filename,
                hashname
         FROM File
         WHERE hashname IN
             (SELECT hashname
              FROM File
              WHERE pkghash IN %(hshs)s
                AND fileclass != 'directory')
           AND pkghash IN
             (SELECT pkghash
              FROM Package
              WHERE pkghash IN
                  (SELECT pkghash
                   FROM last_assigments
                   WHERE assigment_name= %(branch)s
                     AND pkghash NOT IN %(hshs)s )
                AND sourcepackage = 0
                AND name NOT LIKE '%%-debuginfo'
                AND arch IN %(arch)s)) AS LeftPkg
      LEFT JOIN
        (SELECT pkghash,
                hashname
         FROM File
         WHERE pkghash IN %(hshs)s) AS InPkg USING hashname
      GROUP BY (InPkg.pkghash,
                pkghash)) AS Sel1
   LEFT JOIN
     (SELECT name AS foundpkgname,
             pkghash
      FROM Package) AS pkgCom ON Sel1.pkghash = pkgCom.pkghash) AS Sel2
LEFT JOIN
  (SELECT name AS inpkgname,
          pkghash
   FROM Package) AS pkgIn ON pkgIn.pkghash = InPkg.pkghash
WHERE foundpkgname != inpkgname