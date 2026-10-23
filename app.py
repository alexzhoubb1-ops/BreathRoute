import os
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from shapely.geometry import Point, LineString

# -----------------------------------------------------------------------------
# 1. Page Configuration & Translations Dictionary
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BreatheRoute | CA-16 Highway 101 Air Quality",
    page_icon="🌬️",
    layout="wide"
)

# Bilingual dictionary for dynamic language switching
I18N = {
    "en": {
        "title": "🌬️ BreatheRoute: CA-16 Freeway Pollution Exposure Tool",
        "subtitle": "Mapping school and household proximity to Highway 101 traffic exhaust across Palo Alto, East Palo Alto, Mountain View, and San Jose.",
        "lookup_header": "📍 Proximity Lookup",
        "lookup_label": "Enter an address or school in CA-16:",
        "lookup_placeholder": "e.g., 1050 Myrtle St, East Palo Alto",
        "btn_check": "Check Proximity",
        "found_msg": "Address located!",
        "in_buffer_msg": "⚠️ Inside 500ft High Exhaust Buffer Zone!",
        "out_buffer_msg": "✅ Outside 500ft buffer zone.",
        "legend_header": "🔑 Map Legend",
        "legend_red": "🔴 Red Pin: Within 500ft (High Exposure)",
        "legend_orange": "🟠 Orange Pin: 500 - 1,000ft",
        "legend_green": "🟢 Green Pin: > 1,000ft",
        "legend_buffer": "🔴 Shaded Band: 500ft High-Risk Buffer Zone",
        "tab_map": "🗺️ Interactive Map",
        "tab_rankings": "🏫 School Proximity Rankings",
        "tab_guidance": "🛡️ What You Can Do (Official Guidance)",
        "asthma_alert": "⚕️ **Important Health Notice:** If your child has asthma, follow the asthma action plan from your doctor.",
        "g1_title": "1. Indoor Air Filtration",
        "g1_desc": "Use MERV 13+ rated HVAC filters or portable HEPA air purifiers in bedrooms and classrooms facing major roadways.",
        "g1_link": "[CARB Certified Air Cleaning Devices](https://www.arb.ca.gov/research/indoor/aircleaners/certified.htm)",
        "g2_title": "2. Peak Recess Scheduling",
        "g2_desc": "Schedule outdoor activities outside of peak commute hours (7-9 AM, 4-6 PM) when freeway particulate levels spike.",
        "g2_link": "[Bay Area Air Quality Management District (BAAQMD)](https://www.baaqmd.gov/)",
        "g3_title": "3. Spare the Air Alerts",
        "g3_desc": "Monitor real-time Air Quality Index (AQI) alerts and limit outdoor exertion on Spare the Air days.",
        "g3_link": "[Spare the Air Notifications](https://www.sparetheair.org/)",
        "g4_title": "4. School Bus & Vehicle Idle Policies",
        "g4_desc": "Enforce anti-idling zones during school pickup and dropoff to minimize localized exhaust concentration.",
        "g4_link": "[US EPA Healthy School Environments Guide](https://www.epa.gov/schools)"
    },
    "es": {
        "title": "🌬️ BreatheRoute: Exposición a la Contaminación en la CA-16",
        "subtitle": "Mapeo de la proximidad de escuelas y hogares a los gases de escape de la Autopista 101 en Palo Alto, East Palo Alto, Mountain View y San José.",
        "lookup_header": "📍 Búsqueda de Proximidad",
        "lookup_label": "Ingrese una dirección o escuela en CA-16:",
        "lookup_placeholder": "ej. 1050 Myrtle St, East Palo Alto",
        "btn_check": "Verificar Proximidad",
        "found_msg": "¡Dirección localizada!",
        "in_buffer_msg": "⚠️ ¡Dentro de la zona de peligro de 500 pies!",
        "out_buffer_msg": "✅ Fuera de la zona de amortiguamiento de 500 pies.",
        "legend_header": "🔑 Leyenda del Mapa",
        "legend_red": "🔴 Marcador Rojo: Dentro de 500 pies (Alta exposición)",
        "legend_orange": "🟠 Marcador Naranja: 500 - 1,000 pies",
        "legend_green": "🟢 Marcador Verde: > 1,000 pies",
        "legend_buffer": "🔴 Banda Sombreada: Zona de amortiguamiento de 500 pies",
        "tab_map": "🗺️ Mapa Interactivo",
        "tab_rankings": "🏫 Clasificación de Escuelas",
        "tab_guidance": "🛡️ Qué Puede Hacer (Guía Oficial)",
        "asthma_alert": "⚕️ **Aviso de Salud Importante:** Si su hijo tiene asma, siga el plan de acción contra el asma recomendado por su médico.",
        "g1_title": "1. Filtración del Aire Interior",
        "g1_desc": "Utilice filtros HVAC con clasificación MERV 13+ o purificadores de aire HEPA portátiles en dormitorios y aulas con vista a la autopista.",
        "g1_link": "[Dispositivos de Limpieza de Aire Certificados por CARB](https://www.arb.ca.gov/research/indoor/aircleaners/certified.htm)",
        "g2_title": "2. Programación de Recreos en Horas Pico",
        "g2_desc": "Programe actividades al aire libre fuera de las horas pico de tráfico (7-9 AM, 4-6 PM) cuando se disparan las partículas.",
        "g2_link": "[Distrito de Gestión de la Calidad del Aire del Área de la Bahía (BAAQMD)](https://www.baaqmd.gov/)",
        "g3_title": "3. Alertas Spare the Air",
        "g3_desc": "Monitoree las alertas en tiempo real del Índice de Calidad del Aire (ICA) y limite el esfuerzo al aire libre en días de alerta.",
        "g3_link": "[Notificaciones de Spare the Air](https://www.sparetheair.org/)",
        "g4_title": "4. Políticas Anti-Ralentí en Autobuses",
        "g4_desc": "Haga cumplir las zonas prohibidas para dejar motores encendidos durante la llegada y salida escolar.",
        "g4_link": "[Guía de Entornos Escolares Saludables de la EPA de EE. UU.](https://www.epa.gov/schools)"
    }
}

