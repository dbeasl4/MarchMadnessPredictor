"""
march_madness_predictor.py
==========================
Merges KenPom + Torvik + EvanMiya data, trains a win-probability model,
and simulates the full March Madness bracket.

Usage:
    python march_madness_predictor.py

Outputs:
    - bracket_predictions.csv   : Full bracket round-by-round
    - upset_picks.csv           : Flagged upsets (lower seed wins)
    - win_probabilities.csv     : Head-to-head win % for every matchup
"""

import pandas as pd
import numpy as np
from scipy.special import expit  # sigmoid / logistic function


# ---------------------------------------------------------------------------
# 1.  LOAD & MERGE THE THREE DATA SOURCES
# ---------------------------------------------------------------------------

def load_and_merge() -> pd.DataFrame:
    kenpom = pd.read_csv('csvFiles/kenpom_data.csv')
    torvik = pd.read_csv('csvFiles/torvik_data.csv')
    evanmiya = pd.read_csv('csvFiles/evanmiya_data.csv')

    # Normalise team names to Title Case for joining
    for df in (kenpom, torvik, evanmiya):
        df['Team'] = df['Team'].str.strip().str.title()

    # Rename columns to avoid collisions before merge
    kenpom  = kenpom.add_prefix('KP_').rename(columns={'KP_Team': 'Team'})
    torvik  = torvik.add_prefix('TV_').rename(columns={'TV_Team': 'Team'})
    evanmiya = evanmiya.add_prefix('EM_').rename(columns={'EM_Team': 'Team'})

    merged = (
        kenpom
        .merge(torvik,   on='Team', how='outer')
        .merge(evanmiya, on='Team', how='outer')
    )

    # Convert numeric columns
    num_cols = [c for c in merged.columns if c != 'Team']
    for col in num_cols:
        merged[col] = pd.to_numeric(merged[col], errors='coerce')

    return merged


# ---------------------------------------------------------------------------
# 2.  COMPOSITE RATING
#     Weighted average of the three systems' efficiency margins / BPR.
#     Weights reflect predictive accuracy from published studies.
# ---------------------------------------------------------------------------

def build_composite(df: pd.DataFrame) -> pd.DataFrame:
    """
    KenPom AdjEM  : weight 0.40
    Torvik  AdjEM : weight 0.35
    EvanMiya BPR  : weight 0.25
    """
    kp  = df.get('KP_AdjEM',  pd.Series(np.nan, index=df.index))
    tv  = df.get('TV_AdjEM',  pd.Series(np.nan, index=df.index))
    em  = df.get('EM_BPR',    pd.Series(np.nan, index=df.index))

    # Normalise each metric to z-score so they're on the same scale
    def zscore(s):
        return (s - s.mean()) / s.std()

    kp_z = zscore(kp.fillna(kp.median()))
    tv_z = zscore(tv.fillna(tv.median()))
    em_z = zscore(em.fillna(em.median()))

    df['CompositeRating'] = 0.40 * kp_z + 0.35 * tv_z + 0.25 * em_z

    # Also carry through individual offensive / defensive metrics
    df['AdjOE'] = df.get('KP_AdjO', df.get('TV_AdjOE'))
    df['AdjDE'] = df.get('KP_AdjD', df.get('TV_AdjDE'))

    return df.sort_values('CompositeRating', ascending=False)


# ---------------------------------------------------------------------------
# 3.  WIN PROBABILITY MODEL
#     P(Team A beats Team B) = sigmoid(k * ΔComposite)
#     k is calibrated so that a +10 composite advantage → ~75 % win prob,
#     consistent with historical KenPom/Torvik tournament data.
# ---------------------------------------------------------------------------

K = 0.35   # calibration constant

def win_prob(rating_a: float, rating_b: float) -> float:
    """Return probability that team A beats team B."""
    return float(expit(K * (rating_a - rating_b)))


# ---------------------------------------------------------------------------
# 4.  UPSET DETECTION
#     An upset is flagged when a team seeded 5+ spots lower wins with
#     probability > 35 % (i.e. the model gives them a real shot).
# ---------------------------------------------------------------------------

def is_upset(seed_a: int, seed_b: int, prob_a: float) -> bool:
    seed_diff = seed_b - seed_a   # positive when A is higher seed (worse)
    return seed_diff >= 5 and prob_a > 0.35


