# File Name: TAMU_AGOL_DeleteStatus.py
# Decription: This script accesses the AGOL database and calculates which items should be flagged and deleted
#             based on their EntraID status and updated dates. When a user is flagged for deletion, their 
#             on-file email is contacted as well as their supervisor if applicable.
#             Delete Statuses:
#             0 - No action needed
#             1 - User is flagged for deletion, email sent to user & supervisor
#             2 - User has been flagged for 30 days, user & content should be deleted and email sent to user & supervisor
# Author: Dalton Peterson
# Date: 2026-04-02


import pandas as pd

from sqlalchemy import create_engine, text, Float
from sqlalchemy.dialects.mssql import NVARCHAR, DATETIME, BIT, INTEGER

import datetime
import os

from os import getenv
from dotenv import load_dotenv

import smtplib
from email.message import EmailMessage

# GLOBAL VARIABLES & INITIALIZATION
############################################################################################

load_dotenv()
engine = create_engine(getenv("SQL_CONNECTION_STRING"))

CURRENT_DATE = datetime.datetime.now().date()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SENDER_EMAIL = getenv("SENDER_EMAIL")
SENDER_PASSWORD = getenv("SENDER_PASSWORD") 

DELETE_STATUS_TABLE_NAME = getenv("DELETE_STATUS_TABLE_NAME")
WHITELISTED_ENTRAID_GROUPS_TABLE_NAME = getenv("WHITELISTED_ENTRAID_GROUPS_TABLE_NAME")

# FUNCTIONS
#############################################################################################

def Email_Delete_Users(useremail, manageremail, username, name):
    """This function emails the user and their manager (if applicable) to notify them that their account has been marked for deletion."""

    # Set up the email parameters
    msg = EmailMessage()
    msg['Subject'] = 'Your ArcGIS Online Account Has been deleted'
    msg['From'] = SENDER_EMAIL
    msg['To'] = useremail , manageremail if manageremail else None

    msg.set_content()

def Email_Flagged_Users(useremail, manageremail, username, name):
    """This function emails the user and their manager (if applicable) to notify them that their account has been flagged for deletion."""

    # Set up the email parameters
    msg = EmailMessage()
    msg['Subject'] = 'Action Required: Your ArcGIS Online Account Has Been Flagged for Deletion'
    msg['From'] = SENDER_EMAIL
    msg['To'] = useremail , manageremail if manageremail else None

    msg.set_content()

def deletestatus_sql_datatypes():
    """This function defines the SQL data types for the DeleteStatus table."""
    return {
        'Username': NVARCHAR(255),
        'Name': NVARCHAR(255),
        'WorkingEmail': NVARCHAR(255),
        'ManagerEmail': NVARCHAR(255),
        'DeleteStatus': INTEGER,
        'FlagDate': DATETIME,
        'DeleteDate': DATETIME,
        'Override': BIT,
        'updated_date': DATETIME
    }

def Update_DeleteStatus_Table(member_table_name, delete_status_table_name):
    """This function retrieves the DeleteStatus and Current OrganizationMembers tables from the database. If there is a member in the OrganizationMembers table that is not in the DeleteStatus table, they are added with a DeleteStatus of 0. This function serves to add newly created accounts to the DeleteStatus table so that they can be monitored for deletion if needed."""

    with engine.connect() as connection:
        delete_status_df = pd.read_sql(text(f"SELECT * FROM {delete_status_table_name}"), connection)
        member_df = pd.read_sql(text(f"SELECT * FROM {member_table_name}"), connection)

    # Identify new members that are not in the delete status table
    new_members_df = member_df[~member_df['Username'].isin(delete_status_df['Username'])]

    # If there are new members, add them to the delete status table with a status of 0
    if not new_members_df.empty:
        new_delete_status_entries = new_members_df[['Username', 'Name', 'WorkingEmail', 'ManagerEmail']].copy()
        new_delete_status_entries['DeleteStatus'] = 0
        new_delete_status_entries['FlagDate'] = None
        new_delete_status_entries['DeleteDate'] = None
        new_delete_status_entries['Override'] = False
        new_delete_status_entries['updated_date'] = CURRENT_DATE

        # Append the new entries to the existing delete status DataFrame
        updated_delete_status_df = pd.concat([delete_status_df, new_delete_status_entries], ignore_index=True)

        # Upload the updated delete status DataFrame back to the database
        updated_delete_status_df.to_sql(delete_status_table_name, con=engine, if_exists='replace', index=False, dtype=deletestatus_sql_datatypes())
    
    return delete_status_df


def Calculate_Delete_Status(delete_status_df,entraid_status_df):
    """This function calculates the deletion status for each user based on their EntraID status and updated dates, updates the database, and sends notification emails as needed."""

    whitelisted_groups_df = pd.read_sql(text(f"SELECT * FROM {WHITELISTED_ENTRAID_GROUPS_TABLE_NAME}"), engine)
    whitelisted_group_ids = whitelisted_groups_df['ID'].tolist()

    for row in delete_status_df.itertuples():
        user_entraid_info = entraid_status_df[entraid_status_df['Username'] == row.Username]
        user_entraid_groups = user_entraid_info['Groups'].values[0].split(',') if not user_entraid_info.empty else []

        # If a user has an override, remove potential flags and move to next user
        if row.Override:
            delete_status_df.at[row.Index, 'DeleteStatus'] = 0
            print(f"User {row.Username} has an override enabled. Setting DeleteStatus to 0 and skipping further checks.")

        # Determine if an unflagged user should be flagged based on EntraID affiliations
        elif row.DeleteStatus == 0:
            if user_entraid_info.EntraID_Status == 0:
                delete_status_df.at[row.Index, 'DeleteStatus'] = 1
                delete_status_df.at[row.Index, 'FlagDate'] = CURRENT_DATE
                Email_Flagged_Users(row.WorkingEmail, row.ManagerEmail, row.Username, row.Name)
            elif user_entraid_info.EntraID_Status == 1:
                if any(group_id in whitelisted_group_ids for group_id in user_entraid_groups):
                        continue
                else:
                    delete_status_df.at[row.Index, 'DeleteStatus'] = 1
                    delete_status_df.at[row.Index, 'FlagDate'] = CURRENT_DATE
                    Email_Flagged_Users(row.WorkingEmail, row.ManagerEmail, row.Username, row.Name)
        
        # Determine if flagged users should be marked for deletion based on how long they have been flagged
        elif row.DeleteStatus == 1 and row.FlagDate and (CURRENT_DATE - row.FlagDate.date()).days >= 30:
            delete_status_df.at[row.Index, 'DeleteStatus'] = 2
            delete_status_df.at[row.Index, 'DeleteDate'] = CURRENT_DATE
            Email_Delete_Users(row.WorkingEmail, row.ManagerEmail, row.Username, row.Name)

    # Upload the updated delete status DataFrame back to the database
    delete_status_df.to_sql(DELETE_STATUS_TABLE_NAME, con=engine, if_exists='replace', index=False, dtype=deletestatus_sql_datatypes())