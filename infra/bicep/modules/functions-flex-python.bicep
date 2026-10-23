@description('Region inherited from the resource-group deployment.')
param location string

@description('Validated lowercase project identifier.')
@minLength(3)
param projectName string

@description('Short-lived academic environment.')
param environment string

@description('Stable token used to make globally unique resource names.')
@minLength(8)
param resourceToken string

@description('Non-sensitive lifecycle and ownership tags.')
param commonTags object

var normalizedProjectName = replace(toLower(projectName), '-', '')
var storageAccountName = take('st${normalizedProjectName}${resourceToken}', 24)
var functionAppName = take('func-${projectName}-${environment}-${resourceToken}', 60)
var deploymentContainerName = 'app-package-${take(resourceToken, 16)}'

// Built-in data-plane roles required by the Functions host and package deployment.
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${projectName}-${environment}-${take(resourceToken, 8)}'
  location: location
  tags: commonTags
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  tags: commonTags
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }

  resource blobService 'blobServices' = {
    name: 'default'

    resource deploymentContainer 'containers' = {
      name: deploymentContainerName
      properties: {
        publicAccess: 'None'
      }
    }
  }
}

resource blobOwnerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workloadIdentity.id, storageBlobDataOwnerRoleId)
  scope: storageAccount
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
  }
}

resource tableContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workloadIdentity.id, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorRoleId)
  }
}

resource flexPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-${projectName}-${environment}-${take(resourceToken, 8)}'
  location: location
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  tags: commonTags
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentity.id}': {}
    }
  }
  properties: {
    functionAppConfig: {
      deployment: {
        storage: {
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: workloadIdentity.id
          }
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}${deploymentContainerName}'
        }
      }
      runtime: {
        name: 'python'
        version: '3.12'
      }
      scaleAndConcurrency: {
        instanceMemoryMB: 512
        maximumInstanceCount: 1
      }
    }
    httpsOnly: true
    serverFarmId: flexPlan.id
    siteConfig: {
      minTlsVersion: '1.2'
    }
  }

  resource appSettings 'config' = {
    name: 'appsettings'
    properties: {
      AzureWebJobsStorage__accountName: storageAccount.name
      AzureWebJobsStorage__clientId: workloadIdentity.properties.clientId
      AzureWebJobsStorage__credential: 'managedidentity'
    }
  }
}

output resourceTypes array = [
  'Microsoft.ManagedIdentity/userAssignedIdentities'
  'Microsoft.Storage/storageAccounts'
  'Microsoft.Storage/storageAccounts/blobServices/containers'
  'Microsoft.Authorization/roleAssignments'
  'Microsoft.Web/serverfarms'
  'Microsoft.Web/sites'
]