# Language Toggle Widget in Sidebar Top
selected_lang_label = st.sidebar.radio("🌐 Language / Idioma", options=["English", "Español"], horizontal=True)
lang = "es" if selected_lang_label == "Español" else "en"
t = I18N[lang]

st.title(t["title"])
st.caption(t["subtitle"])

# -----------------------------------------------------------------------------
# 2. Session State & Load Processed Geospatial Data
# -----------------------------------------------------------------------------
if "map_center" not in st.session_state:
    st.session_state["map_center"] = [37.4500, -122.1200]
if "map_zoom" not in st.session_state:
    st.session_state["map_zoom"] = 12
if "searched_point" not in st.session_state:
    st.session_state["searched_point"] = None
if "searched_dist_ft" not in st.session_state:
    st.session_state["searched_dist_ft"] = None

DATA_PATH = os.path.join("data", "processed_schools_ca16.geojson")

@st.cache_data
def load_data():
    if os.path.exists(DATA_PATH):
        gdf = gpd.read_file(DATA_PATH)
    else:
        schools_data = [
            {"name": "Costaño Community School", "city": "East Palo Alto", "lat": 37.4648, "lng": -122.1382, "distance_feet": 320.0, "within_500ft_buffer": True},
            {"name": "César Chávez Ravenswood Middle", "city": "East Palo Alto", "lat": 37.4691, "lng": -122.1325, "distance_feet": 450.0, "within_500ft_buffer": True},
            {"name": "Los Arboles Elementary", "city": "East Palo Alto", "lat": 37.4612, "lng": -122.1350, "distance_feet": 480.0, "within_500ft_buffer": True},
            {"name": "Greendell School", "city": "Palo Alto", "lat": 37.4225, "lng": -122.1189, "distance_feet": 620.0, "within_500ft_buffer": False},
            {"name": "Stevenson Elementary", "city": "Mountain View", "lat": 37.4089, "lng": -122.0912, "distance_feet": 410.0, "within_500ft_buffer": True},
            {"name": "Duveneck Elementary", "city": "Palo Alto", "lat": 37.4521, "lng": -122.1332, "distance_feet": 890.0, "within_500ft_buffer": False},
            {"name": "Crittenden Middle School", "city": "Mountain View", "lat": 37.4124, "lng": -122.0831, "distance_feet": 1100.0, "within_500ft_buffer": False},
            {"name": "Palo Alto High School", "city": "Palo Alto", "lat": 37.4367, "lng": -122.1564, "distance_feet": 1850.0, "within_500ft_buffer": False}
        ]
        gdf = gpd.GeoDataFrame(
            schools_data,
            geometry=[Point(s["lng"], s["lat"]) for s in schools_data],
            crs="EPSG:4326"
        )
    return gdf

gdf_schools = load_data()

US101_COORDS = [
    (37.4800, -122.1500),
    (37.4650, -122.1390),
    (37.4500, -122.1280),
    (37.4300, -122.1100),
    (37.4100, -122.0850),
    (37.3900, -121.9800)
]

# -----------------------------------------------------------------------------
# 3. Sidebar Proximity Lookup Controls & Legend
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header(t["lookup_header"])

address_query = st.sidebar.text_input(
    t["lookup_label"],
    placeholder=t["lookup_placeholder"]
)

if st.sidebar.button(t["btn_check"], type="primary"):
    if address_query:
        try:
            geolocator = Nominatim(user_agent="breatheroute_app_v1")
            location = geolocator.geocode(f"{address_query}, California")

            if location:
                lat, lng = location.latitude, location.longitude
                st.session_state["searched_point"] = (lat, lng)
                st.session_state["map_center"] = [lat, lng]
                st.session_state["map_zoom"] = 12 if location.raw.get("addresstype") == "city" else 15

                pt_proj = (
                    gpd.GeoSeries([Point(lng, lat)], crs="EPSG:4326")
                    .to_crs(epsg=3310)
                    .iloc[0]
                )
                dist_meters = pt_proj.distance(road_geometry)

                st.sidebar.success(t["found_msg"])
            else:
                st.sidebar.warning("Address not found. Please try adding city name.")
        except Exception:
            st.sidebar.error("Geocoding lookup timed out. Please try again.")

