import time
import json
import requests
import boto3
from datetime import datetime
from requests.exceptions import RequestException
from botocore.exceptions import ClientError

# Initialize the S3 client
s3 = boto3.resource('s3')

# Retrieves a specified API key from AWS Secrets Manager for authentication purposes.
def get_secret():

    secret_name = "LoopsAPI"
    region_name = "us-west-1"

    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    return get_secret_value_response['SecretString']

# Performs HTTP GET requests with exponential backoff retry logic for handling network failures.
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

# Saves data as a JSON file to an AWS S3 bucket, with the filename including a timestamp.
def save_to_s3(data, bucket_name, filename):
    try:
        json_data = json.dumps(data, indent=4)
        filename = f" {filename}_{datetime.now()}.json"
        # Upload the JSON string to S3
        s3.Object(bucket_name, filename).put(Body=json_data)
        
        print(f"File {filename} uploaded to {bucket_name}")
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        raise

# Fetches shipment job data from an API, filtering jobs by specified date parameters.
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

# Enhances shipment jobs with carrier details fetched from a different API endpoint.
def fetch_merge_shipment_carrier(shipment_jobs,api_key):
    org_url = "https://api.loop.us/v1/organizations"  # API endpoint for organizations
    headers = {"Authorization": f"Bearer {api_key}"}
   
    for job in shipment_jobs:
        carrier_qid = job.get("jobTypeInfo", {}).get("carrierOrganizationQid")
        if carrier_qid:
            try:
                org_response = exponential_backoff_request(f"{org_url}/{carrier_qid}", headers)
                org_data = org_response.json()
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
    return shipment_jobs

# Adds cost allocation codes to shipment jobs based on freight terms and job types.
def generate_cost_allocation_codes(shipment_jobs):
    freight_term_codes = {"3rd party": "123.445", "collect": "987.434", "unknown": "756.434"}
    job_type_codes = {"ftl": "999.123", "ltl": "001.456", "unknown": "000.000"}

    for shipment in shipment_jobs:
        freight_term = shipment.get("jobTypeInfo", {}).get("freightChargeTerms", "Not Found").lower()
        job_type = shipment.get("jobType", "Not Found").lower()

        shipment["AllocationCodes"] = {
            "Freight Charge Terms": freight_term_codes.get(freight_term, "Not Found"),
            "Job Type": job_type_codes.get(job_type, "Not Found")
        }

    return shipment_jobs

# Main AWS Lambda function handler that orchestrates the entire process, including fetching, processing, and saving shipment job data.
def lambda_handler(event, context):
    try:

        api_key = json.loads(get_secret()).get("password")
        
        shipment_jobs = fetch_shipment_jobs(api_key)
        if not shipment_jobs:
            return ('Process failed to fetch Shipment jobs, downstream enrichment failed')
            
        merged_carrier_details = fetch_merge_shipment_carrier(shipment_jobs,api_key)
        cost_allocation = generate_cost_allocation_codes(merged_carrier_details)
        
        
        # Save to S3 instead of local file system
        bucket_name = 'loop-tms-ftp'  # S3 bucket name
        file_name = 'shipment_jobs.json'
        save_to_s3(cost_allocation, bucket_name, file_name)

        return {
            'statusCode': 200,
            'body': json.dumps('Process completed successfully!')
        }

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }