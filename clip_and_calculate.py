import json
import os
import tempfile
import time
from collections import defaultdict
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
from shapely.geometry import Point, shape
from shapely.ops import unary_union

METERS_TO_FEET = 3.28084
BUFFER_THRESHOLD_FT = 500
AADT_THRESHOLD = 100_000
AADT_YEAR = 2024
ROAD_COVERAGE_BUFFER_METERS = 2_000
DISTRICT_GEOID = "0616"
CENSUS_BOUNDARY_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2024/CD/tl_2024_06_cd119.zip"
)
CALTRANS_BASE_URL = (
    "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHhighway"
)
ROAD_LAYER_URL = f"{CALTRANS_BASE_URL}/SHN_Lines/FeatureServer/0/query"
AADT_LAYER_URL = f"{CALTRANS_BASE_URL}/Traffic_AADT/FeatureServer/0/query"
OUTPUT_DIR = "data"
ROADS_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "qualifying_roads_ca16.geojson")
SCHOOLS_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "processed_schools_ca16.geojson")

SCHOOLS = [
    {"name": "Costaño Community School", "city": "East Palo Alto", "lat": 37.4780700, "lng": -122.1385900},
    {"name": "César Chávez Ravenswood Middle", "city": "East Palo Alto", "lat": 37.4733726, "lng": -122.1450348},
    {"name": "Los Robles-Ronald McNair Academy", "city": "East Palo Alto", "lat": 37.462029, "lng": -122.130869},
    {"name": "Greendell School", "city": "Palo Alto", "lat": 37.4157329, "lng": -122.1062238},
    {"name": "Stevenson Elementary", "city": "Mountain View", "lat": 37.4035542, "lng": -122.0841173},
    {"name": "Duveneck Elementary", "city": "Palo Alto", "lat": 37.4496809, "lng": -122.1340934},
    {"name": "Crittenden Middle School", "city": "Mountain View", "lat": 37.4106558, "lng": -122.0854778},
    {"name": "Palo Alto High School", "city": "Palo Alto", "lat": 37.4358242, "lng": -122.1553327},
    {"name": "San José High School", "city": "San Jose", "lat": 37.3493264, "lng": -121.8716555},
    {"name": "Hillbrook School San José Campus", "city": "San Jose", "lat": 37.3394388, "lng": -121.8935683},
    {"name": "Notre Dame High", "city": "San Jose", "lat": 37.3284231, "lng": -121.8826632},
    {"name": "Washington Elementary School", "city": "San Jose", "lat": 37.3207744, "lng": -121.8822882},
]

ROAD_FIELDS = (
    "Route,RouteS,RteSuffix,County,PMPrefix,bPM,ePM,PMSuffix,"
    "AlignCode,RouteType,Direction"
)
AADT_FIELDS = (
    "RTE,RTE_SFX,CNTY,PM,PM_PFX,PM_SFX,BACK_AADT,AHEAD_AADT"
)


