param(
    [ValidateSet("user", "project")]
    [string]$Scope = "user"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SourceRoot = Join-Path $RepoRoot "skills\book-video"

if ($Scope -eq "user") {
    $TargetRoot = Join-Path $env:USERPROFILE ".codebuddy\skills"
} else {
    $TargetRoot = Join-Path $RepoRoot ".codebuddy\skills"
}

$Skills = @(
    @{
        Source = Join-Path $SourceRoot "story-producer"
        TargetName = "book-story-producer"
    },
    @{
        Source = Join-Path $SourceRoot "video-renderer"
        TargetName = "book-video-renderer"
    }
)

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

foreach ($Skill in $Skills) {
    if (-not (Test-Path $Skill.Source)) {
        throw "Skill source not found: $($Skill.Source)"
    }

    $Target = Join-Path $TargetRoot $Skill.TargetName

    if (Test-Path $Target) {
        Remove-Item -Recurse -Force $Target
    }

    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Copy-Item -Path (Join-Path $Skill.Source "*") -Destination $Target -Recurse -Force

    Write-Host "Installed $($Skill.TargetName) -> $Target"
}

Write-Host ""
Write-Host "WorkBuddy skills installed successfully."
Write-Host "Restart WorkBuddy / CodeBuddy Code if the skills are not picked up in the current session."
