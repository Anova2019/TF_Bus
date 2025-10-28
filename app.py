# app.py (Your main script)
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import streamlit.components.v1 as components

# Import modular components
import bods_api
from utils import haversine, process_activities_to_data
from bods_api import TELFORD_BOUNDING_BOX # Access the Bounding Box for map centering


# --- 1. Data Fetching & Caching ---

@st.cache_data(ttl=30) # Cache for 30 seconds
def get_initial_data():
    """Fetches and processes data, optimized with Streamlit caching."""
    try:
        vehicle_activities = bods_api.fetch_live_data()
        bus_data = process_activities_to_data(vehicle_activities)
        return vehicle_activities, bus_data
    except Exception as e:
        st.error(f"An error occurred while fetching BODS data: {e}")
        return [], []


# --- 2. UI Components ---

def render_map(filtered_activities, filtered_bus_data, user_loc):
    """Generates and renders the Folium map with bus and user markers."""
    
    # Determine map center
    map_center = [
        (TELFORD_BOUNDING_BOX.min_latitude + TELFORD_BOUNDING_BOX.max_latitude) / 2,
        (TELFORD_BOUNDING_BOX.min_longitude + TELFORD_BOUNDING_BOX.max_longitude) / 2
    ]
    if user_loc:
        map_center = user_loc

    bus_map = folium.Map(location=map_center, zoom_start=12)
    marker_cluster = MarkerCluster().add_to(bus_map)

    for data in filtered_bus_data:
        latitude = data['Lat']
        longitude = data['Lon']
        
        popup_text = f"Bus Ref: {data['Vehicle Ref']}<br>Line: {data['Line']}<br>From: {data['From']}<br>To: {data['To']}"
        
        color = "blue"
        if user_loc and data['Distance (km)'] != 'N/A':
            popup_text += f"<br>Distance: {data['Distance (km)']} km"
            color = "red" if data['Distance (km)'] < 1 else "blue"
        
        # Custom DivIcon with line number
        line_number = data['Line'] if data['Line'] != 'N/A' else ''
        html = f'''
            <div style="position: relative; text-align: center; width: 40px; height: 40px;">
                <i class="fa fa-bus" style="font-size: 24px; color: {color};"></i>
                <span style="position: absolute; top: 24px; left: 50%; transform: translateX(-50%); font-size: 12px; color: black; background-color: white; padding: 2px; border-radius: 3px;">{line_number}</span>
            </div>
        '''
        custom_icon = folium.DivIcon(html=html)
        
        folium.Marker(
            location=[latitude, longitude],
            popup=popup_text,
            icon=custom_icon
        ).add_to(marker_cluster)

    # Add user location marker if available
    if user_loc:
        folium.Marker(
            location=user_loc,
            popup="Your Location",
            icon=folium.Icon(color="green", icon="user", prefix="fa")
        ).add_to(bus_map)

    folium_static(bus_map, width=800, height=600)
    st.success(f"Found {len(filtered_activities)} live bus reports in the area (after filters).")


def render_sidebar(lines, operators):
    """Renders the filters and location input in the Streamlit sidebar."""
    with st.sidebar:
        st.header("Filters")
        selected_lines = st.multiselect("Filter by Line", lines)
        selected_operators = st.multiselect("Filter by Operator", operators)
        
        st.header("Set Your Location")
        
        # Postcode input
        postcode = st.text_input("Enter UK Postcode (e.g., TF1 1AA)")
        if postcode:
            postcode_loc = bods_api.geocode_postcode(postcode)
            if postcode_loc:
                st.session_state.user_loc = postcode_loc
                st.success(f"Location set to postcode {postcode}")
            else:
                st.error("Invalid postcode or API error. Try again.")
        
        # Browser location button (JS component remains in the main app file for simplicity)
        if st.button("Or Get My Browser Location"):
             # IMPORTANT: This JS component must remain here as it communicates directly with Streamlit's parent window
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
             """, height=0, key='geolocation_script')

        if 'user_loc' not in st.session_state:
             st.session_state.user_loc = None
            
    return selected_lines, selected_operators


# --- 3. Main Application Flow ---

def main():
    st.title("Real-Time Telford Bus Tracker 🚍")
    st.write("Live bus locations in Telford. Click 'Refresh' to update data.")

    # 3.1 Initialize Data in Session State
    if 'vehicle_activities' not in st.session_state or 'bus_data' not in st.session_state:
        st.session_state.vehicle_activities, st.session_state.bus_data = get_initial_data()
        st.session_state.user_loc = None

    # Refresh Button
    if st.button("Refresh Data", type="primary", use_container_width=True):
        st.session_state.vehicle_activities, st.session_state.bus_data = get_initial_data()
    
    # Use stored data
    vehicle_activities = st.session_state.vehicle_activities
    bus_data = st.session_state.bus_data

    # Collect unique filters
    lines = sorted(set([item['Line'] for item in bus_data if item['Line'] != 'N/A']))
    operators = sorted(set([item['Operator'] for item in bus_data if item['Operator'] != 'N/A']))

    # 3.2 Render Sidebar and Get Inputs
    selected_lines, selected_operators = render_sidebar(lines, operators)
    
    # 3.3 Apply Filters
    filtered_activities = []
    filtered_bus_data = []
    for activity, data in zip(vehicle_activities, bus_data):
        if (not selected_lines or data['Line'] in selected_lines) and \
           (not selected_operators or data['Operator'] in selected_operators):
            filtered_activities.append(activity)
            # Create a COPY of the dict for distance calculation
            filtered_bus_data.append(data.copy()) 

    # 3.4 Update Distances and Sort
    user_loc = st.session_state.get('user_loc')
    if user_loc and filtered_bus_data:
        user_lat, user_lon = user_loc
        for data in filtered_bus_data:
            data['Distance (km)'] = round(haversine(user_lat, user_lon, data['Lat'], data['Lon']), 2)
        
        filtered_bus_data.sort(key=lambda x: x['Distance (km)'])

    # 3.5 Render Map and Table
    if filtered_activities:
        render_map(filtered_activities, filtered_bus_data, user_loc)
        
        st.subheader("Bus Details Table")
        df = pd.DataFrame(filtered_bus_data)
        st.dataframe(df, use_container_width=True)

if __name__ == '__main__':
    main()
