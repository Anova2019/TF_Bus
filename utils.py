# utils.py
from math import radians, sin, cos, sqrt, atan2

# --- Calculations ---

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth (Haversine formula)."""
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# --- Data Processing ---

def process_activities_to_data(vehicle_activities):
    """
    Converts a list of BODS VehicleActivity objects into a simplified list of dictionaries 
    for easier filtering and table display, safely handling missing attributes.
    """
    bus_data = []
    
    def safe_get(obj, attr_path, default='N/A'):
        """Helper to safely access nested or optional attributes in BODS objects."""
        current = obj
        for attr in attr_path.split('.'):
            if current is None or not hasattr(current, attr):
                return default
            current = getattr(current, attr)
        return current
    
    for activity in vehicle_activities:
        mvj = activity.monitored_vehicle_journey
        
        bus_data.append({
            'Vehicle Ref': safe_get(mvj, 'vehicle_ref'),
            # Use line name or line ref if published name is missing
            'Line': safe_get(mvj, 'published_line_name') or safe_get(mvj, 'line_ref') or 'N/A',
            'Direction': safe_get(mvj, 'direction_ref'),
            'Operator': safe_get(mvj, 'operator_ref'),
            'Speed (km/h)': safe_get(mvj, 'velocity'),
            'Bearing': safe_get(mvj, 'bearing'),
            'Next Stop': safe_get(mvj, 'monitored_call.stop_point_name'),
            'ETA': safe_get(mvj, 'monitored_call.expected_arrival_time'),
            'From': safe_get(mvj, 'origin_name'),
            'To': safe_get(mvj, 'destination_name'),
            'Lat': safe_get(mvj, 'vehicle_location.latitude', 0.0),
            'Lon': safe_get(mvj, 'vehicle_location.longitude', 0.0),
            'Distance (km)': 'N/A'
        })
    def get_bus_details_by_ref(bus_data_list, vehicle_ref):
        """Retrieves the full data dictionary for a selected Vehicle Ref."""
    for data in bus_data_list:
        if data['Vehicle Ref'] == vehicle_ref:
            # Return a copy to ensure we don't accidentally modify session state data
            return data.copy() 
    return None
    return bus_data

