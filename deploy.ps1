[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [string]$Location,

    [Parameter(Mandatory = $true)]
    [string]$BackendAppName,

    [string]$FrontendAppName,

    [string]$StorageAccountName,

    [string]$SearchServiceName,

    [string]$FoundryAccountName,

    [string]$DocumentIntelligenceAccountName,

    [string]$StorageResourceGroup,
    [string]$SearchResourceGroup,
    [string]$FoundryResourceGroup,
    [string]$DocumentIntelligenceResourceGroup,
    [string]$AppServicePlanName,
    [string]$SubscriptionId,
    [string]$EnvironmentFile = (Join-Path $PSScriptRoot ".env"),
    [switch]$BackendOnly,

    [ValidateRange(60, 3600)]
    [int]$DeploymentTimeoutSeconds = 2400,

    [ValidateSet("B1", "B2", "B3", "P0v3", "P1v3", "P2v3")]
    [string]$Sku = "B1"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$script:AzCliPythonWarningShown = $false

function Invoke-AzCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Description,

        [Parameter(Mandatory = $true)]
        [string]$DisplayCommand,

        [switch]$StreamOutput
    )

    Write-Host "`n$Description"
    Write-Host "> az $DisplayCommand --only-show-errors"
    $cliArguments = @($Arguments) + @("--only-show-errors")
    $stderrPath = Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        "az-stderr-$([guid]::NewGuid().ToString('N')).txt"
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $PSNativeCommandUseErrorActionPreference = $false
            $output = @()
            if ($StreamOutput) {
                & az @cliArguments 2> $stderrPath | ForEach-Object { Write-Host $_ }
            }
            else {
                $output = & az @cliArguments 2> $stderrPath
            }
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }

        $stderr = ""
        if (Test-Path -LiteralPath $stderrPath) {
            $stderrContent = Get-Content -LiteralPath $stderrPath -Raw
            if ($null -ne $stderrContent) {
                $stderr = $stderrContent.Trim()
            }
        }
        if ($exitCode -ne 0) {
            $safeOutput = (@($output) + @($stderr) | Out-String).Trim()
            if ($configuration.ContainsKey("JWT_SECRET")) {
                $secret = [string]$configuration["JWT_SECRET"]
                if ($secret) {
                    $safeOutput = $safeOutput.Replace($secret, "<JWT_SECRET oculto>")
                }
            }
            throw "Azure CLI terminó con código $exitCode. $safeOutput"
        }

        if ($stderr) {
            if ($stderr -match "UserWarning:\s*([^\r\n]+)") {
                if (-not $script:AzCliPythonWarningShown) {
                    Write-Warning "Azure CLI reportó una advertencia no fatal de Python: $($Matches[1])"
                    $script:AzCliPythonWarningShown = $true
                }
            }
            else {
                Write-Warning "Azure CLI escribió mensajes por stderr, pero terminó con código 0."
            }
        }
        return ($output | Out-String).Trim()
    }
    finally {
        if (Test-Path -LiteralPath $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force
        }
    }
}

function Read-EnvironmentFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "No se encontró el archivo de configuración: $Path"
    }

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -match '^\s*$') {
            continue
        }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            throw "Línea inválida en el archivo de configuración."
        }

        $name = $Matches[1]
        $value = $Matches[2]
        if (
            $value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'")))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$name] = $value
    }
    return $values
}

