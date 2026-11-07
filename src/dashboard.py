"""Bouwt het publieke dashboard docs/index.html (GitHub Pages) uit de samenvattingen in data/.

Gebruik:  python src/dashboard.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pijplijn import DATA, FOCUS, ROOT

DOCS = ROOT / "docs"
VENSTER_DAGEN = 30          # periode voor rangschikkingen, kaart en uurprofiel
MIN_METINGEN_STATION = 300  # in die periode, anders te weinig treinen voor een betrouwbaar percentage
MIN_METINGEN_RELATIE = 1000
MIN_METINGEN_UUR = 100     # uren met minder aankomsten (nacht) geven een onbetrouwbaar percentage


def lees(tabel: str) -> pd.DataFrame:
    df = pd.concat((pd.read_csv(p) for p in sorted((DATA / "dag" / tabel).glob("*.csv"))), ignore_index=True)
    df["datum"] = pd.to_datetime(df.datum)
    return df


def mooi(station: str) -> str:
    return station.title()


def pct(stipt, metingen):
    return np.round(100 * stipt / metingen, 1)


def _lijst(s: pd.Series, n=1):
    return [None if pd.isna(v) else round(float(v), n) for v in s]


def bouw_data() -> dict:
    nat = lees("dag_nationaal").sort_values("datum")
    st = lees("dag_station")
    rel = lees("dag_relatie")
    uur = lees("dag_uur")
    stations = pd.read_csv(DATA / "stations.csv")
    officieel = pd.read_csv(DATA / "officieel" / "stiptheid_per_stopplaats.csv")
    oorzaken = pd.read_csv(DATA / "officieel" / "oorzaken_per_maand.csv")
    meta = json.loads((DATA / "meta.json").read_text("utf-8"))

    laatste = nat.datum.max()
    van = laatste - pd.Timedelta(days=VENSTER_DAGEN - 1)

    # Rangschikking en kaart: laatste 30 dagen per station.
    s30 = (st[st.datum >= van].groupby("station")
             .agg(metingen=("metingen", "sum"), stipt=("stipt", "sum"),
                  vertragingsminuten=("vertragingsminuten", "sum"), zwaar=("zwaar_vertraagd", "sum"))
             .reset_index())
    s30 = s30[s30.metingen >= MIN_METINGEN_STATION].merge(stations, on="station", how="left")
    s30["stiptheid"] = pct(s30.stipt, s30.metingen)
    s30["gem_vertraging"] = (s30.vertragingsminuten / s30.metingen).round(2)

    r30 = (rel[rel.datum >= van].groupby(["relatie", "operator"])
             .agg(metingen=("metingen", "sum"), stipt=("stipt", "sum"), zwaar=("zwaar_vertraagd", "sum"))
             .reset_index())
    r30 = r30[r30.metingen >= MIN_METINGEN_RELATIE]
    r30["stiptheid"] = pct(r30.stipt, r30.metingen)

    # Dagreeks per focusstation (alle beschikbare dagen) en uurprofiel over 30 dagen.
    dagen = sorted(nat.datum.dt.strftime("%Y-%m-%d"))
    reeks = {}
    for s in FOCUS:
        d = st[st.station == s].set_index(st[st.station == s].datum.dt.strftime("%Y-%m-%d"))
        reeks[s] = [None if k not in d.index else float(pct(d.at[k, "stipt"], d.at[k, "metingen"])) for k in dagen]
    u30 = (uur[uur.datum >= van].groupby(["station", "uur"]).agg(metingen=("metingen", "sum"), stipt=("stipt", "sum"))
             .reset_index())
    profiel = {s: {int(r.uur): float(pct(r.stipt, r.metingen)) for r in g.itertuples() if r.metingen >= MIN_METINGEN_UUR}
               for s, g in u30.groupby("station")}

    # Officiële maandcijfers voor de focusstations (sinds 2023) en het hele net (gewogen).
    officieel = officieel[officieel.maand >= "2023-01"]
    maanden = sorted(officieel.maand.unique())
    off = {}
    for s in FOCUS:
        d = officieel[officieel.station == s].set_index("maand")
        off[s] = [None if m not in d.index else round(float(d.at[m, "stiptheid"]), 1) for m in maanden]
    net = officieel.groupby("maand").agg(metingen=("metingen", "sum"), stipt=("stipt", "sum"))
    off["NETWERK"] = _lijst(pct(net.stipt, net.metingen).reindex(maanden))

    # Oorzaken: aandeel in het stiptheidsverlies, laatste 12 beschikbare maanden.
    laatste12 = sorted(oorzaken.maand.unique())[-12:]
    oz = oorzaken[oorzaken.maand.isin(laatste12)].groupby("verantwoordelijk").totaal_onstipte_metingen.sum()
    oz = (100 * oz / oz.sum()).sort_values()

    gisteren = st[st.datum == laatste].set_index("station")
    n_g = nat[nat.datum == laatste].iloc[0]
    return {
        "bijgewerkt": pd.Timestamp(meta["bijgewerkt"]).strftime("%d-%m-%Y %H:%M"),
        "laatste_dag": laatste.strftime("%d-%m-%Y"),
        "venster": f"{van:%d-%m} – {laatste:%d-%m-%Y}",
        "gisteren": {
            "netwerk": float(pct(n_g.stipt, n_g.metingen)),
            "gem_vertraging": round(float(n_g.vertragingsminuten / n_g.metingen), 2),
            "zwaar": int(n_g.zwaar_vertraagd), "metingen": int(n_g.metingen), "treinen": int(n_g.treinen),
            "stations": {s: float(pct(gisteren.at[s, "stipt"], gisteren.at[s, "metingen"]))
                         for s in FOCUS if s in gisteren.index},
        },
        "dagen": dagen,
        "netwerk_dag": _lijst(pct(nat.stipt, nat.metingen)),
        "station_dag": reeks,
        "profiel": profiel,
        "officieel": {"maanden": maanden, "reeksen": off},
        "focus": [{"code": s, "naam": mooi(s)} for s in FOCUS],
        "stations30": [{"naam": mooi(r.station), "stiptheid": r.stiptheid, "metingen": int(r.metingen),
                        "gem": r.gem_vertraging, "lat": r.lat, "lon": r.lon, "klasse": r.classificatie}
                       for r in s30.itertuples() if pd.notna(r.lat)],
        "relaties30": [{"naam": r.relatie, "operator": r.operator, "stiptheid": r.stiptheid,
                        "label": r.relatie if r.operator == "SNCB/NMBS" else f"{r.relatie} ({r.operator})",
                        "metingen": int(r.metingen)} for r in r30.sort_values("stiptheid").itertuples()],
        "oorzaken": {"labels": list(oz.index), "aandeel": _lijst(oz), "periode": f"{laatste12[0]} – {laatste12[-1]}"},
    }


def main():
    data = bouw_data()
    html = (ROOT / "src" / "sjabloon.html").read_text("utf-8").replace(
        "/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html, "utf-8")
    print(f"docs/index.html: {len(html) / 1024:.0f} kB, laatste dag {data['laatste_dag']}, "
          f"netwerk {data['gisteren']['netwerk']} %")


if __name__ == "__main__":
    main()
