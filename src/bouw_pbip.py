"""Bouwt het Power BI-project (PBIP) als code: semantisch model in TMDL + rapport in PBIR.

Gebruik:  python src/bouw_pbip.py
Uitvoer:  powerbi/Treinstiptheid.pbip  (+ .SemanticModel/ en .Report/)

Het model leest de samenvattingen rechtstreeks van GitHub (raw.githubusercontent.com); de workflow werkt ze
meerdere keren per dag bij. Nieuwe maandbestanden komen er bij Vernieuwen vanzelf bij.
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NAAM = "Treinstiptheid"
DATA_URL = "https://raw.githubusercontent.com/BadaninaAnna/treinstiptheid-belgie/main/data/"
T = "\t"


def lt() -> str:
    return str(uuid.uuid4())


# ==========================================================================
# 1. Semantisch model (TMDL)
# ==========================================================================
def csv_bron(pad: str, types: list[tuple[str, str]]) -> str:
    """Power Query: CSV van GitHub lezen met vaste locale (punt als decimaalteken)."""
    t = ", ".join(f'{{"{k}", {v}}}' for k, v in types)
    return (f'let\n'
            f'    Inhoud = Csv.Document ( Web.Contents ( DataUrl & "{pad}" ), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv] ),\n'
            f'    Koppen = Table.PromoteHeaders ( Inhoud, [PromoteAllScalars = true] ),\n'
            f'    Types = Table.TransformColumnTypes ( Koppen, {{{t}}}, "en-US" )\n'
            f'in\n    Types')


def maand_bron(tabel: str, types: list[tuple[str, str]]) -> str:
    """Power Query: alle maandbestanden data/dag/<tabel>/JJJJ-MM.csv vanaf augustus 2026 combineren.
    Maanden die (nog) niet bestaan worden overgeslagen, dus nieuwe maanden komen er vanzelf bij."""
    t = ", ".join(f'{{"{k}", {v}}}' for k, v in types)
    return f'''let
    Vandaag = Date.From ( DateTime.LocalNow () ),
    Start = #date ( 2026, 8, 1 ),
    Aantal = ( Date.Year ( Vandaag ) - 2026 ) * 12 + Date.Month ( Vandaag ) - 8 + 1,
    Maanden = List.Transform ( {{ 0 .. Aantal - 1 }}, each Date.ToText ( Date.AddMonths ( Start, _ ), "yyyy-MM", "en-US" ) ),
    Lees = ( m as text ) =>
        try Table.PromoteHeaders ( Csv.Document ( Web.Contents ( DataUrl & "dag/{tabel}/" & m & ".csv" ), [Delimiter = ",", Encoding = 65001] ), [PromoteAllScalars = true] )
        otherwise null,
    Samen = Table.Combine ( List.RemoveNulls ( List.Transform ( Maanden, Lees ) ) ),
    Types = Table.TransformColumnTypes ( Samen, {{{t}}}, "en-US" )
in
    Types'''


STATIONS_M = csv_bron("stations.csv", [
    ("station", "type text"), ("ptcar_no", "Int64.Type"), ("classificatie", "type text"),
    ("lat", "type number"), ("lon", "type number")]).replace(
    '\nin\n    Types',
    ',\nNaam = Table.AddColumn ( Types, "naam", each Text.Proper ( [station] ), type text )\nin\n    Naam')

OFFICIEEL_M = csv_bron("officieel/stiptheid_per_stopplaats.csv", [
    ("maand", "type text"), ("station", "type text"), ("ptcar_no", "Int64.Type"), ("classificatie", "type text"),
    ("stiptheid", "type number"), ("metingen", "type number"), ("stipt", "type number"),
    ("lat", "type number"), ("lon", "type number")]).replace(
    '\nin\n    Types',
    ',\nDatum = Table.AddColumn ( Types, "maand_datum", each Date.FromText ( [maand] & "-01", [Culture = "en-US", Format = "yyyy-MM-dd"] ), type date )\nin\n    Datum')

OORZAKEN_M = csv_bron("officieel/oorzaken_per_maand.csv", [
    ("maand", "type text"), ("verantwoordelijk", "type text"), ("totaal_onstipte_metingen", "type number"),
    ("totaal_aantal_metingen", "type number"), ("stiptheidsverlies", "type number"), ("aandeel", "type number")]).replace(
    '\nin\n    Types',
    ',\nDatum = Table.AddColumn ( Types, "maand_datum", each Date.FromText ( [maand] & "-01", [Culture = "en-US", Format = "yyyy-MM-dd"] ), type date )\nin\n    Datum')

TABELLEN = {
    "dag_station": (maand_bron("dag_station", [
        ("datum", "type date"), ("station", "type text"), ("metingen", "Int64.Type"), ("stipt", "Int64.Type"),
        ("gem_vertraging_min", "type number"), ("p90_vertraging_min", "type number"),
        ("zwaar_vertraagd", "Int64.Type"), ("vertragingsminuten", "type number")]), [
        ("datum", "dateTime", "none", "dd-mm-yyyy", {}),
        ("station", "string", "none", None, {}),
        ("metingen", "int64", "sum", "#,0", {}),
        ("stipt", "int64", "sum", "#,0", {}),
        ("gem_vertraging_min", "double", "none", "0.00", {}),
        ("p90_vertraging_min", "double", "none", "0.00", {}),
        ("zwaar_vertraagd", "int64", "sum", "#,0", {}),
        ("vertragingsminuten", "double", "sum", "#,0", {}),
    ]),
    "dag_relatie": (maand_bron("dag_relatie", [
        ("datum", "type date"), ("relatie", "type text"), ("operator", "type text"), ("metingen", "Int64.Type"),
        ("stipt", "Int64.Type"), ("gem_vertraging_min", "type number"), ("zwaar_vertraagd", "Int64.Type"),
        ("treinen", "Int64.Type")]), [
        ("datum", "dateTime", "none", "dd-mm-yyyy", {}),
        ("relatie", "string", "none", None, {}),
        ("operator", "string", "none", None, {}),
        ("metingen", "int64", "sum", "#,0", {}),
        ("stipt", "int64", "sum", "#,0", {}),
        ("gem_vertraging_min", "double", "none", "0.00", {}),
        ("zwaar_vertraagd", "int64", "sum", "#,0", {}),
        ("treinen", "int64", "sum", "#,0", {}),
    ]),
    "dag_uur": (maand_bron("dag_uur", [
        ("datum", "type date"), ("station", "type text"), ("uur", "Int64.Type"), ("metingen", "Int64.Type"),
        ("stipt", "Int64.Type"), ("gem_vertraging_min", "type number")]), [
        ("datum", "dateTime", "none", "dd-mm-yyyy", {}),
        ("station", "string", "none", None, {}),
        ("uur", "int64", "none", "0", {}),
        ("metingen", "int64", "sum", "#,0", {}),
        ("stipt", "int64", "sum", "#,0", {}),
        ("gem_vertraging_min", "double", "none", "0.00", {}),
    ]),
    "stations": (STATIONS_M, [
        ("station", "string", "none", None, {}),
        ("ptcar_no", "int64", "none", "0", {}),
        ("classificatie", "string", "none", None, {}),
        ("lat", "double", "none", "0.00000", {"dataCategory": "Latitude"}),
        ("lon", "double", "none", "0.00000", {"dataCategory": "Longitude"}),
        ("naam", "string", "none", None, {}),
    ]),
    "officieel": (OFFICIEEL_M, [
        ("maand", "string", "none", None, {}),
        ("station", "string", "none", None, {}),
        ("ptcar_no", "int64", "none", "0", {}),
        ("classificatie", "string", "none", None, {}),
        ("stiptheid", "double", "none", "0.0", {}),
        ("metingen", "double", "sum", "#,0", {}),
        ("stipt", "double", "sum", "#,0", {}),
        ("lat", "double", "none", "0.00000", {}),
        ("lon", "double", "none", "0.00000", {}),
        ("maand_datum", "dateTime", "none", "yyyy-mm", {}),
    ]),
    "oorzaken": (OORZAKEN_M, [
        ("maand", "string", "none", None, {}),
        ("verantwoordelijk", "string", "none", None, {}),
        ("totaal_onstipte_metingen", "double", "sum", "#,0", {}),
        ("totaal_aantal_metingen", "double", "sum", "#,0", {}),
        ("stiptheidsverlies", "double", "none", "0.00", {}),
        ("aandeel", "double", "none", "0.0", {}),
        ("maand_datum", "dateTime", "none", "yyyy-mm", {}),
    ]),
}

# (tabel, naam, DAX, formatString, displayFolder)
MEASURES = [
    ("dag_station", "Stiptheid", "DIVIDE ( SUM ( dag_station[stipt] ), SUM ( dag_station[metingen] ) )", "0.0%", "Stiptheid"),
    ("dag_station", "Stiptheid netwerk", "CALCULATE ( [Stiptheid], REMOVEFILTERS ( stations ) )", "0.0%", "Stiptheid"),
    ("dag_station", "Verschil met netwerk (pp)", "( [Stiptheid] - [Stiptheid netwerk] ) * 100", "+0.0;-0.0;0.0", "Stiptheid"),
    ("dag_station", "Aankomsten", "SUM ( dag_station[metingen] )", "#,0", "Stiptheid"),
    ("dag_station", "Gem. vertraging (min)",
     "DIVIDE ( SUM ( dag_station[vertragingsminuten] ), SUM ( dag_station[metingen] ) )", "0.00", "Stiptheid"),
    ("dag_station", "Zwaar vertraagd", "SUM ( dag_station[zwaar_vertraagd] )", "#,0", "Stiptheid"),
    ("dag_station", "Laatste dag", "CALCULATE ( MAX ( dag_station[datum] ), REMOVEFILTERS () )", "dd-mm-yyyy", "Stiptheid"),
    ("dag_station", "Stiptheid laatste dag",
     "VAR d = [Laatste dag]\nRETURN CALCULATE ( [Stiptheid], REMOVEFILTERS ( Datum ), dag_station[datum] = d )",
     "0.0%", "Stiptheid"),
    ("dag_uur", "Stiptheid per uur", "DIVIDE ( SUM ( dag_uur[stipt] ), SUM ( dag_uur[metingen] ) )", "0.0%", "Uur"),
    ("dag_uur", "Stiptheid per uur netwerk",
     "CALCULATE ( DIVIDE ( SUM ( dag_uur[stipt] ), SUM ( dag_uur[metingen] ) ), REMOVEFILTERS ( stations ), dag_uur[station] = \"NETWERK\" )",
     "0.0%", "Uur"),
    ("dag_relatie", "Stiptheid lijn", "DIVIDE ( SUM ( dag_relatie[stipt] ), SUM ( dag_relatie[metingen] ) )", "0.0%", "Lijnen"),
    ("dag_relatie", "Aankomsten lijn", "SUM ( dag_relatie[metingen] )", "#,0", "Lijnen"),
    ("officieel", "Officiële stiptheid", "DIVIDE ( SUM ( officieel[stipt] ), SUM ( officieel[metingen] ) )", "0.0%", "Officieel"),
    ("officieel", "Officiële stiptheid netwerk",
     "CALCULATE ( [Officiële stiptheid], REMOVEFILTERS ( stations ) )", "0.0%", "Officieel"),
    ("officieel", "Verschil eigen - officieel (pp)",
     "IF ( NOT ISBLANK ( [Stiptheid] ) && NOT ISBLANK ( [Officiële stiptheid] ), ( [Stiptheid] - [Officiële stiptheid] ) * 100 )",
     "+0.0;-0.0;0.0", "Officieel"),
    ("oorzaken", "Aandeel in verlies",
     "DIVIDE ( SUM ( oorzaken[totaal_onstipte_metingen] ), CALCULATE ( SUM ( oorzaken[totaal_onstipte_metingen] ), REMOVEFILTERS ( oorzaken[verantwoordelijk] ) ) )",
     "0.0%", "Officieel"),
]

DATUM_DAX = """VAR basis = CALENDAR ( DATE ( 2023, 1, 1 ), TODAY () )
RETURN
    ADDCOLUMNS (
        basis,
        "Jaar", YEAR ( [Date] ),
        "Maand", FORMAT ( [Date], "yyyy-mm" ),
        "MaandSort", YEAR ( [Date] ) * 100 + MONTH ( [Date] )
    )"""
DATUM_KOLOMMEN = [
    ("Date", "dateTime", "dd-mm-yyyy", {"isKey": None}),
    ("Jaar", "int64", "0", {}),
    ("Maand", "string", None, {"sortByColumn": "MaandSort"}),
    ("MaandSort", "int64", "0", {}),
]

RELATIES = [
    ("dag_station", "station", "stations", "station"),
    ("dag_uur", "station", "stations", "station"),
    ("officieel", "station", "stations", "station"),
    ("dag_station", "datum", "Datum", "Date"),
    ("dag_relatie", "datum", "Datum", "Date"),
    ("dag_uur", "datum", "Datum", "Date"),
    ("officieel", "maand_datum", "Datum", "Date"),
    ("oorzaken", "maand_datum", "Datum", "Date"),
]


def naam(n: str) -> str:
    return n if n.replace("_", "").isalnum() else "'" + n.replace("'", "''") + "'"


def inspring(tekst: str, niveau: int) -> str:
    return "\n".join(T * niveau + r for r in tekst.splitlines())


def tmdl_measure(m) -> str:
    _, n, dax, fmt, map_ = m
    kop = f"{T}measure {naam(n)} =\n{inspring(dax, 3)}" if "\n" in dax else f"{T}measure {naam(n)} = {dax}"
    return f"{kop}\n{T*2}formatString: {fmt}\n{T*2}displayFolder: {map_}\n{T*2}lineageTag: {lt()}\n"


def tmdl_kolom(n, dt, summ, fmt, extra, berekend=False) -> str:
    r = [f"{T}column {naam(n)}"]
    if berekend:
        r.append(f"{T*2}isNameInferred")
    r.append(f"{T*2}dataType: {dt}")
    if berekend:
        r.append(f"{T*2}isDataTypeInferred")
    for k, v in extra.items():
        r.append(f"{T*2}{k}" if v is None else f"{T*2}{k}: {v}")
    if fmt:
        r.append(f"{T*2}formatString: {fmt}")
    r += [f"{T*2}lineageTag: {lt()}", f"{T*2}summarizeBy: {summ}",
          f"{T*2}sourceColumn: {'[' + n + ']' if berekend else n}", "",
          f"{T*2}annotation SummarizationSetBy = Automatic"]
    return "\n".join(r) + "\n"


def tmdl_tabel(t: str) -> str:
    m, kolommen = TABELLEN[t]
    delen = [f"table {t}\n{T}lineageTag: {lt()}\n"]
    delen += [tmdl_measure(x) for x in MEASURES if x[0] == t]
    delen += [tmdl_kolom(*k) for k in kolommen]
    delen.append(f"{T}partition {t} = m\n{T*2}mode: import\n{T*2}source =\n{inspring(m, 3)}\n")
    delen.append(f"{T}annotation PBI_ResultType = Table\n")
    return "\n".join(delen)


def tmdl_datum() -> str:
    delen = [f"table Datum\n{T}dataCategory: Time\n{T}lineageTag: {lt()}\n"]
    delen += [tmdl_kolom(n, dt, "none", fmt, extra, berekend=True) for n, dt, fmt, extra in DATUM_KOLOMMEN]
    delen.append(f"{T}partition Datum = calculated\n{T*2}mode: import\n{T*2}source =\n{inspring(DATUM_DAX, 3)}\n")
    return "\n".join(delen)


def schrijf_model(map_: Path):
    d = map_ / "definition"
    (d / "tables").mkdir(parents=True)
    (map_ / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), "utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n", "utf-8")
    alle = ["Datum", *TABELLEN]
    (d / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        f"annotation PBI_QueryOrder = {json.dumps(['DataUrl', *TABELLEN])}\n\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        + "".join(f"ref table {t}\n" for t in alle), "utf-8")
    (d / "expressions.tmdl").write_text(
        f'expression DataUrl = "{DATA_URL}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {lt()}\n\n\tannotation PBI_ResultType = Text\n", "utf-8")
    (d / "relationships.tmdl").write_text("\n".join(
        f"relationship {lt()}\n\tfromColumn: {a}.{b}\n\ttoColumn: {c}.{e}\n" for a, b, c, e in RELATIES), "utf-8")
    for t in TABELLEN:
        (d / "tables" / f"{t}.tmdl").write_text(tmdl_tabel(t), "utf-8")
    (d / "tables" / "Datum.tmdl").write_text(tmdl_datum(), "utf-8")


# ==========================================================================
# 2. Rapport (PBIR)
# ==========================================================================
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PM = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
AGG = {0: "Sum", 1: "Avg", 3: "Min", 4: "Max"}


def nid():
    return uuid.uuid4().hex[:20]


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def tekst(s):
    return lit("'" + s.replace("'", "''") + "'")


def col(e, p):
    return {"Column": {"Expression": {"SourceRef": {"Entity": e}}, "Property": p}}


def meas(e, p):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": e}}, "Property": p}}


def agg(e, p, f):
    return {"Aggregation": {"Expression": col(e, p), "Function": f}}


def proj(field, display=None, fmt=None, active=None):
    if "Measure" in field:
        m = field["Measure"]
        ref = f"{m['Expression']['SourceRef']['Entity']}.{m['Property']}"
    elif "Aggregation" in field:
        c = field["Aggregation"]["Expression"]["Column"]
        ref = f"{AGG[field['Aggregation']['Function']]}({c['Expression']['SourceRef']['Entity']}.{c['Property']})"
    else:
        ref = f"{field['Column']['Expression']['SourceRef']['Entity']}.{field['Column']['Property']}"
    p = {"field": field, "queryRef": ref}
    if display:
        p["displayName"] = display
    if fmt:
        p["format"] = fmt
    if active is not None:
        p["active"] = active
    return p


def container(naam_, x, y, w, h, visual, filters=None):
    c = {"$schema": VC, "name": naam_,
         "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}, "visual": visual}
    if filters:
        c["filterConfig"] = {"filters": filters}
    return c


def titel(s):
    return {"title": [{"properties": {"show": lit("true"), "text": tekst(s)}}],
            "subTitle": [{"properties": {"show": lit("false")}}]}


def visual(vtype, roles, titeltekst=None, objects=None, sort=None, **extra):
    v = {"visualType": vtype,
         "query": {"queryState": {r: {"projections": p} for r, p in roles.items()}},
         "drillFilterOtherVisuals": True}
    if sort:
        v["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
    if objects:
        v["objects"] = objects
    if titeltekst:
        v["visualContainerObjects"] = titel(titeltekst)
    v.update(extra)
    return v


def tekstvak(x, y, w, h, regels):
    par = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{g}pt", **({"fontWeight": "bold"} if vet else {})}}]}
           for t, g, vet in regels]
    return container(nid(), x, y, w, h, {"visualType": "textbox",
                                         "objects": {"general": [{"properties": {"paragraphs": par}}]},
                                         "drillFilterOtherVisuals": True})


def in_filter(entity, prop, waarden, alias="f"):
    return {"Version": 2, "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}}],
                "Values": [[{"Literal": {"Value": w}}] for w in waarden]}}}]}


def filter_max(entity, prop, waarde):
    return {"name": nid(), "field": col(entity, prop), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "f", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {
                           "ComparisonKind": 4,
                           "Left": {"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": prop}},
                           "Right": {"Literal": {"Value": waarde}}}}}]}}


def slicer(x, y, w, h, entity, prop, kop, standaard, groep):
    return container(nid(), x, y, w, h, visual(
        "slicer", {"Values": [proj(col(entity, prop), active=True)]}, kop,
        objects={"data": [{"properties": {"mode": tekst("Basic")}}],
                 "selection": [{"properties": {"singleSelect": lit("true")}}],
                 "general": [{"properties": {"filter": {"filter": in_filter(entity, prop, [standaard], "s")}}}]},
        syncGroup={"groupName": groep, "fieldChanges": True, "filterChanges": True}))


def kaart(x, y, w, h, tabel, maat, kop, fmt=None):
    return container(nid(), x, y, w, h, visual(
        "card", {"Values": [proj(meas(tabel, maat), fmt=fmt)]}, kop,
        objects={"categoryLabels": [{"properties": {"show": lit("false")}}]}))


def breedtes(paren):
    return [{"properties": {"value": lit(f"{b}D")}, "selector": {"metadata": q}} for q, b in paren]


LABELS = {"labels": [{"properties": {"show": lit("true")}}]}
RECHT = {"lineStyles": [{"properties": {"lineChartType": tekst("straight")}}]}
STANDAARD = "'Antwerpen-Centraal'"
BELANGRIJK = ["'Zeer belangrijk station'", "'Belangrijk station'"]


def kop(t, sub, w=1300):
    return tekstvak(40, 20, w, 130, [(t, 28, True), (sub, 16, False)])


def stationslicer():
    s = slicer(1380, 20, 500, 150, "stations", "naam", "Station", STANDAARD, "station")
    s["visual"]["objects"]["data"] = [{"properties": {"mode": tekst("Dropdown")}}]
    return s


def filter_in(entity, prop, waarden):
    return {"name": nid(), "field": col(entity, prop), "type": "Categorical",
            "filter": in_filter(entity, prop, waarden)}


def paginas():
    p = {}
    # ------------------------------------------------------------ Overzicht
    p["Overzicht"] = ([
        kop("Treinstiptheid België",
            "Ruwe stiptheidsgegevens van Infrabel (CC0) · stipt = aankomst met < 6 min vertraging · klik op Vernieuwen voor de laatste dag"),
        stationslicer(),
        kaart(40, 190, 350, 170, "dag_station", "Stiptheid", "Stiptheid station"),
        kaart(410, 190, 350, 170, "dag_station", "Stiptheid netwerk", "Stiptheid netwerk"),
        kaart(780, 190, 350, 170, "dag_station", "Verschil met netwerk (pp)", "Verschil met netwerk (pp)"),
        kaart(1150, 190, 350, 170, "dag_station", "Gem. vertraging (min)", "Gem. vertraging per aankomst (min)"),
        kaart(1520, 190, 360, 170, "dag_station", "Laatste dag", "Gegevens tot en met"),
        container(nid(), 40, 380, 1080, 670, visual(
            "lineChart",
            {"Category": [proj(col("Datum", "Date"), "Datum", active=True)],
             "Y": [proj(meas("dag_station", "Stiptheid"), "Station"),
                   proj(meas("dag_station", "Stiptheid netwerk"), "Netwerk")]},
            "Stiptheid per dag: station tegenover netwerk", objects=RECHT),
            filters=[{"name": nid(), "field": col("Datum", "Date"), "type": "Advanced",
                      "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "Datum", "Type": 0}],
                                 "Where": [{"Condition": {"Comparison": {
                                     "ComparisonKind": 2,
                                     "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Date"}},
                                     "Right": {"Literal": {"Value": "datetime'2026-08-01T00:00:00'"}}}}}]}}]),
        container(nid(), 1160, 380, 720, 670, visual(
            "lineChart",
            {"Category": [proj(col("dag_uur", "uur"), "Gepland aankomstuur", active=True)],
             "Y": [proj(meas("dag_uur", "Stiptheid per uur"), "Station"),
                   proj(meas("dag_uur", "Stiptheid per uur netwerk"), "Netwerk")]},
            "Stiptheid per uur van de dag",
            objects={"lineStyles": [{"properties": {"showMarker": lit("true"), "lineChartType": tekst("straight")}}],
                     "categoryAxis": [{"properties": {"axisType": tekst("Categorical")}}]},
            sort=[{"field": col("dag_uur", "uur"), "direction": "Ascending"}]),
            filters=[filter_in("dag_uur", "uur", [f"{u}L" for u in range(5, 24)])]),
    ], [])

    # ------------------------------------------------------------- Stations
    p["Stations"] = ([
        kop("Stations", "Alle stopplaatsen, gesorteerd van minst naar meest stipt · periode: alle beschikbare dagen", 1840),
        container(nid(), 40, 190, 760, 860, visual(
            "clusteredBarChart",
            {"Category": [proj(col("stations", "naam"), "Station", active=True)],
             "Y": [proj(meas("dag_station", "Stiptheid"), "Stiptheid")]},
            "Grote stations: minst stipt bovenaan", objects=LABELS,
            sort=[{"field": meas("dag_station", "Stiptheid"), "direction": "Ascending"}]),
            filters=[filter_in("stations", "classificatie", BELANGRIJK)]),
        container(nid(), 840, 190, 1040, 860, visual(
            "tableEx",
            {"Values": [proj(col("stations", "naam"), "Station"),
                        proj(col("stations", "classificatie"), "Type"),
                        proj(meas("dag_station", "Aankomsten"), "Aankomsten"),
                        proj(meas("dag_station", "Stiptheid"), "Stiptheid"),
                        proj(meas("dag_station", "Verschil met netwerk (pp)"), "t.o.v. netwerk (pp)"),
                        proj(meas("dag_station", "Gem. vertraging (min)"), "Gem. vertraging (min)"),
                        proj(meas("dag_station", "Zwaar vertraagd"), "≥ 15 min")]},
            "Alle stopplaatsen",
            objects={"total": [{"properties": {"totals": lit("false")}}],
                     "columnWidth": breedtes([("stations.naam", 260), ("stations.classificatie", 200),
                                              ("dag_station.Aankomsten", 120), ("dag_station.Stiptheid", 110),
                                              ("dag_station.Verschil met netwerk (pp)", 140),
                                              ("dag_station.Gem. vertraging (min)", 130),
                                              ("dag_station.Zwaar vertraagd", 90)])},
            sort=[{"field": meas("dag_station", "Stiptheid"), "direction": "Ascending"}])),
    ], [])

    # --------------------------------------------------------------- Lijnen
    p["Lijnen"] = ([
        kop("Treinlijnen", "Stiptheid per relatie (bv. IC 26, S1) en operator · minst stipt bovenaan", 1840),
        container(nid(), 40, 190, 1080, 860, visual(
            "clusteredBarChart",
            {"Category": [proj(col("dag_relatie", "relatie"), "Lijn", active=True)],
             "Y": [proj(meas("dag_relatie", "Stiptheid lijn"), "Stiptheid")]},
            "Stiptheid per lijn", objects=LABELS,
            sort=[{"field": meas("dag_relatie", "Stiptheid lijn"), "direction": "Ascending"}])),
        container(nid(), 1160, 190, 720, 860, visual(
            "tableEx",
            {"Values": [proj(col("dag_relatie", "relatie"), "Lijn"),
                        proj(col("dag_relatie", "operator"), "Operator"),
                        proj(meas("dag_relatie", "Aankomsten lijn"), "Aankomsten"),
                        proj(meas("dag_relatie", "Stiptheid lijn"), "Stiptheid")]},
            "Lijnen in cijfers",
            objects={"total": [{"properties": {"totals": lit("false")}}],
                     "columnWidth": breedtes([("dag_relatie.relatie", 140), ("dag_relatie.operator", 170),
                                              ("dag_relatie.Aankomsten lijn", 150), ("dag_relatie.Stiptheid lijn", 130)])},
            sort=[{"field": meas("dag_relatie", "Stiptheid lijn"), "direction": "Ascending"}])),
    ], [])

    # ---------------------------------------------------- Officieel & validatie
    p["Officieel en validatie"] = ([
        kop("Officiële cijfers en validatie",
            "Officiële maandstiptheid van Infrabel per stopplaats sinds 2023, en de vergelijking met mijn eigen berekening uit de ruwe gegevens"),
        stationslicer(),
        container(nid(), 40, 190, 1080, 430, visual(
            "lineChart",
            {"Category": [proj(col("Datum", "Maand"), "Maand", active=True)],
             "Y": [proj(meas("officieel", "Officiële stiptheid"), "Station"),
                   proj(meas("officieel", "Officiële stiptheid netwerk"), "Netwerk")]},
            "Officiële stiptheid per maand",
            objects={"lineStyles": [{"properties": {"showMarker": lit("true"), "lineChartType": tekst("straight")}}]},
            sort=[{"field": col("Datum", "Maand"), "direction": "Ascending"}])),
        container(nid(), 40, 640, 1080, 410, visual(
            "tableEx",
            {"Values": [proj(col("Datum", "Maand"), "Maand"),
                        proj(meas("dag_station", "Stiptheid"), "Eigen berekening"),
                        proj(meas("officieel", "Officiële stiptheid"), "Officieel (Infrabel)"),
                        proj(meas("officieel", "Verschil eigen - officieel (pp)"), "Verschil (pp)")]},
            "Validatie: eigen berekening tegenover officiële cijfers",
            objects={"total": [{"properties": {"totals": lit("false")}}],
                     "columnWidth": breedtes([("Datum.Maand", 160), ("dag_station.Stiptheid", 200),
                                              ("officieel.Officiële stiptheid", 220),
                                              ("officieel.Verschil eigen - officieel (pp)", 160)])},
            sort=[{"field": col("Datum", "Maand"), "direction": "Descending"}]),
            filters=[{"name": nid(), "field": col("Datum", "Date"), "type": "Advanced",
                      "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "Datum", "Type": 0}],
                                 "Where": [{"Condition": {"Comparison": {
                                     "ComparisonKind": 2,
                                     "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Date"}},
                                     "Right": {"Literal": {"Value": "datetime'2026-08-01T00:00:00'"}}}}}]}}]),
        container(nid(), 1160, 190, 720, 860, visual(
            "clusteredBarChart",
            {"Category": [proj(col("oorzaken", "verantwoordelijk"), "Verantwoordelijk", active=True)],
             "Y": [proj(meas("oorzaken", "Aandeel in verlies"), "Aandeel")]},
            "Oorzaken van stiptheidsverlies (alle maanden sinds 2023)", objects=LABELS,
            sort=[{"field": meas("oorzaken", "Aandeel in verlies"), "direction": "Descending"}]),
            filters=[{"name": nid(), "field": col("Datum", "Date"), "type": "Advanced",
                      "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "Datum", "Type": 0}],
                                 "Where": [{"Condition": {"Comparison": {
                                     "ComparisonKind": 2,
                                     "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Date"}},
                                     "Right": {"Literal": {"Value": "datetime'2023-01-01T00:00:00'"}}}}}]}}]),
    ], [])
    return p


def schrijf_rapport(map_: Path):
    d = map_ / "definition"
    (d / "pages").mkdir(parents=True)
    (map_ / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAAM}.SemanticModel"}}}, indent=2), "utf-8")
    (d / "version.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"}, indent=2), "utf-8")
    basis = "Fluent2-CY26SU10"
    sr = map_ / "StaticResources"
    (sr / "SharedResources" / "BaseThemes").mkdir(parents=True)
    (sr / "RegisteredResources").mkdir(parents=True)
    shutil.copy(PBI / "_bronnen" / f"{basis}.json", sr / "SharedResources" / "BaseThemes" / f"{basis}.json")
    shutil.copy(PBI / "_bronnen" / "thema.json", sr / "RegisteredResources" / "thema.json")
    versie = {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}
    (d / "report.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": basis, "reportVersionAtImport": versie, "type": "SharedResources"},
            "customTheme": {"name": "thema.json", "reportVersionAtImport": versie, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": basis, "path": f"BaseThemes/{basis}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "thema.json", "path": "thema.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}}, indent=2), "utf-8")
    volgorde = []
    for titel_, (visuals, inter) in paginas().items():
        pid = nid()
        volgorde.append(pid)
        pd_ = d / "pages" / pid
        page = {"$schema": PG, "name": pid, "displayName": titel_, "displayOption": "FitToPage",
                "height": 1080, "width": 1920}
        if inter:
            page["visualInteractions"] = inter
        (pd_ / "visuals").mkdir(parents=True)
        (pd_ / "page.json").write_text(json.dumps(page, ensure_ascii=False, indent=2), "utf-8")
        for z, vis in enumerate(visuals):
            vis["position"]["z"] = vis["position"]["tabOrder"] = z * 1000
            vd = pd_ / "visuals" / vis["name"]
            vd.mkdir()
            (vd / "visual.json").write_text(json.dumps(vis, ensure_ascii=False, indent=2), "utf-8")
    (d / "pages" / "pages.json").write_text(json.dumps(
        {"$schema": PM, "pageOrder": volgorde, "activePageName": volgorde[0]}, indent=2), "utf-8")


def synchroniseer(bron: Path, doel: Path):
    """Kopieert de gegenereerde bestanden naar `doel` en verwijdert verouderde bestanden.
    Mappen zelf blijven staan: OneDrive houdt ze soms vast, waardoor rmtree mislukt."""
    nieuw = {f.relative_to(bron) for f in bron.rglob("*") if f.is_file()}
    if doel.exists():
        for f in [f for f in doel.rglob("*") if f.is_file()]:
            if f.relative_to(doel) not in nieuw and ".pbi" not in f.parts:
                f.unlink()
    for rel in nieuw:
        (doel / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bron / rel, doel / rel)
    for d in sorted((d for d in doel.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
        try:
            d.rmdir()                       # alleen lege mappen
        except OSError:
            pass


def main():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        schrijf_model(tmp / f"{NAAM}.SemanticModel")
        schrijf_rapport(tmp / f"{NAAM}.Report")
        for sub in (f"{NAAM}.SemanticModel", f"{NAAM}.Report"):
            synchroniseer(tmp / sub, PBI / sub)
    (PBI / f"{NAAM}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAAM}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2), "utf-8")
    print("Klaar:", PBI / f"{NAAM}.pbip")


if __name__ == "__main__":
    main()
