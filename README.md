# US Political Power

A Streamlit app that ranks US political positions by how much power they hold. It has a searchable ranking, charts, side-by-side comparison, and a full explanation of the method.

## Goal

Most people would guess that the President is the most powerful single position in the US. Few could say where other positions rank. Where do the Vice President, a US Senator, the governor of a large or small state, or the mayor of New York City or Los Angeles fall?

This project ranks positions, not the people who hold them, on two things:

1. **Reach:** the number of people the position represents.
2. **Influence:** a simplified measure of how much the position can actually get done.

Reach alone is not enough. Two mayors of similar-sized cities can hold very different power depending on how the city government is set up. A strong mayor runs the city's departments and budget, while a mayor in a council-manager city may mostly chair the council. Likewise, the Texas Lieutenant Governor represents the same people as the Governor and has unusual control over the state senate, so that position may rank higher than the title suggests.

## Approach

### Positions

The core dataset is a list of positions. Names and party affiliations are not needed for the first version.

| Phase | Positions |
| --- | --- |
| 1. Core | President, Vice President, US Senators, US Representatives, governors, mayors |
| 2. Extended federal | Cabinet secretaries and other top executive branch officials |
| 3. Extended state | Lieutenant governors, other statewide officials, state legislators and legislative leaders |

### Dataset columns

Each row is one position in one jurisdiction, such as "Governor of Texas" or "US Senator from Wyoming". The Phase 1 data is in `data/positions.csv` (637 rows). The influence index is a first cut.

