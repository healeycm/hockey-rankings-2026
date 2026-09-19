import pandas as pd

df = pd.read_csv('data/processed/games_archive.csv')
season = df[df['Season'] == 20252026]
targets = ['Michigan', 'Michigan State', 'North Dakota']

for t in targets:
    m = season[(season['HomeTeam'] == t) | (season['AwayTeam'] == t)]
    wins = sum((m['HomeTeam']==t) & (m['Result']==1.0)) + sum((m['AwayTeam']==t) & (m['Result']==0.0))
    losses = sum((m['HomeTeam']==t) & (m['Result']==0.0)) + sum((m['AwayTeam']==t) & (m['Result']==1.0))
    ties = sum(m['Result']==0.5)
    print(f'{t}: {wins}-{losses}-{ties} ({len(m)} games)')
