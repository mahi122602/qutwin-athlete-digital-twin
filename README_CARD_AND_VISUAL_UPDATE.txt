QUTwin Forecasting Card + Seven-Day Visualisation Update

Replace/copy these files:
1. app.py -> project root app.py
2. views/forecasting_page.py -> project views/forecasting_page.py
3. views/forecasting_card.py -> project views/forecasting_card.py

Then open views/athlete_home.py and apply the two small additions shown in
ATHLETE_HOME_PATCH.py.

The updated app removes the special Forecasting button from the top navigation.
Forecasting is opened from its own feature card on Athlete Home.

The Forecasting page now shows:
- the existing seven-day table;
- an interactive metric selector;
- a seven-day line visualisation;
- an expandable date/span/result/confidence summary;
- menstrual-cycle context in the visual summary when enabled.

Restart with:
streamlit run app.py
