# bods_api.py
import os
import requests
from dotenv import load_dotenv
from bods_client.client import BODSClient
from bods_client.models import BoundingBox, SIRIVMParams, Siri

# --- Configuration & Initialization ---
load_dotenv("env_variables.env")
API_KEY = os.getenv("BODS_API_KEY")

# Define Telford Bounding Box (Centralized configuration)
TELFORD_BOUNDING_BOX = BoundingBox(
    min_latitude=52.65,
    max_latitude=52.75,
    min_longitude=-2.55,
    max_longitude=-2.35,
)

if not API_KEY:
    # Raise error immediately if key is missing
    raise ValueError("BODS_API_KEY not found in env_variables.env. Check the file.")

# Global BODS Client instance
bods_client = BODSClient(api_key=API_KEY)

# --- Functions ---

def fetch_live_data():
    """Fetches and parses live SIRI-VM data from BODS."""
    siri_params = SIRIVMParams(bounding_box=TELFORD_BOUNDING_BOX)
    
    # BODS client is a global instance
    raw_response = bods_client.get_siri_vm_data_feed(params=siri_params)
    siri = Siri.from_bytes(raw_response)
    
    # Return a list of VehicleActivity objects
    return siri.service_delivery.vehicle_monitoring_delivery.vehicle_activities


def geocode_postcode(postcode):
    """Geocodes UK postcode using postcodes.io API."""
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
