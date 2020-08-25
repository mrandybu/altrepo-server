SELECT DISTINCT SrcPkg.name,
                SrcPkg.version,
                SrcPkg.release,
                SrcPkg.epoch,
                SrcPkg.serial_,
                sourcerpm AS filename,
                assigment_name,
                groupUniqArray(arch),
                CAST(toDateTime(any(SrcPkg.buildtime)), 'String') AS buildtime_str
FROM last_packages
INNER JOIN
  (SELECT name,
          version,
          release,
          epoch,
          serial_,
          filename,
          assigment_name,
          buildtime
   FROM last_packages
   WHERE name IN
       (SELECT *
        FROM {tmp_table})
     AND assigment_name = %(branch)s
     AND sourcepackage = 1) AS SrcPkg USING filename
WHERE assigment_name = %(branch)s
  AND sourcepackage = 0
GROUP BY (SrcPkg.name,
          SrcPkg.version,
          SrcPkg.release,
          SrcPkg.epoch,
          SrcPkg.serial_,
          filename,
          assigment_name)
