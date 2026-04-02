# Author: Dalton Peterson
# Description: This script downloads arcgis online reports and updates the database with the new information. 
# It uses the ArcGIS API for Python to access the reports and pandas to manipulate the data before updating the database.

from arcgis.gis import GIS
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from os import getenv
import subprocess
import datetime
import os


# GLOBAL VARIABLES & INITIALIZATION
########################################################################################################################


load_dotenv()
engine = create_engine(getenv("SQL_CONNECTION_STRING"))

gis = GIS("home")
print(f'connected to ArcGIS online as {gis.users.me.username}')

CURRENT_DATE = datetime.datetime.now().date()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(os.path.join(SCRIPT_DIR, 'reports'), exist_ok=True)


# FUNCTIONS
########################################################################################################################


def fetch_reports():
    "Fetches reports from ArcGIS Online, saves them as CSV's, and returns them as a pandas DataFrame."
    print("fetching AGOL item and member reports...")

    # Get all org item & member reports. These are generated daily by 
    items = gis.content.search('title:"OrganizationItems_"', max_items=100)
    members = gis.content.search('title:"OrganizationMembers_"', max_items=100)

    # Assume first result is the most recent report (the one you want)
    item_report = sorted(items, key=lambda x: x.created, reverse=True)[0]
    member_report = sorted(members, key=lambda x: x.created, reverse=True)[0]

    print(f'found item report: {item_report.title} created on {item_report.created}'
          f'\nfound member report: {member_report.title} created on {member_report.created}')

    # Download the report data and convert to DataFrame
    item_report_df = pd.read_csv(item_report.download())
    member_report_df = pd.read_csv(member_report.download())

    # Add dates to each row in the DataFrames based on the report creation date
    item_report_df['updated_date'] = CURRENT_DATE
    member_report_df['updated_date'] = CURRENT_DATE

    # Save the DataFrames as CSV files
    item_report_title = item_report.title.replace("/", "-")
    member_report_title = member_report.title.replace("/", "-")
    item_report_df.to_csv(os.path.join(SCRIPT_DIR, 'reports', f'{item_report_title}.csv'), index=False)
    member_report_df.to_csv(os.path.join(SCRIPT_DIR, 'reports', f'{member_report_title}.csv'), index=False)

    print (f'saved item report to ./reports/{item_report_title}.csv'
           f'\nsaved member report to ./reports/{member_report_title}.csv')

    member_report_csv_path = f'./reports/{member_report_title}.csv'
    item_report_csv_path = f'./reports/{item_report_title}.csv'

    return item_report_df, member_report_df, item_report_csv_path, member_report_csv_path, item_report_title, member_report_title


def Collect_EntraID_Information(member_report_csv_path):
    "Calls TAMU_AGOL_EntraID.ps1 to collect EntraID information for each user in the member report and write to a CSV."

    # # Run the PowerShell script to collect EntraID information for each user in the member report and write to CSV
    # print("executing TAMU_AGOL_EntraID.ps1...")
    # result = subprocess.run(
    #     [
    #     'powershell', 
    #     '-ExecutionPolicy', 'Bypass',
    #     '-File', os.path.join(SCRIPT_DIR, 'TAMU_AGOL_EntraID.ps1'),
    #     '-input_csv_path', member_report_csv_path,
    #     ], 
    #     capture_output=True, 
    #     text=True,
    #     cwd = SCRIPT_DIR
    #     )

    # print ("PowerShell script output:"
    #           f"\n{result.stdout}")

    # if result.returncode != 0:
    #     print(f"Error executing PowerShell script: {result.stderr}")
    
    # Add date to each row in the csv file
    print("adding updated_date to EntraID status report...")
    entraid_status_df = pd.read_csv(os.path.join(SCRIPT_DIR, 'reports', 'AGOL_EntraID_Status.csv'))
    entraid_status_df['updated_date'] = CURRENT_DATE
    entraid_status_df.to_csv(os.path.join(SCRIPT_DIR, 'reports', 'AGOL_EntraID_Status.csv'), index=False)


