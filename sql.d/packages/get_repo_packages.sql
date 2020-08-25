SELECT name,
       version,
       release,
       summary,
       groupUniqArray(packager_email) AS packagers,
       url,
       license,
       group_,
       groupUniqArray(arch),
       acl_list
FROM last_packages
LEFT JOIN
  (SELECT acl_for AS name,
          acl_list
   FROM last_acl
   WHERE acl_branch = '{branch_l}') AS Acl USING name
WHERE assigment_name = '{branch}'
  AND sourcepackage IN {src}
  AND arch IN {archs}
GROUP BY name,
         version,
         release,
         summary,
         url,
         license,
         group_,
         acl_list