from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
INPUTS_DIR = DATA_DIR / "inputs"

LEVEL_COLORS = {"Federal": "#2a78d6", "State": "#eb6834", "City": "#1baf7a"}
TEXT_COLOR = "#0b0b0b"
MUTED_TEXT = "#52514e"
GRID_COLOR = "#e6e5e0"
SURFACE_COLOR = "#fcfcfb"

MAYOR_TYPES = {
    "mayor_council": "Mayor (mayor-council)",
    "hybrid": "Mayor (hybrid)",
    "council_manager": "Mayor (council-manager)",
}
POSITION_TYPES = [
    "President",
    "Vice President",
    "Governor",
    "US Senator",
    "US Representative",
    *MAYOR_TYPES.values(),
]
FACTORS = {
    "unilateral": "Acting alone",
    "budget": "Budget",
    "appointments": "Appointments",
    "agenda": "Agenda",
    "decision_share": "Decision share",
}
SCENARIO_COLUMNS = ["reach_index", "influence_index", "power_score", "power_rank"]

# Labeled on the scatter chart when they pass the current filters.
CHART_LABELS = [
    "president", "vice-president", "governor-ca", "governor-ny", "governor-wy",
    "senator-ca", "senator-wy", "mayor-ny-new-york", "mayor-tx-dallas",
]


def scenario_label(scenario: str) -> str:
    return scenario.replace("_", " ").capitalize()


def display_name(row: pd.Series) -> str:
    match row["position"]:
        case "Governor":
            return f"Governor of {row['jurisdiction']}"
        case "Mayor":
            return f"Mayor of {row['jurisdiction']}"
        case "US Senator" | "US Representative":
            return f"{row['position']}, {row['jurisdiction']}"
        case _:
            return row["position"]


@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    positions = pd.read_csv(DATA_DIR / "positions.csv")
    cities = pd.read_csv(INPUTS_DIR / "city_government_types.csv")

    positions = positions.merge(
        cities[["jurisdiction", "government_type"]], on="jurisdiction", how="left"
    )
    positions["position_type"] = positions["government_type"].map(MAYOR_TYPES).fillna(positions["position"])
    positions["name"] = positions.apply(display_name, axis=1)
    positions["rank_range"] = (
        positions["power_rank_best"].astype(str) + "–" + positions["power_rank_worst"].astype(str)
    )
    return {
        "positions": positions,
        "results": pd.read_csv(DATA_DIR / "scenario_results.csv"),
        "scenarios": pd.read_csv(INPUTS_DIR / "scenarios.csv"),
        "rubric": pd.read_csv(INPUTS_DIR / "influence_rubric.csv"),
    }


def apply_scenario(positions: pd.DataFrame, results: pd.DataFrame, scenario: str) -> pd.DataFrame:
    chosen = results.loc[results["scenario"] == scenario, ["position_id", *SCENARIO_COLUMNS]]
    view = positions.drop(columns=SCENARIO_COLUMNS).merge(chosen, on="position_id")
    return view.sort_values(["power_rank", "people_represented"], ascending=[True, False])


