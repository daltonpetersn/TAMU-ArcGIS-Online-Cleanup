# File Name: Identify_Historical_AGOL_Users.p1
# Author: Dalton Peterson
# Date: 03/26/2026
# Requires: Powershell 7.0+
# Description: This file takes an input report from ArcGIS Online (AGOL) and produces a csv of all members with a 
#              fields that identify the user's current affiliation w/ TAMU and their manager (if exists)



# collect csv
param(
    [string]$input_csv_path
)

# Import library for accessing TAMU Identification System
Import-Module Microsoft.Graph.Users 
Connect-MgGraph -Scopes "User.Read.All" -NoWelcome

Write-Host "input csv path: $($input_csv_path)"

# $input_csv = Import-Csv -Path $input_csv_path
$input_csv = Import-Csv -Path "./TAMU-ArcGIS-Online-Cleanup/reports/OrganizationMembers_2026-04-02.csv"

$UserTable = @()
$ErrorUsers = @()

$UserTable = $input_csv | ForEach-Object {
    Import-Module Microsoft.Graph.Users
    Connect-MgGraph -Scopes "User.Read.All" -NoWelcome

    function Format-Email {
        param([string]$username)
        $username = $username -replace '_tamu$', ''
        if ($username -match '@') { $username = $username.Split('@')[0] }
        return "$username@tamu.edu"
    }

    function Get-EntraIDStatus {
        param([array]$emailsToTry)
        $emailsToTry = @($emailsToTry) | Where-Object { $_ -and $_.Trim() -ne "" } | Select-Object -Unique
        foreach ($emailToTry in $emailsToTry) {
            try {
                $user = Get-MgUser -UserId $emailToTry -Property Department, DisplayName -ErrorAction Stop
                $userdepartment = if ($user.Department) { $user.Department } else { "" }
                return 1, $userdepartment, $emailToTry
            }
            catch {
                Write-Host "Failed to find user with email: $emailToTry"
            }
        }
        return 0, "", ""
    }

    function Find-ManagerEmail {
        param([string]$email)
        try {
            $manager = Get-MgUserManager -UserId $email -ErrorAction Stop
            if ($manager) {
                $manageruser = Get-MgUser -UserId $manager.Id -Property Mail, Department, DisplayName -ErrorAction Stop
                $managerdepartment = if ($manageruser.Department) { $manageruser.Department } else { "" }
                $managerEmail = if ($manageruser.Mail) { $manageruser.Mail } else { "" }
                Write-Host "Found manager: $($manageruser.DisplayName) with email: $managerEmail"
            }
            else {
                $managerEmail = ""; $managerdepartment = ""
            }
        }
        catch {
            Write-Host "Error getting manager: $($_.Exception.Message)"
            $managerEmail = ""; $managerdepartment = ""
        }
        return $managerEmail, $managerdepartment
    }

    function Find-GroupMemberships {
        param([string]$email)
        try {
            $groupMemberships = Get-MgUserMemberOf -UserId $email -Property id -ErrorAction Stop | Select-Object -ExpandProperty Id
        }
        catch {
            Write-Host "Error getting groups: $($_.Exception.Message)"
            $groupMemberships = ""
        }
        return $groupMemberships
    }

    function Find-AlternateEmail {
        param([array]$emailstotry)

        foreach ($emailToCheck in $emailstotry) {
            if (-not $emailToCheck -or $emailToCheck.Trim() -eq "") { continue }
            try {
                $alternateMatch = Get-MgUser -Filter "otherMails/any(x:x eq '$emailToCheck')" -Property id, displayName, userPrincipalName -ErrorAction Stop
                $altEmail = $alternateMatch.UserPrincipalName
                return $altEmail
            }
            catch {
                # Continue to next email
            }
        }
        return ""
    }

    # Initialize variables for analysis
    $username = $_.Username
    $email = $_.Email
    $name = $_.Name

    $formattedEmail1 = Format-Email -username $username
    $formattedEmail2 = Format-Email -username $email
    $emailstotry = @($email, $formattedEmail1, $formattedEmail2) | Select-Object -Unique

    $altEmail = Find-AlternateEmail -emailstotry $emailstotry
    if ($altEmail -and $altEmail.Trim() -ne "") {
        $emailstotry += $altEmail
    }
    $entraid_lookup = Get-EntraIDStatus -emailsToTry $emailstotry

    if ($entraid_lookup[0] -eq 1) {
        Write-Host "$email found in EntraID as $($entraid_lookup[2]). Department: $($entraid_lookup[1])"
        $entraid_status = $entraid_lookup[0]
        $userDepartment = $entraid_lookup[1]
        $workingEmail = $entraid_lookup[2]
        
        $managerInfo = Find-ManagerEmail -email $workingEmail
        $managerEmail = $managerInfo[0]
        $managerDepartment = $managerInfo[1]

        $groupMemberships = Find-GroupMemberships -email $workingEmail
        $groupMemberships = if ($groupMemberships) { $groupMemberships -join ", " } else { "" }
        $groupMemberships = $groupMemberships.Substring(0, [math]::Min(1000, $groupMemberships.Length))
    }
    else {
        $entraid_status = 0
        $managerEmail = ""
        $managerDepartment = ""
        $userDepartment = ""
        $groupMemberships = ""
        $workingEmail = ""
    }

    try {
        $emailsTried = ($emailstotry -join ", ")
        $emailsTried = $emailsTried.Substring(0, [math]::Min(500, $emailsTried.Length))
        [PSCustomObject]@{
            Username          = $username
            Email             = $email
            Name              = $name
            EmailsTried       = $emailsTried
            EntraID_Status    = $entraid_status
            ManagerEmail      = $managerEmail
            ManagerDepartment = $managerDepartment
            UserDepartment    = $userDepartment
            WorkingEmail      = $workingEmail
            Groups            = $groupMemberships
            ErrorUser         = ""
        }
    }
    catch {
        [PSCustomObject]@{
            Username          = $username
            Email             = $email
            Name              = $name
            EmailsTried       = ""
            EntraID_Status    = 0
            ManagerEmail      = ""
            ManagerDepartment = ""
            UserDepartment    = ""
            WorkingEmail      = ""
            Groups            = ""
            ErrorUser         = $username
        }
    }

}

$ErrorUsers = $UserTable | Where-Object { $_.ErrorUser } | Select-Object -ExpandProperty ErrorUser
$UserTable = $UserTable | Select-Object -ExcludeProperty ErrorUser


# Export results
# $UserTable | Export-Csv -Path ".\reports\AGOL_EntraID_Status.csv" -NoTypeInformation
# $ErrorUsers | Out-File -FilePath ".\reports\error_hist_users.txt"

$UserTable | Export-Csv -Path ".\TAMU-ArcGIS-Online-Cleanup\reports\AGOL_EntraID_Status.csv" -NoTypeInformation
$ErrorUsers | Out-File -FilePath ".\TAMU-ArcGIS-Online-Cleanup\reports\error_hist_users.txt"

Write-Host "Processing complete:"
Write-Host "Users Processed: $($UserTable.Count)"