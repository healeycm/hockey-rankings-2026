import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from utils.data_loader import get_team_schedule, get_logo_url, load_team_analysis, load_rankings, load_rank_distribution, get_canonical_name
import urllib.parse
import traceback

dash.register_page(__name__, path_template="/team/<team_name>")

def layout(team_name=None, model="KRACH", division="men", **kwargs):
    try:
        if not team_name:
            return html.Div("Team name missing.")

        # Team-detail data loading below (get_team_schedule,
        # load_team_analysis, load_rank_distribution, and the plain
        # load_rankings(model) call) is NOT YET division-aware -- it always
        # reads men's data regardless of what's passed here. Since many
        # schools field both a men's and a women's program under the exact
        # same name (e.g. "Wisconsin"), silently proceeding for
        # division="women" would render the MEN'S team's page under a
        # women's-hockey link — a real correctness bug, not a cosmetic one
        # (see reports/womens_hockey_import.md's Phase 3 risk notes). Guard
        # explicitly rather than wire this incompletely.
        if division == "women":
            return dbc.Alert(
                f"Team detail pages for women's hockey ({team_name}) aren't available yet — "
                "only the rankings table has been updated so far. See the rankings page for "
                "current women's D-I standings.",
                color="info",
                className="mt-4",
            )

        # 0. Canonicalize and Decode
        # Unquote handles %20 etc, get_canonical_name handles nicknames/variations
        team_name = urllib.parse.unquote(team_name)
        team_name = get_canonical_name(team_name)
        
        # 1. Fetch Data
        logo_url = get_logo_url(team_name)
        schedule_df = get_team_schedule(team_name, model=model) 
        analysis_data = load_team_analysis(team_name, model=model)
        rank_df = load_rankings(model) 
        
        # 2. Extract Team Info
        team_row = rank_df[rank_df['Team'] == team_name]
        
        record_str = "-"
        conf_str = ""
        proj_record_str = ""
        
        if not team_row.empty:
            row = team_row.iloc[0]
            record_str = row.get('Record', '-')
            conf_str = row.get('Conference', '')
            
            if not schedule_df.empty:
                current_w = row.get('W', 0)
                current_l = row.get('L', 0)
                current_t = row.get('T', 0)
                
                # Projections
                expected_future_wins = schedule_df['WinProb'].sum()
                future_games_count = len(schedule_df)
                expected_future_losses = future_games_count - expected_future_wins
                
                proj_w = int(round(current_w + expected_future_wins))
                proj_l = int(round(current_l + expected_future_losses))
                proj_t = current_t
                proj_record_str = f"Proj: {proj_w}-{proj_l}-{proj_t}"
        
        # --- UI COMPONENTS ---
        
        header = html.Div([
            dbc.Row([
                dbc.Col(
                    html.Img(src=logo_url, style={"height": "80px", "maxWidth": "100%"}, alt=f"{team_name} Logo"), 
                    width="auto", className="pe-3"
                ),
                dbc.Col([
                    html.H1(team_name, className="mb-0 display-4"),
                    html.Div([
                        html.Span(conf_str, className="badge bg-secondary me-2") if conf_str else None,
                        html.Span(record_str, className="fw-bold lead me-3"),
                        html.Span(proj_record_str, className="text-muted small") if proj_record_str else None
                    ], className="d-flex align-items-center mt-1"),
                    html.P(f"Analysis based on {model.replace('_', ' ')}", className="text-muted small mb-0 mt-1")
                ])
            ], className="align-items-center")
        ], className="mb-5 pt-4 pb-4 border-bottom")
        
        # Stats
        stats_content = []
        if analysis_data and analysis_data.get('stats'):
            s = analysis_data['stats']
            card_content = dbc.Row([
                dbc.Col([
                    html.Div("Win Pct", className="text-uppercase small text-muted fw-bold"),
                    html.Div(f"{s.get('WinPct', 0)*100:.1f}%", className="display-6")
                ], width=6),
                dbc.Col([
                    html.Div("SOS Rank", className="text-uppercase small text-muted fw-bold"),
                    html.Div(f"#{int(s.get('SOS_Rank', 0))}", className="display-6")
                ], width=6),
            ], className="mb-4")
            stats_content.append(card_content)
            
            if not analysis_data['top_wins'].empty:
                stats_content.append(html.H5("Best Wins", className="mt-4 mb-3 border-bottom pb-2"))
                for _, row in analysis_data['top_wins'].iterrows():
                    stats_content.append(dbc.Row([
                        dbc.Col(html.Span(f"vs {row['Opponent']}", className="fw-bold"), width=8),
                        dbc.Col(html.Span(f"+{row['Rating Impact']:.1f}", className="text-success fw-bold small"), width=4, className="text-end"),
                    ], className="mb-2"))

            if not analysis_data['worst_losses'].empty:
                stats_content.append(html.H5("Toughest Losses", className="mt-4 mb-3 border-bottom pb-2"))
                for _, row in analysis_data['worst_losses'].iterrows():
                    stats_content.append(dbc.Row([
                        dbc.Col(html.Span(f"vs {row['Opponent']}", className="fw-bold"), width=8),
                        dbc.Col(html.Span(f"{row['Rating Impact']:.1f}", className="text-danger fw-bold small"), width=4, className="text-end"),
                    ], className="mb-2"))
        else:
            stats_content.append(dbc.Alert(f"No analysis stats available for {model}.", color="secondary"))

        # Distribution
        dist_df = load_rank_distribution(team_name, model=model)
        dist_content = []
        if not dist_df.empty:
            plot_df = dist_df.sort_values('Rank')
            fig = go.Figure(data=[
                go.Bar(
                    x=plot_df['Rank'],
                    y=plot_df['Probability'] * 100,
                    marker_color='#007bff',
                    hovertemplate="Rank #%{x}<br>Probability: %{y:.1f}%<extra></extra>"
                )
            ])
            fig.update_layout(
                margin=dict(l=40, r=20, t=20, b=40), height=250,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title="Finishing Rank", gridcolor='#eee', dtick=5 if len(plot_df) > 10 else 1),
                yaxis=dict(title="Probability (%)", gridcolor='#eee', range=[0, max(plot_df['Probability'] * 100) * 1.1]),
                font=dict(family="Roboto, sans-serif", size=11), showlegend=False
            )
            dist_content = [
                html.H5("Projected Finish Distribution", className="mt-4 mb-3 border-bottom pb-2"),
                dcc.Graph(figure=fig, config={'displayModeBar': False}, className="bg-white rounded")
            ]
        
        # Schedule
        sched_content = []
        if not schedule_df.empty:
            s_rows = []
            for _, row in schedule_df.iterrows():
                prob = row['WinProb']
                pct = int(prob * 100)
                bg_class = "win-prob-low" if prob <= 0.4 else ("win-prob-high" if prob > 0.6 else "win-prob-med")
                
                bar = html.Div(html.Div(className=f"prob-bar-fill {bg_class}", style={"width": f"{pct}%"}), className="prob-bar-container")
                s_rows.append(html.Tr([
                    html.Td(row['Date'].strftime("%b %d"), style={"width":"15%"}),
                    html.Td([html.Span(row['Location'], className="text-muted small me-2"), html.Span(row['Opponent'], className="fw-bold")]),
                    html.Td([dbc.Row([dbc.Col(bar, width=9), dbc.Col(html.Span(f"{pct}%", className="small fw-bold"), width=3, className="text-end")], className="align-items-center g-0")], style={"width":"40%"})
                ]))
            sched_table = html.Table([
                html.Thead(html.Tr([html.Th("Date"), html.Th("Opponent"), html.Th("Win Probability")])),
                html.Tbody(s_rows)
            ], className="five-thirty-eight-table table-sm")
            sched_content.append(sched_table)
        else:
            sched_content.append(html.P("No schedule data."))

        return html.Div([
            header,
            dbc.Row([
                dbc.Col([html.Div(stats_content + dist_content, className="content-card")], md=4),
                dbc.Col([html.H4("Schedule & Projections", className="mb-3"), html.Div(sched_content, className="content-card")], md=8)
            ])
        ])

    except Exception as e:
        err_msg = traceback.format_exc()
        return html.Div([
            dbc.Alert([
                html.H4("Error Loading Team Page", className="alert-heading"),
                html.P(f"An error occurred while processing the page for {team_name}."),
                html.Pre(err_msg, style={"fontSize": "10px"})
            ], color="danger")
        ], className="mt-5")