def scatter_chart(view: pd.DataFrame) -> alt.LayerChart:
    tooltip = [
        alt.Tooltip("name:N", title="Position"),
        alt.Tooltip("people_represented:Q", title="People represented", format=","),
        alt.Tooltip("influence_index:Q", title="Influence", format=".1f"),
        alt.Tooltip("power_score:Q", title="Power score", format=".1f"),
        alt.Tooltip("power_rank:Q", title="Rank"),
    ]
    x = alt.X(
        "people_represented:Q",
        title="People represented (log scale)",
        scale=alt.Scale(type="log", domain=[100_000, 500_000_000]),
        axis=alt.Axis(values=[100_000, 1_000_000, 10_000_000, 100_000_000], format="~s"),
    )
    y = alt.Y("influence_index:Q", title="Influence index", scale=alt.Scale(domain=[0, 100]))
    points = (
        alt.Chart(view)
        .mark_circle(size=70, opacity=0.75, stroke=SURFACE_COLOR, strokeWidth=1)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "level:N",
                title="Level of government",
                scale=alt.Scale(domain=list(LEVEL_COLORS), range=list(LEVEL_COLORS.values())),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=tooltip,
        )
    )
    labeled = alt.Chart(view[view["position_id"].isin(CHART_LABELS)]).encode(x=x, y=y, text="name:N")
    text_style = {"align": "left", "dx": 8, "dy": -7, "fontSize": 12}
    # A thick background-colored copy behind each label keeps it readable over dots.
    label_halos = labeled.mark_text(**text_style, stroke=SURFACE_COLOR, strokeWidth=5)
    labels = labeled.mark_text(**text_style, color=TEXT_COLOR)
    return (
        (points + label_halos + labels)
        .properties(height=520)
        .configure_axis(gridColor=GRID_COLOR, labelColor=MUTED_TEXT, titleColor=MUTED_TEXT, domain=False)
        .configure_view(stroke=None)
    )


def range_chart(view: pd.DataFrame) -> alt.LayerChart:
    order = view["name"].tolist()
    y = alt.Y("name:N", title=None, sort=order, axis=alt.Axis(labelLimit=280))
    tooltip = [
        alt.Tooltip("name:N", title="Position"),
        alt.Tooltip("power_rank:Q", title="Rank in this scenario"),
        alt.Tooltip("power_rank_best:Q", title="Best rank"),
        alt.Tooltip("power_rank_worst:Q", title="Worst rank"),
    ]
    bars = (
        alt.Chart(view)
        .mark_rule(strokeWidth=3, color="#9dc3f0")
        .encode(
            x=alt.X(
                "power_rank_best:Q",
                title="Rank (1 is the most powerful)",
                axis=alt.Axis(orient="top", tickCount=6),
                scale=alt.Scale(domain=[0, int(view["power_rank_worst"].max())], nice=False),
            ),
            x2="power_rank_worst:Q",
            y=y,
            tooltip=tooltip,
        )
    )
    dots = (
        alt.Chart(view)
        .mark_circle(size=80, opacity=1, color=LEVEL_COLORS["Federal"], stroke=SURFACE_COLOR, strokeWidth=1)
        .encode(x="power_rank:Q", y=y, tooltip=tooltip)
    )
    return (
        (bars + dots)
        .properties(height=max(120, 24 * len(view)))
        .configure_axis(gridColor=GRID_COLOR, labelColor=MUTED_TEXT, titleColor=MUTED_TEXT, domain=False)
        .configure_view(stroke=None)
    )


def show_rankings(view: pd.DataFrame) -> None:
    table = view[[
        "power_rank", "name", "power_score", "rank_range", "people_represented",
        "reach_index", "influence_index", "position_type", "influence_notes",
    ]]
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=620,
        column_config={
            "power_rank": st.column_config.NumberColumn(
                "Rank", help="Rank among all 637 positions, even when filters are on. 1 is the most powerful."
            ),
            "name": st.column_config.TextColumn("Position", width="medium"),
            "power_score": st.column_config.ProgressColumn(
                "Power score", help="Combines reach and influence. See How it works.",
                min_value=0, max_value=100, format="%.1f",
            ),
            "rank_range": st.column_config.TextColumn(
                "Rank range", help="Best and worst rank across all scenarios."
            ),
            "people_represented": st.column_config.NumberColumn(
                "People represented", help="Population of the position's jurisdiction.", format="localized"
            ),
            "reach_index": st.column_config.NumberColumn(
                "Reach", help="Population on a log scale from 0 to 100.", format="%.1f"
            ),
            "influence_index": st.column_config.NumberColumn(
                "Influence", help="How much the position can do, from 0 to 100.", format="%.1f"
            ),
            "position_type": st.column_config.TextColumn("Type"),
            "influence_notes": st.column_config.TextColumn("Why this influence score", width="large"),
        },
    )


