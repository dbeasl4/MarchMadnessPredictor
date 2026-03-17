import pytest
import pandas as pd
import numpy as np
from io import StringIO

# --- 1. Testing the Data Cleaning (Logic) ---
def clean_cbb_data(raw_df):
    """The function we are testing"""
    df = raw_df.copy()
    # Convert strings to floats
    df['adjOE'] = pd.to_numeric(df['adjOE'], errors='coerce')
    df['adjDE'] = pd.to_numeric(df['adjDE'], errors='coerce')
    # Create the key ML feature
    df['net_eff'] = df['adjOE'] - df['adjDE']
    return df

def test_data_cleaning_types():
    # Create fake "dirty" data
    data = "team,adjOE,adjDE\nHouston,115.4,88.2\nUConn,120.1,92.5"
    raw_df = pd.read_csv(StringIO(data))
    
    cleaned = clean_cbb_data(raw_df)
    
    # Assertions: If these fail, your program has a bug
    assert cleaned['adjOE'].dtype == float
    assert cleaned['net_eff'].iloc[0] == pytest.approx(27.2)
    assert not cleaned.isnull().values.any()

# --- 2. Testing the Matchup Simulator ---
def test_matchup_logic():
    # Setup two mock teams
    team_a = {'adjOE': 120, 'adjDE': 90}
    team_b = {'adjOE': 100, 'adjDE': 110}
    
    # Logic: Team A should have a much higher Net Efficiency
    a_net = team_a['adjOE'] - team_a['adjDE'] # 30
    b_net = team_b['adjOE'] - team_b['adjDE'] # -10
    
    diff = a_net - b_net
    assert diff == 40
    assert diff > 0  # Team A is clearly better

# --- 3. Testing the Scraper Output (File Check) ---
def test_csv_structure():
    try:
        df = pd.read_csv('kenpom_data.csv')
        required_columns = {'team', 'adjOE', 'adjDE'}
        assert required_columns.issubset(df.columns)
    except FileNotFoundError:
        pytest.skip("Scraper hasn't run yet; no CSV to test.")