| Column | Description |
| --- | --- |
| `position_id` | Short unique ID for the position |
| `position` | Title of the position |
| `level` | Federal, state, or city |
| `branch` | Executive or legislative |
| `state` | State the position belongs to (blank for President and Vice President) |
| `jurisdiction` | The place the position covers |
| `seats` | How many people hold this position in the jurisdiction (e.g. 2 for a state's US Senators) |
| `people_represented` | Population of the jurisdiction or district |
| `population_year` | Year of the population figure |
| `population_source` | Dataset the population figure came from |
| `unilateral`, `budget`, `appointments`, `agenda`, `decision_share` | Factor scores from 0 to 5 (see below) |
| `influence_index` | Score from 0 to 100 for how much the position can do |
| `influence_notes` | Short reason for the score, with a source |
| `reach_index` | Population on a log scale from 0 to 100 |
| `power_score` | Final score from 0 to 100, combining reach and influence |
| `power_rank` | Rank on `power_score`, where 1 is the most powerful. Positions with the same rounded score share a rank. |
| `power_score_low`, `power_score_high` | Lowest and highest score across all scenarios |
| `power_rank_best`, `power_rank_worst` | Best and worst rank across all scenarios |

### Influence index

This is a first cut, and the scores are judgment calls that should be challenged. Each position gets five factor scores from 0 to 5:

- **Unilateral authority:** can the position act alone, for example through vetoes or executive orders?
- **Budget control:** does it write, approve, or control spending?
- **Appointments:** does it choose who runs agencies and departments?
- **Agenda control:** does it decide what gets considered?
- **Decision share:** how much of the decision does it hold? A sole executive holds all of it, and one of 435 representatives holds very little.

The index is the share of the 25 possible points, scaled by how broad that level of government's powers are:

```
influence_index = 100 x (sum of factors / 25) x scope
```

Scope is 1.0 for federal, 0.8 for state, and 0.5 for city positions. States hold general lawmaking power, while cities have only the powers their state gives them. These multipliers are judgment calls.

The factor scores come from different places:

| Position | Where the scores come from |
| --- | --- |
| President, Vice President, Senators, Representatives | One set of scores per position in `data/inputs/influence_rubric.csv` |
| Governors | Each state's scores from the Beyle index in `data/inputs/beyle_governor_powers_2007.csv`: veto for unilateral authority, budget, appointment, and separately elected officials for decision share. Agenda is a flat 3, since Beyle doesn't measure it. |
| Mayors | One of three sets of scores in the rubric, based on the city's form of government in `data/inputs/city_government_types.csv`: mayor-council, hybrid, or council-manager |

Known limits of the first cut:

- **Governor data is old.** The latest Beyle scores found are from 2007, so some states will have changed.
- **Party control is left out.** Beyle's index includes it, but it depends on who holds office, not on the position. Tenure is left out too, since it doesn't map to any of the five factors.
- **All mayor-council cities score the same.** New York and much smaller strong-mayor cities are identical for now. Charter-level scoring would separate them.
- **Formal powers only.** The index doesn't count informal power, such as the Vice President's role as successor or a Senator's seniority. Every Senator and Representative also scores the same, so leadership roles such as Speaker aren't captured.
- **Some city types are uncertain.** Sources disagree on some cities, and Honolulu and Mesa are unverified. See the `source` and `note` columns of `city_government_types.csv`.

### Overall ranking

The final score combines reach and influence, and `data/positions.csv` is sorted by it. Like the influence index, this is a first cut.

Reach uses a log scale, so each tenfold increase in population adds the same amount. Otherwise the President's 340 million people would swamp everything else. A population of 100,000 scores 0, and the US population scores 100:

```
reach_index = 100 x (log10(people) - log10(100,000)) / (log10(US population) - log10(100,000))
power_score = square root of (reach_index x influence_index)
```

The square root of the product is a geometric mean. Unlike a simple average, it means a position needs both reach and influence to score well: the Vice President has maximum reach but scores 40, because influence is low.

### Scenarios

Some results depend heavily on the formula's assumptions, so the build scores every position under several scenarios. The main columns in `data/positions.csv` use the baseline, and the low, high, best, and worst columns show the range across all scenarios.

Scenarios are defined in `data/inputs/scenarios.csv`, one per row. Each sets the population where reach starts at zero, how much weight influence gets, and the scope multipliers. To add a scenario, add a row and rebuild the dataset. The final score generalizes to:

```
power_score = reach_index ^ (1 - influence_weight) x influence_index ^ influence_weight
```

| Scenario | What changes |
| --- | --- |
| `baseline` | Main method: reach and influence count equally, and reach starts at 100,000 people |
| `low_reach_floor` | Reach starts at 10,000 people |
| `high_reach_floor` | Reach starts at 200,000 people |
| `influence_heavy` | Influence counts twice as much as reach |
| `reach_heavy` | Reach counts twice as much as influence |
| `strong_local` | State and city scope rise to 0.9 and 0.7 |
| `weak_local` | State and city scope fall to 0.7 and 0.3 |

`data/scenario_results.csv` has every position's reach, influence, score, and rank under each scenario.

The ranges show how much a result depends on these assumptions. They are not statistical confidence intervals, and they don't capture uncertainty in the factor scores themselves. Wider or narrower scenarios would give wider or narrower ranges. Scores from different scenarios also aren't on quite the same footing, so ranks are the better way to compare them.

## Planned features

Built so far:

- A ranked table of all positions, filterable by position type and state, with search
- A chart of reach against influence
- A chart of each position's rank range across scenarios
- A scenario selector that re-ranks every position under different assumptions
- Side-by-side comparison of up to five positions
- A page explaining the method and its limits

Possible later extensions:

- Current officeholders' names and party affiliations
- Power by party or by state
- Changes over time

## Data sources

### In use

| Need | Source |
| --- | --- |
| State, city, and national population | [US Census Bureau Population Estimates](https://www.census.gov/programs-surveys/popest.html), Vintage 2025 |
| Congressional district population | US Census Bureau American Community Survey 2024 1-year, table B01003 |
| Governor powers | [Thad Beyle's Gubernatorial Power data](https://web.archive.org/web/2013/http://www.unc.edu/~beyle/gubnewpwr.html), Governors' Institutional Powers 2007 (archived copy). The Oklahoma total in the source reads 175, a typo for 17; totals aren't used here. |
| City form of government | Mainly Wikipedia. City websites, charters, and Ballotpedia were used where Wikipedia was blank or unclear. Each city's source is recorded. |

`scripts/build_positions.py` downloads the Census files and builds the dataset. No API key is needed. The governor and city data are saved in `data/inputs/`.

Choices and limits in the Phase 1 data:

- **Mayors:** the 100 largest cities by population, which is a starting cutoff and easy to change.
- **County-wide mayors:** Honolulu and Baton Rouge use county or parish population, because their mayors govern more than the Census city area. Indianapolis, Louisville, and Nashville use their consolidated city-county population.
- **DC and territories:** the Mayor of DC is included as a city mayor. DC's non-voting delegate and all US territories are left out for now.
- **House districts:** figures use 2024 data and the 119th Congress boundaries, so they are a year older than the other populations. States that have redrawn their maps since then won't match exactly.
- **Senators:** each row is one state with `seats` set to 2, and `people_represented` is the full state population.

### Candidates

These have not been checked or downloaded yet.

| Need | Candidate source |
| --- | --- |
| Newer governor powers | Later Beyle/Ferguson updates in *Politics in the American States*; [The Book of the States](https://bookofthestates.org/), table 4.4 |
| Lieutenant governor powers | [The Book of the States, Lieutenant Governors: Powers and Duties](https://bookofthestates.org/tables/2022-4-14/), which lists who presides, appoints committees, and assigns bills |
| Mayor powers within a form of government | City charters; Morgan and Watson (1996) on mayors' formal powers |
| List of federal positions | [USA.gov](https://www.usa.gov/) and White House listings of the Cabinet |

## Open questions

- **Balancing the two measures:** should reach and influence count equally in the final score? The 100,000 floor also needs lowering if smaller positions, such as state legislators, are added.
- **Weights:** should all five factors count equally? Are the scope multipliers right?
- **Comparing levels:** can one index fairly compare a federal position to a city position? A mayor may control their city more fully than a Senator controls anything, but over far fewer people and with narrower authority.
- **Positions without constituents:** Cabinet secretaries are appointed and don't directly represent anyone. Should their reach be the US population, or the people their department affects?
- **Shared representation:** should a Senator's reach be the whole state, or should it be split with the state's other Senator?
- **Mayor cutoff:** the US has thousands of mayors. The list currently stops at the largest 100 cities. Is that the right place to stop?
- **Territories and DC:** should US territories and non-voting delegates be added?
- **Beyond elected office:** should the list stay with elected and political positions, or later add roles such as Supreme Court justices and the Federal Reserve Chair?

## Running locally

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run streamlit run app.py
```

The app opens in your browser at http://localhost:8501.

To rebuild the dataset:

```sh
uv run python scripts/build_positions.py
```
