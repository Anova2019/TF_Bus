import os
import time
import streamlit as st  # New import for Streamlit
from dotenv import load_dotenv
from bods_client.client import BODSClient
from bods_client.models import BoundingBox, SIRIVMParams, Siri
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static  # New import to display Folium in Streamlit; pip install streamlit-folium

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

# Function to fetch data and generate the Folium map
@st.cache_data(ttl=10)  # Cache for 10 seconds to avoid redundant fetches
def fetch_and_generate_map():
    try:
        # Parameters to filter the data by the bounding box
        siri_params = SIRIVMParams(bounding_box=telford_bounding_box)
        
        # Get raw response (XML bytes) and parse to Siri object
        raw_response = bods_client.get_siri_vm_data_feed(params=siri_params)
        siri = Siri.from_bytes(raw_response)
        
        # Extract data
        vehicle_activities = siri.service_delivery.vehicle_monitoring_delivery.vehicle_activities
        
        # Create the map
        map_center = [(telford_bounding_box.min_latitude + telford_bounding_box.max_latitude) / 2,
                      (telford_bounding_box.min_longitude + telford_bounding_box.max_longitude) / 2]
        bus_map = folium.Map(location=map_center, zoom_start=12)
        
        # Add markers for all buses
        marker_cluster = MarkerCluster().add_to(bus_map)
        for activity in vehicle_activities:
            vehicle_ref = activity.monitored_vehicle_journey.vehicle_ref
            latitude = activity.monitored_vehicle_journey.vehicle_location.latitude
            longitude = activity.monitored_vehicle_journey.vehicle_location.longitude
            popup_text = f"Bus Ref: {vehicle_ref}<br>Lat: {latitude}<br>Lon: {longitude}"
            folium.Marker(
                location=[latitude, longitude],
                popup=popup_text,
                icon=folium.Icon(color="blue", icon="bus", prefix="fa")
            ).add_to(marker_cluster)
        
        return bus_map, len(vehicle_activities)
    
    except Exception as e:
        st.error(f"An error occurred while fetching BODS data: {e}")
        st.info("Double check your API key and the bounding box coordinates.")
        return None, 0

# Streamlit app layout
st.title("Real-Time Telford Bus Tracker")
st.write("Live bus locations in Telford, updating every 10 seconds.")

# Fetch and display the map
bus_map, num_buses = fetch_and_generate_map()
if bus_map:
    folium_static(bus_map, width=800, height=600)
    st.success(f"Found {num_buses} live bus reports in the area.")

# Auto-refresh every 10 seconds
time.sleep(10)
st.rerun()