def fetch_json(url, params=None):
    request_url = f"{url}?{urlencode(params)}" if params else url
    request = Request(
        request_url,
        headers={"User-Agent": "BreatheRoute/1.0 (CA-16 AADT school proximity map)"},
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=90) as response:
                result = json.load(response)
            if isinstance(result, dict) and result.get("error"):
                raise RuntimeError(
                    f"Data service error from {url}: {result['error']}"
                )
            return result
        except HTTPError as error:
            if error.code not in (500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(
                    f"Unable to retrieve data from {url}: HTTP {error.code}"
                ) from error
            time.sleep(0.5 * (attempt + 1))
        except (URLError, TimeoutError) as error:
            raise RuntimeError(
                f"Unable to retrieve data from {url}: {error}"
            ) from error
    raise RuntimeError(f"Unable to retrieve data from {url} after retries.")


def load_ca16_boundary():
    request = Request(
        CENSUS_BOUNDARY_URL,
        headers={"User-Agent": "BreatheRoute/1.0 (CA-16 AADT school proximity map)"},
    )
    try:
        with urlopen(request, timeout=90) as response:
            boundary_zip = response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(
            f"Unable to download the Census CA-16 boundary: {error}"
        ) from error

    with tempfile.TemporaryDirectory() as temporary_dir:
        zip_path = os.path.join(temporary_dir, "ca16_boundary.zip")
        with open(zip_path, "wb") as boundary_file:
            boundary_file.write(boundary_zip)
        boundary_gdf = gpd.read_file(f"zip://{zip_path}")

    district = boundary_gdf.loc[boundary_gdf["GEOID"] == DISTRICT_GEOID]
    if district.empty:
        raise ValueError(
            f"Census boundary file does not contain CA-16 ({DISTRICT_GEOID})."
        )
    return district.to_crs(epsg=3310).geometry.union_all()


def build_road_coverage_boundary(boundary):
    return boundary.buffer(ROAD_COVERAGE_BUFFER_METERS)


def query_caltrans_features(layer_url, boundary_wgs84, fields):
    min_lng, min_lat, max_lng, max_lat = boundary_wgs84.bounds
    query_params = {
        "where": "1=1",
        "outFields": fields,
        "returnGeometry": "true",
        "geometry": f"{min_lng},{min_lat},{max_lng},{max_lat}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "f": "geojson",
        "resultRecordCount": 2000,
    }
    features = []
    result_offset = 0
    while True:
        response = fetch_json(
            layer_url, {**query_params, "resultOffset": result_offset}
        )
        page = response.get("features", [])
        if not page:
            break
        features.extend(page)
        if not response.get("exceededTransferLimit"):
            break
        result_offset += len(page)
    return features


def parse_volume(value):
    if value in (None, ""):
        return None
    try:
        volume = int(float(value))
    except (TypeError, ValueError):
        return None
    return volume if volume >= 0 else None


def normalized(value):
    return str(value or "").strip().upper()


def normalized_route(value):
    route = normalized(value)
    return str(int(route)) if route.isdigit() else route


def collect_count_stations(aadt_features):
    stations = defaultdict(lambda: defaultdict(lambda: {"back": None, "ahead": None}))
    for feature in aadt_features:
        properties = feature["properties"]
        try:
            postmile = float(properties["PM"])
        except (KeyError, TypeError, ValueError):
            continue
        route_key = (
            normalized_route(properties.get("RTE")),
            normalized(properties.get("RTE_SFX")),
            normalized(properties.get("CNTY")),
            normalized(properties.get("PM_PFX")),
            normalized(properties.get("PM_SFX")),
        )
        station = stations[route_key][postmile]
        for field, side in (("BACK_AADT", "back"), ("AHEAD_AADT", "ahead")):
            volume = parse_volume(properties.get(field))
            if volume is not None:
                current = station[side]
                station[side] = volume if current is None else max(current, volume)
    return stations


def qualifying_intervals(stations):
    for route_key, route_stations in stations.items():
        sorted_stations = sorted(route_stations.items())
        for (start_pm, start_data), (end_pm, end_data) in zip(
            sorted_stations, sorted_stations[1:]
        ):
            adjacent_volumes = [
                volume
                for volume in (start_data["ahead"], end_data["back"])
                if volume is not None
            ]
            if end_pm <= start_pm or not adjacent_volumes:
                continue
            # Treat the interval as qualifying if either adjacent Caltrans count
            # for that section exceeds the threshold.
            volume = max(adjacent_volumes)
            if volume > AADT_THRESHOLD:
                yield route_key, start_pm, end_pm, volume


def intersecting_line_parts(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == "LineString":
        yield geometry
    elif geometry.geom_type in ("MultiLineString", "GeometryCollection"):
        for part in geometry.geoms:
            yield from intersecting_line_parts(part)


def build_qualifying_roads(road_features, aadt_features, boundary):
    aadt_points = gpd.GeoSeries(
        [shape(feature["geometry"]) for feature in aadt_features],
        crs="EPSG:4326",
    ).to_crs(epsg=3310)
    in_area_aadt_features = [
        feature
        for feature, point in zip(aadt_features, aadt_points)
        if boundary.covers(point)
    ]
    counts_by_route = collect_count_stations(in_area_aadt_features)
    qualifying_routes = {}
    for route_key, _, _, aadt in qualifying_intervals(counts_by_route):
        qualifying_routes[route_key] = max(
            aadt, qualifying_routes.get(route_key, 0)
        )

    raw_lines = []
    for feature in road_features:
        properties = feature["properties"]
        route_key = (
            normalized_route(properties.get("Route")),
            normalized(properties.get("RteSuffix")),
            normalized(properties.get("County")),
            normalized(properties.get("PMPrefix")),
            normalized(properties.get("PMSuffix")),
        )
        if route_key in qualifying_routes:
            raw_lines.append(
                (route_key, properties, shape(feature["geometry"]))
            )

    projected_lines = gpd.GeoSeries(
        [line for _, _, line in raw_lines], crs="EPSG:4326"
    ).to_crs(epsg=3310)

    records = []
    for (route_key, properties, _), line in zip(raw_lines, projected_lines):
        clipped_line = line.intersection(boundary)
        for part in intersecting_line_parts(clipped_line):
            if part.length == 0:
                continue
            records.append(
                {
                    "route": f"{route_key[0]}{route_key[1]}",
                    "county": route_key[2],
                    "direction": properties.get("Direction", ""),
                    "aadt": qualifying_routes[route_key],
                    "aadt_year": AADT_YEAR,
                    "geometry": part,
                }
            )

    if not records:
        raise ValueError(
            "No Caltrans routes with sections exceeding 100,000 AADT "
            "intersect the study area."
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:3310")


def build_school_results(roads):
    schools_gdf = gpd.GeoDataFrame(
        SCHOOLS,
        geometry=[Point(school["lng"], school["lat"]) for school in SCHOOLS],
        crs="EPSG:4326",
    ).to_crs(epsg=3310)
    road_geometry = unary_union(roads.geometry.tolist())
    schools_gdf["distance_feet"] = (
        schools_gdf.geometry.distance(road_geometry) * METERS_TO_FEET
    ).round(1)
    schools_gdf["within_500ft_buffer"] = (
        schools_gdf["distance_feet"] <= BUFFER_THRESHOLD_FT
    )
    return schools_gdf.to_crs(epsg=4326)


def run_geospatial_pipeline(
    progress_callback: Optional[Callable[[str], None]] = None,
):
    def report(message):
        print(message)
        if progress_callback:
            progress_callback(message)

    report(f"Downloading {AADT_YEAR} Census CA-16 boundary...")
    boundary = load_ca16_boundary()
    report("Expanding CA-16 road coverage by 2 km...")
    road_coverage = build_road_coverage_boundary(boundary)
    coverage_wgs84 = gpd.GeoSeries([road_coverage], crs="EPSG:3310").to_crs(
        epsg=4326
    ).iloc[0]
    report("Downloading Caltrans highway geometry...")
    road_features = query_caltrans_features(
        ROAD_LAYER_URL, coverage_wgs84, ROAD_FIELDS
    )
    report(f"Downloading Caltrans {AADT_YEAR} AADT count stations...")
    aadt_features = query_caltrans_features(
        AADT_LAYER_URL, coverage_wgs84, AADT_FIELDS
    )
    report("Selecting AADT-qualified routes and clipping their lines to the expanded study area...")
    roads = build_qualifying_roads(
        road_features, aadt_features, road_coverage
    )
    report("Calculating school distances and saving map data...")
    schools = build_school_results(roads)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    roads.to_crs(epsg=4326).to_file(ROADS_OUTPUT_PATH, driver="GeoJSON")
    schools.to_file(SCHOOLS_OUTPUT_PATH, driver="GeoJSON")

    routes = sorted(roads["route"].unique())
    report(f"Selected {len(roads)} road segments across routes: {', '.join(routes)}")
    report(f"Processed {len(schools)} schools.")
    report(f"Road data: {ROADS_OUTPUT_PATH}")
    report(f"School data: {SCHOOLS_OUTPUT_PATH}")


if __name__ == "__main__":
    run_geospatial_pipeline()