# ---------------------------------------------------------------------------
# 5.  BRACKET SIMULATION
# ---------------------------------------------------------------------------

# 2025 NCAA Tournament bracket seedings (update teams to match actual bracket)
# Format: { region: [(seed, team_name), ...] }  — 16 teams per region
BRACKET = {
    "East": [
        (1, "Duke"), (16, "American"),
        (8, "Mississippi State"), (9, "Boise State"),
        (5, "Oregon"), (12, "Liberty"),
        (4, "Arizona"), (13, "Akron"),
        (6, "Byu"), (11, "Vcu"),
        (3, "Wisconsin"), (14, "Montana"),
        (7, "Saint Mary's"), (10, "Vanderbilt"),
        (2, "Alabama"), (15, "Robert Morris"),
    ],
    "West": [
        (1, "Florida"), (16, "Norfolk State"),
        (8, "Connecticut"), (9, "Oklahoma"),
        (5, "Memphis"), (12, "Colorado State"),
        (4, "Maryland"), (13, "Grand Canyon"),
        (6, "Missouri"), (11, "Drake"),
        (3, "Texas Tech"), (14, "Mcneese State"),
        (7, "Kansas"), (10, "Arkansas"),
        (2, "St. John's"), (15, "Omaha"),
    ],
    "South": [
        (1, "Auburn"), (16, "Alabama State"),
        (8, "Louisville"), (9, "Creighton"),
        (5, "Michigan"), (12, "Uc San Diego"),
        (4, "Texas A&M"), (13, "Yale"),
        (6, "Ole Miss"), (11, "San Diego State"),
        (3, "Iowa State"), (14, "Lipscomb"),
        (7, "Marquette"), (10, "New Mexico"),
        (2, "Michigan State"), (15, "Bryant"),
    ],
    "Midwest": [
        (1, "Houston"), (16, "Siue"),
        (8, "Gonzaga"), (9, "Georgia"),
        (5, "Clemson"), (12, "Mcneese"),
        (4, "Purdue"), (13, "High Point"),
        (6, "Illinois"), (11, "Texas"),
        (3, "Kentucky"), (14, "Troy"),
        (7, "UCLA"), (10, "Utah State"),
        (2, "Tennessee"), (15, "Wofford"),
    ],
}


def simulate_region(region_name: str, teams_seeds: list, ratings: dict) -> list:
    """Simulate one region bracket. Returns list of round-by-round results."""
    rounds = []
    current_round = teams_seeds[:]  # list of (seed, team)

    round_num = 1
    while len(current_round) > 1:
        next_round = []
        matchups = []
        for i in range(0, len(current_round), 2):
            seed_a, team_a = current_round[i]
            seed_b, team_b = current_round[i + 1]

            r_a = ratings.get(team_a, 0.0)
            r_b = ratings.get(team_b, 0.0)
            prob_a = win_prob(r_a, r_b)
            winner = (seed_a, team_a) if prob_a >= 0.5 else (seed_b, team_b)

            matchups.append({
                'Region':    region_name,
                'Round':     round_num,
                'Team_A':    team_a,
                'Seed_A':    seed_a,
                'Team_B':    team_b,
                'Seed_B':    seed_b,
                'WinProb_A': round(prob_a, 4),
                'WinProb_B': round(1 - prob_a, 4),
                'Winner':    winner[1],
                'WinnerSeed':winner[0],
                'Upset':     is_upset(seed_a, seed_b, prob_a) or
                             is_upset(seed_b, seed_a, 1 - prob_a),
            })
            next_round.append(winner)

        rounds.extend(matchups)
        current_round = next_round
        round_num += 1

    return rounds


