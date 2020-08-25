SELECT name,
       groupUniqArray(arch)
FROM Package
WHERE pkghash IN {hshs}
GROUP BY name