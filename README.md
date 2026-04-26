# 🌬️ AirWatch — IQAir Powered Dashboard

## Live Demo

This app is live at: https://salman006.pythonanywhere.com/author

## Setup

```bash
pip install flask
python app.py
# The first time it runs, it will ask for your IQAir API key in the terminal.
# Enter the key and it will be saved to api_key.txt for future runs.
# Open: http://localhost:5000
```

## Features
- Country → State → City cascade dropdowns (IQAir API)
- Live AQI with animated gauge + needle
- Health status, advice, main pollutant
- Weather conditions (temp, humidity, wind, pressure)
- Multi-city comparison bars
- Auto-detect nearest city button

## API Key
This app no longer hardcodes the API key.
On first run, it will prompt you in the terminal for your IQAir API key and store it in `api_key.txt`.
Make sure not to commit `api_key.txt` to Git — it is already ignored by `.gitignore`.

Get your API key by signing up at the IQAir API page: https://www.iqair.com/air-pollution-data-api
Free plan: 10,000 calls/month.
