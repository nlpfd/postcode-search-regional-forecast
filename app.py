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
        return [], None
    
    data = response.json()
    
    # Extract the region name from the response
    region_name = data['data'].get('shortname', 'Unknown Region')
    
    return data['data']['data'], region_name

# Create a color based on the percentage of wind, solar, and hydro energy
def create_tile_color(average_percentage):
    if average_percentage < 25:
        return "rgb(230, 230, 230)"  # Light grey for percentages under 25%
    elif average_percentage < 50:
        green_color = (173, 255, 47)  # Light green (lime green base)
        light_grey_color = (230, 230, 230)
        factor = (average_percentage - 25) / 25
        factor = min(max(factor, 0), 1)
        color = tuple(int(light_grey_color[i] * (1 - factor) + green_color[i] * factor) for i in range(3))
    elif average_percentage < 70:
        strong_green_color = (50, 205, 50)  # Lime green
        light_green_color = (173, 255, 47)
        factor = (average_percentage - 50) / 20
        factor = min(max(factor, 0), 1)
        color = tuple(int(light_green_color[i] * (1 - factor) + strong_green_color[i] * factor) for i in range(3))
    else:
        luminous_green_color = (0, 255, 0)  # Very bright green
        strong_green_color = (50, 205, 50)
        factor = (average_percentage - 70) / 30
        factor = min(max(factor, 0), 1)
        color = tuple(int(strong_green_color[i] * (1 - factor) + luminous_green_color[i] * factor) for i in range(3))
    
    return f"rgb({color[0]},{color[1]},{color[2]})"

# Group data by hour and calculate the average for each hour, including hydro
def group_data_by_hour(combined_data):
    hourly_data = {}
    
    for entry in combined_data:
        timestamp = datetime.strptime(entry['from'], "%Y-%m-%dT%H:%MZ")
        hour = timestamp.replace(minute=0)  # Use the hour, discard minutes
        
        wind_perc = next((item['perc'] for item in entry['generationmix'] if item['fuel'] == 'wind'), 0)
        solar_perc = next((item['perc'] for item in entry['generationmix'] if item['fuel'] == 'solar'), 0)
        hydro_perc = next((item['perc'] for item in entry['generationmix'] if item['fuel'] == 'hydro'), 0)
        
        # Include hydro in the combined renewable percentage
        combined_renewable_perc = wind_perc + solar_perc + hydro_perc
        
        if hour not in hourly_data:
            hourly_data[hour] = {'count': 0, 'total_renewable_perc': 0}
        
        hourly_data[hour]['count'] += 1
        hourly_data[hour]['total_renewable_perc'] += combined_renewable_perc
    
    # Calculate the average for each hour
    for hour in hourly_data:
        hourly_data[hour]['average_renewable_perc'] = round(hourly_data[hour]['total_renewable_perc'] / hourly_data[hour]['count'])
    
    return hourly_data

