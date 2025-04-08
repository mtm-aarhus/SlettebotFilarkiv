import uuid 
import requests
import pyodbc
from datetime import datetime
from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

def invoke_AfslutSag(KMDNovaURL, KMD_access_token, DeskProID, orchestrator_connection):
    task_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    Server = orchestrator_connection.get_constant('SqlServer').value

    # --- Henter CaseUuid fra Databasen --- # 
    def fetch_case_uuids_by_deskpro(deskpro_id):
        conn = pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};" + f"SERVER={Server};DATABASE=PYORCHESTRATOR;Trusted_Connection=yes;")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT CaseUuid FROM dbo.AktBobNovaCases
            WHERE DeskProID = ?
            """,
            deskpro_id
        )
        case_uuids = [row[0] for row in cursor.fetchall()]

            # Update status to 'Closed'
        cursor.execute(
        """
        UPDATE dbo.AktBobNovaCases
        SET [Open/Closed] = 'Closed'
        WHERE DeskProID = ?
        """,
        deskpro_id
        )

        conn.commit()
        cursor.close()
        conn.close()
        return case_uuids

    CaseUuid = fetch_case_uuids_by_deskpro(DeskProID)
    
    if CaseUuid:
        # Looper igennem caseUuid'erne:
        for case_uuid in CaseUuid:
            
            ## --- Henter CaseTitle --- #
            TransactionID = str(uuid.uuid4())

            Caseurl = f"{KMDNovaURL}/Case/GetList?api-version=2.0-Case"

            # Define headers
            headers = {
                "Authorization": f"Bearer {KMD_access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
            "common": {
                "transactionId":TransactionID,
                "uuid": case_uuid 
            },
            "paging": {
                "startRow": 1,
                "numberOfRows": 100
            },
            "caseGetOutput": { 
                "caseAttributes":{
                "userFriendlyCaseNumber": True,
                "title": True,
                "caseDate": True
                }
            }
            }
            try:
                response = requests.put(Caseurl, headers=headers, json=data)
                
                # Handle response
                if response.status_code == 200:
                    response_data = response.json()
                    case = response_data["cases"][0]

                    # Extract required case attributes
                    title = case["caseAttributes"]["title"]
                    caseDate = case["caseAttributes"]["caseDate"]
                else: 
                    print("failed to fetch case data")
            except Exception as e:
                raise Exception("Failed to fetch case data:", str(e))

            ## --- API til at opdaterer sagen --- #

            TransactionID = str(uuid.uuid4())

            # Define API URL
            Caseurl = f"{KMDNovaURL}/Case/Update?api-version=2.0-Case"

            # Define headers
            headers = {
                "Authorization": f"Bearer {KMD_access_token}",
                "Content-Type": "application/json"
            }
            data = {
            "common": {
            "transactionId": TransactionID,
            "uuid": case_uuid  
            },
            "paging": {
            "startRow": 1,
            "numberOfRows": 3000
            },
            "caseAttributes": {
            "title": title,
            "caseDate": caseDate,
            "caseCategory": "BomByg"
            },
            "state":"Afsluttet",
            "buildingCase":{
            "applicationStatusDates":{
            "decisionDate": datetime.now().strftime("%Y-%m-%dT00:00:00"), # Sættes til den dato hvor afgørelses processen kører
            "closeDate": datetime.now().strftime("%Y-%m-%dT00:00:00"), # Sættes til den dato hvor afgørelses processen kører
            "closingReason": "Anden afgørelse"
            }
            }
            }
            try:
                response = requests.patch(Caseurl, headers=headers, json=data)
                
                # Handle response
                if response.status_code == 200:
                    print("Sagen er opdateret")
                else: 
                    raise Exception("failed to fetch case data")
            except Exception as e:
                raise Exception("Failed to fetch case data:", str(e))


            # --- Henter Task listen --- #
            Caseurl = f"{KMDNovaURL}/Task/GetList?api-version=2.0-Case"
            TransactionID = str(uuid.uuid4())
            # Define headers
            headers = {
                "Authorization": f"Bearer {KMD_access_token}",
                "Content-Type": "application/json"
            }

            data = {
            "common": {
            "transactionId": TransactionID
            },
            "paging": {
            "startRow": 1,
            "numberOfRows": 3000
            },
            "caseUuid": case_uuid, 
            "taskDescription": True
            }
            try:
                response = requests.put(Caseurl, headers=headers, json=data)

                if response.status_code == 200:
                    print("API call successful. Parsing task list...")
                    
                    klar_til_sagsbehandling_uuid = None
                    afslut_sagen_uuid = None
                    tidsreg_sagsbehandling_uuid = None

                    task_list = response.json().get("taskList", [])
                    print(f"Found {len(task_list)} tasks")

                    for task in task_list:
                        title = task.get("taskTitle")
                        task_uuid = task.get("taskUuid")
                        print(f"Found task: '{title}' with UUID: {task_uuid}")

                        if title == "05. Klar til sagsbehandling":
                            klar_til_sagsbehandling_uuid = task_uuid
                        elif title == "25. Afslut/henlæg sagen":
                            afslut_sagen_uuid = task_uuid
                        elif title == "11. Tidsreg: Sagsbehandling":
                            tidsreg_sagsbehandling_uuid = task_uuid

                    # Create a list of tuples with task names and their UUIDs
                    task_uuids = [
                        ("05. Klar til sagsbehandling", klar_til_sagsbehandling_uuid),
                        ("25. Afslut/henlæg sagen", afslut_sagen_uuid),
                        ("11. Tidsreg: Sagsbehandling", tidsreg_sagsbehandling_uuid),
                    ]

                    print("\nFinal result:")
                    for task_name, task_uuid in task_uuids:
                        if task_uuid:
                            print(f"UUID for '{task_name}': {task_uuid}")
                        else:
                            print(f"Missing UUID for task: '{task_name}'")
                else:
                    print(f"Failed to fetch task data. Status code: {response.status_code}")
                    print(response.text)
                    raise Exception("Failed to fetch task data.")

            except Exception as e:
                print("Exception occurred:", str(e))



            # -- Opdaterer Task listen --- #
            
            for task_name,task_uuid in task_uuids:
                Caseurl = f"{KMDNovaURL}/Task/Update?api-version=2.0-Case"
                TransactionID = str(uuid.uuid4())
                # Define headers
                headers = {
                "Authorization": f"Bearer {KMD_access_token}",
                "Content-Type": "application/json"
                }

                task_data= {
                "common": {
                    "transactionId": TransactionID
                },
                "uuid": task_uuid, 
                "caseUuid": case_uuid,
                "title": task_name, 
                "caseworker": { 
                    "kspIdentity": {
                        "novaUserId": "78897bfc-2a36-496d-bc76-07e7a6b0850e",
                        "racfId": "AZX0075",
                        "fullName": "Aktindsigter Novabyg"
                    }
                },
                "closeDate": task_date,
                "statusCode": "F",
                "taskType": "Aktivitet" 
                }
                
                try:
                    response = requests.put(Caseurl, headers=headers, json=task_data)
                    if response.status_code == 200:
                        print(f"{task_name} er blevet færdiggjort")
                    else: 
                        print(response.status_code)
                        print(response.text)
                except Exception as e:
                    raise Exception("Failed to update task:", str(e))