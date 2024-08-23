import os
from flask import Flask, request, render_template_string
import requests
from datetime import datetime

app = Flask(__name__)

# Function to convert full postcode to outward code using Postcodes.io
def convert_to_outward_code(postcode):
    response = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 200:
            outward_code = data['result']['outcode']
            return outward_code
    return None

# Fetch renewable energy data for the specified postcode
def fetch_combined_data(postcode):
    current_datetime = datetime.utcnow()
    fw48h_start = current_datetime.strftime("%Y-%m-%dT%H:%MZ")
    fw48h_url = f"https://api.carbonintensity.org.uk/regional/intensity/{fw48h_start}/fw48h/postcode/{postcode}"
    
    try:
        response = requests.get(fw48h_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data: {e}")
        return []
    
    data = response.json()
    return data['data']['data']

# Create a color based on the percentage of wind and solar energy
def create_tile_color(wind_perc, solar_perc):
    combined_renewable_perc = wind_perc + solar_perc

    if combined_renewable_perc < 40:
        return "rgb(230, 230, 230)"  # Light grey for percentages under 40%
    else:
        green_color = (0, 255, 0)
        light_grey_color = (230, 230, 230)
        factor = (combined_renewable_perc - 40) / 60  # Normalizing between 40% and 100%
        color = tuple(int(green_color[i] * factor + light_grey_color[i] * (1 - factor)) for i in range(3))
        return f"rgb({color[0]},{color[1]},{color[2]})"

# Function to get the correct ordinal suffix for a given day
def get_ordinal_suffix(day):
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix

# Generate an HTML file for the energy calendar
def generate_html_calendar(postcode):
    combined_data = fetch_combined_data(postcode)
    
    if not combined_data:
        return "<p>Sorry, no data is available for the postcode '{}'. Please try entering another postcode.</p>".format(postcode)
    
    calendar_html = '''
    <html>
    <head>
        <style>
            body {
                font-family: Calibri, sans-serif;
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            .calendar {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(60px, 1fr)); /* Default Responsive columns */
                gap: 2px;
                padding: 10px;
            }
            .tile {
                background-color: #f0f0f0;
                text-align: center;
                font-size: 11px;
                padding: 5px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            }
            .header {
                text-align: center;
                font-weight: bold;
                background-color: #f2f2f2;
                font-family: Calibri, sans-serif;
                padding: 10px;
            }
            /* Mobile-friendly adjustments */
            @media (max-width: 600px) {
                .calendar {
                    grid-template-columns: repeat(4, 1fr); /* Max 4 columns wide */
                }
                .tile {
                    font-size: 10px;
                    padding: 3px;
                }
                .header {
                    font-size: 14px;
                    padding: 5px;
                }
            }
            /* Embedded version adjustments */
            @media (min-width: 601px) and (max-width: 1200px) {
                .calendar {
                    grid-template-columns: repeat(10, 1fr); /* Max 10 columns wide */
                }
            }
        </style>
    </head>
    <body>
        <h2 class="header">48-Hour Wind & Solar Forecast: {{ postcode }}</h2>
        <div class="calendar">
            {% for tile in tiles %}
                <div class="tile" style="background-color: {{ tile.color }};">
                    <span>{{ tile.time }}</span><br>
                    <span>{{ tile.date }}</span><br>
                    <span>{{ tile.percentage }}%</span>
                </div>
            {% endfor %}
        </div>
    </body>
    </html>
    '''

    tiles = []
    for entry in combined_data:
        wind_perc = next((item['perc'] for item in entry['generationmix'] if item['fuel'] == 'wind'), 0)
        solar_perc = next((item['perc'] for item in entry['generationmix'] if item['fuel'] == 'solar'), 0)
        combined_renewable_perc = round(wind_perc + solar_perc)  # Rounded to nearest whole number
        color = create_tile_color(wind_perc, solar_perc)
        
        timestamp = datetime.strptime(entry['from'], "%Y-%m-%dT%H:%MZ")
        time_str = timestamp.strftime("%H:%M")
        day = timestamp.day
        month = timestamp.strftime("%B")
        date_str = f"{month} {day}{get_ordinal_suffix(day)}"
        
        tiles.append({'color': color, 'time': time_str, 'date': date_str, 'percentage': combined_renewable_perc})
    
    return render_template_string(calendar_html, tiles=tiles, postcode=postcode)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        postcode = request.form['postcode']
        outward_code = convert_to_outward_code(postcode)
        if outward_code:
            calendar_html = generate_html_calendar(outward_code)
            return calendar_html
        else:
            return "<p>Invalid postcode. Please try again.</p>"
    return '''
        <form method="post">
            Enter your postcode: <input type="text" name="postcode">
            <input type="submit" value="Check Forecast">
        </form>
    '''

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
