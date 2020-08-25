INSERT INTO {tmp_table} (pkgname)
SELECT DISTINCT *
FROM
  (SELECT name
   FROM Package
   WHERE (filename IN
            (SELECT DISTINCT if(sourcepackage = 1, filename, sourcerpm) AS sourcerpm
             FROM Package
             WHERE pkghash IN ({wrapper})))
     AND sourcepackage = 1
   UNION ALL
     (SELECT *
      FROM {tmp_table}))
