## Thursday, Oct 22 - Geospatial Pipeline & Projection Calculations

### Progress Completed
- Implemented GeoPandas processing script (`clip_and_calculate.py`).
- Reprojected spatial data from spherical WGS84 (`EPSG:4326`) to California Albers (`EPSG:3310`) to perform accurate metric linear distance calculations.
- Computed exact point-to-line perpendicular distance from each school in CA-16 to the US-101 freeway geometry and converted meters to feet.
- Flagged all school points falling within the high-risk 500-foot traffic exhaust buffer zone.
- Exported processed results to GeoJSON format (`data/processed_schools_ca16.geojson`).

### Technical Challenge & Solution
- **Challenge:** Initial spherical distance logic produced non-linear distortions along curved sections of Highway 101.
- **Solution:** Converted all geometries to projected metric CRS (`EPSG:3310`), computed Shapely `distance()` on unified polyline geometry, and multiplied by `3.28084` for precise distance in feet.



## Friday, Oct 23 - Streamlit Interface & Interactive Folium Map

### Progress Completed
- Built the main Streamlit application layout (`app.py`).
- Integrated `folium` via `streamlit-folium` to render Highway 101 vector polylines and dynamic 500ft buffer polygons.
- Implemented real-time address geocoding with `geopy` (Nominatim engine) for family and school lookup.
- Rendered proximity metrics and color-coded risk markers (Red < 500ft, Orange < 1000ft, Green > 1000ft).
- Constructed interactive school ranking table sorted by exact freeway distance.

### Technical Challenge & Solution
- **Challenge:** Map state re-rendering caused slow reloading when running address lookups in Streamlit.
- **Solution:** Cached GeoJSON dataset loading using `@st.cache_data` and separated map state handling to improve interface responsiveness.


## Saturday, Oct 24 - Language Toggle, Official Guidance & Cloud Deployment

### Progress Completed
- Integrated a bilingual dictionary (`I18N`) into `app.py` enabling real-time toggling between English and Spanish.
- Built the "What You Can Do" tab featuring official environmental and health actions linked directly to source agencies (EPA, CARB, BAAQMD, Spare the Air).
- Embedded the mandatory medical statement: *"If your child has asthma, follow the asthma action plan from your doctor."*
- Deployed application to Streamlit Community Cloud linked directly to public GitHub repository.
- Conducted user testing with family members to verify geocoding and bilingual UI responsiveness.

### Technical Challenge & Solution
- **Challenge:** Dynamic language state changes reset map zoom levels during navigation.
- **Solution:** Maintained map coordinate states independently from language state variables within Streamlit's reactive execution loop.