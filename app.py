import os
import time
import streamlit as st  # New import for Streamlit
from dotenv import load_dotenv
from bods_client.client import BODSClient
from bods_client.models import BoundingBox, SIRIVMParams, Siri
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static  # New import to display Folium in Streamlit; pip install streamlit-folium
import pandas as pd  # Add for DataFrame
from math import radians, sin, cos, sqrt, atan2  # For haversine distance
import streamlit.components.v1 as components  # For custom JS components
import requests  # Add for postcode API calls

# 1. Load the API key from the .env file
load_dotenv("env_variables.env")
API_KEY = os.getenv("BODS_API_KEY")

if not API_KEY:
    raise ValueError("BODS_API_KEY not found in .env file. Please check your .env file.")

# 2. Define the geographic area for Telford (approximate values)
telford_bounding_box = BoundingBox(
    min_latitude=52.65,
    max_latitude=52.75,
    min_longitude=-2.55,
    max_longitude=-2.35,
)

# 3. Set up the BODS Client
bods_client = BODSClient(api_key=API_KEY)

# Function to calculate haversine distance
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Function to geocode UK postcode using postcodes.io API
def geocode_postcode(postcode):
    try:
        url = f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()['result']
            return [data['latitude'], data['longitude']]
        else:
            return None
    except Exception:
        return None

# Function to fetch raw data
@st.cache_data(ttl=10)  # Cache for 10 seconds to avoid redundant fetches
def fetch_data():
    try:
        # Parameters to filter the data by the bounding box
        siri_params = SIRIVMParams(bounding_box=telford_bounding_box)
        
        # Get raw response (XML bytes) and parse to Siri object
        raw_response = bods_client.get_siri_vm_data_feed(params=siri_params)
        siri = Siri.from_bytes(raw_response)
        
        # Extract data
        vehicle_activities = siri.service_delivery.vehicle_monitoring_delivery.vehicle_activities
        
        # Create bus data list for the table
        bus_data = []
        for activity in vehicle_activities:
            mvj = activity.monitored_vehicle_journey
            bus_data.append({
                'Vehicle Ref': mvj.vehicle_ref,
                'Line': mvj.published_line_name or mvj.line_ref or 'N/A',
                'Direction': mvj.direction_ref or 'N/A',
                'Operator': mvj.operator_ref or 'N/A',
                'Speed (km/h)': mvj.velocity if hasattr(mvj, 'velocity') else 'N/A',
                'Bearing': mvj.bearing if hasattr(mvj, 'bearing') else 'N/A',
                'Next Stop': mvj.monitored_call.stop_point_name if hasattr(mvj, 'monitored_call') else 'N/A',
                'ETA': mvj.monitored_call.expected_arrival_time if hasattr(mvj, 'monitored_call') else 'N/A',
                'Lat': mvj.vehicle_location.latitude,
                'Lon': mvj.vehicle_location.longitude,
                'Distance (km)': 'N/A'  # Placeholder, will be updated if user location available
            })
        
        return vehicle_activities, bus_data
    
    except Exception as e:
        st.error(f"An error occurred while fetching BODS data: {e}")
        st.info("Double check your API key and the bounding box coordinates.")
        return [], []

# Streamlit app layout
st.title("Real-Time Telford Bus Tracker")
st.write("Live bus locations in Telford, updating every 10 seconds.")

# Fetch raw data
vehicle_activities, bus_data = fetch_data()
num_buses = len(vehicle_activities)

# Collect unique lines and operators for filters
lines = sorted(set([item['Line'] for item in bus_data if item['Line'] != 'N/A']))
operators = sorted(set([item['Operator'] for item in bus_data if item['Operator'] != 'N/A']))

# Sidebar filters and location inputs
with st.sidebar:
    st.header("Filters")
    selected_lines = st.multiselect("Filter by Line", lines)
    selected_operators = st.multiselect("Filter by Operator", operators)
    
    st.header("Set Your Location")
    # Postcode input
    postcode = st.text_input("Enter UK Postcode (e.g., TF1 1AA)")
    if postcode:
        postcode_loc = geocode_postcode(postcode)
        if postcode_loc:
            st.session_state.user_loc = postcode_loc
            st.success(f"Location set to postcode {postcode}")
        else:
            st.error("Invalid postcode or API error. Try again.")
    
    # Browser location button (alternative)
    if st.button("Or Get My Browser Location"):
        # Custom JS to get geolocation and set it in session state
        components.html("""
            <script>
            function getLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(sendPosition, showError);
                } else {
                    alert("Geolocation is not supported by this browser.");
                }
            }

            function sendPosition(position) {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                parent.window.postMessage({type: 'streamlit:setComponentValue', value: [lat, lon]}, '*');
            }

            function showError(error) {
                alert("Error getting location: " + error.message);
            }

            getLocation();
            </script>
        """, height=0)
    
    # Listen for the geolocation message (using session state)
    if 'user_loc' not in st.session_state:
        st.session_state.user_loc = None

# Apply filters
filtered_activities = []
filtered_bus_data = []
for activity, data in zip(vehicle_activities, bus_data):
    if (not selected_lines or data['Line'] in selected_lines) and \
       (not selected_operators or data['Operator'] in selected_operators):
        filtered_activities.append(activity)
        filtered_bus_data.append(data)

filtered_num_buses = len(filtered_activities)

# Update distances if user location is available
user_loc = st.session_state.get('user_loc')
if user_loc:
    for data in filtered_bus_data:
        data['Distance (km)'] = round(haversine(user_loc[0], user_loc[1], data['Lat'], data['Lon']), 2)
    
    # Sort table by distance
    filtered_bus_data.sort(key=lambda x: x['Distance (km)'])

# Generate the map with filtered activities
if filtered_activities:
    map_center = [(telford_bounding_box.min_latitude + telford_bounding_box.max_latitude) / 2,
                  (telford_bounding_box.min_longitude + telford_bounding_box.max_longitude) / 2]
    if user_loc:
        map_center = user_loc  # Center on user if available
    bus_map = folium.Map(location=map_center, zoom_start=12)
    
    # Add markers for filtered buses
    marker_cluster = MarkerCluster().add_to(bus_map)
    for activity, data in zip(filtered_activities, filtered_bus_data):
        vehicle_ref = activity.monitored_vehicle_journey.vehicle_ref
        latitude = activity.monitored_vehicle_journey.vehicle_location.latitude
        longitude = activity.monitored_vehicle_journey.vehicle_location.longitude
        popup_text = f"Bus Ref: {vehicle_ref}<br>Lat: {latitude}<br>Lon: {longitude}"
        if user_loc:
            popup_text += f"<br>Distance: {data['Distance (km)']} km"
            color = "red" if data['Distance (km)'] < 1 else "blue"  # Highlight nearest in red
        else:
            color = "blue"
        folium.Marker(
            location=[latitude, longitude],
            popup=popup_text,
            icon=folium.Icon(color=color, icon="bus", prefix="fa")
        ).add_to(marker_cluster)
    
    # Add user location marker if available
    if user_loc:
        folium.Marker(
            location=user_loc,
            popup="Your Location",
            icon=folium.Icon(color="green", icon="user", prefix="fa")
        ).add_to(bus_map)
    
    folium_static(bus_map, width=800, height=600)
    st.success(f"Found {filtered_num_buses} live bus reports in the area (after filters).")
    
    # Display the filterable data table with filtered data
    st.subheader("Bus Details Table")
    df = pd.DataFrame(filtered_bus_data)
    st.dataframe(df, use_container_width=True)  # Interactive table with sorting

# Auto-refresh every 10 seconds
time.sleep(10)
st.rerun()
