# OSDR Environmental Data App (EDA): manual download

**Preferred:** `python data/fetch/fetch_osdr_eda.py` downloads the same tables through the public EDA API.
The manual steps below are the fallback if the API is down.

1. Open https://visualization.osdr.nasa.gov/eda/
2. On the **Mission Dashboard**, pick a Rodent Research (RR) mission. Start with one long mission, then add 2–3 more so the notebooks can compare missions.
3. Open the **Data Tables** tab and download:
   - the **telemetry** table (ISS + ground: temperature, relative humidity, CO2 at each time point), **full/raw** version, not only the summary;
   - the **radiation** table (GCR dose, SAA dose, accumulated dose, total dose; daily).
4. Save the files unchanged into `data/raw/osdr_eda/`, named like `RR-<n>_telemetry.csv` and `RR-<n>_radiation.csv` (keep the original extension if it is .xlsx).
5. Run `python data/fetch/inspect_sources.py` and write down in `docs/DATASETS.md`:
   - the CO2 unit (% or mmHg; 0.5 % = 3.8 mmHg at 1 atm),
   - the sampling interval (it isn't documented),
   - the mission dates covered.

Credit line to use in the app and the slides: *"Data and visualizations are courtesy of the Environmental Data Application (EDA) (https://visualization.osdr.nasa.gov/eda/)."*

Optional programmatic alternative for ISS radiation only: the OSDR **RadLab** portal and its Data API.
