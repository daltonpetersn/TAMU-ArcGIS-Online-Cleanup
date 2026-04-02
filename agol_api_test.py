# Filename: migrate_agol_items.py
# Description: This script is used to migrate items from one ArcGIS Online account to another. It uses the ArcGIS API for Python to access the items a the source account and create new items in the destination account.
# Author: Dalton Peterson

### IMPORTS

from arcgis.gis import GIS

### GLOBAL VARIABLES & SETUP
API_KEY = "AAPTxy8BH1VEsoebNVZXo8HurBpInFZCTFXQGtfmyLZoMTR0194S0ZOv99u0zmcw-4BCR9LH9CAsNj7diSgc2VcOJRuZd8ckLQll2dBM3Jf6Aep-bbVvQCLL2VkBQE9aX_Ou60dgeCGpDQCI5sxe6cw_ViKVprgLrF5zN5XsOQn0BMrjecxc1fUBi03QncOXaeA-DOgvQIAK0B6DaYMW-CwGcai05Sj-Zzcsu1eAfbS7Glw.AT1_wIm6P7Gg"

# Connect to ArcGIS Online
gis = GIS("home")
# gis = GIS(url = "https://www.arcgis.com", api_key = API_KEY, verify_cert = False)

print(f'{gis.users.me.username} is connected to ArcGIS Online.')

HISTORICAL_ITEM_ACCT = gis.users.me.username

### FUNCTIONS

def migrate_item(id, dest_user):
    item = gis.content.get(id)
    print(f'Migrating item {item.title} from {item.owner} to {dest_user}...')

    try:
        item.reassign_to(dest_user)
        print(f'Item {item.title} has been migrated to {dest_user}.')
    except Exception as e:
        print(f'Error migrating item {item.title}: {e}')

def delete_item(id):
    item = gis.content.get(id)
    print(f'Deleting item {item.title} from {item.owner}...')

    try:
        item.delete()
        print(f'Item {item.title} has been deleted.')
    except Exception as e:
        print(f'Error deleting item {item.title}: {e}')

### TEST CODE

# test_item_id = '9e7c8a2fdbf2407e91546ada82f44c1d'
# test_item_id2 = '44a4b1242a6048c7951194b2325a2f36'
test_item_id3 = '31f16fc3ec6c4f3e8859ef09b2ada2b6'

qe = f'owner: daniel.goldberg@tamu.edu_tamu'
user_content_count = gis.content.advanced_search(query = qe, return_count = True)
print(f'User has {user_content_count} items in their ArcGIS Online account.')

# print(f'{gis.users.me.groups}')

delete_item(test_item_id3)

user_content_count2 = gis.content.advanced_search(query = qe, return_count = True)
print(f'User has {user_content_count2} items in their ArcGIS Online account.')

### MAIN

