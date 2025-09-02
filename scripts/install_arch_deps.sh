#!/bin/bash
# Install DRADIS dependencies on Arch Linux using pacman
# Run with: sudo ./install_arch_deps.sh

echo "Installing DRADIS dependencies on Arch Linux..."

# Available in Arch repos
ARCH_PACKAGES=(
    "python-requests"
    "python-feedparser"
    "python-beautifulsoup4"
    "python-dotenv"
    "python-pypdf"         # Note: Using pypdf instead of PyPDF2
    "python-email-validator"
    "python-numpy"
)

echo "Installing packages from Arch repositories..."
pacman -S --needed "${ARCH_PACKAGES[@]}"

# Packages not available in Arch repos - need pip
PIP_PACKAGES=(
    "google-generativeai"
    "arxiv"
    "schedule"
)

echo ""
echo "The following packages are not available in Arch repos and need to be installed via pip:"
for pkg in "${PIP_PACKAGES[@]}"; do
    echo "  - $pkg"
done

echo ""
echo "You can install them with:"
echo "pip install --user ${PIP_PACKAGES[*]}"
echo ""
echo "Or if you prefer system-wide (as root):"
echo "pip install ${PIP_PACKAGES[*]}"

echo ""
echo "Arch package installation complete!"
echo "Don't forget to install the pip packages listed above."