def Upload_Tables_to_Database(item_report_df, member_report_df, entraid_status_path, item_report_title, member_report_title):
    "Uploads the item and member report DataFrames to the database."

    # Upload the item report DataFrame to the database
    print("uploading item report to database...")
    item_report_df.to_sql(item_report_title, engine, if_exists='replace', index=False)

    # Upload the member report DataFrame to the database
    print("uploading member report to database...")
    member_report_df.to_sql(member_report_title, engine, if_exists='replace', index=False)

    # Upload the EntraID status CSV to the database
    print("uploading EntraID status report to database...")
    entraid_status_df = pd.read_csv(entraid_status_path)
    entraid_status_df.to_sql('EntraID_Status', engine, if_exists='replace', index=False)

def Catalog_and_Cleanup():
    "Adds data from previous reports to history tables and deletes old reports from the database."
    print("cataloging previous reports and clearing previous reports...")

    # Collect names of previous reports from the database
    with engine.connect() as connection:
        cursor_item = connection.execute(text("SELECT name FROM sys.tables WHERE name LIKE 'OrganizationItems_%'"))
        previous_item_reports = cursor_item.fetchall()
        
        cursor_member = connection.execute(text("SELECT name FROM sys.tables WHERE name LIKE 'OrganizationMembers_%'"))
        previous_member_reports = cursor_member.fetchall()
        
        cursor_entraid = connection.execute(text("SELECT name FROM sys.tables WHERE name = 'AGOL_EntraID_Status'"))
        previous_entraid_status = cursor_entraid.fetchall()

    item_history_table_title = 'HIST_OrganizationItems'
    member_history_table_title = 'HIST_OrganizationMembers'
    entraid_status_history_table_title = 'HIST_EntraID_Status'

    # Add previous reports to history tables and delete if they exist
    print("adding tables to history tables and clearing previous reports...")
    
    with engine.connect() as connection:
        # For item reports
        if previous_item_reports:
            for row in previous_item_reports:
                table_name = row[0]  # Assuming name is the first column
                # Check if history table exists, if not, create it
                check_result = connection.execute(text(f"SELECT OBJECT_ID('{item_history_table_title}')"))
                exists = check_result.fetchone()
                if exists[0] is None:
                    connection.execute(text(f"SELECT * INTO {item_history_table_title} FROM {table_name}"))
                else:
                    connection.execute(text(f"INSERT INTO {item_history_table_title} SELECT * FROM {table_name}"))
                connection.execute(text(f"DROP TABLE {table_name}"))
                connection.commit()  # Commit after each operation
        else:
            print("No previous item reports found in the database.")
        
        # For member reports
        if previous_member_reports:
            for row in previous_member_reports:
                table_name = row[0]
                check_result = connection.execute(text(f"SELECT OBJECT_ID('{member_history_table_title}')"))
                exists = check_result.fetchone()
                if exists[0] is None:
                    connection.execute(text(f"SELECT * INTO {member_history_table_title} FROM {table_name}"))
                else:
                    connection.execute(text(f"INSERT INTO {member_history_table_title} SELECT * FROM {table_name}"))
                connection.execute(text(f"DROP TABLE {table_name}"))
                connection.commit()
        else:
            print("No previous member reports found in the database.")   
        
        # For EntraID status
        if previous_entraid_status:
            table_name = previous_entraid_status[0][0]
            check_result = connection.execute(text(f"SELECT OBJECT_ID('{entraid_status_history_table_title}')"))
            exists = check_result.fetchone()
            if exists[0] is None:
                connection.execute(text(f"SELECT * INTO {entraid_status_history_table_title} FROM {table_name}"))
            else:
                connection.execute(text(f"INSERT INTO {entraid_status_history_table_title} SELECT * FROM {table_name}"))
            connection.execute(text(f"DROP TABLE {table_name}"))
            connection.commit()
        else:
            print("No previous entraID status reports found in the database.")

    # clear reports directory
    print("clearing reports directory...")
    for filename in os.listdir(os.path.join(SCRIPT_DIR, 'reports')):
        file_path = os.path.join(SCRIPT_DIR, 'reports', filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

def main():
    # Catalog_and_Cleanup()
    item_report_df, member_report_df, item_report_csv_path, member_report_csv_path, item_report_title, member_report_title = fetch_reports()
    Collect_EntraID_Information(member_report_csv_path)
    Upload_Tables_to_Database(item_report_df, member_report_df, os.path.join(SCRIPT_DIR, 'reports', 'AGOL_EntraID_Status.csv'), item_report_title, member_report_title)    


# EXECUTION
#########################################################################################################################


if __name__ == "__main__":
    main()






    





