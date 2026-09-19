import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
from utils.data_loader import load_rankings, get_logo_url, get_available_models

dash.register_page(__name__, path='/')

def layout():
    # 1. Get Models (men's by default; the division toggle switches this client-side)
    models = get_available_models('men')
    default_model = "KRACH" if "KRACH" in models else (models[0] if models else "")

    return html.Div([
        # --- Page Header + Selectors ---
        dbc.Row([
            dbc.Col([
                html.H2("NCAA Hockey Rankings", className="mb-1"),
                html.P("Live projections and power ratings.", className="text-subtle")
            ], md=6),
            dbc.Col([
                html.Label("Division:", className="fw-bold small"),
                dcc.RadioItems(
                    id='division-selector',
                    options=[
                        {'label': " Men's", 'value': 'men'},
                        {'label': " Women's", 'value': 'women'},
                    ],
                    value='men',
                    inline=True,
                    inputStyle={"marginRight": "4px", "marginLeft": "12px"},
                )
            ], md=3, className="d-flex flex-column align-items-end justify-content-center"),
            dbc.Col([
                html.Label("Ranking System:", className="fw-bold small"),
                dcc.Dropdown(
                    id='model-selector',
                    options=[{'label': m.replace('_', ' '), 'value': m} for m in models],
                    value=default_model,
                    clearable=False,
                    style={"minWidth": "200px"}
                )
            ], md=3, className="d-flex flex-column align-items-end justify-content-center")
        ], className="mb-4 border-bottom pb-3 align-items-end"),

        # --- Rankings Table ---
        dbc.Spinner(
            html.Div(id='rankings-content'),
            color="primary",
            type="border"
        )
    ])

@callback(
    Output('model-selector', 'options'),
    Output('model-selector', 'value'),
    Input('division-selector', 'value')
)
def update_model_options(division):
    """
    Refreshes the model dropdown when the division toggle changes -- the
    two divisions don't have the same validated model roster available
    (women's hockey only has the 5-model set from
    reports/womens_hockey_import.md; men's has the full ~13-model roster
    this project has built), so the options list itself must switch, not
    just which data gets loaded for a fixed option list.
    """
    models = get_available_models(division or 'men')
    options = [{'label': m.replace('_', ' '), 'value': m} for m in models]
    default = "Massey" if "Massey" in models else ("KRACH" if "KRACH" in models else (models[0] if models else ""))
    return options, default

@callback(
    Output('rankings-content', 'children'),
    Input('model-selector', 'value'),
    Input('division-selector', 'value')
)
def update_rankings(selected_model, division):
    division = division or 'men'
    if not selected_model:
        return dbc.Alert("No ranking models found.", color="warning")

    # Load Data
    df = load_rankings(selected_model, division=division)

    if df.empty:
        return dbc.Alert(f"No data available for {selected_model} ({division}).", color="info")

    # Determine Columns
    rank_col = f'{selected_model}_Rank'
    val_col = f'{selected_model}_Val'

    # Sort
    if rank_col in df.columns:
        df = df.sort_values(rank_col)

    # Build Table Rows
    rows = []
    for idx, row in df.iterrows():
        # Rank: Use model rank or just row index counter
        rank_val = row.get(rank_col)
        rank_display = str(int(rank_val)) if pd.notna(rank_val) else str(idx + 1)

        # Rating: Format nicely
        rating_val = row.get(val_col, 0)
        rating_display = f"{rating_val:.4f}" if isinstance(rating_val, float) else str(rating_val)

        # Team Cell: Logo + Name Link
        team_name = row['Team']
        logo = get_logo_url(team_name, division=division)

        team_content = html.Div([
            html.Img(src=logo, style={"height": "24px", "width": "24px", "objectFit": "contain"}, className="me-2"),
            # division is passed through so the team-detail page can guard
            # against rendering the wrong (men's) team for a shared school
            # name -- see webpage/pages/team_detail.py's explicit check.
            dcc.Link(team_name, href=f"/team/{team_name}?model={selected_model}&division={division}",
                      className="text-dark fw-bold")
        ], className="d-flex align-items-center")

        rows.append(html.Tr([
            html.Td(rank_display, className="rank-cell"),
            html.Td(team_content),
            html.Td(row.get('Conference', '-'), className="text-muted small"),
            html.Td(row.get('Record', '-'), className="small"),
            html.Td(rating_display, className="rating-cell")
        ]))

    # Construct Header
    table_header = html.Thead(html.Tr([
        html.Th("Rank", style={"width": "60px"}),
        html.Th("Team"),
        html.Th("Conference", style={"width": "150px"}),
        html.Th("Record", style={"width": "160px"}),
        html.Th("Rating", style={"width": "100px", "textAlign": "right"})
    ]))

    table_body = html.Tbody(rows)

    return html.Table([table_header, table_body], className="five-thirty-eight-table")
