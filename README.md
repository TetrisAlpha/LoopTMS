Loop TMS Data Processor

Overview

    This Python script is designed to interact with the Loop Transportation Management System (TMS) API. It performs several key functions:

    Fetching Shipment Jobs: Retrieves shipment job data from the Loop TMS API for a specified date range.
    Merging Carrier Details: Enhances the shipment job data with carrier details fetched from another endpoint in the Loop TMS API.
    Generating Cost Allocation Codes: Adds cost allocation codes to the shipment job data based on predefined rules.
    Saving Data to AWS S3: The enriched data is then saved as a JSON file in an AWS S3 bucket.

Prerequisites
    Python 3.x
    AWS account with configured access credentials.
    Access to Loop TMS API with a valid API key.
    Required Python packages: boto3, requests, json, datetime
Setup
    Install Required Libraries:
    Use pip to install the necessary Python libraries.
        pip install boto3 requests
AWS Credentials:
    Ensure that your AWS credentials are configured correctly. These credentials are required to access AWS Secrets Manager and S3 services.

API Key:
    The script expects an API key for the Loop TMS API, which should be stored in AWS Secrets Manager. The secret should be in the following JSON format:
        { "password": "<YOUR_API_KEY>" }

GitHub Actions Setup for AWS Lambda Deployment
    Configure GitHub Secrets:

        Set up the following secrets in your GitHub repository:

            AWS_ACCESS_KEY_ID: Your AWS access key ID.
            AWS_SECRET_ACCESS_KEY: Your AWS secret access key.
    AWS Lambda Function:

        Ensure that an AWS Lambda function named PullShipmentJobData exists in your AWS account, as the GitHub Actions workflow is configured to update this function.

    AWS Region Configuration:

        The AWS region is set to us-west-1 in the workflow. Change this if your Lambda function is hosted in a different region.