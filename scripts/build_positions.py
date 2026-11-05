"""Build data/positions.csv: the Phase 1 positions, influence index, and power ranking.

Run from the project root:

    uv run python scripts/build_positions.py

Raw Census files are downloaded to data/raw/ on the first run and reused after
that. Delete that folder to download fresh copies.

The influence index is built from the hand-maintained files in data/inputs/.
See the "Influence index" section of the README for the method.
"""

import math
import re
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
INPUTS_DIR = ROOT / "data" / "inputs"
OUTPUT = ROOT / "data" / "positions.csv"
SCENARIO_OUTPUT = ROOT / "data" / "scenario_results.csv"

POPEST = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025"
ACS = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/1YRData"
SOURCES = {
    "states.csv": f"{POPEST}/state/totals/NST-EST2025-ALLDATA.csv",
    "places.csv": f"{POPEST}/cities/totals/sub-est2025.csv",
    "acs_population.dat": f"{ACS}/acsdt1y2024-b01003.dat",
}

POPEST_SOURCE = "Census Population Estimates, Vintage 2025"
ACS_SOURCE = "Census ACS 1-year 2024, table B01003"

MAYOR_COUNT = 100

FACTORS = ["unilateral", "budget", "appointments", "agenda", "decision_share"]
MAX_FACTOR_SCORE = 5

# Beyle's index has no measure of a governor's agenda power, so every governor
# gets the same score for it.
GOVERNOR_AGENDA_SCORE = 3

STATE_ABBREVIATIONS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

# Census names that the general clean-up rule in clean_city_name can't handle.
CITY_NAME_FIXES = {
    "Boise City": "Boise",
    "Lexington-Fayette": "Lexington",
    "Louisville/Jefferson County": "Louisville",
    "Nashville-Davidson": "Nashville",
    "Urban Honolulu": "Honolulu",
}

# Mayors who govern a whole county, while the Census "place" covers only part
# of it. Maps (city, state) to the county row to use for population instead.
COUNTY_WIDE_MAYORS = {
    ("Honolulu", "Hawaii"): "Honolulu County",
    ("Baton Rouge", "Louisiana"): "East Baton Rouge Parish",
}


