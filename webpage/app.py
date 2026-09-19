import datetime
import dash
from dash import html
import dash_bootstrap_components as dbc
from utils.data_loader import ensure_logos_in_assets

# Initialize Assets
ensure_logos_in_assets()

# Initialize App
app = dash.Dash(
    __name__, 
    use_pages=True, 
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True
)
server = app.server

# --- Layout Components ---

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Rankings", href="/")),
        # Add more links here if needed (e.g. "About", "Methodology")
    ],
    brand="College Hockey Projections",
    brand_href="/",
    color="dark",
    dark=True,
    className="mb-4"
)

footer = html.Footer([
    dbc.Container([
        html.P(f"© {datetime.date.today().year} College Hockey Projections. Data inspired by KRACH, LRMC.",
               className="text-center mb-0")
    ])
], className="page-footer bg-light")

# --- Main Layout ---
app.layout = html.Div([
    navbar,
    dbc.Container([
        dash.page_container
    ], className="mb-5", style={"minHeight": "80vh"}),
    footer
])

if __name__ == "__main__":
    app.run(debug=True)
