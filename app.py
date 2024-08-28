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
            return outward_code.upper()
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
        factor = (combined_renewable_perc - 40) / 60
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
                grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
                gap: 2px;
                padding: 10px;
            }
            .tile {
                background-color: #f0f0f0;
                text-align: center;
                font-size: 16px;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            }
            .header {
                text-align: center;
                font-weight: 900; /* Extra bold */
                background-color: #f2f2f2;
                font-family: Calibri, sans-serif;
                padding: 20px;
                font-size: 30px; /* Slightly larger and bolder */
            }
            .tile span:first-child {
                font-weight: bold;
            }
            .postcode-form {
                text-align: center;
                margin-bottom: 20px;
                margin-top: 20px;
                font-size: 22px;
                font-weight: bold;
            }
            .postcode-form input[type="text"] {
                font-size: 20px;
                padding: 10px;
                width: 40%;
                margin-right: 10px;
            }
            .postcode-form input[type="submit"] {
                font-size: 20px;
                padding: 10px 20px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <h2 class="header">48-Hour Wind & Solar Forecast: {{ postcode }}</h2>
        <form method="post" class="postcode-form">
            Enter your postcode: <input type="text" name="postcode" value="{{ postcode }}">
            <input type="submit" value="Check Forecast">
        </form>
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
        combined_renewable_perc = round(wind_perc + solar_perc)
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
        if 'postcode' not in request.form or not request.form['postcode']:
            return "<p>Postcode is required. Please enter a valid postcode.</p>"
        
        postcode = request.form['postcode']
        outward_code = convert_to_outward_code(postcode)
        
        if outward_code:
            calendar_html = generate_html_calendar(outward_code)
            return calendar_html
        else:
            return "<p>Invalid postcode. Please try again.</p>"
    return '''
        <div style="display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column;">
            <h1 style="text-align: center; font-size: 3em; font-weight: bold; font-family: Calibri, sans-serif; margin-bottom: 20px;">48-Hour Wind & Solar Forecast</h1>
            <form method="post" style="text-align: center; font-family: Calibri, sans-serif;">
                <label for="postcode" style="font-size: 2em; font-weight:bold;">Enter your postcode:</label><br>
                <input type="text" id="postcode" name="postcode" style="font-size: 2em; padding: 10px; width: 300px;"><br>
                <input type="submit" value="Check Forecast" style="font-size: 2em; padding: 10px 20px; margin-top: 20px;">
            </form>
        </div>
    '''

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
