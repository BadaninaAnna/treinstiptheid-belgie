-- Maandelijks archiefbestand (komma-gescheiden, andere kolomnamen en datumnotatie '01SEP2026')
-- -> dezelfde genormaliseerde tabel `haltes` als bij de dagelijkse D-1-gegevens.
CREATE OR REPLACE TABLE haltes AS
SELECT
    strptime("DATDEP", '%d%b%Y')::DATE                                  AS datum,
    "TRAIN_NO"                                                          AS trein,
    "RELATION"                                                          AS relatie,
    "TRAIN_SERV"                                                        AS operator,
    upper(trim("PTCAR_LG_NM_NL"))                                       AS meetpunt,
    coalesce(try_cast("PLANNED_TIME_ARR" AS TIME),
             try_cast("PLANNED_TIME_DEP" AS TIME))                      AS gepland,
    try_cast("DELAY_ARR" AS BIGINT)                                     AS vertraging_aankomst_s,
    try_cast("DELAY_DEP" AS BIGINT)                                     AS vertraging_vertrek_s
FROM read_csv('{bestand}', delim = ',', header = true, all_varchar = true);