def show_compare(positions: pd.DataFrame, results: pd.DataFrame, scenarios: pd.DataFrame) -> None:
    st.write("Pick positions to compare side by side. This list ignores the sidebar filters.")
    defaults = ["Governor of Texas", "Mayor of New York, NY", "US Senator, California", "Vice President"]
    names = st.multiselect(
        "Positions", positions["name"].tolist(), default=defaults, max_selections=5
    )
    if not names:
        st.info("Choose at least one position.")
        return

    chosen = positions.set_index("name").loc[names]
    rows = {
        "Rank": chosen["power_rank"].astype(str),
        "Rank range": chosen["rank_range"],
        "Power score": chosen["power_score"].map("{:.1f}".format),
        "People represented": chosen["people_represented"].map("{:,}".format),
        "Reach": chosen["reach_index"].map("{:.1f}".format),
        "Influence": chosen["influence_index"].map("{:.1f}".format),
    }
    rows |= {label: chosen[factor].map("{:g} / 5".format) for factor, label in FACTORS.items()}
    st.dataframe(pd.DataFrame(rows).T, width="stretch")

    st.subheader("Rank under each scenario")
    by_scenario = (
        results[results["position_id"].isin(chosen["position_id"])]
        .merge(positions[["position_id", "name"]], on="position_id")
        .pivot(index="scenario", columns="name", values="power_rank")
        .reindex(index=scenarios["scenario"], columns=names)
        .rename(index=scenario_label)
        .rename_axis(index="Scenario", columns=None)
    )
    st.dataframe(by_scenario, width="stretch")

    st.subheader("Why these influence scores")
    for name, notes in chosen["influence_notes"].items():
        st.markdown(f"**{name}:** {notes}")


