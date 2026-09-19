# src/data/loader.py

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from src.utils.config import load_config


class DataLoader:
    def __init__(self, data_dir=None, file_pattern="games_*.csv"):
        """
        Initialize the DataLoader.
        """
        # Resolve Project Root
        self.project_root = Path(__file__).resolve().parents[2]

        if data_dir is None:
            self.data_dir = self.project_root / "data" / "raw"
        else:
            self.data_dir = Path(data_dir)

        self.file_pattern = file_pattern
        self._raw_df = None

        # Load Config to check for Advanced Stats settings
        try:
            self.config = load_config()
        except:
            self.config = {}

    def _load_name_mapping(self):
        """
        Loads the USCHO <-> CHN team name mapping.
        Returns a dictionary: {CHN_Name: USCHO_Name}
        """
        mapping = {}
        try:
            map_path = self.project_root / self.config.get('data', {}).get('advanced_stats', {}).get('mapping_file', '')
            if map_path.exists():
                df_map = pd.read_csv(map_path)
                # Ensure columns exist
                if 'CHN_Name' in df_map.columns and 'USCHO_Name' in df_map.columns:
                    # Create dict
                    mapping = dict(zip(df_map['CHN_Name'], df_map['USCHO_Name']))
        except Exception as e:
            print(f"Warning: Could not load team mapping file: {e}")

        return mapping

    def _load_advanced_stats(self, base_df):
        """
        Loads CHN advanced stats and merges them into the base dataframe.
        """
        adv_settings = self.config.get('data', {}).get('advanced_stats', {})
        if not adv_settings.get('enabled', False):
            return base_df

        adv_dir = self.project_root / adv_settings.get('source_dir', 'data/raw_advanced')
        if not adv_dir.exists():
            return base_df

        print(f"Merging Advanced Stats from {adv_dir}...")

        # 1. Load all advanced files (chn_games_*.csv)
        all_adv_files = list(adv_dir.glob("chn_games_*.csv"))
        if not all_adv_files:
            return base_df

        adv_dfs = []
        for f in all_adv_files:
            try:
                # Expecting columns: season, date, away_team, home_team, away_xg, home_xg, url
                temp = pd.read_csv(f)
                adv_dfs.append(temp)
            except Exception:
                continue

        if not adv_dfs:
            return base_df

        full_adv = pd.concat(adv_dfs, ignore_index=True)

        # 2. Normalize Advanced Data for Merge
        # A. Map CHN Team Names -> USCHO Team Names
        mapping = self._load_name_mapping()
        if mapping:
            full_adv['home_team'] = full_adv['home_team'].map(mapping).fillna(full_adv['home_team'])
            full_adv['away_team'] = full_adv['away_team'].map(mapping).fillna(full_adv['away_team'])

        # B. Parse Dates
        # CHN dates might be YYYYMMDD strings or parsing from URL
        # Attempt to clean 'date' column
        full_adv['date'] =full_adv['url'].str.extract(r'/(\d{8})/', expand=False)
        full_adv['Date'] = pd.to_datetime(full_adv['date'], format='%Y%m%d', errors='coerce')

        # If date failed, try parsing from URL if needed?
        # Assuming scraper saved clean YYYYMMDD in 'date' column as requested.

        # Select cols to merge
        # Rename to match base_df conventions (HomeTeam, AwayTeam)
        full_adv = full_adv.rename(columns={
            'home_team': 'HomeTeam',
            'away_team': 'AwayTeam',
            'home_xg': 'Home_xG',
            'away_xg': 'Away_xG',
            'home_eng': 'Home_ENG',
            'away_eng': 'Away_ENG',
            'home_ev_goals': 'Home_EV_Goals',
            'away_ev_goals': 'Away_EV_Goals',
        })

        cols_to_use = ['Date', 'HomeTeam', 'AwayTeam', 'Home_xG', 'Away_xG']
        # Home_ENG/Away_ENG (empty-net goal counts) and Home_EV_Goals/
        # Away_EV_Goals (even-manpower goal counts, excluding PP/SH/EN --
        # see extract_even_manpower_goals()) are only present in CHN scrapes
        # done after each field was added — older cached chn_games_*.csv
        # files won't have these columns at all.
        has_eng = 'Home_ENG' in full_adv.columns and 'Away_ENG' in full_adv.columns
        if has_eng:
            cols_to_use += ['Home_ENG', 'Away_ENG']
        has_ev = 'Home_EV_Goals' in full_adv.columns and 'Away_EV_Goals' in full_adv.columns
        if has_ev:
            cols_to_use += ['Home_EV_Goals', 'Away_EV_Goals']

        # Filter for validity
        full_adv = full_adv[cols_to_use].dropna(subset=['Date'])

        # 3. Merge
        # Merge on Date, Home, Away
        # Left join to keep all original games even if xG missing
        merged_df = pd.merge(
            base_df,
            full_adv,
            on=['Date', 'HomeTeam', 'AwayTeam'],
            how='left'
        )

        count_matched = merged_df['Home_xG'].notna().sum()
        print(f"  -> Matched xG data for {count_matched} games.")
        if has_eng:
            count_eng_matched = merged_df['Home_ENG'].notna().sum()
            print(f"  -> Matched empty-net-goal data for {count_eng_matched} games.")
        else:
            # Downstream code (HockeyLRMC) checks for these columns' presence
            # and falls back gracefully when absent, but keep them present
            # (all-NaN) for a consistent schema across runs/seasons.
            merged_df['Home_ENG'] = np.nan
            merged_df['Away_ENG'] = np.nan
        if has_ev:
            count_ev_matched = merged_df['Home_EV_Goals'].notna().sum()
            print(f"  -> Matched even-manpower-goal data for {count_ev_matched} games.")
        else:
            merged_df['Home_EV_Goals'] = np.nan
            merged_df['Away_EV_Goals'] = np.nan

        return merged_df

    def _load_all_raw(self):
        """Internal helper: Loads, concatenates, and cleans raw CSVs."""
        if self._raw_df is not None:
            return self._raw_df

        search_path = self.data_dir / self.file_pattern
        files = sorted(glob.glob(str(search_path)))

        if not files:
            raise FileNotFoundError(f"No files found matching '{search_path}'.")

        print(f"Loading {len(files)} season files from {self.data_dir}...")
        df_list = []
        for f in files:
            try:
                temp_df = pd.read_csv(f)
                df_list.append(temp_df)
            except Exception as e:
                print(f"Error reading {f}: {e}")

        if not df_list:
            raise ValueError("No data could be loaded.")

        full_df = pd.concat(df_list, ignore_index=True)

        # 0. Drop exact-duplicate rows. Confirmed on disk (2026-09-13,
        # while researching a preseason-priors question --
        # research/preseason/reports/probe_pre2011_scrape.md): every raw
        # season file from 2011-12 through 2020-21 contains a consistent
        # ~3% rate of fully-identical duplicate rows (same Day/Date/Time/
        # teams/scores/etc., byte-for-byte) -- apparently a USCHO
        # composite-schedule rendering quirk that stopped appearing from
        # 2021-22 onward (0 duplicates in every season since). This had
        # gone unnoticed since the project's earliest reports. Using a
        # full-row match (not just Date+HomeTeam+AwayTeam) is deliberately
        # conservative: it only removes rows that are ENTIRELY identical,
        # so it can't accidentally collapse two genuinely different games
        # that merely share a date and matchup (e.g. the same game listed
        # once as an exhibition and once as a real game differs in
        # Is_Exhibition/Type, so it correctly survives this step --
        # _filter_exhibition() below is what disambiguates that case, not
        # this one).
        n_before = len(full_df)
        full_df = full_df.drop_duplicates().reset_index(drop=True)
        n_dropped = n_before - len(full_df)
        if n_dropped:
            print(f"  -> Dropped {n_dropped} exact-duplicate raw game rows.")

        # 1. Standardize Boolean Columns
        bool_cols = ['Is_Final', 'Is_Neutral', 'Is_Exhibition', 'Is_OT']
        for col in bool_cols:
            if col in full_df.columns:
                full_df[col] = full_df[col].astype(str).str.lower().map({
                    'true': True, 'false': False,
                    '1': True, '0': False,
                    'yes': True, 'no': False,
                    'nan': False
                }).fillna(False)

        # 2. Parse Dates
        if 'Date' in full_df.columns:
            full_df['Date'] = pd.to_datetime(full_df['Date'], errors='coerce')

        # 3. Rename columns to internal standard BEFORE merging advanced stats
        col_map = {
            'Home_Team': 'HomeTeam',
            'Visitor_Team': 'AwayTeam',
            'Home_Score': 'HomeGoals',
            'Visitor_Score': 'AwayGoals',
            'Is_Neutral': 'NeutralSite',
            'Is_OT': 'IsOT',
            'Season': 'Season'
        }
        full_df = full_df.rename(columns=col_map)

        # 4. Standardize Numeric Scores (fill NaNs with 0 temporarily for logic)
        for col in ['HomeGoals', 'AwayGoals']:
            if col in full_df.columns:
                full_df[col] = pd.to_numeric(full_df[col], errors='coerce').fillna(0).astype(int)

        # 5. Load and Merge Advanced Stats (xG)
        full_df = self._load_advanced_stats(full_df)

        self._raw_df = full_df
        return self._raw_df

    def _filter_exhibition(self, df):
        if 'Is_Exhibition' in df.columns:
            is_ex_mask = df['Is_Exhibition'] == True
        else:
            is_ex_mask = pd.Series(False, index=df.index)

        if 'Type' in df.columns:
            type_ex_mask = df['Type'].astype(str).str.lower().str.contains('ex', na=False)
        else:
            type_ex_mask = pd.Series(False, index=df.index)

        return df[~(is_ex_mask | type_ex_mask)].copy()

    def get_history(self):
        """
        Returns COMPLETED games (Is_Final=True).
        """
        df = self._load_all_raw().copy()

        if 'Is_Final' in df.columns:
            df = df[df['Is_Final'] == True]

        df = self._filter_exhibition(df)

        required_cols = ['HomeTeam', 'AwayTeam', 'HomeGoals', 'AwayGoals']
        cols_to_check = [c for c in required_cols if c in df.columns]
        df = df.dropna(subset=cols_to_check)

        # Calculate Result (1.0 = Home Win, 0.5 = Tie, 0.0 = Away Win)
        # Use actual goals for the Result column (xG is a feature, not the result)
        df['GoalMargin'] = df['HomeGoals'] - df['AwayGoals']

        conditions = [
            (df['GoalMargin'] > 0),
            (df['GoalMargin'] < 0)
        ]
        choices = [1.0, 0.0]
        df['Result'] = np.select(conditions, choices, default=0.5)

        return df.sort_values('Date').reset_index(drop=True)

    def get_schedule(self, target_season=None):
        """
        Returns FUTURE/UNPLAYED games for ONE season -- `target_season` if
        given, else whichever season is newest in the raw data.

        BUG FIXED (2026-09-08): this used to return every Is_Final=False
        row across ALL seasons in the raw archive with no season filter at
        all. A game that never got marked final for any reason (a scraper
        miss, a postponement/cancellation, or a Frozen-Four bracket slot
        left as a placeholder team like "Clarkson/Dartmouth" once the real
        matchup is decided) stayed in "upcoming" FOREVER, across every
        season back to 2011-12 -- confirmed on disk: data/processed/
        upcoming_schedule.csv had 6 stray rows from 2013-14, 2014-15,
        2023-24, and leftover 2025-26 bracket placeholders sitting
        alongside the real 2026-27 schedule. process_data() is the only
        caller and always wanted "the current season's future games", so
        that's now the actual contract, not an assumption downstream
        callers had to enforce for themselves (see reports/
        season_2026_27_rollover_audit.md).
        """
        df = self._load_all_raw().copy()

        if 'Season' in df.columns and not df.empty:
            season = target_season if target_season is not None else df['Season'].max()
            df = df[df['Season'] == season]

        if 'Is_Final' in df.columns:
            df = df[df['Is_Final'] == False]

        df = self._filter_exhibition(df)

        keep_cols = ['Date', 'HomeTeam', 'AwayTeam', 'NeutralSite', 'Season']
        existing_cols = [c for c in keep_cols if c in df.columns]

        return df[existing_cols].sort_values('Date').reset_index(drop=True)