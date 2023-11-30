import time
import json
import requests
from datetime import datetime
from requests.exceptions import RequestException

def exponential_backoff_request(url, headers, params=None, max_retries=3, initial_delay=1):

    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response
        except RequestException as e:
            wait = initial_delay * (2 ** i)  # Exponential backoff
            print(f"Request failed, retrying in {wait} seconds...")
            time.sleep(wait)
    raise RequestException("Max retries exceeded")

def save_to_json_file(data, filename):
    filename = f" {filename}_{datetime.now()}.json"
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)


def fetch_shipment_jobs(api_key):
    url = "https://api.loop.us/v1/shipment-jobs"  # API endpoint for shipment jobs
    
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "revisedAfter": datetime(2023, 9, 1).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "revisedBefore": datetime(2023, 10, 1).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        }
    all_shipment_jobs = []
    while True:
        try:
            response = exponential_backoff_request(url, headers, params)
                
            response_json = response.json()
            all_shipment_jobs.extend(response_json.get('data', []))
    
            page_info = response_json.get('pageInfo', {})
            if not page_info.get('hasNextPage', False):
                break
            params['after'] = page_info.get('endCursor')
    
        except RequestException as e:
            print(f"Error fetching shipment jobs: {e}")
            break

    return all_shipment_jobs

def fetch_merge_shipment_carrier(shipment_jobs,api_key):
    org_url = "https://api.loop.us/v1/organizations"  # API endpoint for organizations
    headers = {"Authorization": f"Bearer {api_key}"}
    org_data_collected = {} 
   
    for job in shipment_jobs:
        carrier_qid = job.get("jobTypeInfo", {}).get("carrierOrganizationQid")
        if carrier_qid:
            try:
                org_response = exponential_backoff_request(f"{org_url}/{carrier_qid}", headers)
                org_data = org_response.json()
                org_data_collected[carrier_qid] = org_data
                carrier_data = org_data.get("truckingCarrierInfo", {})

                 # Check if bolNumber is "334154782"
                bol_number = job.get("referenceNumbers", {}).get("bolNumber")
                if bol_number == "334154782":
                    job["carrierDetails"] = {
                        "SCAC": carrier_data.get("scac"),
                        "MCNumber": carrier_data.get("mcNumber"),
                        "USDOT": carrier_data.get("usdotNumber"),
                        "legalName": org_data.get("legalName")
                    }
                else:
                    job["carrierDetails"] = {
                        "SCAC": carrier_data.get("scac"),
                        "MCNumber": carrier_data.get("mcNumber"),
                        "USDOT": carrier_data.get("usdotNumber")
                    }
            except RequestException as e:
                job["carrierDetails"] = {"error": str(e)}
        else:
            job["carrierDetails"] = {"error": "Carrier QID not found"}
    return shipment_jobs, org_data_collected

if __name__ == "__main__":
    try:

        api_key = "lk_live_6ChgfS0G5LLEzVXBdEsBokB6F2JIXrupXoz_P-41"
        
        shipment_jobs = fetch_shipment_jobs(api_key)
        if not shipment_jobs:
            print ('Process failed to fetch Shipment jobs, downstream enrichment failed')
            
        merged_carrier_details, org_data = fetch_merge_shipment_carrier(shipment_jobs,api_key)
        
        save_to_json_file(shipment_jobs, 'shipment_jobs.json')
        save_to_json_file(org_data, 'organization_data.json')


        print('Process completed successfully!')

    except Exception as e:
        print(f"An error occurred: {str(e)}")