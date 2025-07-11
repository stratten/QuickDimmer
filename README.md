# QuickDimmer

**Monitor Focus Dimming Tool for macOS**

QuickDimmer automatically dims unfocused displays to help you focus on the active screen. Built with Python backend and Electron frontend for a native macOS experience.

## Features

✅ **Automatic Display Dimming** - Unfocused displays are automatically dimmed  
✅ **Real-time Focus Detection** - Instantly responds to window focus changes  
✅ **Adjustable Opacity** - Control dimming intensity with slider or presets  
✅ **Multi-Display Support** - Works with any number of connected displays  
✅ **Native macOS Integration** - System tray, keyboard shortcuts, and proper app behavior  
✅ **Professional UI** - High-contrast, anti-flat design with clear visual hierarchy  
✅ **Robust Architecture** - Separate Python backend with Electron frontend  

## Architecture

- **Python Backend**: Native macOS display management using PyObjC, HTTP/WebSocket API
- **Electron Frontend**: Modern desktop UI with real-time updates and settings management
- **Communication**: RESTful API + WebSocket for instant state synchronization

## Requirements

- **macOS 10.15+** (Catalina or later)
- **Python 3.11+** 
- **Node.js 16+** and **npm 8+**
- **Xcode Command Line Tools** (for PyObjC compilation)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd MonitorDimmer
```

### 2. Install Python Dependencies

```bash
cd backend
pip3 install -r requirements.txt
```

### 3. Install Node.js Dependencies

```bash
cd ../frontend
npm install
```

### 4. Run in Development Mode

```bash
npm run dev
```

This starts both the Python backend and Electron frontend automatically.

## Development Workflow

### Backend Only (Python)
```bash
cd backend
python3 main.py
```
Starts backend on `http://localhost:8080`

### Frontend Only (Electron)
```bash
cd frontend
npm run dev-frontend
```
Requires backend to be running separately.

### Both Together
```bash
cd frontend
npm run dev
```
Starts backend and frontend with automatic coordination.

## Building for Distribution

### Create macOS App Bundle
```bash
cd frontend
npm run build
```

### Create DMG Installer
```bash
npm run build-mac
```

Built applications will be in the `dist/` directory.

## Usage

### Basic Controls

- **Toggle Dimming**: Click the power button or use `Cmd+D`
- **Adjust Opacity**: Use the slider or preset buttons (Light/Medium/Dark)
- **View Status**: Check the status section for display and overlay information
- **Settings**: Click the arrow to expand advanced settings

### Keyboard Shortcuts

- `Cmd+D` - Toggle dimming on/off
- `Cmd+Shift+D` - Show/hide main window
- `Escape` - Dismiss error messages

### System Tray

QuickDimmer runs in the system tray with:
- Quick toggle for dimming
- Current status display
- Direct access to main window
- Quit option

## How It Works

1. **Focus Detection**: Uses AppleScript to detect the currently focused window and its position
2. **Display Mapping**: Converts window coordinates to determine which display has focus  
3. **Overlay Management**: Creates native macOS overlay windows on unfocused displays
4. **Real-time Updates**: WebSocket connection provides instant UI updates when focus changes

## Project Structure

```
QuickDimmer/
├── backend/                 # Python backend
│   ├── main.py             # Application entry point
│   ├── display_manager.py  # Native display/overlay management
│   ├── focus_detector.py   # Window focus detection
│   ├── api_server.py       # HTTP/WebSocket API
│   └── requirements.txt    # Python dependencies
├── frontend/               # Electron frontend  
│   ├── main.js            # Electron main process
│   ├── package.json       # Node.js configuration
│   └── renderer/          # UI implementation
│       ├── index.html     # Main interface
│       ├── styles.css     # Anti-flat design styling
│       └── app.js         # Frontend logic
└── dist/                  # Built applications
```

## Configuration

### Backend Settings
- **Host/Port**: Backend runs on `localhost:8080` by default
- **Opacity**: Default 70% dimming intensity
- **Polling Rate**: 500ms focus check interval

### Frontend Settings
- **Auto-hide**: Window hides after startup (configurable)
- **Start on Login**: Option to launch with macOS (in development)
- **Debug Mode**: Enhanced logging for troubleshooting

## Troubleshooting

### Python Backend Issues

**"PyObjC not available"**
```bash
pip3 install --upgrade pyobjc-framework-Cocoa
```

**"Permission denied for window detection"**
- Go to System Preferences → Security & Privacy → Privacy → Accessibility
- Add Terminal or your Python interpreter to allowed apps

**Backend won't start**
- Check Python version: `python3 --version` (need 3.11+)
- Install Xcode Command Line Tools: `xcode-select --install`

### Frontend Issues

**"Backend connection failed"**
- Ensure Python backend is running on port 8080
- Check firewall settings if connection is blocked

**App won't build**
- Verify Node.js version: `node --version` (need 16+)
- Clear node_modules: `rm -rf node_modules && npm install`

## Development Notes

### Code Style
- **Python**: PEP 8 compliant, async/await patterns
- **JavaScript**: ES6+, class-based architecture  
- **UI**: Anti-flat design principles with high contrast

### Performance
- **Single Python Process**: No subprocess spawning unlike the original bash script
- **Efficient WebSocket**: Real-time updates without polling overhead
- **Native Overlays**: Hardware-accelerated window compositing

### Testing
```bash
# Test Python backend
cd backend
python3 -m pytest

# Test individual components
python3 display_manager.py
python3 focus_detector.py
```

## Contributing

1. Follow the one-file-at-a-time development approach outlined in the user rules
2. Maintain anti-flat design principles in UI changes
3. Preserve existing comments and functionality unless explicitly modifying
4. Test on multiple display configurations

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by the original `monitor_dimmer.sh` script
- Built with PyObjC for native macOS integration
- Uses Electron for cross-platform desktop UI capabilities

---

**Version 1.0.0** - Complete rewrite from bash script to professional desktop application 