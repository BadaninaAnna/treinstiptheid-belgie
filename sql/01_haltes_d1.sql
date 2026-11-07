-- Ruwe gegevens D-1 (Infrabel open data, puntkomma-gescheiden) -> genormaliseerde tabel `haltes`.
-- Eén rij = één trein aan één meetpunt. {bestand} wordt ingevuld door src/pijplijn.py.
CREATE OR REPLACE TABLE haltes AS
SELECT
    datdep                                              AS datum,
    train_no                                            AS trein,
    relation                                            AS relatie,
    train_serv                                          AS operator,
    upper(trim(ptcar_lg_nm_nl))                         AS meetpunt,
    coalesce(planned_time_arr, planned_time_dep)        AS gepland,
    delay_arr                                           AS vertraging_aankomst_s,
    delay_dep                                           AS vertraging_vertrek_s
FROM read_csv('{bestand}', delim = ';', header = true,
              types = {'delay_arr': 'BIGINT', 'delay_dep': 'BIGINT'});
