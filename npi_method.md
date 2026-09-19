```markdown
# Prompt for NPI System Implementation

**Role:** You are a Sports Analytics Data Engineer specializing in NCAA ranking algorithms.

**Objective:** Write a Python script to replicate the **NCAA NPI (NCAA Power Index)** ranking system for Division I College Hockey.

**Context:** I have the raw game data, but my implementation fails to replicate the "Strength of Schedule" (SOS) and final NPI numbers found on USCHO and College Hockey News. The discrepancy is likely due to the "Bad Wins Filter" and the specific "Game Weighting" logic.

### 1. Data Structure
Assume the input is a list of game objects/dictionaries (or a Pandas DataFrame) with the following fields:
*   `team`: String (Name of the team)
*   `opponent`: String (Name of the opponent)
*   `result`: Float (1.0 for Win, 0.0 for Loss, 0.5 for Tie). *Note: Handle OT logic if necessary, but assume standard W/L for now.*
*   `location`: String ('Home', 'Away', 'Neutral')
*   `is_ot`: Boolean (True if game ended in Overtime)

### 2. The NPI Algorithm Specs

Please implement a class or function `calculate_npi(games)` that performs the following iterative convergence process:

**A. Initialization**
*   Initialize every team's NPI to **0.5000** (or their raw Winning Percentage).

**B. The Iteration Loop**
Repeat the following steps until the NPI values for all teams change by less than `0.0001` between iterations:

1.  **Calculate Game NPI:** For every game played, calculate a specific "Game NPI" value using the *current* iteration's Opponent NPI:
    *   `Game NPI = (Result_Score * 25%) + (Opponent_NPI * 75%) + Bonus`
    *   *Result_Score:* 100 for Win, 0 for Loss.
    *   *Bonus (Quality Win Bonus):* If Result is Win: `(Opponent_NPI - 51) * 0.5`. If negative or a Loss, Bonus is 0.

2.  **Apply Game Weights:** Assign a weight to each game based on difficulty:
    *   **Home Loss / Away Win:** Weight = **1.2** (High impact events)
    *   **Home Win / Away Loss:** Weight = **0.8** (Expected events)
    *   **Neutral:** Weight = **1.0**

3.  **The "Bad Wins" Filter (Crucial Step):**
    *   For each team, separate their schedule into **Losses** (mandatory) and **Wins**.
    *   Sort all **Wins** by their calculated `Game NPI` (descending).
    *   **Mandatory Set:** Include ALL Losses and the Top 12 Wins.
    *   **Optional Set:** Wins 13+.
    *   *Selection Logic:* Calculate the weighted average of the "Mandatory Set". Then, iterate through the "Optional Set" (from best to worst). If adding the next win increases the team's weighted average, keep it. If it decreases the average, **discard it and stop**.

4.  **Quality Win Bonus (QWB):**
    *   **Formula:** `Bonus = (Opponent_NPI - 50.5) * 0.45`
    *   **Condition:** Applies to *ALL Wins* (Regulation and OT) where Opponent NPI > 50.5.
    *   **Method:** Integrated into the Game NPI calculation.
    *   **Rationale:** Rewards beating elevated competition. Tuned to match 2026 validation data.

4.  **Calculate Team NPI:**
    *   `Team NPI = Sum(Game NPI * Game Weight) / Sum(Game Weights)`
    *   *Note:* Only use the games that survived the filter in Step 3.

**C. Final Outputs**
1.  **NPI:** The converged value.
2.  **SOS (Strength of Schedule):** This must be calculated as the **Average of Opponent NPIs** for *only the games that counted toward the final NPI* (i.e., excluding the dropped "bad wins").

### 3. Requirements for the Code
*   Use **Pandas** for data handling.
*   Create a clean function to determine `game_weight`.
*   Create a function `optimize_schedule(team_games)` that handles the logic of dropping wins that lower the average.
*   Include a **Debug Mode** that prints the calculation for a single specific team (e.g., "Minnesota") showing exactly which games were dropped and why.

### 4. Test Data
Please generate a small synthetic dataset of 4 teams to demonstrate the code:
1.  **Team A:** Elite (Wins almost all games against good opponents).
2.  **Team B:** Good (Wins against bad opponents, loses to Team A).
3.  **Team C:** Average (Splits games).
4.  **Team D:** Poor (Loses almost all games).

**Please output the Python code to achieve this.**
```