"""Datapijplijn: stiptheid van de treinen in België (Infrabel open data, CC0).

Gebruik:
    python src/pijplijn.py                      # dagelijkse update (D-1 + officiële maandcijfers)
    python src/pijplijn.py --archief-vanaf 2026-08   # ook ontbrekende maanden uit het archief aanvullen

Stappen:
  1. Officiële maandcijfers per stopplaats en vertragingsoorzaken ophalen (klein, altijd verversen).
  2. Ruwe gegevens van gisteren (D-1) ophalen en met DuckDB-SQL samenvatten (sql/*.sql).
  3. Maanden uit het archief verwerken waarvoor nog geen volledige dagcijfers bestaan.
Alleen de samenvattingen worden bewaard (data/dag/...): de ruwe bestanden zijn te groot voor git
en blijven bij Infrabel beschikbaar.
"""
from __future__ import annotations

import argparse
import calendar
import io
import json
import re
import shutil
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SQL = ROOT / "sql"
API = "https://opendata.infrabel.be/api/explore/v2.1/catalog/datasets"
USER_AGENT = "treinstiptheid-belgie (portfolio-project; github.com/BadaninaAnna/treinstiptheid-belgie)"

# Uurprofiel per station alleen voor deze stations (Antwerpse regio + grote knooppunten).
FOCUS = [
    "ANTWERPEN-CENTRAAL", "ANTWERPEN-BERCHEM", "ANTWERPEN-ZUID", "ANTWERPEN-LUCHTBAL",
    "ANTWERPEN-NOORDERDOKKEN", "ANTWERPEN-OOST", "ANTWERPEN-DAM", "MORTSEL", "MECHELEN", "LIER",
    "BOOM", "KAPELLEN", "ESSEN", "BRUSSEL-ZUID", "BRUSSEL-CENTRAAL", "BRUSSEL-NOORD",
    "GENT-SINT-PIETERS", "LEUVEN", "BRUGGE", "HASSELT", "KORTRIJK", "OOSTENDE",
]
TABELLEN = ["dag_nationaal", "dag_station", "dag_relatie", "dag_uur"]


def _open(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=600)


def download(url: str, doel: Path) -> Path:
    with _open(url) as r, open(doel, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    return doel


def export_csv(dataset: str, select: str | None = None) -> pd.DataFrame:
    url = f"{API}/{dataset}/exports/csv?delimiter=%3B" + (f"&select={select}" if select else "")
    with _open(url) as r:
        return pd.read_csv(io.BytesIO(r.read()), sep=";")


# --------------------------------------------------------------------------
# 1. Officiële maandcijfers
# --------------------------------------------------------------------------
def officiele_cijfers() -> pd.DataFrame:
    """Maandelijkse stiptheid per stopplaats + lijst van stations met coördinaten."""
    df = export_csv("maandelijkse-stiptheid-per-stopplaats",
                    "datum,installatienaam_nederlands,ptcar_no,classificatie,stiptheid,sumoftel,sumofreg,geo_point_2d")
    df = df.rename(columns={"installatienaam_nederlands": "station", "sumoftel": "metingen",
                            "sumofreg": "stipt", "datum": "maand"})
    df["station"] = df.station.str.strip().str.upper()
    ll = df.geo_point_2d.astype(str).str.split(",", expand=True)
    df["lat"] = pd.to_numeric(ll[0], errors="coerce").round(5)
    df["lon"] = pd.to_numeric(ll[1], errors="coerce").round(5)
    df = df.drop(columns="geo_point_2d").sort_values(["maand", "station"])
    (DATA / "officieel").mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA / "officieel" / "stiptheid_per_stopplaats.csv", index=False, lineterminator="\n")

    stations = (df.sort_values("maand").groupby("station").last().reset_index()
                [["station", "ptcar_no", "classificatie", "lat", "lon"]])
    stations.to_csv(DATA / "stations.csv", index=False, lineterminator="\n")

    oorzaken = export_csv("oorzaken-vertraging-per-maand",
                          "jaar_maand,verantwoordelijk,totaal_onstipte_metingen,totaal_aantal_metingen,stiptheidsverlies,aandeel")
    oorzaken.rename(columns={"jaar_maand": "maand"}).sort_values(["maand", "verantwoordelijk"]).to_csv(
        DATA / "officieel" / "oorzaken_per_maand.csv", index=False, lineterminator="\n")
    return stations


# --------------------------------------------------------------------------
# 2. Ruwe gegevens samenvatten met DuckDB
# --------------------------------------------------------------------------
def sql_blokken(pad: Path) -> dict[str, str]:
    """Splitst een SQL-bestand op '-- name: <tabel>'-markeringen."""
    delen = re.split(r"^-- name: (\w+)\s*$", pad.read_text("utf-8"), flags=re.M)
    return {delen[i]: delen[i + 1].strip().rstrip(";") for i in range(1, len(delen), 2)}


