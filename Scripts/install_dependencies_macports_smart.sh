#!/bin/bash

# Photo Management Tool Dependencies Installer - MacPorts Smart Edition
# Checks for existing installations and only installs missing packages

set -e  # Exit on any error

echo "🚀 Photo Management Tool Dependencies Installer (MacPorts Smart)"
echo "=" * 70

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ This installer is designed for macOS only"
    exit 1
fi

# Check if MacPorts is installed
if ! command -v port >/dev/null 2>&1; then
    echo "❌ MacPorts not found. Please install MacPorts first:"
    echo "   https://www.macports.org/install.php"
    echo ""
    echo "   After installing MacPorts, run:"
    echo "   sudo port selfupdate"
    exit 1
fi

echo "✅ MacPorts found"

# Function to check if a port is installed
check_port_installed() {
    local port_name="$1"
    if port installed "$port_name" 2>/dev/null | grep -q "active"; then
        return 0  # installed
    else
        return 1  # not installed
    fi
}

# Function to install port if not already installed
install_port_if_needed() {
    local port_name="$1"
    local description="$2"
    
    if check_port_installed "$port_name"; then
        echo "✅ $description already installed: $port_name"
    else
        echo "📦 Installing $description: $port_name"
        sudo port install "$port_name"
    fi
}

# Function to check if Python package is available
check_python_package() {
    local package_name="$1"
    python3 -c "import $package_name" 2>/dev/null
}

# Update MacPorts (always do this)
echo "🔄 Updating MacPorts..."
sudo port selfupdate

# Install Python 3.11 and essential packages
echo ""
echo "🐍 Installing Python 3.11 and essential packages..."
install_port_if_needed "python311" "Python 3.11"
install_port_if_needed "py311-pip" "Python 3.11 pip"
install_port_if_needed "py311-pillow" "Python 3.11 Pillow"
install_port_if_needed "py311-numpy" "Python 3.11 NumPy"

# Set Python 3.11 as default (only if not already set)
echo ""
echo "🔗 Setting Python 3.11 as default..."
current_python=$(port select --show python3 2>/dev/null | grep "currently selected:" | awk '{print $3}' || echo "none")
if [[ "$current_python" != "python311" ]]; then
    echo "📝 Setting python3 selection to python311"
    sudo port select --set python3 python311
else
    echo "✅ Python 3.11 already set as default"
fi

current_pip=$(port select --show pip 2>/dev/null | grep "currently selected:" | awk '{print $3}' || echo "none")
if [[ "$current_pip" != "pip311" ]]; then
    echo "📝 Setting pip selection to pip311"
    sudo port select --set pip pip311
else
    echo "✅ pip311 already set as default"
fi

# Install image processing tools
echo ""
echo "🖼️ Installing image processing tools..."
install_port_if_needed "exiftool" "ExifTool"
install_port_if_needed "ImageMagick" "ImageMagick"

# Install RAW processing tools
echo ""
echo "📷 Installing RAW processing tools..."
install_port_if_needed "rawtherapee" "RawTherapee"

# Install video processing (optional but useful)
echo ""
echo "🎥 Installing video processing tools..."
install_port_if_needed "ffmpeg" "FFmpeg"

# Install face recognition dependencies (using correct OpenCV package name)
echo ""
echo "👥 Installing face recognition dependencies..."
install_port_if_needed "py311-opencv4" "OpenCV 4 for Python 3.11"
install_port_if_needed "py311-scikit-learn" "scikit-learn for Python 3.11"

# Install additional Python packages via pip (check first)
echo ""
echo "📦 Installing additional Python packages..."

if check_python_package "insightface"; then
    echo "✅ InsightFace already installed"
else
    echo "📦 Installing InsightFace..."
    python3 -m pip install --user insightface
fi

if check_python_package "onnxruntime"; then
    echo "✅ ONNXRuntime already installed"
else
    echo "📦 Installing ONNXRuntime..."
    python3 -m pip install --user onnxruntime
fi

# Create necessary directories
echo ""
echo "📁 Creating project directories..."
mkdir -p "thumbnails"
mkdir -p "HEIC Proxies" 
mkdir -p "RAW Proxies"
mkdir -p "JSON"

# Make scripts executable
echo "🔧 Setting script permissions..."
find Scripts -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
chmod +x *.py 2>/dev/null || true

# Test installations
echo ""
echo "🧪 Testing installations..."
test_passed=true

# Test ExifTool
if command -v exiftool >/dev/null 2>&1; then
    echo "✅ ExifTool: $(exiftool -ver)"
else
    echo "❌ ExifTool not found"
    test_passed=false
fi

# Test ImageMagick
if command -v magick >/dev/null 2>&1; then
    echo "✅ ImageMagick: $(magick -version | head -1)"
else
    echo "❌ ImageMagick not found"
    test_passed=false
fi

# Test RawTherapee
if command -v rawtherapee-cli >/dev/null 2>&1; then
    echo "✅ RawTherapee CLI: Available"
else
    echo "❌ RawTherapee CLI not found"
    test_passed=false
fi

# Test Python packages
echo "🐍 Testing Python packages..."
if python3 -c "import PIL; print(f'✅ Pillow: {PIL.__version__}')" 2>/dev/null; then
    :
else
    echo "❌ Pillow not available"
    test_passed=false
fi

if python3 -c "import cv2; print(f'✅ OpenCV: {cv2.__version__}')" 2>/dev/null; then
    :
else
    echo "❌ OpenCV not available"
    test_passed=false
fi

if python3 -c "import insightface; print('✅ InsightFace: Available')" 2>/dev/null; then
    :
else
    echo "❌ InsightFace not available"
    test_passed=false
fi

if python3 -c "import numpy; print(f'✅ NumPy: {numpy.__version__}')" 2>/dev/null; then
    :
else
    echo "❌ NumPy not available"
    test_passed=false
fi

echo ""
if $test_passed; then
    echo "🎉 All dependencies installed successfully!"
    echo ""
    echo "💡 Next steps:"
    echo "   1. Run: python3 photo_manager.py"
    echo "   2. Extract metadata from your photo library (option 1)"
    echo "   3. Generate thumbnails (option 5)" 
    echo "   4. Generate HEIC proxies (option 6)"
    echo "   5. Generate RAW proxies (option 7)"
    echo "   6. Set up face recognition (option 14)"
    echo ""
    echo "📚 RAW Processing Features:"
    echo "   • Automatic RAW proxy generation during metadata extraction"
    echo "   • Support for CR2, NEF, ARW, DNG, RAF files"
    echo "   • Custom processing settings configurable"
    echo "   • Proxies stored in 'RAW Proxies/' directory"
    echo ""
    echo "🔧 RAW Processing Configuration:"
    echo "   • Default settings applied automatically"
    echo "   • Custom LUTs and presets can be configured"
    echo "   • Regeneration available for picked images"
else
    echo "❌ Some dependencies failed to install. Please check the errors above."
    echo "   You may need to run this script again or install missing packages manually."
    exit 1
fi