function Get-AzResourceId {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$DisplayCommand
    )

    $resourceId = Invoke-AzCli `
        -Arguments $Arguments `
        -Description $Description `
        -DisplayCommand $DisplayCommand
    if ([string]::IsNullOrWhiteSpace($resourceId)) {
        throw "Azure no devolvió el identificador de recurso para $Description."
    }
    return $resourceId
}

function Ensure-RoleAssignment {
    param(
        [Parameter(Mandatory = $true)][string]$PrincipalId,
        [Parameter(Mandatory = $true)][string]$RoleName,
        [Parameter(Mandatory = $true)][string]$Scope
    )

    $query = "[?roleDefinitionName=='$RoleName'].id | [0]"
    $existingAssignment = Invoke-AzCli `
        -Arguments @(
            "role", "assignment", "list",
            "--assignee", $PrincipalId,
            "--scope", $Scope,
            "--query", $query,
            "--output", "tsv"
        ) `
        -Description "Comprobar el rol $RoleName en el recurso indicado." `
        -DisplayCommand "role assignment list --assignee <identidad-backend> --scope <recurso> --query <rol>"
    if (
        -not [string]::IsNullOrWhiteSpace($existingAssignment) -and
        $existingAssignment -ne "None"
    ) {
        Write-Host "El rol $RoleName ya está asignado en este alcance."
        return
    }

    Invoke-AzCli `
        -Arguments @(
            "role", "assignment", "create",
            "--assignee-object-id", $PrincipalId,
            "--assignee-principal-type", "ServicePrincipal",
            "--role", $RoleName,
            "--scope", $Scope,
            "--output", "none"
        ) `
        -Description "Asignar $RoleName a la identidad administrada del backend." `
        -DisplayCommand "role assignment create --assignee-object-id <identidad-backend> --role `"$RoleName`" --scope <recurso>"
}