def download_raw_files() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in SOURCES.items():
        path = RAW_DIR / filename
        if not path.exists():
            print(f"Downloading {url}")
            request = urllib.request.Request(
                url, headers={"User-Agent": "us-political-power-data-build"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                path.write_bytes(response.read())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def row(position_id, position, level, branch, state, jurisdiction, seats, people, year, source):
    return {
        "position_id": position_id,
        "position": position,
        "level": level,
        "branch": branch,
        "state": state,
        "jurisdiction": jurisdiction,
        "seats": seats,
        "people_represented": int(people),
        "population_year": year,
        "population_source": source,
    }


def federal_and_state_rows(states: pd.DataFrame) -> list[dict]:
    us_population = states.loc[states["SUMLEV"] == "010", "POPESTIMATE2025"].iloc[0]
    rows = [
        row("president", "President", "Federal", "Executive", None, "United States",
            1, us_population, 2025, POPEST_SOURCE),
        row("vice-president", "Vice President", "Federal", "Executive", None, "United States",
            1, us_population, 2025, POPEST_SOURCE),
    ]

    # Only the 50 states have Senators and governors, so DC and Puerto Rico drop out.
    state_rows = states[(states["SUMLEV"] == "040") & (states["NAME"].isin(STATE_ABBREVIATIONS))]
    state_rows = state_rows[state_rows["NAME"] != "District of Columbia"]
    for state, people in zip(state_rows["NAME"], state_rows["POPESTIMATE2025"]):
        abbr = STATE_ABBREVIATIONS[state].lower()
        rows.append(row(f"senator-{abbr}", "US Senator", "Federal", "Legislative", state,
                        state, 2, people, 2025, POPEST_SOURCE))
        rows.append(row(f"governor-{abbr}", "Governor", "State", "Executive", state,
                        state, 1, people, 2025, POPEST_SOURCE))
    return rows


def house_rows(states: pd.DataFrame) -> list[dict]:
    acs = pd.read_csv(RAW_DIR / "acs_population.dat", sep="|", dtype=str)
    districts = acs[acs["GEO_ID"].str.startswith("5001900US")].copy()
    districts["fips"] = districts["GEO_ID"].str[-4:-2]
    districts["district"] = districts["GEO_ID"].str[-2:]

    # Code 98 marks non-voting delegates (DC and Puerto Rico).
    districts = districts[districts["district"] != "98"]

    fips_to_state = dict(
        zip(states.loc[states["SUMLEV"] == "040", "STATE"],
            states.loc[states["SUMLEV"] == "040", "NAME"])
    )
    rows = []
    for fips, district, people in zip(
        districts["fips"], districts["district"], districts["B01003_E001"]
    ):
        state = fips_to_state[fips]
        abbr = STATE_ABBREVIATIONS[state].lower()
        at_large = district == "00"
        label = "At-Large" if at_large else f"District {int(district)}"
        position_id = f"rep-{abbr}-{'at-large' if at_large else district}"
        rows.append(row(position_id, "US Representative", "Federal", "Legislative", state,
                        f"{state} {label}", 1, people, 2024, ACS_SOURCE))
    return rows


def clean_city_name(census_name: str) -> str:
    # Census names end in the type of government, e.g. "Chicago city".
    name = re.sub(
        r"\s+(city|town|village|CDP|municipality|urban county|metro government"
        r"|metropolitan government)$",
        "",
        census_name,
    )
    return CITY_NAME_FIXES.get(name, name)


def mayor_rows() -> list[dict]:
    places = pd.read_csv(RAW_DIR / "places.csv", dtype=str, encoding="latin-1")
    places["people"] = places["POPESTIMATE2025"].astype(int)

    # 162 = city or town. 170 = consolidated city-county. "(balance)" rows are
    # a consolidated city minus its smaller towns, so they would double count.
    cities = places[
        places["SUMLEV"].isin(["162", "170"])
        & ~places["NAME"].str.contains(r"\(balance\)", regex=True)
    ].copy()
    cities["city"] = cities["NAME"].map(clean_city_name)

    for (city, state), county in COUNTY_WIDE_MAYORS.items():
        county_people = places.loc[
            (places["SUMLEV"] == "050") & (places["NAME"] == county) & (places["STNAME"] == state),
            "people",
        ].iloc[0]
        cities.loc[(cities["city"] == city) & (cities["STNAME"] == state), "people"] = county_people

    largest = cities.sort_values("people", ascending=False).head(MAYOR_COUNT)

    rows = []
    for city, state, people in zip(largest["city"], largest["STNAME"], largest["people"]):
        abbr = STATE_ABBREVIATIONS[state]
        rows.append(row(f"mayor-{abbr.lower()}-{slugify(city)}", "Mayor", "City", "Executive",
                        state, f"{city}, {abbr}", 1, people, 2025, POPEST_SOURCE))
    return rows


def governor_factors() -> pd.DataFrame:
    """Map Beyle's governor scores onto the five influence factors."""
    beyle = pd.read_csv(INPUTS_DIR / "beyle_governor_powers_2007.csv")
    abbr_to_state = {abbr: state for state, abbr in STATE_ABBREVIATIONS.items()}
    return pd.DataFrame({
        "jurisdiction": beyle["state_abbr"].map(abbr_to_state),
        "unilateral": beyle["veto"],
        "budget": beyle["budget"],
        "appointments": beyle["appointment"],
        "agenda": GOVERNOR_AGENDA_SCORE,
        "decision_share": beyle["separately_elected"],
        "influence_notes": "Scores from the Beyle index of governors' institutional powers (2007): "
                           "veto, budget, appointment, and separately elected officials. "
                           "Agenda is a flat score for all governors.",
    })


def influence_for(positions: pd.DataFrame, scenario: pd.Series) -> pd.Series:
    """Share of the possible factor points, scaled by the scope of each level."""
    control = positions[FACTORS].sum(axis=1) / (len(FACTORS) * MAX_FACTOR_SCORE)
    scope = positions["level"].map({
        "Federal": scenario["scope_federal"],
        "State": scenario["scope_state"],
        "City": scenario["scope_city"],
    })
    return (100 * control * scope).round(1)


def add_influence(positions: pd.DataFrame) -> pd.DataFrame:
    rubric = pd.read_csv(INPUTS_DIR / "influence_rubric.csv").set_index("group")
    cities = pd.read_csv(INPUTS_DIR / "city_government_types.csv").fillna("")
    cities = cities.set_index("jurisdiction")
    governors = governor_factors().set_index("jurisdiction")

    missing = set(positions.loc[positions["position"] == "Mayor", "jurisdiction"]) - set(cities.index)
    assert not missing, f"Add these cities to city_government_types.csv: {sorted(missing)}"

    def score(position: pd.Series) -> pd.Series:
        if position["position"] == "Governor":
            return governors.loc[position["jurisdiction"], FACTORS + ["influence_notes"]]
        if position["position"] == "Mayor":
            city = cities.loc[position["jurisdiction"]]
            factors = rubric.loc[city["government_type"], FACTORS]
            notes = f"{city['government_type']} (source: {city['source']}). {city['note']}".strip()
            return pd.concat([factors, pd.Series({"influence_notes": notes})])
        factors = rubric.loc[position["position"], FACTORS]
        reason = rubric.loc[position["position"], "reason"]
        return pd.concat([factors, pd.Series({"influence_notes": reason})])

    scores = positions.apply(score, axis=1)
    scores[FACTORS] = scores[FACTORS].astype(float)
    return pd.concat([positions, scores[FACTORS + ["influence_notes"]]], axis=1)


def score_scenario(positions: pd.DataFrame, scenario: pd.Series) -> pd.DataFrame:
    """Score and rank every position under one scenario."""
    floor = scenario["reach_floor"]
    assert floor < positions["people_represented"].min(), "reach_floor is above the smallest position"
    top = math.log10(positions["people_represented"].max())
    log_people = positions["people_represented"].map(math.log10)
    reach = 100 * (log_people - math.log10(floor)) / (top - math.log10(floor))
    influence = influence_for(positions, scenario)

    # Weighted geometric mean: a position needs both reach and influence to score well.
    weight = scenario["influence_weight"]
    score = (reach.pow(1 - weight) * influence.pow(weight)).round(1)
    return pd.DataFrame({
        "position_id": positions["position_id"],
        "scenario": scenario["scenario"],
        "reach_index": reach.round(1),
        "influence_index": influence,
        "power_score": score,
        "power_rank": score.rank(method="min", ascending=False).astype(int),
    })


def add_power(positions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add baseline scores and scenario ranges. Also return all scenario results."""
    scenarios = pd.read_csv(INPUTS_DIR / "scenarios.csv")
    assert scenarios["scenario"].iloc[0] == "baseline", "First scenario must be the baseline"
    results = pd.concat(
        [score_scenario(positions, scenario) for _, scenario in scenarios.iterrows()],
        ignore_index=True,
    )

    baseline = results[results["scenario"] == "baseline"].drop(columns="scenario")
    ranges = results.groupby("position_id").agg(
        power_score_low=("power_score", "min"),
        power_score_high=("power_score", "max"),
        power_rank_best=("power_rank", "min"),
        power_rank_worst=("power_rank", "max"),
    )
    positions = positions.merge(baseline, on="position_id").merge(ranges, on="position_id")
    return positions, results


def check(positions: pd.DataFrame) -> None:
    counts = positions["position"].value_counts().to_dict()
    expected = {
        "President": 1, "Vice President": 1, "US Senator": 50,
        "US Representative": 435, "Governor": 50, "Mayor": MAYOR_COUNT,
    }
    assert counts == expected, f"Unexpected row counts: {counts}"
    assert positions["position_id"].is_unique, "Duplicate position_id values"
    assert positions["jurisdiction"].notna().all()
    assert (positions["people_represented"] > 0).all()
    assert positions["influence_index"].between(0, 100).all()
    assert positions["reach_index"].between(0, 100).all()
    assert positions["power_score"].between(0, 100).all()
    assert positions[FACTORS].stack().between(0, MAX_FACTOR_SCORE).all()

    # Districts are drawn from the same people as the states, so these should nearly match.
    house_total = positions.loc[positions["position"] == "US Representative", "people_represented"].sum()
    state_total = positions.loc[positions["position"] == "Governor", "people_represented"].sum()
    assert abs(house_total / state_total - 1) < 0.02, (house_total, state_total)


def main() -> None:
    download_raw_files()
    states = pd.read_csv(RAW_DIR / "states.csv", dtype=str, encoding="latin-1")
    states["POPESTIMATE2025"] = states["POPESTIMATE2025"].astype(int)

    positions = pd.DataFrame(
        federal_and_state_rows(states) + house_rows(states) + mayor_rows()
    )
    positions, results = add_power(add_influence(positions))
    check(positions)
    positions = positions.sort_values(
        ["power_rank", "people_represented"], ascending=[True, False], kind="stable"
    )
    positions.to_csv(OUTPUT, index=False)
    results.to_csv(SCENARIO_OUTPUT, index=False)
    print(f"Wrote {len(positions)} positions to {OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {len(results)} scenario results to {SCENARIO_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
