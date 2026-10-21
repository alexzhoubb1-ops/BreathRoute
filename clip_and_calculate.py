import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Constants
METERS_TO_FEET = 3.28084
BUFFER_THRESHOLD_FT = 500

def run_geospatial_pipeline():
    print("🚀 Starting Day 2 Geospatial Pipeline...")

    # ------------------------------------------------------------------
    # Step 1: Load or Mock Raw Data
    # ------------------------------------------------------------------
    # NOTE: In production, load shapefiles/GeoJSONs via gpd.read_file("path_to_file")
    # For initial testing, we instantiate CA-16 101 corridor geometries directly.
    
    # Raw School Coordinates (EPSG:4326 - WGS84 Lat/Lng)
    schools_raw = pd.DataFrame([
        {"school_id": 101, "name": "Costaño Community School", "city": "East Palo Alto", "lat": 37.4648, "lng": -122.1382},
        {"school_id": 102, "name": "César Chávez Ravenswood Middle", "city": "East Palo Alto", "lat": 37.4691, "lng": -122.1325},
        {"school_id": 103, "name": "Los Arboles Elementary", "city": "East Palo Alto", "lat": 37.4612, "lng": -122.1350},
        {"school_id": 104, "name": "Greendell School", "city": "Palo Alto", "lat": 37.4225, "lng": -122.1189},
        {"school_id": 105, "name": "Stevenson Elementary", "city": "Mountain View", "lat": 37.4089, "lng": -122.0912},
        {"school_id": 106, "name": "Duveneck Elementary", "city": "Palo Alto", "lat": 37.4521, "lng": -122.1332},
        {"school_id": 107, "name": "Crittenden Middle School", "city": "Mountain View", "lat": 37.4124, "lng": -122.0831},
        {"school_id": 108, "name": "Palo Alto High School", "city": "Palo Alto", "lat": 37.4367, "lng": -122.1564}
    ])

    # Convert DataFrame to GeoDataFrame
    geometry = [Point(xy) for xy in zip(schools_raw['lng'], schools_raw['lat'])]
    gdf_schools = gpd.GeoDataFrame(schools_raw, geometry=geometry, crs="EPSG:4326")

    # US-101 Polyline Geometry (CA-16 Corridor Segment)
    us101_line_coords = [
        (-122.1500, 37.4800),
        (-122.1390, 37.4650),
        (-122.1280, 37.4500),
        (-122.1100, 37.4300),
        (-122.0850, 37.4100),
        (-121.9800, 37.3900)
    ]
    from shapely.geometry import LineString
    gdf_freeway = gpd.GeoDataFrame(
        [{"route": "US-101", "corridor": "CA-16"}],
        geometry=[LineString(us101_line_coords)],
        crs="EPSG:4326"
    )

    # ------------------------------------------------------------------
    # Step 2: Project to Metric Coordinate Reference System (EPSG:3310)
    # ------------------------------------------------------------------
    # CRITICAL: Distance calculations on spherical WGS84 (lat/lng) introduce severe distortion.
    # California Albers (EPSG:3310) provides accurate metric projections for Northern California.
    
    print("🗺️ Reprojecting datasets to California Albers (EPSG:3310)...")
    gdf_schools_proj = gdf_schools.to_crs(epsg=3310)
    gdf_freeway_proj = gdf_freeway.to_crs(epsg=3310)

    # Combine US-101 segments into a single geometry object
    freeway_geom = gdf_freeway_proj.geometry.unary_union

    # ------------------------------------------------------------------
    # Step 3: Calculate Exact Perpendicular Distance in Feet
    # ------------------------------------------------------------------
    print("📏 Computing point-to-line distances and 500ft buffer statuses...")
    
    # Point-to-Line metric distance calculation
    gdf_schools_proj['distance_meters'] = gdf_schools_proj.geometry.distance(freeway_geom)
    
    # Convert meters to feet
    gdf_schools_proj['distance_feet'] = (gdf_schools_proj['distance_meters'] * METERS_TO_FEET).round(1)
    
    # High-risk 500ft buffer boolean flag
    gdf_schools_proj['within_500ft_buffer'] = gdf_schools_proj['distance_feet'] <= BUFFER_THRESHOLD_FT

    # Sort schools by proximity (closest first)
    gdf_schools_ranked = gdf_schools_proj.sort_values(by='distance_feet').reset_index(drop=True)

    # ------------------------------------------------------------------
    # Step 4: Export Processed Data for Streamlit App (Friday Step)
    # ------------------------------------------------------------------
    # Convert back to WGS84 for GeoJSON / Folium map display
    gdf_output = gdf_schools_ranked.to_crs(epsg=4326)
    
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "processed_schools_ca16.geojson")
    
    gdf_output.to_file(output_path, driver="GeoJSON")
    print(f"✅ Exported processed dataset to: {output_path}")

    # Display Results Table in Terminal
    print("\n--- CA-16 Schools Ranked by US-101 Proximity ---")
    summary = gdf_schools_ranked[['name', 'city', 'distance_feet', 'within_500ft_buffer']]
    print(summary.to_string(index=False))

if __name__ == "__main__":
    run_geospatial_pipeline()