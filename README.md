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
| 2. Extended federal | Congressional leaders, selected Cabinet secretaries, White House roles, the Supreme Court, the Federal Reserve Chair, and the Chairman of the Joint Chiefs |
| 3. Extended state | Lieutenant governors, other statewide officials, state legislators and legislative leaders |

### Dataset columns

Each row is one position in one jurisdiction, such as "Governor of Texas". Rank-and-file Senators and Representatives each share one row. The data is in `data/positions.csv` (172 rows). The influence index is a first cut.

| Column | Description |
| --- | --- |
| `position_id` | Short unique ID for the position |
| `position` | Title of the position |
| `category` | Group for national positions, such as Cabinet secretary (blank for others) |
| `power_source` | Where the power comes from: own, president, or congress |
| `level` | Federal, state, or city |
| `branch` | Executive, legislative, judicial, or independent |
| `state` | State the position belongs to (blank for President and Vice President) |
| `jurisdiction` | The place the position covers |
| `seats` | How many people hold this position in the jurisdiction (e.g. 100 for US Senators) |
| `people_represented` | Population of the jurisdiction. National positions use the US population divided by the number of people sharing that power. |
| `population_year` | Year of the population figure |
| `population_source` | Dataset the population figure came from |
| `unilateral`, `budget`, `appointments`, `agenda`, `decision_share` | Factor scores from 0 to 5 (see below) |
| `influence_index` | Score from 0 to 100 for how much the position can do |
| `influence_notes` | Short reason for the score, with a source |
| `reach_index` | Cube root of the share of the US population, from 0 to 100 |
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

The index is the share of the 25 possible points, scaled by how broad that level of government's powers are and by a borrowed-power discount:

```
influence_index = 100 x (sum of factors / 25) x scope x discount
```

The discount reflects that some power belongs to someone else. Presidential appointees keep 70% of their influence, because they act on the President's authority and can be removed. Congressional leaders keep 85%, because they need the support of members. Everyone else keeps 100%.

Scope is 1.0 for federal, 0.8 for state, and 0.5 for city positions. States hold general lawmaking power, while cities have only the powers their state gives them. These multipliers are judgment calls.

The factor scores come from different places:

| Position | Where the scores come from |
| --- | --- |
| Federal positions | One set of scores per position in `data/inputs/influence_rubric.csv`. National positions are listed in `data/inputs/national_positions.csv`. |
| Governors | Each state's scores from the Beyle index in `data/inputs/beyle_governor_powers_2007.csv`: veto for unilateral authority, budget, appointment, and separately elected officials for decision share. Agenda is a flat 3, since Beyle doesn't measure it. |
| Mayors | One of three sets of scores in the rubric, based on the city's form of government in `data/inputs/city_government_types.csv`: mayor-council, hybrid, or council-manager |

Known limits of the first cut:

- **National reach shares are judgment calls, and they matter.** They set much of the order at the top of the ranking. So do the borrowed-power discounts. An appointee's dependence on the President lowers decision share, reach, and the discount, so it counts more than once.
- **The five factors fit some roles poorly.** They don't capture the Supreme Court's final say or the Federal Reserve's power over interest rates.
- **Governor data is old.** The latest Beyle scores found are from 2007, so some states will have changed.
- **Party control is left out.** Beyle's index includes it, but it depends on who holds office, not on the position. Tenure is left out too, since it doesn't map to any of the five factors.
- **All mayor-council cities score the same.** New York and much smaller strong-mayor cities are identical for now. Charter-level scoring would separate them.
- **Formal powers only.** The index doesn't count informal power, such as the Vice President's role as successor or a member of Congress's seniority.
- **Some city types are uncertain.** Sources disagree on some cities, and Honolulu and Mesa are unverified. See the `source` and `note` columns of `city_government_types.csv`.

### Overall ranking

The final score combines reach and influence, and `data/positions.csv` is sorted by it. Like the influence index, this is a first cut.

Reach uses a cube root of the position's share of the US population. Raw population would swamp everything else, since the President represents about 580 times as many people as Wyoming's governor. A cube root reduces that to 8.3 times. A log scale was tried first, but it reduced the gap to 4.6 times and needed an arbitrary starting point.

```
reach_index = 100 x (people / US population) ^ (1/3)
power_score = square root of (reach_index x influence_index)
```

The square root of the product is a geometric mean. Unlike a simple average, it means a position needs both reach and influence to score well: the Vice President has maximum reach but scores 40, because influence is low.

### Scenarios

Some results depend heavily on the formula's assumptions, so the build scores every position under several scenarios. The main columns in `data/positions.csv` use the baseline, and the low, high, best, and worst columns show the range across all scenarios.

Scenarios are defined in `data/inputs/scenarios.csv`, one per row. Each sets the root used for reach, how much weight influence gets, the scope multipliers, and the borrowed-power discounts. To add a scenario, add a row and rebuild the dataset. The final score generalizes to:

```
power_score = reach_index ^ (1 - influence_weight) x influence_index ^ influence_weight
```

