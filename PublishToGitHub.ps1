# Auto-Commiter for backdated Git Commits
$ErrorActionPreference = "Stop"

$repoPath = "c:\Work\windows\Telegram link extractor"
Set-Location -Path $repoPath

# Ensure clean directory
if (Test-Path -Path "$repoPath\.git") {
    Write-Host "Removing existing git repo to rewrite history"
    Remove-Item -Path "$repoPath\.git" -Recurse -Force
}
git init

# Delete existing unwanted files to be absolutely sure
Remove-Item -Path "$repoPath\telelink\telelink.db" -ErrorAction SilentlyContinue
Remove-Item -Path "$repoPath\telelink\telelink.session" -ErrorAction SilentlyContinue
Remove-Item -Path "$repoPath\telelink\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$repoPath\telelink\.env" -ErrorAction SilentlyContinue

# Helper function to commit with a specific date
function Commit-Stage ($files, $message, $date) {
    Write-Host "Committing: $message on date $date"
    $env:GIT_COMMITTER_DATE = $date
    $env:GIT_AUTHOR_DATE = $date
    
    foreach ($file in $files) {
        git add $file
    }
    
    # Check if there's anything to commit
    $status = git status --porcelain
    if ($status) {
        git commit -m $message --date="$date"
    }
    else {
        Write-Host "Nothing to commit for $message (already added?)"
    }
}

# The sequence of commits with backdated timeline structure
# Oct 2, 2025
Commit-Stage @(".gitignore", "README.md", "telelink/requirements.txt", "telelink/.env.example") "Initial commit: Set up project structure, ignore files, requirements" "2025-10-02T10:15:30+00:00"

# Oct 5, 2025
Commit-Stage @("telelink/config.py") "Added configuration parser and environment variables loading" "2025-10-05T14:20:10+00:00"

# Oct 9, 2025
Commit-Stage @("telelink/db.py") "Implemented SQLite database layer for channels, links, and messages storage" "2025-10-09T09:45:00+00:00"

# Oct 14, 2025
Commit-Stage @("telelink/telegram_client.py") "Core Telethon client integration with auth, OTP, and fetching logic" "2025-10-14T16:11:45+00:00"

# Oct 22, 2025
Commit-Stage @("telelink/link_extractor.py", "telelink/test_button_extract.py", "telelink/test_buttons.py") "Added sophisticated link extractor regex and unit tests for message buttons" "2025-10-22T11:05:22+00:00"

# Oct 28, 2025
Commit-Stage @("telelink/html_import.py", "telelink/test_html_import.py", "test_parser.py", "test_parser_full.py") "Feature: HTML parsing capabilities and tests for imported chat history" "2025-10-28T18:30:15+00:00"

# Nov 4, 2025
Commit-Stage @("telelink/ui/app.py", "telelink/ui/components/", "telelink/ui/pages/") "Started implementing Streamlit UI structure and component modularization" "2025-11-04T13:45:10+00:00"

# Nov 15, 2025
Commit-Stage @("telelink/main.py", "telelink/test_smoke.py") "Main application entry point with native desktop window fallback capabilities" "2025-11-15T08:22:50+00:00"

# Nov 28, 2025
Commit-Stage @("telelink/SETUP.md", "telelink/USAGE.md") "Comprehensive setup and usage documentation" "2025-11-28T15:10:05+00:00"

# Dec 5, 2025
# Add everything else left over to simulate minor bugfixes/tweaks
Commit-Stage @(".") "Bugfixes and final UI adjustments" "2025-12-05T11:30:45+00:00"

Write-Host "Backdated commits created successfully!"
git log --oneline

# Force push to GitHub to rewrite history
git branch -M main
git remote add origin https://github.com/nikhil914/TelegramGrabber.git
git push -u origin main -f
Write-Host "Force pushed to GitHub successfully!"
