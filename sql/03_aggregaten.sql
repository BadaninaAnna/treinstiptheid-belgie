-- Kerncijfers per dag. Elke SELECT hieronder levert één uitvoertabel op (zie src/pijplijn.py).
-- Gemiddelde vertraging: te vroeg rijden telt als 0, zodat vroege treinen de vertraging niet "wegpoetsen".

-- name: dag_nationaal
SELECT datum,
       count(*)                                              AS metingen,
       count(*) FILTER (WHERE stipt)                         AS stipt,
       round(avg(greatest(vertraging_s, 0)) / 60, 3)         AS gem_vertraging_min,
       count(*) FILTER (WHERE vertraging_s >= 900)           AS zwaar_vertraagd,      -- 15 minuten of meer
       round(sum(greatest(vertraging_s, 0)) / 60)            AS vertragingsminuten,
       count(DISTINCT trein)                                 AS treinen
FROM metingen
GROUP BY datum;

-- name: dag_station
SELECT datum, station,
       count(*)                                              AS metingen,
       count(*) FILTER (WHERE stipt)                         AS stipt,
       round(avg(greatest(vertraging_s, 0)) / 60, 3)         AS gem_vertraging_min,
       round(quantile_cont(greatest(vertraging_s, 0), 0.9) / 60, 2) AS p90_vertraging_min,
       count(*) FILTER (WHERE vertraging_s >= 900)           AS zwaar_vertraagd,
       round(sum(greatest(vertraging_s, 0)) / 60)            AS vertragingsminuten
FROM metingen
GROUP BY datum, station;

-- name: dag_relatie
SELECT datum, relatie, operator,
       count(*)                                              AS metingen,
       count(*) FILTER (WHERE stipt)                         AS stipt,
       round(avg(greatest(vertraging_s, 0)) / 60, 3)         AS gem_vertraging_min,
       count(*) FILTER (WHERE vertraging_s >= 900)           AS zwaar_vertraagd,
       count(DISTINCT trein)                                 AS treinen
FROM metingen
WHERE relatie IS NOT NULL
GROUP BY datum, relatie, operator;

-- name: dag_uur
-- Uurprofiel voor het hele net en voor de focusstations (rest van het land: te veel rijen voor git).
SELECT datum, 'NETWERK' AS station, uur,
       count(*) AS metingen, count(*) FILTER (WHERE stipt) AS stipt,
       round(avg(greatest(vertraging_s, 0)) / 60, 3) AS gem_vertraging_min
FROM metingen
GROUP BY datum, uur
UNION ALL
SELECT m.datum, m.station, m.uur,
       count(*), count(*) FILTER (WHERE m.stipt),
       round(avg(greatest(m.vertraging_s, 0)) / 60, 3)
FROM metingen AS m
JOIN focus AS f ON f.station = m.station
GROUP BY m.datum, m.station, m.uur;