def show_method(data: dict[str, pd.DataFrame]) -> None:
    positions, rubric, scenarios = data["positions"], data["rubric"], data["scenarios"]
    baseline = scenarios.iloc[0]
    example = positions.set_index("position_id").loc["governor-tx"]

    st.header("How it works")
    st.write(
        "Each position gets two measures, **reach** and **influence**, which are combined "
        "into one **power score**. This is a first cut built on simplified assumptions, and "
        "many inputs are judgment calls. Rankings cover positions, not the people holding them."
    )

    st.subheader("Step 1: Reach")
    st.write(
        "Reach is the number of people the position represents, on a log scale from 0 to 100. "
        "On a log scale, every tenfold increase in population adds the same number of points. "
        f"A population of {baseline['reach_floor']:,.0f} scores 0, and the US population scores 100."
    )
    st.latex(r"\text{reach} = 100 \times \frac{\log_{10}(\text{people}) - \log_{10}(100{,}000)}{\log_{10}(\text{US population}) - \log_{10}(100{,}000)}")

    st.subheader("Step 2: Influence")
    st.write("Each position is scored from 0 to 5 on five factors:")
    st.markdown(
        "- **Acting alone:** can it act by itself, for example with a veto or executive order?\n"
        "- **Budget:** does it write, approve, or control spending?\n"
        "- **Appointments:** does it choose who runs agencies and departments?\n"
        "- **Agenda:** does it decide what gets considered?\n"
        "- **Decision share:** how much of the decision does it hold? A sole executive holds "
        "all of it, and one of 435 Representatives holds very little."
    )
    st.write(
        "The index is the share of the 25 possible points, multiplied by the **scope** of that "
        "level of government. States have general lawmaking power, while cities have only the "
        "powers their state gives them."
    )
    st.latex(r"\text{influence} = 100 \times \frac{\text{sum of the five factors}}{25} \times \text{scope}")
    st.dataframe(
        pd.DataFrame({
            "Level": ["Federal", "State", "City"],
            "Scope": [baseline["scope_federal"], baseline["scope_state"], baseline["scope_city"]],
        }),
        hide_index=True,
    )

    st.write("**Where the factor scores come from**")
    st.markdown(
        "- **Federal positions:** one set of scores per position, which are judgment calls.\n"
        "- **Mayors:** one of three sets of scores, based on the city's form of government. "
        "In a mayor-council city, the mayor runs the government. In a council-manager city, "
        "an appointed manager does. Hybrid cities split that power.\n"
        "- **Governors:** each state's own scores from Thad Beyle's index of governors' "
        "institutional powers (2007). Veto power stands in for acting alone, and the number of "
        "separately elected officials stands in for decision share. Beyle doesn't measure "
        "agenda power, so every governor gets a 3."
    )
    labels = {
        "mayor_council": "Mayor, mayor-council city",
        "hybrid": "Mayor, hybrid city",
        "council_manager": "Mayor, council-manager city",
    }
    st.table(
        rubric.assign(group=rubric["group"].replace(labels))
        .rename(columns={"group": "Position", "reason": "Reason", **FACTORS})
        .set_index("Position")
    )

    st.subheader("Step 3: Power score")
    st.write(
        "The power score is the geometric mean of reach and influence. Unlike a simple average, "
        "this means a position needs both to score well."
    )
    st.latex(r"\text{power score} = \sqrt{\text{reach} \times \text{influence}}")
    st.write(
        f"**Example:** the Governor of Texas has a reach of {example['reach_index']:.1f} and "
        f"an influence of {example['influence_index']:.1f}, so the power score is "
        f"√({example['reach_index']:.1f} × {example['influence_index']:.1f}) = "
        f"{example['power_score']:.1f}. That ranks number {example['power_rank']} of {len(positions)}."
    )

    st.subheader("Scenarios and rank ranges")
    st.write(
        "The formula rests on assumptions, so every position is also scored under the scenarios "
        "below. **Rank range** shows its best and worst rank across all of them. A narrow range "
        "means the result holds up, and a wide one means it depends on the assumptions."
    )
    st.table(
        scenarios.assign(
            scenario=scenarios["scenario"].map(scenario_label),
            reach_floor=scenarios["reach_floor"].map("{:,}".format),
            influence_weight=scenarios["influence_weight"].map("{:.2f}".format),
            scope_federal=scenarios["scope_federal"].map("{:.1f}".format),
            scope_state=scenarios["scope_state"].map("{:.1f}".format),
            scope_city=scenarios["scope_city"].map("{:.1f}".format),
        )
        .rename(columns={
            "scenario": "Scenario", "description": "What changes", "reach_floor": "Reach starts at",
            "influence_weight": "Influence weight", "scope_federal": "Federal scope",
            "scope_state": "State scope", "scope_city": "City scope",
        })
        .set_index("Scenario")
    )
    st.write(
        "With an influence weight other than 0.5, the score is "
        "reach^(1 − weight) × influence^weight. "
        "These ranges are not statistical confidence intervals. They only reflect the chosen "
        "scenarios, and they don't account for errors in the factor scores."
    )

    st.subheader("What's included")
    st.markdown(
        "- President, Vice President, US Senators, US Representatives, governors, and the "
        "mayors of the 100 largest cities (including DC).\n"
        "- Each state's two Senators share one row, and each is credited with the full state population.\n"
        "- Honolulu and Baton Rouge use county or parish population, since their mayors govern that wider area.\n"
        "- Not yet included: the Cabinet, lieutenant governors, state legislators, courts, "
        "non-voting delegates, and US territories."
    )

    st.subheader("Known limits")
    st.markdown(
        "- **Formal powers only.** The index leaves out informal power, including the Vice "
        "President's place in the line of succession. Every Senator and Representative scores "
        "the same, so roles like Speaker aren't captured.\n"
        "- **Governor data is from 2007,** the latest found, so some states will have changed.\n"
        "- **All mayors of the same city type score the same.** The New York mayor's influence "
        "equals that of any other mayor-council city.\n"
        "- **Some city types are uncertain.** Sources disagree on a few cities, and Honolulu and "
        "Mesa are unverified. Oakland held a strong-mayor vote in November 2026, and the result "
        "isn't reflected here.\n"
        "- **Party control and term length are left out.** Party control depends on who holds "
        "office, not on the position."
    )

    st.subheader("Data sources")
    st.markdown(
        "- **Population:** [US Census Bureau Population Estimates](https://www.census.gov/programs-surveys/popest.html), "
        "Vintage 2025. House districts use the American Community Survey 2024 1-year estimates "
        "on 119th Congress boundaries.\n"
        "- **Governor powers:** [Thad Beyle's Gubernatorial Power data](https://web.archive.org/web/2013/http://www.unc.edu/~beyle/gubnewpwr.html), 2007.\n"
        "- **City form of government:** mainly Wikipedia, with city websites, charters, and "
        "Ballotpedia used where Wikipedia was blank or unclear."
    )