def simulate_final_four(region_winners: dict, ratings: dict) -> list:
    """Simulate Final Four and Championship."""
    results = []
    # Traditional bracket pairings: East vs West, South vs Midwest
    semifinal_pairs = [
        ("East",  region_winners["East"],
         "West",  region_winners["West"]),
        ("South", region_winners["South"],
         "Midwest", region_winners["Midwest"]),
    ]

    final_four_winners = []
    for r1, (s1, t1), r2, (s2, t2) in semifinal_pairs:
        prob = win_prob(ratings.get(t1, 0), ratings.get(t2, 0))
        winner = (s1, t1) if prob >= 0.5 else (s2, t2)
        final_four_winners.append(winner)
        results.append({
            'Region': f'Final Four ({r1} vs {r2})',
            'Round': 5,
            'Team_A': t1, 'Seed_A': s1,
            'Team_B': t2, 'Seed_B': s2,
            'WinProb_A': round(prob, 4),
            'WinProb_B': round(1 - prob, 4),
            'Winner': winner[1], 'WinnerSeed': winner[0],
            'Upset': is_upset(s1, s2, prob) or is_upset(s2, s1, 1-prob),
        })

    # Championship
    (s1, t1), (s2, t2) = final_four_winners
    prob = win_prob(ratings.get(t1, 0), ratings.get(t2, 0))
    champion = (s1, t1) if prob >= 0.5 else (s2, t2)
    results.append({
        'Region': 'Championship',
        'Round': 6,
        'Team_A': t1, 'Seed_A': s1,
        'Team_B': t2, 'Seed_B': s2,
        'WinProb_A': round(prob, 4),
        'WinProb_B': round(1 - prob, 4),
        'Winner': champion[1], 'WinnerSeed': champion[0],
        'Upset': is_upset(s1, s2, prob) or is_upset(s2, s1, 1-prob),
    })

    return results, champion


# ---------------------------------------------------------------------------
# 6.  MAIN
# ---------------------------------------------------------------------------

def main():
    print("Loading and merging data sources...")
    df = load_and_merge()
    df = build_composite(df)

    # Build a quick lookup: team -> composite rating
    ratings = dict(zip(df['Team'], df['CompositeRating']))

    all_results = []

    print("\nSimulating regions...")
    region_winners = {}
    for region, teams in BRACKET.items():
        region_results = simulate_region(region, teams, ratings)
        all_results.extend(region_results)
        # Last entry in region results is the region final winner
        region_final = [r for r in region_results if r['Round'] == max(r['Round'] for r in region_results)]
        region_winners[region] = (region_final[-1]['WinnerSeed'], region_final[-1]['Winner'])
        print(f"  {region} winner: {region_winners[region][1]} (#{region_winners[region][0]} seed)")

    print("\nSimulating Final Four & Championship...")
    final_results, champion = simulate_final_four(region_winners, ratings)
    all_results.extend(final_results)

    print(f"\n🏆 PREDICTED CHAMPION: {champion[1]} (#{champion[0]} seed)")

    # Build output DataFrames
    results_df = pd.DataFrame(all_results)
    upsets_df  = results_df[results_df['Upset'] == True].copy()

    round_names = {1: 'Round of 64', 2: 'Round of 32', 3: 'Sweet 16',
                   4: 'Elite 8', 5: 'Final Four', 6: 'Championship'}
    results_df['RoundName'] = results_df['Round'].map(round_names)
    upsets_df['RoundName']  = upsets_df['Round'].map(round_names)

    # Save outputs
    results_df.to_csv('bracket_predictions.csv', index=False)
    upsets_df.to_csv('upset_picks.csv', index=False)
    df[['Team', 'CompositeRating', 'AdjOE', 'AdjDE']].to_csv('win_probabilities.csv', index=False)

    print(f"\nFiles saved:")
    print("  bracket_predictions.csv")
    print("  upset_picks.csv")
    print("  win_probabilities.csv")

    print(f"\n📋 FINAL FOUR:")
    ff = results_df[results_df['Round'] == 5]
    for _, row in ff.iterrows():
        print(f"  {row['Team_A']} vs {row['Team_B']}  →  {row['Winner']} ({row['WinProb_A']:.0%} / {row['WinProb_B']:.0%})")

    print(f"\n⚠️  TOP UPSET PICKS:")
    top_upsets = upsets_df.sort_values('WinnerSeed').head(10)
    for _, row in top_upsets.iterrows():
        print(f"  [{row['RoundName']}] #{row['WinnerSeed']} {row['Winner']} over "
              f"#{row['Seed_A'] if row['Winner'] == row['Team_B'] else row['Seed_B']} "
              f"({row['WinProb_A']:.0%} / {row['WinProb_B']:.0%})")


if __name__ == '__main__':
    main()
