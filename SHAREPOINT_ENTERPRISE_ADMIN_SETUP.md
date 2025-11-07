# SharePoint Enterprise - Admin Setup Guide

## Overview

SharePoint Enterprise enables tenant-wide syncing with access controls using **Azure AD Application Permissions**. This guide is for Microsoft 365 administrators setting up the integration.

## What You'll Need

- Microsoft 365 tenant with SharePoint Online
- **Global Administrator** or **Application Administrator** role in Azure AD
- 15 minutes for Azure AD setup

## Step 1: Create Azure AD App Registration

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to **Azure Active Directory** → **App registrations**
3. Click **+ New registration**
4. Fill in the registration form:
   - **Name**: `Airweave SharePoint Enterprise` (or your preferred name)
   - **Supported account types**: Select "Accounts in this organizational directory only (Single tenant)"
   - **Redirect URI**: Leave empty (not needed for service account authentication)
5. Click **Register**

6. **Copy these values** (you'll need them for Airweave):
   - **Application (client) ID**: Found on the Overview page
     ```
     Example: 12345678-1234-1234-1234-123456789012
     ```
   - **Directory (tenant) ID**: Also on the Overview page
     ```
     Example: 87654321-4321-4321-4321-210987654321
     ```

## Step 2: Create Client Secret

1. In your app registration, navigate to **Certificates & secrets** (left sidebar)
2. Under **Client secrets**, click **+ New client secret**
3. Add configuration:
   - **Description**: `Airweave SharePoint Sync Secret`
   - **Expires**: Choose **24 months** (recommended) or **Never** (if policy allows)
4. Click **Add**

5. **IMMEDIATELY copy the secret VALUE**:
   ```
   Example: abc123~def456.ghi789_jkl012-mno345
   ```
   ⚠️ **Critical**: You cannot view this value again! If you lose it, you must create a new secret.

## Step 3: Grant API Permissions

1. In your app registration, go to **API permissions**
2. Click **+ Add a permission**
3. Select **Microsoft Graph** → **Application permissions** (NOT Delegated)

4. Search for and add these 5 permissions:

   ### Content Access Permissions
   - `Sites.Read.All` - Read items in all site collections
   - `Files.Read.All` - Read files in all site collections

   ### Access Control Permissions
   - `User.Read.All` - Read all users' full profiles
   - `Group.Read.All` - Read all groups
   - `GroupMember.Read.All` - Read memberships of all groups

5. After adding all 5 permissions, they will show "Not granted for [Your Organization]"

6. **Click "Grant admin consent for [Your Organization]"** (top button)
   - ⚠️ Only Global Admin or Application Admin can do this
   - After clicking, Status should change to ✅ "Granted for [Your Organization]"
   - All 5 permissions should have green checkmarks

## Step 4: Verify Configuration

Your app registration should now look like this:

**API Permissions** tab:
```
Permission                  Type         Status
Sites.Read.All              Application  ✅ Granted for [Org]
Files.Read.All              Application  ✅ Granted for [Org]
User.Read.All               Application  ✅ Granted for [Org]
Group.Read.All              Application  ✅ Granted for [Org]
GroupMember.Read.All        Application  ✅ Granted for [Org]
```

**Certificates & secrets** tab:
```
Description                     Expires      Value
Airweave SharePoint Sync...     (date)       (hidden) ← You copied this earlier
```

## Step 5: Configure in Airweave

1. In Airweave, create a new **SharePoint Enterprise** connection
2. Authentication method: **Direct Credentials**
3. Enter the three values from above:
   ```
   Client ID:      [paste Application (client) ID]
   Client Secret:  [paste the secret VALUE you copied]
   Tenant ID:      [paste Directory (tenant) ID]
   ```
4. Click **Connect** - Airweave will validate credentials
5. Create a sync and run it

## How It Works

### Authentication Flow (Client Credentials)

```
Airweave → POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
         ↓
         {
           "client_id": "...",
           "client_secret": "...",
           "scope": "https://graph.microsoft.com/.default",
           "grant_type": "client_credentials"
         }
         ↓
         ← { "access_token": "eyJ0...", "expires_in": 3599 }
         ↓
Airweave → GET https://graph.microsoft.com/v1.0/sites/root
         (with Authorization: Bearer eyJ0...)
         ↓
         ← SharePoint data
```

**Key Points:**
- No user interaction needed (fully automated)
- Token expires after ~60 minutes (Airweave refreshes automatically)
- App acts as itself (not on behalf of a user)
- Requires admin consent (cannot be done by regular users)

### What Gets Synced

**Phase 1: Entity Sync**
- All SharePoint sites across tenant
- All document libraries and files
- File permissions: `["user:john@acme.com", "group:engineering"]`
- Lists, pages, and metadata

**Phase 2: Access Control Sync** (Adjacent Pipeline)
- All groups in the tenant
- Group memberships (using `/transitivemembers` for nested groups)
- User-group relationships stored in `access_control_membership` table

**Phase 3: Search with Access Controls**
- User searches → Groups expanded → Results filtered
- Only shows files user has access to
- Respects SharePoint permissions in Airweave search

## Security & Compliance

### Principle of Least Privilege

The app registration uses **only read permissions**:
- ✅ Can read content, permissions, and memberships
- ❌ Cannot modify files, permissions, or group memberships
- ❌ Cannot delete anything
- ❌ Cannot send emails or perform actions on behalf of users

### Audit Trail

- Azure AD Sign-in logs show all API calls by the app
- Airweave logs show all sync operations
- Search logs show access control filtering

### Data Flow

```
SharePoint (Microsoft 365 Tenant)
    ↓ (Application Permissions - read-only)
Airweave Backend (processes and indexes)
    ↓ (Encrypted at rest)
Vector Database (Qdrant) + PostgreSQL
    ↓ (Search with access control filtering)
End Users (only see files they can access)
```

## Troubleshooting

### Error: "Invalid client secret"

**Symptoms**: Token acquisition fails immediately

**Solutions**:
1. Verify client secret hasn't expired (check Certificates & secrets tab)
2. Ensure you copied the secret VALUE (not the Secret ID)
3. Check for extra spaces or characters when pasting
4. Create a new client secret if the old one is lost

### Error: "Unauthorized" or "Access denied"

**Symptoms**: Token acquires but API calls fail with 401/403

**Solutions**:
1. Verify all 5 API permissions are granted (green checkmarks)
2. Ensure you clicked "Grant admin consent" button
3. Wait 5-10 minutes after granting consent (propagation delay)
4. Try re-granting admin consent

### Error: "AADSTS700016: Application not found"

**Symptoms**: Token endpoint returns app not found

**Solutions**:
1. Verify you're using the correct **tenant_id** (not client_id by mistake)
2. Ensure app registration exists in the correct Azure AD tenant
3. Check that tenant_id matches your M365 organization

### No Files Synced

**Symptoms**: Sync completes but no files appear

**Possible Causes**:
1. **Empty SharePoint**: Your tenant might not have any sites/files yet
2. **Wrong Tenant**: Verify tenant_id matches your actual M365 organization
3. **Permissions Not Applied**: Re-grant admin consent and wait 10 minutes

**Debug Steps**:
```bash
# Check if app can access Microsoft Graph
curl -X POST https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token \
  -d "client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&scope=https://graph.microsoft.com/.default&grant_type=client_credentials"

# Should return: {"access_token": "eyJ0...", "expires_in": 3599}

# Test access to SharePoint
curl -H "Authorization: Bearer {ACCESS_TOKEN}" \
  https://graph.microsoft.com/v1.0/sites/root

# Should return: {"id": "...", "displayName": "...", ...}
```

## Permission Reference

| Permission | Scope | Why Needed |
|------------|-------|------------|
| `Sites.Read.All` | All site collections | Read SharePoint sites and structure |
| `Files.Read.All` | All files | Download files for content extraction |
| `User.Read.All` | All users | Map emails to users for access controls |
| `Group.Read.All` | All groups | Understand organizational structure |
| `GroupMember.Read.All` | Group memberships | Resolve who can access what |

**Note**: These are **Application Permissions** (not Delegated Permissions). The difference:
- **Application**: App acts independently, requires admin consent, full tenant access
- **Delegated**: App acts on behalf of a user, limited to user's access

## Best Practices

1. **Secret Management**:
   - Store client secret in Airweave's encrypted storage
   - Set expiration to 24 months (not "Never" unless required by policy)
   - Rotate before expiration
   - Document expiration date in your runbook

2. **Monitoring**:
   - Review Azure AD sign-in logs monthly
   - Monitor Airweave sync logs for errors
   - Check access control filtering statistics

3. **Testing**:
   - Test in a non-production tenant first (if available)
   - Verify access controls work: different users see different results
   - Ensure nested groups expand correctly

4. **Documentation**:
   - Document the app registration details in your IT runbook
   - Keep track of client secret expiration date
   - Note who has Global Admin access for renewals

## Comparison: OAuth vs Admin Credentials

| Aspect | Standard SharePoint (OAuth) | SharePoint Enterprise (Admin) |
|--------|---------------------------|---------------------------|
| **Who authenticates?** | Individual user | Service account (app) |
| **What can be accessed?** | User's files only | All tenant files |
| **User interaction?** | Required (browser login) | Not required |
| **Access controls?** | No | Yes (file-level) |
| **Best for** | Personal/team use | Enterprise deployments |
| **Setup complexity** | Easy | Requires admin |
| **Syncs without users?** | No (needs user token) | Yes (automated) |

## Next Steps After Setup

1. **Run First Sync**: Trigger a sync in Airweave to test the connection
2. **Verify Data**: Check that files appear in your collection
3. **Test Search**: Search as different users to verify access controls work
4. **Monitor**: Review sync logs for any errors or warnings
5. **Schedule**: Set up automated sync schedule (daily or hourly)

## Support

If you encounter issues:
1. Check Azure AD app permissions (all 5 granted?)
2. Verify client secret hasn't expired
3. Review Airweave sync logs for specific error messages
4. Contact Airweave support with:
   - App registration ID (client_id)
   - Error messages from sync logs
   - Azure AD tenant ID

**Do not share client_secret** in support tickets!

