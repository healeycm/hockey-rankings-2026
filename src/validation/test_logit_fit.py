import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from collections import defaultdict

# Imports from your project
from src.data.loader import DataLoader
from src.rankings.lrmc import LRMC
from src.utils.config import load_config


def get_adjusted_margin(row, cap=3, power=1.0):
    """Replicates the margin adjustment logic from LRMC class."""
    margin = row['HomeGoals'] - row['AwayGoals']

    # Cap
    if abs(margin) > cap:
        margin = cap if margin > 0 else -cap

    # Power
    if power != 1.0:
        sign = 1 if margin >= 0 else -1
        margin = sign * (abs(margin) ** power)

    return margin


def extract_training_data(df, margin_cap, margin_power):
    """
    Replicates the 'Home-and-Home' data extraction logic.
    Returns: DataFrame with ['Margin', 'ReturnGameWin']
    """
    games_as_home = defaultdict(list)
    results_as_visitor = defaultdict(list)

    valid_rows = df[~df['NeutralSite']]

    # 1. First Pass: Organize Data
    for _, row in valid_rows.iterrows():
        s = row['Season']
        h = row['HomeTeam']
        a = row['AwayTeam']

        m = get_adjusted_margin(row, cap=margin_cap, power=margin_power)

        # Store Margin when H is Home
        games_as_home[(s, h, a)].append(m)

        # Store Result when H is Visitor (Opponent 'a' is Home)
        # Result 1.0 = Home Win (Visitor Loss)
        # We want to know if Visitor (h) Won.
        vis_win = 1 if row['Result'] < 0.5 else 0
        results_as_visitor[(s, a, h)].append(vis_win)

    # 2. Second Pass: Find Pairs
    data_points = []

    for (season, A, B), margins in games_as_home.items():
        # Check for return game
        return_results = results_as_visitor.get((season, A, B))

        if return_results:
            # Create pairs
            for m in margins:
                for res in return_results:
                    data_points.append({'Margin': m, 'Win': res})

    return pd.DataFrame(data_points)


def main():
    print("--- Testing Logistic Regression Fit (LRMC Input) ---")

    # 1. Load Config & Data
    config = load_config()
    lrmc_conf = config['models']['lrmc']['LRMC_Classic']

    print("Loading Full History...")
    loader = DataLoader()
    full_history = loader.get_history()

    # 2. Run LRMC to get the fitted parameters
    print("Fitting LRMC Model to learn parameters...")
    # Force auto_fit=True for this test
    lrmc_conf['auto_fit'] = True
    lrmc_conf['fit_source'] = 'history'

    model = LRMC(full_history, config=lrmc_conf, history_df=full_history)
    model.fit()  # This triggers _learn_params_home_and_home

    alpha = model.alpha
    beta = model.beta
    print(f"Learned Parameters: Alpha={alpha:.3f}, Beta={beta:.3f}")

    # 3. Extract the raw data points used for training
    print("Extracting training pairs for visualization...")
    df_train = extract_training_data(
        full_history,
        lrmc_conf['margin_cap'],
        lrmc_conf['margin_power']
    )

    if df_train.empty:
        print("Error: No home-and-home pairs found in history.")
        return

    # 4. Bin Data (20 equal width bins)
    # We bin by Margin.
    # Note: Margin is discrete (1, 2, 3...), so usually we group by integer margin
    # rather than creating arbitrary float bins, but prompt asked for 20 bins.
    df_train['Bin'] = pd.cut(df_train['Margin'], bins=20)

    # Calculate Stats per Bin
    bin_stats = df_train.groupby('Bin', observed=True).agg(
        AvgMargin=('Margin', 'mean'),
        ActualWinPct=('Win', 'mean'),
        Count=('Win', 'count')
    ).reset_index()

    # Filter empty bins
    bin_stats = bin_stats[bin_stats['Count'] > 0]

    # 5. Generate Theoretical Curve
    # Logic: Prob = 1 / (1 + exp(-(alpha + beta*x)))
    x_theoretical = np.linspace(df_train['Margin'].min(), df_train['Margin'].max(), 100)
    y_theoretical = 1 / (1 + np.exp(-(alpha + beta * x_theoretical)))

    # 6. Plotting
    output_dir = Path(__file__).resolve().parents[2] / "output" / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 7))
    sns.set_style("whitegrid")

    # Plot Reality (Red Dots)
    plt.scatter(
        bin_stats['AvgMargin'],
        bin_stats['ActualWinPct'],
        color='red',
        s=bin_stats['Count'] / 5,  # Size dots by sample size
        label='Actual Win % (Bin Size)',
        zorder=5
    )

    # Plot Theory (Blue Line)
    plt.plot(
        x_theoretical,
        y_theoretical,
        color='blue',
        linewidth=2,
        label=f'Theoretical Curve\n(α={alpha:.2f}, β={beta:.2f})'
    )

    plt.title(f"LRMC Logistic Fit Check\n(Margin vs Return Game Win Probability)", fontsize=14)
    plt.xlabel("Goal Margin (Home Game)", fontsize=12)
    plt.ylabel("Probability of Winning Return Game (Road)", fontsize=12)
    plt.legend()
    plt.ylim(-0.05, 1.05)

    # Add text annotation
    plt.text(
        x_theoretical.min(), 0.9,
        f"Config: Cap={lrmc_conf['margin_cap']}, Power={lrmc_conf['margin_power']}",
        bbox=dict(facecolor='white', alpha=0.8)
    )

    save_path = output_dir / "lrmc_logit_fit.png"
    plt.savefig(save_path)
    print(f"Plot saved to: {save_path}")
    plt.close()


if __name__ == "__main__":
    main()