"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
import os
import pytz
import requests
import json
from datetime import datetime, timedelta  # Samlet relevant datetime-import

# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    def GetFilarkivToken(orchestrator_connection: OrchestratorConnection):

        try:
            FilarkivTokenTimestamp = orchestrator_connection.get_constant("FilarkivTokenTimestamp1").value
            Filarkiv_access= orchestrator_connection.get_credential("FilarkivAccessToken1")
            Filarkiv_access_token = Filarkiv_access.password
            Filarkiv_URL = Filarkiv_access.username
            Filarkiv_client= orchestrator_connection.get_credential("FilarkivClientSecret")
            client_secret = Filarkiv_client.password

            # Define Danish timezone
            danish_timezone = pytz.timezone("Europe/Copenhagen")

            # Parse the old timestamp to a datetime object
            old_time = datetime.strptime(FilarkivTokenTimestamp.strip(), "%d-%m-%Y %H:%M:%S")
            old_time = danish_timezone.localize(old_time)  # Localize to Danish timezone
            print('Old timestamp: ' + old_time.strftime("%d-%m-%Y %H:%M:%S"))

            # Get the current timestamp in Danish timezone
            current_time = datetime.now(danish_timezone)
            print('current timestamp: '+current_time.strftime("%d-%m-%Y %H:%M:%S"))
            str_current_time = current_time.strftime("%d-%m-%Y %H:%M:%S")

            # Calculate the difference between the two timestamps
            time_difference = current_time - old_time
            print(time_difference)

            # Check if the difference is over 1 hour and 30 minutes
            GetNewTimeStamp = time_difference > timedelta(minutes=30)

            # Output for the boolean
            print("GetNewTimeStamp:", GetNewTimeStamp)

            # Example of using it in an if-statement
            if GetNewTimeStamp:
                print("The difference is over 30 minutes. Fetch a new timestamp!")
                # Replace these values with your actual keys
                client_id = 'fa_de_aarhus_job_user'
                scope = 'fa_de_api:normal'
                grant_type = 'client_credentials'

                # Data to be sent in the POST request
                keys = {
                    'client_secret': client_secret,
                    'client_id': client_id,
                    'scope': scope,
                    'grant_type': grant_type,  # Specify the grant type you're using
                }

                try:
                    # Sending POST request to get the access token
                    response = requests.post(Filarkiv_URL, data=keys)
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    raise ConnectionError(f"Failed to fetch new access token: {e}")
                
                # Extract access token
                Filarkiv_access_token = response.json().get('access_token')
                if not Filarkiv_access_token:
                    raise RuntimeError("Access token not found in response.")

                print("Access token granted successfully.")

                # Update credentials and timestamp in the orchestrator
                orchestrator_connection.update_credential("FilarkivAccessToken1", Filarkiv_URL, Filarkiv_access_token)
                orchestrator_connection.update_constant("FilarkivTokenTimestamp1", current_time.strftime("%d-%m-%Y %H:%M:%S"))

                return Filarkiv_access_token

            else:
                print("No need to fetch a new token. Using existing one.")
                return Filarkiv_access_token

        except Exception as e:
            raise RuntimeError(f"An error occurred in GetFilarkivToken: {e}")

    def GetFileID(CaseID):
        Filarkiv_access_token = GetFilarkivToken(orchestrator_connection)

        url = f"https://core.filarkiv.dk/api/v1/Documents"
        params = {
            "caseid": CaseID,
            "expand": "Files"
        }
        response = requests.get(url, headers={"Authorization": f"Bearer {Filarkiv_access_token}", "Content-Type": "application/json"}, params = params)
        if response.status_code in [200, 201]:
            print("FilID'er henter")
        else:
            print("Fejl i henting af fil-id'er:", response.text)
        
        response_json = response.json()
        file_ids = []

        for document in response_json:
            files = document.get("files", [])
            for file_entry in files:
                file_id = file_entry.get("id")
                if file_id:
                    file_ids.append(file_id)

        return file_ids
        
    def DeleteFromFilarkiv(CaseID, Filarkiv_access_token ):
        Filarkiv_access_token = GetFilarkivToken(orchestrator_connection)

        url = f"https://core.filarkiv.dk/api/v1/Cases" 

        data = {
                "id": CaseID,
        }
        response = requests.delete(url, headers={"Authorization": f"Bearer {Filarkiv_access_token}", "Content-Type": "application/json"}, data=json.dumps(data))
        if response.status_code in [200, 201, 204]:
            orchestrator_connection.log_info("Sagen er slettet")
        else:
            orchestrator_connection.log_info(f'Fejl i sletning af sagen: {response.text}')

    def PostFileIDtoEndPoint(API_params, FileIDs):
        url = f'{API_params.username}/Jobs/QueueFilArkivFilesForDeletion'
        key = API_params.password
        Filarkiv_access_token = GetFilarkivToken(orchestrator_connection)

        headers = {
            "Authorization": f"Bearer {Filarkiv_access_token}", 
            "ApiKey": key
            }
        payload = {
            "files": FileIDs
            }
        response = requests.post(url, headers= headers, json=payload)
        orchestrator_connection.log_info(f'{response.status_code}')
        if response.status_code in [200, 201, 204]:
            print("FilID'er henter")
        else:
            print("Fejl i henting af fil-id'er:", response.text)
    queue_json = json.loads(queue_element.data)
    CaseID = queue_json.get('FilArkivCaseId')
    Token = GetFilarkivToken(orchestrator_connection)
    API_params = orchestrator_connection.get_credential('AktbobAPIKey')
    FileIDs = GetFileID(CaseID)
    PostFileIDtoEndPoint(API_params, FileIDs)
    DeleteFromFilarkiv(CaseID=CaseID, Filarkiv_access_token= Token)