#!/bin/bash
# DRADIS Privacy Scanner
# Clones the GitHub repository and scans for personal information leaks
# If no personal info is found, cleans up automatically

set -e

# Configuration
REPO_URL="https://github.com/wevbarker/DRADIS.git"
CLONE_DIR="$HOME/Downloads/DRADIS-privacy-scan"
LOG_FILE="/tmp/privacy_scan.log"

# Personal information patterns to search for
PERSONAL_PATTERNS=(
    "barker@fzu.cz"
    "Will Barker"
    "wjb-iv"
    "AIzaSy"  # Gemini API key prefix
    "sk-"     # OpenAI API key prefix
    "system-green"
    "system-orange"
    "limba"   # Jump host
    "DRADIS Configuration - Will Barker"
    "barker@"
    "@fzu.cz"
    "/home/barker"
    "USER_EMAIL="
    "GEMINI_API_KEY="
    "SMTP_USER="
    "SMTP_PASSWORD="
)

# Sensitive file extensions and names to check
SENSITIVE_FILES=(
    ".env"
    ".env.*"
    "*.key"
    "*.pem"
    "*.p12"
    "*.pfx"
    "id_rsa"
    "id_ed25519"
    "known_hosts"
    "config"
    "credentials"
    "*.db"
    "*.sqlite"
    "*.sqlite3"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $1" | tee -a "$LOG_FILE"
}

# Print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}" | tee -a "$LOG_FILE"
}

print_status "$BLUE" "=== DRADIS PRIVACY SCANNER ==="
print_status "$BLUE" "Starting comprehensive privacy scan of GitHub repository"
log "Repository: $REPO_URL"
log "Clone directory: $CLONE_DIR"
log "Log file: $LOG_FILE"

# Clean up any existing clone
if [ -d "$CLONE_DIR" ]; then
    print_status "$YELLOW" "Removing existing clone directory..."
    rm -rf "$CLONE_DIR"
fi

# Clone the repository
print_status "$BLUE" "Cloning repository from GitHub..."
if git clone "$REPO_URL" "$CLONE_DIR" >> "$LOG_FILE" 2>&1; then
    log "Repository cloned successfully"
else
    print_status "$RED" "Failed to clone repository"
    exit 1
fi

cd "$CLONE_DIR"

# Initialize scan results
PRIVACY_VIOLATIONS=0
VIOLATION_DETAILS=""

print_status "$BLUE" "Starting comprehensive privacy scan..."

# 1. Search for personal information patterns in all files
print_status "$YELLOW" "Scanning for personal information patterns..."
for pattern in "${PERSONAL_PATTERNS[@]}"; do
    log "Searching for pattern: $pattern"
    
    # Search in current files (case insensitive)
    matches=$(grep -r -i -n "$pattern" . --exclude-dir=.git 2>/dev/null || true)
    if [ -n "$matches" ]; then
        PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
        VIOLATION_DETAILS+="PATTERN FOUND: $pattern\n$matches\n\n"
        print_status "$RED" "  ❌ FOUND: $pattern"
    else
        log "  ✅ Clean: $pattern"
    fi
    
    # Search in git history
    git_matches=$(git log --all -S "$pattern" --oneline 2>/dev/null || true)
    if [ -n "$git_matches" ]; then
        PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
        VIOLATION_DETAILS+="PATTERN IN GIT HISTORY: $pattern\n$git_matches\n\n"
        print_status "$RED" "  ❌ FOUND IN HISTORY: $pattern"
    fi
done

# 2. Check for sensitive files
print_status "$YELLOW" "Scanning for sensitive files..."
for file_pattern in "${SENSITIVE_FILES[@]}"; do
    log "Searching for file pattern: $file_pattern"
    
    # Find files matching pattern
    matches=$(find . -name "$file_pattern" -type f 2>/dev/null | grep -v ".git/" || true)
    if [ -n "$matches" ]; then
        PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
        VIOLATION_DETAILS+="SENSITIVE FILE FOUND: $file_pattern\n$matches\n\n"
        print_status "$RED" "  ❌ FOUND FILE: $file_pattern"
        
        # Show content preview for small text files
        while read -r file; do
            if [ -f "$file" ] && [ $(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0) -lt 1000 ]; then
                file_type=$(file -b "$file" 2>/dev/null || echo "unknown")
                if [[ "$file_type" == *"text"* ]]; then
                    VIOLATION_DETAILS+="CONTENT PREVIEW ($file):\n$(head -5 "$file" 2>/dev/null || echo "Cannot read file")\n\n"
                fi
            fi
        done <<< "$matches"
    else
        log "  ✅ Clean: $file_pattern"
    fi
done

