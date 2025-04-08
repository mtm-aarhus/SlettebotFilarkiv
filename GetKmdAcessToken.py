from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
import os
from datetime import datetime, timedelta
import pytz
import requests

def GetKMDToken(orchestrator_connection: OrchestratorConnection):

    try:    
        TokenTimeStamp = orchestrator_connection.get_constant("KMDTokenTimestamp").value
        KMD_access = orchestrator_connection.get_credential("KMDAccessToken")
        KMD_access_token = KMD_access.password
        KMD_URL = KMD_access.username
        KMD_Client = orchestrator_connection.get_credential("KMDClientSecret")
        client_secret = KMD_Client.password
        
        # Define Danish timezone
        danish_timezone = pytz.timezone("Europe/Copenhagen")

        # Parse the old timestamp to a datetime object
        old_time = datetime.strptime(TokenTimeStamp.strip(), "%d-%m-%Y %H:%M:%S")
        old_time = danish_timezone.localize(old_time)  # Localize to Danish timezone

        # Get the current timestamp in Danish timezone
        current_time = datetime.now(danish_timezone)
        str_current_time = current_time.strftime("%d-%m-%Y %H:%M:%S")

        # Calculate the difference between the two timestamps
        time_difference = current_time - old_time

        # Check if the difference is over 1 hour and 30 minutes
        GetNewTimeStamp = time_difference > timedelta(hours=1, minutes=30)

        # Output for the boolean
        orchestrator_connection.log_info(f"GetNewTimeStamp: {GetNewTimeStamp}")

        # Example of using it in an if-statement
        if GetNewTimeStamp:
            orchestrator_connection.log_info("The difference is over 1 hour and 30 minutes. Fetch a new timestamp!")
            # Replace these values with your actual keys
            client_id = 'aarhus_kommune'
            scope = 'client'
            grant_type = 'client_credentials'


            # Data to be sent in the POST request
            keys = {
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': scope,
                'grant_type': grant_type,  # Specify the grant type you're using
            }

            try:
                # Sending POST request to get the access token
                response = requests.post(KMD_URL, data=keys)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"Failed to fetch new access token: {e}")

            # Extract access token
            KMD_access_token = response.json().get('access_token')
            if not KMD_access_token:
                raise RuntimeError("Access token not found in response.")

            orchestrator_connection.log_info("Access token granted successfully.")

            # Update credentials and timestamp in the orchestrator
            orchestrator_connection.update_credential("KMDAccessToken", KMD_URL, KMD_access_token)
            orchestrator_connection.update_constant("KMDTokenTimestamp", current_time.strftime("%d-%m-%Y %H:%M:%S"))

            return KMD_access_token

        else:
            orchestrator_connection.log_info("No need to fetch a new token. Using existing one.")
            return KMD_access_token
    
    except Exception as e:
        raise RuntimeError(f"An error occurred in getting KMD Token: {e}")