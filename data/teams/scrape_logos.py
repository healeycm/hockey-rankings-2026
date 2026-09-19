import os
import csv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://www.collegehockeynews.com"
START_URL = "https://www.collegehockeynews.com/reports/team/"
IMAGE_FOLDER = "team_logos"
DATA_FILE = "college_hockey_teams.csv"

# Create folder for images
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)


def scrape_hockey_teams():
    print(f"Connecting to {START_URL}...")
    try:
        response = requests.get(START_URL, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
    except Exception as e:
        print(f"Error accessing main page: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    rows = soup.find_all('tr')

    current_conference = "Independent"
    team_data_list = []

    print("Parsing team list and conferences...")
    for row in rows:
        # Check for Conference Header
        if 'stats-section' in row.get('class', []):
            current_conference = row.get_text(strip=True)
            continue

        cells = row.find_all('td')
        # Structure: td[0] = Name, td[1] = Link to Team Page
        if len(cells) >= 2:
            team_name = cells[0].get_text(strip=True)
            link_tag = cells[1].find('a', href=True)

            if link_tag:
                team_url = urljoin(BASE_URL, link_tag['href'])
                team_data_list.append({
                    "name": team_name,
                    "conference": current_conference,
                    "url": team_url
                })

    final_output = []

    # Process individual team pages
    for team in team_data_list:
        print(f"Processing: {team['name']} ({team['conference']})")

        try:
            res = requests.get(team['url'], headers={'User-Agent': 'Mozilla/5.0'})
            team_soup = BeautifulSoup(res.text, 'html.parser')

            # Find logo in <div class="logo"> as <img>
            logo_div = team_soup.find('div', class_='logo')
            img_tag = logo_div.find('img') if logo_div else None

            logo_url = "N/A"
            local_image_path = "N/A"

            if img_tag and img_tag.get('src'):
                logo_url = urljoin(BASE_URL, img_tag['src'])

                # Download and save the image
                img_ext = logo_url.split('.')[-1].split('?')[0]  # handle potential url params
                filename = f"{team['name'].replace(' ', '_').lower()}.{img_ext}"
                local_image_path = os.path.join(IMAGE_FOLDER, filename)

                img_data = requests.get(logo_url).content
                with open(local_image_path, 'wb') as f:
                    f.write(img_data)

            final_output.append([team['name'], team['conference'], team['url'], logo_url, local_image_path])

        except Exception as e:
            print(f"   Failed to process {team['name']}: {e}")

    # Save data to CSV
    with open(DATA_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Team Name", "Conference", "Team Page URL", "Logo URL", "Local Image Path"])
        writer.writerows(final_output)

    print(f"\nDone! Processed {len(final_output)} teams.")
    print(f"Data saved to {DATA_FILE}")
    print(f"Logos saved to folder: {IMAGE_FOLDER}/")


if __name__ == "__main__":
    scrape_hockey_teams()