# 3. Search for hardcoded IPs, URLs, and paths
print_status "$YELLOW" "Scanning for hardcoded network information..."
NETWORK_PATTERNS=(
    "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"  # IP addresses
    "ssh://.*@"
    "ftp://.*@"
    "sftp://.*@"
    "\/home\/[a-z]+"
    "\/Users\/[a-z]+"
)

for pattern in "${NETWORK_PATTERNS[@]}"; do
    log "Searching for network pattern: $pattern"
    matches=$(grep -r -E "$pattern" . --exclude-dir=.git 2>/dev/null || true)
    if [ -n "$matches" ]; then
        # Filter out common false positives
        filtered_matches=$(echo "$matches" | grep -v "0.0.0.0\|127.0.0.1\|localhost\|example.com" || true)
        if [ -n "$filtered_matches" ]; then
            PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
            VIOLATION_DETAILS+="NETWORK INFO FOUND: $pattern\n$filtered_matches\n\n"
            print_status "$RED" "  ❌ FOUND NETWORK INFO: $pattern"
        fi
    else
        log "  ✅ Clean: $pattern"
    fi
done

# 4. Check git configuration and remotes
print_status "$YELLOW" "Checking git configuration..."
git_user=$(git config user.name 2>/dev/null || echo "")
git_email=$(git config user.email 2>/dev/null || echo "")
git_remotes=$(git remote -v 2>/dev/null || echo "")

if [[ "$git_user" == *"Barker"* ]] || [[ "$git_email" == *"barker"* ]] || [[ "$git_email" == *"fzu.cz"* ]]; then
    PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
    VIOLATION_DETAILS+="GIT CONFIG CONTAINS PERSONAL INFO:\nUser: $git_user\nEmail: $git_email\n\n"
    print_status "$RED" "  ❌ FOUND PERSONAL INFO IN GIT CONFIG"
fi

# 5. Scan commit messages and author information
print_status "$YELLOW" "Scanning commit history..."
personal_commits=$(git log --all --pretty=format:"%H %an %ae %s" | grep -i -E "(barker|will|fzu\.cz)" || true)
if [ -n "$personal_commits" ]; then
    PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
    VIOLATION_DETAILS+="PERSONAL INFO IN COMMITS:\n$personal_commits\n\n"
    print_status "$RED" "  ❌ FOUND PERSONAL INFO IN COMMIT HISTORY"
fi

# 6. Check for API keys or tokens in diffs
print_status "$YELLOW" "Scanning for API keys in git diffs..."
api_key_diffs=$(git log --all -p | grep -E "(api[_-]?key|token|secret)" -i || true)
if [ -n "$api_key_diffs" ]; then
    PRIVACY_VIOLATIONS=$((PRIVACY_VIOLATIONS + 1))
    VIOLATION_DETAILS+="API KEYS IN DIFFS:\n$api_key_diffs\n\n"
    print_status "$RED" "  ❌ FOUND API KEYS IN GIT DIFFS"
fi

# Results summary
print_status "$BLUE" "=== PRIVACY SCAN RESULTS ==="
if [ "$PRIVACY_VIOLATIONS" -eq 0 ]; then
    print_status "$GREEN" "✅ CLEAN: No personal information found in repository"
    print_status "$GREEN" "✅ Repository appears safe for public sharing"
    
    # Clean up the cloned repository
    cd "$HOME"
    print_status "$BLUE" "Cleaning up cloned repository..."
    rm -rf "$CLONE_DIR"
    log "Cloned repository removed from Downloads"
    
    print_status "$GREEN" "Privacy scan completed successfully - repository is clean!"
    
else
    print_status "$RED" "❌ PRIVACY VIOLATIONS FOUND: $PRIVACY_VIOLATIONS issues detected"
    print_status "$RED" "❌ DO NOT make this repository public without addressing these issues"
    
    # Save detailed report
    REPORT_FILE="$HOME/Downloads/DRADIS-privacy-violations.txt"
    echo "DRADIS Privacy Scan Report" > "$REPORT_FILE"
    echo "Generated: $(date)" >> "$REPORT_FILE"
    echo "Repository: $REPO_URL" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "VIOLATIONS FOUND: $PRIVACY_VIOLATIONS" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo -e "$VIOLATION_DETAILS" >> "$REPORT_FILE"
    
    print_status "$YELLOW" "Detailed report saved to: $REPORT_FILE"
    print_status "$YELLOW" "Cloned repository preserved at: $CLONE_DIR (for investigation)"
    
    echo ""
    print_status "$RED" "SUMMARY OF VIOLATIONS:"
    echo -e "$VIOLATION_DETAILS" | head -20
fi

log "Privacy scan completed with $PRIVACY_VIOLATIONS violations"
print_status "$BLUE" "Log file: $LOG_FILE"