def samenvatten(bestand: Path, bron: str, stations: pd.DataFrame) -> dict[str, pd.DataFrame]:
    con = duckdb.connect()
    con.register("stations_df", stations)
    con.execute("CREATE TABLE stations AS SELECT * FROM stations_df")
    con.execute("CREATE TABLE focus AS SELECT unnest(?::VARCHAR[]) AS station", [FOCUS])
    pad = bestand.as_posix().replace("'", "''")
    con.execute((SQL / f"01_haltes_{bron}.sql").read_text("utf-8").replace("{bestand}", pad))
    con.execute((SQL / "02_metingen.sql").read_text("utf-8"))
    uit = {naam: con.sql(q).df() for naam, q in sql_blokken(SQL / "03_aggregaten.sql").items()}
    con.close()
    return uit


# --------------------------------------------------------------------------
# 3. Opslag: één CSV per tabel per maand; verwerkte datums worden vervangen
# --------------------------------------------------------------------------
def bewaar(tabellen: dict[str, pd.DataFrame]) -> list[str]:
    gewijzigd = []
    for naam, nieuw in tabellen.items():
        if nieuw.empty:
            continue
        nieuw = nieuw.assign(datum=pd.to_datetime(nieuw.datum).dt.strftime("%Y-%m-%d"))
        for maand, deel in nieuw.groupby(nieuw.datum.str[:7]):
            pad = DATA / "dag" / naam / f"{maand}.csv"
            pad.parent.mkdir(parents=True, exist_ok=True)
            oud = pd.read_csv(pad) if pad.exists() else deel.iloc[0:0]
            samen = pd.concat([oud[~oud.datum.isin(deel.datum.unique())], deel])
            sleutel = [k for k in ["datum", "station", "relatie", "operator", "uur"] if k in samen.columns]
            samen = samen.sort_values(sleutel)
            samen.to_csv(pad, index=False, lineterminator="\n")
            gewijzigd.append(f"{naam}/{maand}")
    return gewijzigd


def verwerkte_datums() -> set[str]:
    return {d for p in (DATA / "dag" / "dag_nationaal").glob("*.csv") for d in pd.read_csv(p).datum}


def verwerk_d1(stations: pd.DataFrame, tmp: Path) -> str:
    bestand = download(f"{API}/ruwe-gegevens-van-stiptheid-d-1/exports/csv?delimiter=%3B", tmp / "d1.csv")
    uit = samenvatten(bestand, "d1", stations)
    datums = sorted(pd.to_datetime(uit["dag_nationaal"].datum).dt.strftime("%Y-%m-%d"))
    bewaar(uit)
    return ", ".join(datums)


def verwerk_archief(stations: pd.DataFrame, tmp: Path, vanaf: str) -> list[str]:
    """Verwerkt archiefmaanden (vanaf `vanaf`) waarvoor nog niet alle dagen bestaan."""
    links = export_csv("stiptheid-gegevens-maandelijksebestanden")
    links = links[links.mois >= vanaf].sort_values("mois")
    klaar = verwerkte_datums()
    gedaan = []
    for _, r in links.iterrows():
        j, m = map(int, r.mois.split("-"))
        dagen = {f"{r.mois}-{d:02d}" for d in range(1, calendar.monthrange(j, m)[1] + 1)}
        if dagen <= klaar:
            continue
        print(f"Archief {r.mois} ophalen …", flush=True)
        bestand = download(r.link_to_data, tmp / f"archief_{r.mois}.csv")
        bewaar(samenvatten(bestand, "archief", stations))
        bestand.unlink()
        gedaan.append(r.mois)
    return gedaan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archief-vanaf", help="ontbrekende maanden uit het archief aanvullen vanaf JJJJ-MM")
    args = ap.parse_args()
    stations = officiele_cijfers()
    print(f"Officiële cijfers: {len(stations)} stopplaatsen")
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        print("D-1 verwerkt:", verwerk_d1(stations, tmp))
        vanaf = args.archief_vanaf or (date.today().replace(day=1) - pd.DateOffset(months=3)).strftime("%Y-%m")
        print("Archief verwerkt:", verwerk_archief(stations, tmp, vanaf) or "niets nieuw")
    meta = {"bijgewerkt": pd.Timestamp.now(tz="Europe/Brussels").strftime("%Y-%m-%d %H:%M"),
            "laatste_dag": max(verwerkte_datums())}
    (DATA / "meta.json").write_text(json.dumps(meta, indent=1), "utf-8")
    print(meta)


if __name__ == "__main__":
    main()