# Generate an HTML file for the energy calendar
def generate_html_calendar(postcode, region_name):
    combined_data, _ = fetch_combined_data(postcode)
    
    if not combined_data:
        return "<p>Sorry, no data is available for the postcode '{}'. Please try entering another postcode.</p>".format(postcode)
    
    # Group data by hour and calculate the average
    hourly_data = group_data_by_hour(combined_data)
    
    # Ensure we have exactly 48 hour intervals (trim if needed)
    tiles = []
    count = 0
    for hour, data in hourly_data.items():
        if count >= 48:  # Stop at 48 entries
            break
        average_renewable_perc = data['average_renewable_perc']
        color = create_tile_color(average_renewable_perc)
        
        time_str = hour.strftime("%H:%M")
        day_of_week = hour.strftime("%A")
        
        tiles.append({'color': color, 'time': time_str, 'date': day_of_week, 'percentage': average_renewable_perc})
        count += 1  # Increment counter to ensure exactly 48 tiles
    
    # Ensure a 48-tile layout with 16 tiles per row
    calendar_html = '''
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            box-sizing: border-box;  /* Ensure padding/margin are included in the width */
        }

        body {
            font-family: 'Arial', sans-serif;
            background-color: #f7f9fb;
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            color: #333;
        }

        .header {
            text-align: center;
            background-color: #4CAF50;
            font-family: 'Arial', sans-serif;
            padding: 30px 20px;
            font-size: 36px;
            color: white;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .postcode-form {
            text-align: center;
            margin-bottom: 10px;
            margin-top: 20px;
            font-size: 18px;
        }

        .postcode-form input[type="text"] {
            font-size: 18px;
            padding: 12px;
            width: 260px;
            margin-right: 15px;
            border-radius: 6px;
            border: 1px solid #ccc;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
            transition: box-shadow 0.3s ease;
        }

        .postcode-form input[type="text"]:focus {
            outline: none;
            box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.2);
        }

        .postcode-form input[type="submit"] {
            font-size: 18px;
            padding: 12px 20px;
            font-weight: bold;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: background-color 0.3s ease, box-shadow 0.3s ease;
        }

        .postcode-form input[type="submit"]:hover {
            background-color: #45a049;
            box-shadow: 0 6px 10px rgba(0, 0, 0, 0.15);
        }

        .postcode-form input[type="submit"]:focus {
            outline: none;
            box-shadow: 0 0 6px rgba(50, 205, 50, 0.6);
        }

        .calendar {
            display: grid;
            grid-template-columns: repeat(8, 1fr);  /* 8 tiles per row for larger screens */
            gap: 10px;
            padding: 20px;
            max-width: 100%;
            margin: 0 auto;
        }

        /* Styling for 1920px screen width */
        @media (max-width: 1920px) {
            .calendar {
                grid-template-columns: repeat(8, 1fr);  /* 8 tiles per row for screens 1920px */
            }
        }

        /* Mobile styling */
        @media (max-width: 768px) {
            .header {
                font-size: 28px;
                padding: 20px;
            }

            .postcode-form {
                margin-top: 20px;
                margin-bottom: 20px;
            }

            .postcode-form input[type="text"] {
                width: 70%;
                margin-bottom: 10px;
            }

            .postcode-form input[type="submit"] {
                width: 60%;
            }

            .calendar {
                grid-template-columns: repeat(4, 1fr);  /* 4 tiles per row for screens smaller than 768px */
                padding-left: 5px;  /* Ensure slight padding on left side */
                padding-right: 5px; /* Ensure slight padding on right side */
            }

            .tile span.day {
                font-weight: bold;
                font-size: 10.5px !important;  /* Change the font size only for mobile */
            }

            .tile span.time {
                font-size: 10px !important;  /* Adjust the time font size for mobile */
            }

            .tile span.percentage {
                font-size: 12px !important;  /* Adjust percentage size for mobile */
            }
        }

        /* Ensure the tile content is centered */
        .tile {
            background-color: #ffffff;
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            display: flex;
            flex-direction: column;
            justify-content: space-between;  /* Keep original vertical spacing */
            align-items: center;             /* Ensure horizontal centering */
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            font-size: 12px;
            min-width: 80px;   /* Adjust the width of the tiles */
            height: 100px;     /* Adjust the height of the tiles */
        }

        .tile:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 10px rgba(0, 0, 0, 0.12);
        }

        .tile span.day, .tile span.time, .tile span.percentage {
            text-align: center;  /* Ensure all text stays centered */
        }

        footer {
            text-align: center;
            margin-top: 10px;
            padding-bottom: 20px;
            font-size: 12px;
            color: #777;
        }
    </style>
</head>
<body>
    <h2 class="header">48-Hour Renewable Energy Regional Forecast: {{ region_name }}</h2>
    <form method="post" class="postcode-form">
        <input type="text" name="postcode" placeholder="Enter postcode">
        <input type="submit" value="Check Forecast">
    </form>
    <div class="calendar">
        {% for tile in tiles %}
            <div class="tile" style="background-color: {{ tile.color }};">
                <span class="day">{{ tile.date }}</span><br>
                <span class="time">{{ tile.time }}</span><br>
                <span class="percentage">{{ tile.percentage }}%</span>
            </div>
        {% endfor %}
    </div>
    <footer>
        Data from National Grid ESO, Carbon Intensity API
    </footer>
</body>
</html>
    '''
    
    return render_template_string(calendar_html, tiles=tiles, postcode=postcode, region_name=region_name)

# First view page with updated design (without affecting the results page)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'postcode' not in request.form or not request.form['postcode']:
            return "<p>Postcode is required. Please enter a valid postcode.</p>"
        
        postcode = request.form['postcode']
        outward_code = convert_to_outward_code(postcode)
        
        if outward_code:
            combined_data, region_name = fetch_combined_data(outward_code)
            if combined_data:
                return generate_html_calendar(outward_code, region_name)
            else:
                return "<p>Sorry, no data is available for this region. Please try again later.</p>"
        else:
            return "<p>Invalid postcode. Please try again.</p>"
    
    # First view page (postcode input page) with reduced white space
    return '''
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Arial', sans-serif;
                background-color: #f7f9fb;
                color: #333;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                flex-direction: column;
            }

            h1 {
                font-size: 3em;
                font-weight: bold;
                margin-bottom: 20px;
                text-align: center;
            }

            form {
                text-align: center;
                margin-bottom: 0;  /* Adjust this to control space below the form */
            }

            input[type="text"] {
                padding: 15px;
                font-size: 1.2em;
                width: 350px;
                margin-bottom: 20px;
                border-radius: 8px;
                border: 1px solid #ddd;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
            }

            input[type="text"]:focus {
                outline: none;
                border: 1px solid #4CAF50;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            }

            input[type="submit"] {
                padding: 15px 30px;
                font-size: 1.2em;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                margin-top: 10px;  /* Adjust the space between input and button */
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
            }

            input[type="submit"]:hover {
                background-color: #45a049;
                box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
            }

            /* Mobile styling */
            @media (max-width: 768px) {
                h1 {
                    font-size: 2.5em;
                }

                input[type="text"] {
                    width: 80%;  /* Adjust width for mobile devices */
                }

                input[type="submit"] {
                    width: 70%;  /* Adjust button size for mobile */
                }
            }
        </style>
    </head>
    <body>
        <h1>48-Hour Renewable Energy Forecast</h1>
        <form method="post">
            <input type="text" id="postcode" name="postcode" placeholder="Enter postcode"><br>
            <input type="submit" value="Check Forecast">
        </form>
    </body>
    </html>
    '''
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
