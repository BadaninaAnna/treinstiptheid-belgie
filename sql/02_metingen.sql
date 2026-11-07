-- Van meetpunten naar metingen aan officiële stopplaatsen, met de stiptheidsdefinitie van Infrabel:
-- een trein is stipt als hij met minder dan 6 minuten (360 s) vertraging AANKOMT.
-- Vertrekken aan de beginhalte tellen dus niet mee (Infrabel meet bij aankomst); zo sluiten onze
-- cijfers aan bij de officiële maandstiptheid per stopplaats (zie README, validatie).
CREATE OR REPLACE TABLE metingen AS
SELECT
    h.datum,
    h.trein,
    h.relatie,
    h.operator,
    h.meetpunt                              AS station,
    hour(h.gepland)                         AS uur,
    h.vertraging_aankomst_s                 AS vertraging_s,
    h.vertraging_aankomst_s < 360           AS stipt
FROM haltes AS h
JOIN stations AS s ON s.station = h.meetpunt          -- alleen echte stopplaatsen, geen bundels of wijksporen
WHERE h.vertraging_aankomst_s IS NOT NULL;