function Copy-RequiredItem {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Falta un archivo requerido para el paquete: $Source"
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function New-PortableZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    Add-Type -AssemblyName System.IO.Compression
    $sourceRoot = (Resolve-Path -LiteralPath $SourceDirectory).Path.TrimEnd([char[]]@('\', '/'))
    $outputStream = [System.IO.File]::Create($DestinationPath)
    try {
        $archive = [System.IO.Compression.ZipArchive]::new(
            $outputStream,
            [System.IO.Compression.ZipArchiveMode]::Create,
            $false
        )
        try {
            foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File) {
                $relativePath = $file.FullName.Substring($sourceRoot.Length).
                    TrimStart([char[]]@('\', '/')).
                    Replace('\', '/')
                $entry = $archive.CreateEntry(
                    $relativePath,
                    [System.IO.Compression.CompressionLevel]::Optimal
                )
                $inputStream = [System.IO.File]::OpenRead($file.FullName)
                try {
                    $entryStream = $entry.Open()
                    try {
                        $inputStream.CopyTo($entryStream)
                    }
                    finally {
                        $entryStream.Dispose()
                    }
                }
                finally {
                    $inputStream.Dispose()
                }
            }
        }
        finally {
            $archive.Dispose()
        }
    }
    finally {
        $outputStream.Dispose()
    }
}

function New-BackendPackage {
    param([Parameter(Mandatory = $true)][string]$TemporaryRoot)

    $backendStage = Join-Path $TemporaryRoot "backend"
    New-Item -ItemType Directory -Path (Join-Path $backendStage "backend\scripts") -Force | Out-Null
    Copy-RequiredItem -Source (Join-Path $PSScriptRoot "backend\app\main.py") `
        -Destination (Join-Path $backendStage "main.py")
    Copy-RequiredItem -Source (Join-Path $PSScriptRoot "backend\__init__.py") `
        -Destination (Join-Path $backendStage "backend\__init__.py")
    Copy-RequiredItem -Source (Join-Path $PSScriptRoot "backend\app") `
        -Destination (Join-Path $backendStage "backend\app")
    Get-ChildItem -LiteralPath (Join-Path $backendStage "backend\app") `
        -Directory -Filter "__pycache__" -Recurse |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
    foreach ($scriptName in @("create_admin.py", "seed_data.py")) {
        Copy-RequiredItem -Source (Join-Path $PSScriptRoot "backend\scripts\$scriptName") `
            -Destination (Join-Path $backendStage "backend\scripts\$scriptName")
    }
    Copy-RequiredItem -Source (Join-Path $PSScriptRoot "backend\requirements.txt") `
        -Destination (Join-Path $backendStage "requirements.txt")
    $backendZip = Join-Path $TemporaryRoot "backend.zip"
    New-PortableZip -SourceDirectory $backendStage -DestinationPath $backendZip

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($backendZip)
    try {
        $archiveEntries = @($archive.Entries | ForEach-Object { $_.FullName })
        if ($archiveEntries | Where-Object { $_.Contains("\") }) {
            throw "El ZIP del backend contiene separadores Windows; se requieren rutas con /."
        }
        foreach ($requiredEntry in @(
            "main.py",
            "requirements.txt",
            "backend/__init__.py",
            "backend/app/main.py",
            "backend/scripts/seed_data.py"
        )) {
            if ($archiveEntries -notcontains $requiredEntry) {
                throw "El ZIP del backend no contiene la ruta requerida en su ubicación esperada: $requiredEntry"
            }
        }
    }
    finally {
        $archive.Dispose()
    }

    return $backendZip
}

function Set-BackendStartup {
    Invoke-AzCli `
        -Arguments @(
            "webapp", "config", "set",
            "--resource-group", $ResourceGroup,
            "--name", $BackendAppName,
            "--startup-file", "python -m uvicorn main:app --host 0.0.0.0 --port 8000",
            "--always-on", "true",
            "--output", "none"
        ) `
        -Description "Configurar Uvicorn para escuchar en el puerto 8000." `
        -DisplayCommand "webapp config set --resource-group `"$ResourceGroup`" --name `"$BackendAppName`" --startup-file `"python -m uvicorn main:app --host 0.0.0.0 --port 8000`" --always-on true"
}

function Show-BackendLogs {
    Invoke-AzCli `
        -Arguments @(
            "webapp", "log", "tail",
            "--name", $BackendAppName,
            "--resource-group", $ResourceGroup
        ) `
        -Description "Seguir los logs del backend en tiempo real; pulsa Ctrl+C para terminar." `
        -DisplayCommand "webapp log tail --name `"$BackendAppName`" --resource-group `"$ResourceGroup`"" `
        -StreamOutput
}

function Wait-ForDeploymentEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$ResourceGroupName,
        [Parameter(Mandatory = $true)][string]$AppName,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [switch]$ExpectBackendHealth
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastProgress = Get-Date
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest `
                -Uri $Uri `
                -TimeoutSec 15 `
                -UseBasicParsing
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                if ($ExpectBackendHealth) {
                    $health = $response.Content | ConvertFrom-Json
                    if ($health.status -ne "ok") {
                        Start-Sleep -Seconds 10
                        continue
                    }
                }
                Write-Host "$Name disponible: $Uri"
                return
            }
        }
        catch {
            # App Service returns transient errors while Oryx builds and starts the app.
        }

        if (((Get-Date) - $lastProgress).TotalSeconds -ge 30) {
            Write-Host "Esperando a que Azure complete la compilación y arranque de $Name..."
            $lastProgress = Get-Date
        }
        Start-Sleep -Seconds 10
    }

    throw (
        "$Name no quedó disponible en $TimeoutSeconds segundos. " +
        "Consulta los logs con: az webapp log deployment show " +
        "--resource-group `"$ResourceGroupName`" --name `"$AppName`""
    )
}

$configuration = @{}
if ($BackendOnly) {
    if ([string]::IsNullOrWhiteSpace($ResourceGroup) -or [string]::IsNullOrWhiteSpace($BackendAppName)) {
        throw "El grupo de recursos y el nombre del backend son obligatorios."
    }
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Instala Azure CLI y ejecuta az login antes de iniciar el despliegue."
    }
    if ($SubscriptionId) {
        Invoke-AzCli `
            -Arguments @("account", "set", "--subscription", $SubscriptionId) `
            -Description "Seleccionar la suscripción de Azure." `
            -DisplayCommand "account set --subscription `"$SubscriptionId`"" | Out-Null
    }
    $account = Invoke-AzCli `
        -Arguments @("account", "show", "--query", "name", "--output", "tsv") `
        -Description "Verificar la cuenta de Azure activa." `
        -DisplayCommand "account show --query name --output tsv"
    Write-Host "Cuenta de Azure: $account"
    Write-Host "Se actualizará únicamente el backend $BackendAppName en $ResourceGroup."
    $confirmation = Read-Host "Escribe SI para continuar"
    if ($confirmation.Trim() -ine "SI") {
        throw "Despliegue cancelado; no se modificaron recursos."
    }

    $temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) `
        "RioClaroDeploy-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    try {
        $backendZip = New-BackendPackage -TemporaryRoot $temporaryRoot
        Set-BackendStartup
        Invoke-AzCli `
            -Arguments @(
                "webapp", "config", "appsettings", "set",
                "--resource-group", $ResourceGroup, "--name", $BackendAppName,
                "--settings", "WEBSITES_PORT=8000", "PORT=8000",
                "SCM_DO_BUILD_DURING_DEPLOYMENT=true", "ENABLE_ORYX_BUILD=true",
                "WEBSITES_CONTAINER_START_TIME_LIMIT=1800",
                "--output", "none"
            ) `
            -Description "Configurar el puerto, la compilación remota y el plazo de inicio del backend." `
            -DisplayCommand "webapp config appsettings set --resource-group `"$ResourceGroup`" --name `"$BackendAppName`" --settings WEBSITES_PORT=8000 PORT=8000 SCM_DO_BUILD_DURING_DEPLOYMENT=true ENABLE_ORYX_BUILD=true WEBSITES_CONTAINER_START_TIME_LIMIT=1800"
        try {
            Invoke-AzCli `
                -Arguments @(
                    "webapp", "deploy", "--resource-group", $ResourceGroup,
                    "--name", $BackendAppName, "--src-path", $backendZip,
                    "--type", "zip", "--async", "true"
                ) `
                -Description "Enviar el ZIP del backend en modo asíncrono." `
                -DisplayCommand "webapp deploy --resource-group `"$ResourceGroup`" --name `"$BackendAppName`" --src-path <backend.zip> --type zip --async true"
        }
        catch {
            Write-Warning "Azure CLI no confirmó el envío del ZIP del backend. Se comprobará /health antes de considerar fallido el despliegue. $($_.Exception.Message)"
        }
        Wait-ForDeploymentEndpoint `
            -Name "Backend" `
            -Uri "https://$BackendAppName.azurewebsites.net/health" `
            -ResourceGroupName $ResourceGroup `
            -AppName $BackendAppName `
            -TimeoutSeconds $DeploymentTimeoutSeconds `
            -ExpectBackendHealth
    }
    finally {
        if (Test-Path -LiteralPath $temporaryRoot) {
            Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
        }
    }
    Show-BackendLogs
    return
}

if ([string]::IsNullOrWhiteSpace($AppServicePlanName)) {
    $AppServicePlanName = "$BackendAppName-plan"
}
foreach ($resourceGroupParameter in @(
    "StorageResourceGroup",
    "SearchResourceGroup",
    "FoundryResourceGroup",
    "DocumentIntelligenceResourceGroup"
)) {
    if ([string]::IsNullOrWhiteSpace((Get-Variable -Name $resourceGroupParameter -ValueOnly))) {
        Set-Variable -Name $resourceGroupParameter -Value $ResourceGroup
    }
}

$requiredNames = @(
    $ResourceGroup,
    $Location,
    $BackendAppName,
    $FrontendAppName,
    $StorageAccountName,
    $SearchServiceName,
    $FoundryAccountName,
    $DocumentIntelligenceAccountName,
    $AppServicePlanName
)
if ($requiredNames | Where-Object { [string]::IsNullOrWhiteSpace($_) }) {
    throw "Los nombres del grupo, región, aplicaciones y servicios Azure son obligatorios."
}
if ($BackendAppName -eq $FrontendAppName) {
    throw "El nombre de App Service debe ser distinto para backend y frontend."
}

$configuration = Read-EnvironmentFile -Path $EnvironmentFile
$requiredSettings = @(
    "JWT_SECRET",
    "FOUNDRY_PROJECT_ENDPOINT",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
    "AZURE_STORAGE_BLOB_URL"
)
foreach ($settingName in $requiredSettings) {
    if (
        -not $configuration.ContainsKey($settingName) -or
        [string]::IsNullOrWhiteSpace($configuration[$settingName])
    ) {
        throw "Define $settingName en el archivo de configuración antes de desplegar."
    }
}
if ($configuration["JWT_SECRET"].Length -lt 32) {
    throw "JWT_SECRET debe tener al menos 32 caracteres."
}

$backendUrl = "https://$BackendAppName.azurewebsites.net"
$frontendUrl = "https://$FrontendAppName.azurewebsites.net"
$backendSettings = [ordered]@{}
foreach ($settingName in @(
    "FOUNDRY_PROJECT_ENDPOINT",
    "FOUNDRY_MODEL_NAME",
    "AI_SEARCH_PROJECT_CONNECTION_ID",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_INDEX_NAME",
    "AZURE_SEARCH_INVENTORY_INDEX_NAME",
    "AZURE_SEARCH_SYNONYM_MAP_NAME",
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
    "AZURE_STORAGE_BLOB_URL",
    "AZURE_STORAGE_CONTAINER_NAME",
    "JWT_SECRET",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "JWT_EXPIRE_MINUTES"
)) {
    if ($configuration.ContainsKey($settingName) -and
        -not [string]::IsNullOrWhiteSpace($configuration[$settingName])) {
        $backendSettings[$settingName] = $configuration[$settingName]
    }
}

if (-not $backendSettings.Contains("JWT_ISSUER")) {
    $backendSettings["JWT_ISSUER"] = "rio-claro-api"
}
if (-not $backendSettings.Contains("JWT_AUDIENCE")) {
    $backendSettings["JWT_AUDIENCE"] = "rio-claro-frontend"
}
if (-not $backendSettings.Contains("JWT_EXPIRE_MINUTES")) {
    $backendSettings["JWT_EXPIRE_MINUTES"] = "30"
}
if (-not $backendSettings.Contains("AZURE_SEARCH_INDEX_NAME")) {
    $backendSettings["AZURE_SEARCH_INDEX_NAME"] = "rio-claro-invoices"
}
if (-not $backendSettings.Contains("AZURE_SEARCH_INVENTORY_INDEX_NAME")) {
    $backendSettings["AZURE_SEARCH_INVENTORY_INDEX_NAME"] = "inventario-index"
}
if (-not $backendSettings.Contains("AZURE_SEARCH_SYNONYM_MAP_NAME")) {
    $backendSettings["AZURE_SEARCH_SYNONYM_MAP_NAME"] = "producto-sinonimos"
}
if (-not $backendSettings.Contains("AZURE_STORAGE_CONTAINER_NAME")) {
    $backendSettings["AZURE_STORAGE_CONTAINER_NAME"] = "facturas-raw"
}
$backendSettings["CORS_ORIGINS"] = $frontendUrl
$backendSettings["AUTH_DATABASE_PATH"] = "/home/data/users.db"
$backendSettings["PYTHONPATH"] = "/home/site/wwwroot"
$backendSettings["WEBSITE_ENABLE_APP_SERVICE_STORAGE"] = "true"
$backendSettings["WEBSITES_PORT"] = "8000"
$backendSettings["PORT"] = "8000"
$backendSettings["SCM_DO_BUILD_DURING_DEPLOYMENT"] = "true"
$backendSettings["ENABLE_ORYX_BUILD"] = "true"
$backendSettings["WEBSITES_CONTAINER_START_TIME_LIMIT"] = "1800"
$frontendSettings = @(
    "NEXT_PUBLIC_BACKEND_URL=$backendUrl",
    "SCM_DO_BUILD_DURING_DEPLOYMENT=true",
    "ENABLE_ORYX_BUILD=true"
)

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Instala Azure CLI y ejecuta az login antes de iniciar el despliegue."
}

if ($SubscriptionId) {
    Invoke-AzCli `
        -Arguments @("account", "set", "--subscription", $SubscriptionId) `
        -Description "Seleccionar la suscripción de Azure." `
        -DisplayCommand "account set --subscription `"$SubscriptionId`"" | Out-Null
}
$account = Invoke-AzCli `
    -Arguments @("account", "show", "--query", "name", "--output", "tsv") `
    -Description "Verificar la cuenta de Azure activa." `
    -DisplayCommand "account show --query name --output tsv"

Write-Host ""
Write-Host "Cuenta de Azure: $account"
Write-Host "Grupo de recursos: $ResourceGroup ($Location)"
Write-Host "Plan Linux: $AppServicePlanName ($Sku)"
Write-Host "Backend: $BackendAppName (Python 3.11)"
Write-Host "Frontend: $FrontendAppName (Node 22 LTS)"
Write-Host "Se actualizarán los App Services y se desplegará código en ambos."
$confirmation = Read-Host "Escribe SI para continuar"
if ($confirmation.Trim() -ine "SI") {
    throw "Despliegue cancelado; no se modificaron recursos."
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) `
    "RioClaroDeploy-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $groupExists = Invoke-AzCli `
        -Arguments @("group", "exists", "--name", $ResourceGroup, "--output", "tsv") `
        -Description "Comprobar el grupo de recursos." `
        -DisplayCommand "group exists --name `"$ResourceGroup`" --output tsv"
    if ($groupExists -ne "true") {
        Invoke-AzCli `
            -Arguments @(
                "group", "create",
                "--name", $ResourceGroup,
                "--location", $Location,
                "--output", "none"
            ) `
            -Description "Crear el grupo de recursos." `
            -DisplayCommand "group create --name `"$ResourceGroup`" --location `"$Location`""
    }

    $existingPlan = Invoke-AzCli `
        -Arguments @(
            "appservice", "plan", "list",
            "--resource-group", $ResourceGroup,
            "--query", "[?name=='$AppServicePlanName'].name | [0]",
            "--output", "tsv"
        ) `
        -Description "Comprobar si existe el plan App Service." `
        -DisplayCommand "appservice plan list --resource-group `"$ResourceGroup`""
    if (
        [string]::IsNullOrWhiteSpace($existingPlan) -or
        $existingPlan -eq "None"
    ) {
        Invoke-AzCli `
            -Arguments @(
                "appservice", "plan", "create",
                "--name", $AppServicePlanName,
                "--resource-group", $ResourceGroup,
                "--location", $Location,
                "--sku", $Sku,
                "--is-linux",
                "--output", "none"
            ) `
            -Description "Crear un plan App Service Linux." `
            -DisplayCommand "appservice plan create --name `"$AppServicePlanName`" --resource-group `"$ResourceGroup`" --location `"$Location`" --sku $Sku --is-linux"
    }

    $existingApps = Invoke-AzCli `
        -Arguments @(
            "webapp", "list",
            "--resource-group", $ResourceGroup,
            "--query", "[].name",
            "--output", "tsv"
        ) `
        -Description "Comprobar los App Services existentes en el grupo." `
        -DisplayCommand "webapp list --resource-group `"$ResourceGroup`" --query [].name"
    $appNames = @($existingApps -split '\r?\n' | Where-Object { $_ })
    if ($appNames -notcontains $BackendAppName) {
        Invoke-AzCli `
            -Arguments @(
                "webapp", "create",
                "--name", $BackendAppName,
                "--resource-group", $ResourceGroup,
                "--plan", $AppServicePlanName,
                "--runtime", "PYTHON:3.11",
                "--output", "none"
            ) `
            -Description "Crear el App Service Linux para FastAPI." `
            -DisplayCommand "webapp create --name `"$BackendAppName`" --resource-group `"$ResourceGroup`" --plan `"$AppServicePlanName`" --runtime PYTHON:3.11"
    }
    if ($appNames -notcontains $FrontendAppName) {
        Invoke-AzCli `
            -Arguments @(
                "webapp", "create",
                "--name", $FrontendAppName,
                "--resource-group", $ResourceGroup,
                "--plan", $AppServicePlanName,
                "--runtime", "NODE:22-lts",
                "--output", "none"
            ) `
            -Description "Crear el App Service Linux para Next.js." `
            -DisplayCommand "webapp create --name `"$FrontendAppName`" --resource-group `"$ResourceGroup`" --plan `"$AppServicePlanName`" --runtime NODE:22-lts"
    }

    Set-BackendStartup
    Invoke-AzCli `
        -Arguments @(
            "webapp", "config", "set",
            "--resource-group", $ResourceGroup,
            "--name", $FrontendAppName,
            "--startup-file", "npm run start",
            "--always-on", "true",
            "--output", "none"
        ) `
        -Description "Configurar el comando de inicio y disponibilidad del frontend; Node 22 LTS ya se fijó al crear el App Service." `
        -DisplayCommand "webapp config set --name `"$FrontendAppName`" --startup-file `"npm run start`" --always-on true"
    foreach ($appName in @($BackendAppName, $FrontendAppName)) {
        Invoke-AzCli `
            -Arguments @(
                "webapp", "update",
                "--resource-group", $ResourceGroup,
                "--name", $appName,
                "--https-only", "true",
                "--output", "none"
            ) `
            -Description "Requerir HTTPS para $appName." `
            -DisplayCommand "webapp update --resource-group `"$ResourceGroup`" --name `"$appName`" --https-only true"
    }

    $backendSettingArguments = @(
        "webapp", "config", "appsettings", "set",
        "--resource-group", $ResourceGroup,
        "--name", $BackendAppName,
        "--settings"
    )
    foreach ($settingName in $backendSettings.Keys) {
        $backendSettingArguments += "$settingName=$($backendSettings[$settingName])"
    }
    $backendSettingArguments += @("--output", "none")
    Invoke-AzCli `
        -Arguments $backendSettingArguments `
        -Description "Configurar variables de entorno del backend desde el archivo local (valores ocultos)." `
        -DisplayCommand "webapp config appsettings set --resource-group `"$ResourceGroup`" --name `"$BackendAppName`" --settings <$($backendSettings.Count) valores protegidos>"
    Invoke-AzCli `
        -Arguments (@(
            "webapp", "config", "appsettings", "set",
            "--resource-group", $ResourceGroup,
            "--name", $FrontendAppName,
            "--settings"
        ) + $frontendSettings + @("--output", "none")) `
        -Description "Configurar la URL del backend en Next.js y habilitar compilación remota." `
        -DisplayCommand "webapp config appsettings set --resource-group `"$ResourceGroup`" --name `"$FrontendAppName`" --settings NEXT_PUBLIC_BACKEND_URL=<URL-backend> SCM_DO_BUILD_DURING_DEPLOYMENT=true"

    $principalId = Get-AzResourceId `
        -Arguments @(
            "webapp", "identity", "assign",
            "--resource-group", $ResourceGroup,
            "--name", $BackendAppName,
            "--query", "principalId",
            "--output", "tsv"
        ) `
        -Description "Habilitar la identidad administrada del backend." `
        -DisplayCommand "webapp identity assign --resource-group `"$ResourceGroup`" --name `"$BackendAppName`" --query principalId --output tsv"

    $storageScope = Get-AzResourceId `
        -Arguments @(
            "storage", "account", "show",
            "--resource-group", $StorageResourceGroup,
            "--name", $StorageAccountName,
            "--query", "id",
            "--output", "tsv"
        ) `
        -Description "Obtener el alcance de la cuenta de Storage." `
        -DisplayCommand "storage account show --resource-group `"$StorageResourceGroup`" --name `"$StorageAccountName`" --query id --output tsv"
    $searchScope = Get-AzResourceId `
        -Arguments @(
            "search", "service", "show",
            "--resource-group", $SearchResourceGroup,
            "--name", $SearchServiceName,
            "--query", "id",
            "--output", "tsv"
        ) `
        -Description "Obtener el alcance del servicio Azure AI Search." `
        -DisplayCommand "search service show --resource-group `"$SearchResourceGroup`" --name `"$SearchServiceName`" --query id --output tsv"
    $foundryScope = Get-AzResourceId `
        -Arguments @(
            "cognitiveservices", "account", "show",
            "--resource-group", $FoundryResourceGroup,
            "--name", $FoundryAccountName,
            "--query", "id",
            "--output", "tsv"
        ) `
        -Description "Obtener el alcance de Azure AI Foundry." `
        -DisplayCommand "cognitiveservices account show --resource-group `"$FoundryResourceGroup`" --name `"$FoundryAccountName`" --query id --output tsv"
    $documentIntelligenceScope = Get-AzResourceId `
        -Arguments @(
            "cognitiveservices", "account", "show",
            "--resource-group", $DocumentIntelligenceResourceGroup,
            "--name", $DocumentIntelligenceAccountName,
            "--query", "id",
            "--output", "tsv"
        ) `
        -Description "Obtener el alcance de Document Intelligence." `
        -DisplayCommand "cognitiveservices account show --resource-group `"$DocumentIntelligenceResourceGroup`" --name `"$DocumentIntelligenceAccountName`" --query id --output tsv"

    Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Storage Blob Data Contributor" -Scope $storageScope
    Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Search Index Data Contributor" -Scope $searchScope
    Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Search Service Contributor" -Scope $searchScope
    Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Cognitive Services User" -Scope $foundryScope
    Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Cognitive Services User" -Scope $documentIntelligenceScope

    $backendZip = New-BackendPackage -TemporaryRoot $temporaryRoot

    $frontendStage = Join-Path $temporaryRoot "frontend"
    New-Item -ItemType Directory -Path $frontendStage | Out-Null
    foreach ($item in @(
        "app",
        "components",
        "lib",
        "public",
        "package.json",
        "package-lock.json",
        "next.config.mjs",
        "postcss.config.cjs",
        "tailwind.config.cjs"
    )) {
        Copy-RequiredItem `
            -Source (Join-Path $PSScriptRoot "frontend\$item") `
            -Destination (Join-Path $frontendStage $item)
    }
    $frontendZip = Join-Path $temporaryRoot "frontend.zip"
    New-PortableZip -SourceDirectory $frontendStage -DestinationPath $frontendZip

    try {
        Invoke-AzCli `
            -Arguments @(
                "webapp", "deploy",
                "--resource-group", $ResourceGroup,
                "--name", $BackendAppName,
                "--src-path", $backendZip,
                "--type", "zip",
                "--async", "true"
            ) `
            -Description "Enviar el ZIP de FastAPI a Kudu en modo asíncrono para evitar el timeout HTTP 504 durante la compilación remota." `
            -DisplayCommand "webapp deploy --resource-group `"$ResourceGroup`" --name `"$BackendAppName`" --src-path <backend.zip> --type zip --async true"
    }
    catch {
        Write-Warning "Azure CLI no confirmó el envío del ZIP del backend. Se comprobará /health antes de considerar fallido el despliegue. $($_.Exception.Message)"
    }
    Wait-ForDeploymentEndpoint `
        -Name "Backend" `
        -Uri "$backendUrl/health" `
        -ResourceGroupName $ResourceGroup `
        -AppName $BackendAppName `
        -TimeoutSeconds $DeploymentTimeoutSeconds `
        -ExpectBackendHealth

    Invoke-AzCli `
        -Arguments @(
            "webapp", "deploy",
            "--resource-group", $ResourceGroup,
            "--name", $FrontendAppName,
            "--src-path", $frontendZip,
            "--type", "zip",
            "--async", "true"
        ) `
        -Description "Enviar el ZIP de Next.js a Kudu en modo asíncrono para completar la compilación remota fuera de la solicitud inicial." `
        -DisplayCommand "webapp deploy --resource-group `"$ResourceGroup`" --name `"$FrontendAppName`" --src-path <frontend.zip> --type zip --async true"
    Wait-ForDeploymentEndpoint `
        -Name "Frontend" `
        -Uri $frontendUrl `
        -ResourceGroupName $ResourceGroup `
        -AppName $FrontendAppName `
        -TimeoutSeconds $DeploymentTimeoutSeconds

    Write-Host "`nDespliegue y verificaciones completados."
    Write-Host "Backend: $backendUrl"
    Write-Host "Frontend: $frontendUrl"
    Write-Host "La base SQLite persistente se configura en /home/data/users.db."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
Show-BackendLogs
