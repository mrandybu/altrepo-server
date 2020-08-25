SELECT DISTINCT acl_for,
                groupUniqArray(acl_list)
FROM last_acl
WHERE acl_for IN
    (SELECT pkgname
     FROM {tmp_table})
  AND acl_branch = %(branch)s
GROUP BY acl_for