st.set_page_config(page_title="US Political Power", page_icon="🏛️", layout="wide")

data = load_data()
positions, results, scenarios = data["positions"], data["results"], data["scenarios"]

st.title("US Political Power")
st.write(
    "The President is probably the most powerful position in the US. But where do a Senator, "
    "a governor, or a big-city mayor rank? This app ranks 637 positions, not the people who hold them."
)

with st.container(border=True):
    st.markdown("**How the ranking works**")
    reach_col, influence_col, power_col = st.columns(3)
    reach_col.markdown("**Reach (0–100)**  \nHow many people the position represents, on a log scale.")
    influence_col.markdown(
        "**Influence (0–100)**  \nHow much it can do: acting alone, budget, appointments, agenda, "
        "and decision share, adjusted for level of government."
    )
    power_col.markdown(
        "**Power score (0–100)**  \nThe geometric mean of the two, so a position needs both to score well."
    )
    st.caption(
        "This is a first cut, and many scores are judgment calls. Rank range shows how far a "
        "rank moves under other assumptions. Full details are in the How it works tab."
    )

with st.sidebar:
    st.header("Scenario")
    scenario = st.selectbox("Assumptions", scenarios["scenario"].tolist(), format_func=scenario_label)
    st.caption(scenarios.set_index("scenario").loc[scenario, "description"])

    st.header("Filters")
    types = st.multiselect("Position type", POSITION_TYPES, placeholder="All position types")
    states = st.multiselect(
        "State", sorted(positions["state"].dropna().unique()), placeholder="All states"
    )
    search = st.text_input("Search", placeholder="e.g. Chicago")
    st.caption(
        "Filters don't change ranks, which always compare all 637 positions. Filtering by state "
        "hides the President and Vice President."
    )

view = apply_scenario(positions, results, scenario)
filtered = view
if types:
    filtered = filtered[filtered["position_type"].isin(types)]
if states:
    filtered = filtered[filtered["state"].isin(states)]
if search:
    filtered = filtered[filtered["name"].str.contains(search, case=False, regex=False)]

rankings_tab, chart_tab, range_tab, compare_tab, method_tab = st.tabs(
    ["Rankings", "Reach vs. influence", "Rank ranges", "Compare", "How it works"]
)

with rankings_tab:
    st.caption(f"Showing {len(filtered)} of {len(view)} positions, using the {scenario_label(scenario).lower()} scenario.")
    if filtered.empty:
        st.info("No positions match these filters.")
    else:
        show_rankings(filtered)

with chart_tab:
    st.subheader("Which positions have reach, and which have real influence?")
    st.write(
        "Each dot is a position. Higher means more influence, and further right means more people. "
        "Many dots overlap because positions of the same type can share an influence score. "
        "Hover over a dot for details."
    )
    if filtered.empty:
        st.info("No positions match these filters.")
    else:
        st.altair_chart(scatter_chart(filtered), width="stretch")

with range_tab:
    st.subheader("How much does each rank depend on the assumptions?")
    st.write(
        "The dot is the rank under the selected scenario, and the line runs from the best to the "
        "worst rank across all scenarios. Long lines mean less certain rankings. "
        "This chart shows the top 30 positions that match the filters."
    )
    if filtered.empty:
        st.info("No positions match these filters.")
    else:
        st.altair_chart(range_chart(filtered.head(30)), width="stretch")

with compare_tab:
    show_compare(view, results, scenarios)

with method_tab:
    show_method(data)
