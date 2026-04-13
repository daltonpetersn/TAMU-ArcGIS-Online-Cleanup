# File Name: TAMU_AGOL_DeleteEmptyUsers.py
# Decription: This script accesses the AGOL catalog database, calculates all users that have 0 items published, and deletes them.
# Author: Dalton Peterson
# Date: 2026-04-02

import pandas as pd
from arcgis.gis import GIS
from sqlalchemy import create_engine
from sqlalchemy import text
from dotenv import load_dotenv
import datetime
import os
from os import getenv

# GLOBAL VARIABLES & INITIALIZATION
############################################################################################

load_dotenv()
engine = create_engine(getenv("SQL_CONNECTION_STRING"))

gis = GIS("home")
print(f'connected to ArcGIS online as {gis.users.me.username}')

CURRENT_DATE = datetime.datetime.now().date()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# FUNCTIONS
#############################################################################################

def collect_table_names():
    """This function collects the names of the most recent member and item report tables from the DB.
    Returns:
        member_table_name (str): The name of the most recent member report table.
        item_table_name (str): The name of the most recent item report table.
    """
    with engine.connect() as connection:
        cursor_item = connection.execute(text("SELECT name FROM sys.tables WHERE name LIKE 'OrganizationItems_%'"))
        previous_item_reports = cursor_item.fetchall()
        
        cursor_member = connection.execute(text("SELECT name FROM sys.tables WHERE name LIKE 'OrganizationMembers_%'"))
        previous_member_reports = cursor_member.fetchall()

    # Return the most recent table names
    member_table_name = previous_member_reports[-1][0] if previous_member_reports else None
    item_table_name = previous_item_reports[-1][0] if previous_item_reports else None

    return member_table_name, item_table_name

def delete_user(username):
    """This function deletes a user from AGOL.
    Args:
        username (str): The username of the user to be deleted.
    """
    try:
        user = gis.users.get(username)
        if user:
            user.delete()
            print(f'User {username} has been deleted.')
        else:
            print(f'User {username} not found.')
    except Exception as e:
        print(f'Error deleting user {username}: {e}')

def get_empty_users():
    """This function queries the AGOL catalog database to find all users that have 0 items published.
    Returns:
        empty_users (list): A list of usernames that have 0 items published.
    """

