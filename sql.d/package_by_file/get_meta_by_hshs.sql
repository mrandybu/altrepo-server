SELECT pkghash,
       pkgcs,
       name,
       version,
       release,
       disttag,
       arch,
       %(branch)s
FROM Package
WHERE pkghash IN %(hashs)s
