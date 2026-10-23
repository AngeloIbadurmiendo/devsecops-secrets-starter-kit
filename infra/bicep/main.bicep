targetScope = 'resourceGroup'

@description('Lowercase project identifier used to derive resource names.')
@minLength(3)
@maxLength(31)
param projectName string

@description('Short-lived academic environment.')
@allowed([
  'dev'
  'test'
])
param environment string = 'dev'

@description('Azure region validated by the project preflight.')
@allowed([
  'brazilsouth'
])
param location string = 'brazilsouth'

@description('Planned deletion date in YYYY-MM-DD format. The starter-kit plan rejects pending values.')
param expiresOn string

var resourceToken = toLower(uniqueString(subscription().id, resourceGroup().id, projectName, environment))
var commonTags = {
  environment: environment
  expiresOn: expiresOn
  managedBy: 'feria-starter'
  projectName: projectName
  purpose: 'academic-devsecops-validation'
}

module functionsProfile 'modules/functions-flex-python.bicep' = {
  name: 'functions-flex-python-${take(resourceToken, 8)}'
  params: {
    commonTags: commonTags
    environment: environment
    location: location
    projectName: projectName
    resourceToken: resourceToken
  }
}

output plannedResourceGroupName string = resourceGroup().name
output plannedResourceTypes array = functionsProfile.outputs.resourceTypes