| Scenario | What changes |
| --- | --- |
| `baseline` | Main method: reach uses a cube root, and reach and influence count equally |
| `flatter_reach` | Reach uses a fourth root |
| `steeper_reach` | Reach uses a square root |
| `influence_heavy` | Influence counts twice as much as reach |
| `reach_heavy` | Reach counts twice as much as influence |
| `strong_local` | State and city scope rise to 0.9 and 0.7 |
| `weak_local` | State and city scope fall to 0.7 and 0.3 |
| `no_discount` | Appointees and congressional leaders keep all of their influence |
| `heavy_discount` | Appointees keep 50% of their influence, and congressional leaders keep 70% |

`data/scenario_results.csv` has every position's reach, influence, score, and rank under each scenario.

The ranges show how much a result depends on these assumptions. They are not statistical confidence intervals, and they don't capture uncertainty in the factor scores themselves. Wider or narrower scenarios would give wider or narrower ranges. Scores from different scenarios also aren't on quite the same footing, so ranks are the better way to compare them.

## Planned features

Built so far:

- A ranked table of all positions, filterable by position type and state, with search
- A category view that collapses positions into groups such as US Senate and State Governor
- A chart of reach against influence
- A chart of each position's rank range across scenarios
- A scenario selector that re-ranks every position under different assumptions
- Side-by-side comparison of up to five positions
- A separate Methodology page explaining the method, its limits, and common questions

Possible later extensions:

- Current officeholders' names and party affiliations
- Power by party or by state
- Changes over time

## Data sources

### In use

| Need | Source |
| --- | --- |
| State, city, and national population | [US Census Bureau Population Estimates](https://www.census.gov/programs-surveys/popest.html), Vintage 2025 |
| Governor powers | [Thad Beyle's Gubernatorial Power data](https://web.archive.org/web/2013/http://www.unc.edu/~beyle/gubnewpwr.html), Governors' Institutional Powers 2007 (archived copy). The Oklahoma total in the source reads 175, a typo for 17; totals aren't used here. |
| City form of government | Mainly Wikipedia. City websites, charters, and Ballotpedia were used where Wikipedia was blank or unclear. Each city's source is recorded. |

`scripts/build_positions.py` downloads the Census files and builds the dataset. No API key is needed. The governor and city data are saved in `data/inputs/`.

Choices and limits in the Phase 1 data:

- **Mayors:** the 100 largest cities by population, which is a starting cutoff and easy to change.
- **County-wide mayors:** Honolulu and Baton Rouge use county or parish population, because their mayors govern more than the Census city area. Indianapolis, Louisville, and Nashville use their consolidated city-county population.
- **DC and territories:** the Mayor of DC is included as a city mayor. DC's non-voting delegate and all US territories are left out for now.
- **National positions:** reach is the US population divided by the number of people sharing that power, set by `reach_divisor` in `data/inputs/national_positions.csv`. The President and Vice President are elected nationally and get the whole country. The Speaker and Senate Majority Leader get 1/2. The inner Cabinet (State, Treasury, Defense, and the Attorney General) and Senate Minority Leader get 1/4, and the House Majority and Minority Leaders get 1/8. Justices get 1/9, the Federal Reserve Chair 1/12, other Cabinet and senior presidential roles 1/15, Senators 1/100, and Representatives 1/435. Budget shares were considered for the Cabinet but rejected, because they would give the Secretary of State and Attorney General very little reach. Population by state or district is not used for Congress.

### Candidates

These have not been checked or downloaded yet.

| Need | Candidate source |
| --- | --- |
| Newer governor powers | Later Beyle/Ferguson updates in *Politics in the American States*; [The Book of the States](https://bookofthestates.org/), table 4.4 |
| Lieutenant governor powers | [The Book of the States, Lieutenant Governors: Powers and Duties](https://bookofthestates.org/tables/2022-4-14/), which lists who presides, appoints committees, and assigns bills |
| Mayor powers within a form of government | City charters; Morgan and Watson (1996) on mayors' formal powers |
| List of federal positions | [USA.gov](https://www.usa.gov/) and White House listings of the Cabinet |

## Open questions

- **Balancing the two measures:** should reach and influence count equally in the final score?
- **Reach scale:** the cube root is a judgment call. The Vice President ranked from 4th to 65th across the scales tested, from raw population to log.
- **Spending controlled:** should the method use the budget each position controls? It may suit the mayor and governor comparison better than a flat scope multiplier: New York City's budget is far larger than Wyoming's or Vermont's. State GDP was tested and is nearly identical to population (correlation 0.99). Land area was tested and is unrelated to population (0.2), but it doesn't clearly measure power.
- **Weights:** should all five factors count equally? Are the scope multipliers right?
- **Comparing levels:** can one index fairly compare a federal position to a city position? A mayor may control their city more fully than a Senator controls anything, but over far fewer people and with narrower authority.
- **National reach shares:** are the divisors right? Would the people a department affects be a better basis?
- **Mayor cutoff:** the US has thousands of mayors. The list currently stops at the largest 100 cities. Is that the right place to stop?
- **Territories and DC:** should US territories and non-voting delegates be added?
- **More positions:** should the list add the remaining Cabinet secretaries or committee chairs?

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
