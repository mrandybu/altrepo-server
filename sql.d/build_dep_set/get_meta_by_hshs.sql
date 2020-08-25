SELECT pkghash,
       name,
       version,
       release,
       epoch,
       groupUniqArray(arch)
FROM Package
WHERE pkghash IN
    (SELECT hsh
     FROM all_hshs)
GROUP BY (pkghash,
          name,
          version,
          release,
          epoch)