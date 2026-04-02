# File Name: Identify_Historical_AGOL_Users.p1
# Author: Dalton Peterson
# Date: 03/26/2026
# Description: This file takes an input report from ArcGIS Online (AGOL) and produces a csv of all members with a 
#              fields that identify the user's current affiliation w/ TAMU and their manager (if exists)


# TAMU Group ID's for reference
# Current Students: f7b90ce2-1842-4830-a8a3-8c22705a2e90
# Current Employees: 5da07dc2-1f1d-4120-91e5-56687befff44


# collect csv
param(
    [string]$input_csv_path
)

# Import library for accessing TAMU Identification System
Import-Module Microsoft.Graph.Users
Connect-MgGraph -Scopes "User.Read.All"

Write-Host "input csv path: $($input_csv_path)"

$input_csv = Import-Csv -Path $input_csv_path
# $input_csv = Import-Csv -Path "./Migrate_Items/reports/OrganizationMembers_2026-03-31.csv"


# Initialize arrays for results
$UserTable = @()
$errorUsers = @()

# Functions
function Format-Email {
    param(
        [string]$username
    )
    # strip any trailing `_tamu` suffix that was appended
    $username = $username -replace '_tamu$', ''

    # if there's an @ sign, just keep the local part before it
    if ($username -match '@') {
        $username = $username.Split('@')[0]
    }

    # normalize to tamu.edu domain
    $formattedEmail = "$username@tamu.edu"

    return $formattedEmail
}

function Get-EntraIDStatus {
    param(
        [string]$email,
        [string]$formattedEmail,
        [string]$altEmail
    )

    $emailsToTry = @($email, $formattedEmail, $altEmail) | Where-Object { $_ -and $_.Trim() -ne "" } | Select-Object -Unique

    foreach ($emailToTry in $emailsToTry) {
        try {
            $user = Get-MgUser -UserId $emailToTry -Property Department, DisplayName -ErrorAction Stop
            $userdepartment = if ($user.Department) { $user.Department } else { "" }
            Write-Host "Found user: $($user.DisplayName) with department: '$userdepartment'"
            return 1, $userdepartment, $emailToTry  # Return status, department, and working email
        }
        catch {
            Write-Host "Failed to find user with email: $emailToTry"
            # Continue to next email
        }
    }

    return 0, "", ""  # Not found
}

function Find-ManagerEmail {
    param(
        [string]$email
    )

    try {
        $manager = Get-MgUserManager -UserId $email -ErrorAction Stop
        if ($manager) {
            $manageruser = Get-MgUser -UserId $manager.Id -Property Mail, Department, DisplayName -ErrorAction Stop
            $managerdepartment = if ($manageruser.Department) { $manageruser.Department } else { "" }
            $managerEmail = if ($manageruser.Mail) { $manageruser.Mail } else { "" }
            Write-Host "Found manager: $($manageruser.DisplayName) with email: $managerEmail"
        }
        else {
            Write-Host "No manager found for user"
            $managerEmail = ""
            $managerdepartment = ""
        }
    }
    catch {
        Write-Host "Error getting manager: $($_.Exception.Message)"
        $managerEmail = ""
        $managerdepartment = ""
    }

    return $managerEmail, $managerdepartment
}

function Find-GroupMemberships {
    param(
        [string]$email
    )

    try {
        $groupMemberships = Get-MgUserMemberOf -UserId $email -Property id -ErrorAction Stop | Select-Object -ExpandProperty id
    }
    catch {
        Write-Host "Error getting groups: $($_.Exception.Message)"
        $groupMemberships = ""
    }

    return $groupMemberships
}

function Find-AlternateEmail {
    param(
        [string]$email,
        [string]$formattedEmail
    )
    try {
        $alternateMatch = Get-MgUser -Filter "otherMails/any(x:x eq '$email')" -Property id, displayName, userPrincipalName -ErrorAction Stop
        $altEmail = $alternateMatch.UserPrincipalName
    }
    catch {
        try {
            $alternateMatch = Get-MgUser -Filter "otherMails/any(x:x eq '$formattedEmail')" -Property id, displayName, userPrincipalName -ErrorAction Stop
            $altEmail = $alternateMatch.UserPrincipalName
        }
        catch {
            $altEmail = ""
        }
    }

    return $altEmail
}


# Process each AGOL member
$input_csv | ForEach-Object {

    # Initialize variables for analysis
    $username = $_.Username
    $email = $_.Email
    $name = $_.Name
    $formattedEmail = Format-Email -username $username
    $altEmail = Find-AlternateEmail -email $email -formattedEmail $formattedEmail
    $entraid_lookup = Get-EntraIDStatus -email $email -formattedEmail $formattedEmail -altEmail $altEmail
    if ($entraid_lookup[0] -eq 1) {
        Write-Host "$email found in EntraID. Formatted email: $formattedEmail , Alternate Email = $altEmail"
        $entraid_status = $entraid_lookup[0]
        $userDepartment = $entraid_lookup[1]
        $workingEmail = $entraid_lookup[2]  # The email that actually worked

        # Use the working email for manager and group lookups
        $managerInfo = Find-ManagerEmail -email $workingEmail
        $managerEmail = $managerInfo[0]
        $managerDepartment = $managerInfo[1]
        $groupMemberships = Find-GroupMemberships -email $workingEmail
        Write-Host "Manager: $managerEmail , Groups: $groupMemberships , Department: $userDepartment"
    }
    else {
        Write-Host "$email not found in any form in EntraID, Formatted Email: $formattedEmail"
        $entraid_status = 0
        $managerEmail = ""
        $managerDepartment = ""
        $userDepartment = ""
        $groupMemberships = ""
    }

    try {
        $UserTable += [PSCustomObject]@{
            Username          = $username
            Email             = $email
            Name              = $name
            FormattedEmail    = $formattedEmail
            AlternateEmail    = $altEmail
            EntraID_Status    = $entraid_status
            ManagerEmail      = $managerEmail
            ManagerDepartment = $managerDepartment
            UserDepartment    = $userDepartment
            Groups            = $groupMemberships
        }
    }
    catch {
        $errorUsers += $username
    }
}

# Export results
$UserTable | Export-Csv -Path ".\reports\AGOL_EntraID_Status.csv" -NoTypeInformation
$errorUsers | Out-File -FilePath ".\reports\error_hist_users.txt"

Write-Host "Processing complete:"
Write-Host "Users Processed: $($UserTable.Count)"