if st.session_state["searched_dist_ft"] is not None:
    dist_ft = st.session_state["searched_dist_ft"]
    if dist_ft <= 500:
        st.sidebar.error(f"{t['in_buffer_msg']} ({dist_ft} ft)")
    else:
        st.sidebar.info(f"{t['out_buffer_msg']} ({dist_ft} ft)")

st.sidebar.markdown("---")
st.sidebar.markdown(f"### {t['legend_header']}")
st.sidebar.markdown(t["legend_red"])
st.sidebar.markdown(t["legend_orange"])
st.sidebar.markdown(t["legend_yellow"])
st.sidebar.markdown(t["legend_gray"])
st.sidebar.markdown(t["legend_buffer"])

# -----------------------------------------------------------------------------
# 4. Main Tabs Navigation
# -----------------------------------------------------------------------------
tab_map, tab_rankings, tab_guidance = st.tabs([t["tab_map"], t["tab_rankings"], t["tab_guidance"]])

with tab_map:
    center_lat, center_lng = st.session_state["map_center"]
    zoom_level = st.session_state["map_zoom"]

    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level, tiles="OpenStreetMap")

    folium.GeoJson(
        gdf_roads.to_json(),
        name="High-traffic highways",
        style_function=lambda feature: {
            "color": "crimson",
            "weight": 4,
            "opacity": 0.9,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["route", "aadt"],
            aliases=["Route:", "2024 AADT:"],
            localize=True,
        ),
    ).add_to(m)

    buffer_wgs84 = gpd.GeoSeries(
        [road_geometry.buffer(152.4)], crs="EPSG:3310"
    ).to_crs(epsg=4326)

    folium.GeoJson(
        buffer_wgs84,
        style_function=lambda x: {
            "fillColor": "#f87171",
            "color": "#ef4444",
            "weight": 1.5,
            "fillOpacity": 0.25,
            "dashArray": "4, 4"
        },
        tooltip="500ft buffer around roads above 100,000 AADT"
    ).add_to(m)

    for idx, row in gdf_schools.iterrows():
        dist_ft = row["distance_feet"]
        color = (
            "red" if dist_ft <= 500
            else "orange" if dist_ft < 1000
            else "yellow" if dist_ft <= 1640
            else "gray"
        )

        popup_html = f"""
        <div style="font-family: sans-serif; font-size: 12px;">
            <b>{row['name']}</b><br>
            <i>{row['city']}</i><br>
            <b>Distance:</b> {dist_ft} ft<br>
            {'<span style="color:red; font-weight:bold;">⚠️ Inside 500ft Buffer</span>' if dist_ft <= 500 else ''}
        </div>
        """

        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=8,
            color="white",
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=popup_html,
            tooltip=f"{row['name']} ({dist_ft} ft)"
        ).add_to(m)

    if st.session_state["searched_point"]:
        s_lat, s_lng = st.session_state["searched_point"]
        s_dist = st.session_state["searched_dist_ft"]
        folium.Marker(
            location=[s_lat, s_lng],
            icon=folium.Icon(color="blue", icon="info-sign"),
            popup=f"Searched Address<br>Distance: {s_dist} ft",
            tooltip="Searched Location"
        ).add_to(m)

    st.caption(t["data_source"])
    st_folium(m, width="100%", height=550)

with tab_rankings:
    display_df = gdf_schools.sort_values("distance_feet")[
        ["name", "city", "distance_feet", "within_500ft_buffer"]
    ].copy()
    display_df.columns = ["School Name", "City", "Distance (ft)", "In 500ft Zone"]
    display_df["In 500ft Zone"] = display_df["In 500ft Zone"].map(
        lambda x: "⚠️ Within 500-ft buffer" if x else "Outside 500-ft buffer"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Distance (ft)": st.column_config.NumberColumn(format="%d ft"),
        }
    )

with tab_guidance:
    st.error(t["asthma_alert"])

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(t["g1_title"])
        st.write(t["g1_desc"])
        st.markdown(f"🔗 **Source:** {t['g1_link']}")
        st.markdown("---")

        st.subheader(t["g3_title"])
        st.write(t["g3_desc"])
        st.markdown(f"🔗 **Source:** {t['g3_link']}")

    with col2:
        st.subheader(t["g2_title"])
        st.write(t["g2_desc"])
        st.markdown(f"🔗 **Source:** {t['g2_link']}")
        st.markdown("---")

        st.subheader(t["g4_title"])
        st.write(t["g4_desc"])
        st.markdown(f"🔗 **Source:** {t['g4_link']}")