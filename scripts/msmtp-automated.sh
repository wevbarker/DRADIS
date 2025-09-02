#!/bin/bash
# MSMTP wrapper for automated DRADIS emails
# Uses GPG agent or cached credentials when available

export GPG_TTY=$(tty)
export GPG_AGENT_INFO

# Try to use gpg-agent if available
if pgrep gpg-agent > /dev/null; then
    # gpg-agent is running, try to use cached credentials
    exec /usr/bin/msmtp "$@"
else
    # No gpg-agent, try with batch mode and hope credentials are cached
    export GNUPGHOME="$HOME/.gnupg"
    exec /usr/bin/msmtp "$@"
fi