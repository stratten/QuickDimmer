#!/bin/bash

# Auto Monitor Dimmer - Python Transparent Overlay Approach
# Uses Python tkinter to create transparent overlay windows that dim unfocused displays
# No interference with existing applications - creates dedicated overlay windows

# Configuration
OVERLAY_OPACITY=0.83     # 0.83 = 83% dark overlay to achieve 17% effective brightness
CHECK_INTERVAL=1        # seconds between checks

# Function to get the currently focused application and window
get_focused_app_and_window() {
    osascript -e '
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp
        try
            set frontWindow to first window of frontApp
            set {x, y} to position of frontWindow
            return appName & "|" & x & "," & y
        on error
            return appName & "|0,0"
        end try
    end tell'
}

# Global variables for display bounds caching
DISPLAY_BOUNDS_CACHED=""
MAIN_SCREEN_HEIGHT=""

# Function to cache display bounds (called once at startup)
cache_display_bounds() {
    echo "Caching display bounds to avoid repeated Python calls..." >&2
    DISPLAY_BOUNDS_CACHED=$(python3 -c "
import sys
import os

# Set environment to prevent dock registration
os.environ['LSUIElement'] = '1'

from Cocoa import NSScreen

try:
    screens = NSScreen.screens()
    
    # Find main screen height for coordinate conversion
    main_height = 0
    for screen in screens:
        device_description = screen.deviceDescription()
        display_id = device_description.get('NSScreenNumber', 1)
        if int(display_id) == 1:  # Main display
            main_height = screen.frame().size.height
            break
    
    print(f'MAIN_HEIGHT:{int(main_height)}')
    
    # Output all display bounds as integers
    for i, screen in enumerate(screens):
        frame = screen.frame()
        device_description = screen.deviceDescription()
        display_id = device_description.get('NSScreenNumber', i+1)
        
        left = int(frame.origin.x)
        right = int(frame.origin.x + frame.size.width)
        top = int(frame.origin.y)
        bottom = int(frame.origin.y + frame.size.height)
        
        print(f'DISPLAY:{int(display_id)}:{left}:{top}:{right}:{bottom}')
except Exception as e:
    print(f'ERROR:{e}', file=sys.stderr)
" 2>/dev/null)
    
    # Extract main screen height (already an integer)
    MAIN_SCREEN_HEIGHT=$(echo "$DISPLAY_BOUNDS_CACHED" | grep "^MAIN_HEIGHT:" | cut -d: -f2)
    
    echo "✓ Display bounds cached successfully" >&2
}

# Function to detect which display contains a window position (using cached bounds)
detect_display_for_position() {
    local x=$1
    local y=$2
    
    # Convert AppleScript coordinates to Cocoa coordinates using cached main height
    if [[ -n "$MAIN_SCREEN_HEIGHT" ]]; then
        local converted_y=$((MAIN_SCREEN_HEIGHT - y))
        echo "DEBUG: Converted AppleScript coords ($x, $y) to Cocoa coords ($x, $converted_y)" >&2
        y=$converted_y
    else
        echo "DEBUG: No cached main height, using original coords ($x, $y)" >&2
    fi
    
    echo "DEBUG: Testing point ($x, $y) against cached display bounds:" >&2
    
    # Test against cached display bounds (no Python process needed!)
    local found_display=1
    while IFS= read -r line; do
        if [[ "$line" =~ ^DISPLAY:([0-9]+):([^:]+):([^:]+):([^:]+):([^:]+)$ ]]; then
            local display_id="${BASH_REMATCH[1]}"
            local left="${BASH_REMATCH[2]}"
            local top="${BASH_REMATCH[3]}"
            local right="${BASH_REMATCH[4]}"
            local bottom="${BASH_REMATCH[5]}"
            
            echo "DEBUG: Display $display_id: bounds=($left, $top) to ($right, $bottom)" >&2
            
            # Check if point is within this display's bounds (using bash integer arithmetic)
            if (( x >= left && x < right && y >= top && y < bottom )); then
                echo "DEBUG: Point ($x, $y) is inside display $display_id" >&2
                found_display=$display_id
                break
            fi
        fi
    done <<< "$DISPLAY_BOUNDS_CACHED"
    
    if [[ $found_display -eq 1 ]] && [[ ! "$DISPLAY_BOUNDS_CACHED" =~ "Point ($x, $y) is inside display" ]]; then
        echo "DEBUG: Point ($x, $y) not found in any display, defaulting to 1" >&2
    fi
    
    echo $found_display
}

# Function to get all available displays with their real coordinates
get_available_displays() {
    # Use Python with Cocoa to get real display information
    if python3 -c "from Cocoa import NSScreen" &> /dev/null; then
        echo "🔍 Scanning for available displays using Cocoa..." >&2
        
                 python3 -c "
from Cocoa import NSScreen
import sys

try:
    screens = NSScreen.screens()
    display_ids = []
    
    print('  Available displays:', file=sys.stderr)
    for i, screen in enumerate(screens):
        frame = screen.frame()
        device_description = screen.deviceDescription()
        display_id = device_description.get('NSScreenNumber', i+1)
        
        print(f'    Display {int(display_id)}: {frame.size.width}x{frame.size.height} at ({frame.origin.x},{frame.origin.y})', file=sys.stderr)
        display_ids.append(int(display_id))
        print(int(display_id))
    
    print(f'🔍 Display scan complete. Found display IDs: {display_ids}', file=sys.stderr)
except Exception as e:
    print('Error getting displays:', e, file=sys.stderr)
    print(1)
"
    else
        echo "Cocoa not available - falling back to system_profiler" >&2
        # Fallback: parse system_profiler output for display IDs
        system_profiler SPDisplaysDataType -json 2>/dev/null | python3 -c "
import json
import sys

try:
    data = json.loads(sys.stdin.read())
    displays = data.get('SPDisplaysDataType', [])
    
    for item in displays:
        if 'spdisplays_ndrvs' in item:
            for display in item['spdisplays_ndrvs']:
                display_id = display.get('_spdisplays_displayID', '1')
                print(display_id)
except:
    print(1)
"
    fi
}

# Function to create overlay on a specific display using real coordinates
create_overlay() {
    local display_id=$1
    
    # Check if overlay already exists for this display
    if [[ -f "/tmp/overlay_${display_id}_process.pid" ]]; then
        local existing_pid=$(cat "/tmp/overlay_${display_id}_process.pid" 2>/dev/null)
        if ps -p "$existing_pid" > /dev/null 2>&1; then
            # Overlay already running for this display
            return 0
        else
            # Clean up stale PID file
            rm "/tmp/overlay_${display_id}_process.pid" 2>/dev/null
        fi
    fi
    
    echo "Creating overlay on display $display_id"
    
    # Get real display coordinates using Cocoa
    local display_info=$(python3 -c "
from Cocoa import NSScreen

try:
    target_display_id = $display_id
    screens = NSScreen.screens()
    
    for screen in screens:
        frame = screen.frame()
        device_description = screen.deviceDescription()
        display_id = device_description.get('NSScreenNumber', 1)
        
        if int(display_id) == target_display_id:
            # Output: x,y,width,height
            print(f'{frame.origin.x},{frame.origin.y},{frame.size.width},{frame.size.height}')
            break
    else:
        # Default fallback
        print('0,0,1920,1080')
except:
    print('0,0,1920,1080')
" 2>/dev/null)
    
    IFS=',' read -r x_pos y_pos screen_width screen_height <<< "$display_info"
    
    # Convert floating point numbers to integers for bash arithmetic
    x_pos=${x_pos%.*}
    y_pos=${y_pos%.*}
    screen_width=${screen_width%.*}
    screen_height=${screen_height%.*}
    
    # Adjust for menu bar on main display (y coordinate needs to account for Cocoa coordinate system)
    local adjusted_y=$y_pos
    if [[ $display_id -eq 1 ]]; then
        adjusted_y=25  # Account for menu bar
    fi
    
    echo "  Display $display_id coordinates: x=$x_pos, y=$adjusted_y, size=${screen_width}x${screen_height}"
    
    # Create native macOS overlay using PyObjC with real coordinates
    python3 -c "
import sys
import os
import signal
import time

# Set environment to prevent dock registration BEFORE importing Cocoa
os.environ['LSUIElement'] = '1'

try:
    from Cocoa import *
    from Foundation import *
except ImportError:
    print('PyObjC not available - falling back to simple overlay')
    # Simple fallback - just maintain a process for tracking
    pid = os.getpid()
    with open('/tmp/overlay_${display_id}_process.pid', 'w') as f:
        f.write(str(pid))
    
    def cleanup_handler(signum, frame):
        try:
            os.remove('/tmp/overlay_${display_id}_process.pid')
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)
    
    while True:
        time.sleep(1)

# Create native overlay window using Cocoa with real display coordinates
# Set activation policy FIRST to prevent any dock appearance
app = NSApplication.sharedApplication()
app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

# Create window using actual display coordinates
window_rect = NSMakeRect($x_pos, $adjusted_y, $screen_width, $((screen_height - (adjusted_y - y_pos))))
window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    window_rect,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    False
)

# Configure window for overlay
window.setLevel_(NSFloatingWindowLevel)  # Always on top
window.setOpaque_(False)  # Allow transparency
window.setAlphaValue_($OVERLAY_OPACITY)  # Set transparency
window.setBackgroundColor_(NSColor.blackColor())  # Black background
window.setIgnoresMouseEvents_(True)  # Click-through!
window.setAcceptsMouseMovedEvents_(False)
window.setHasShadow_(False)
window.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)  # Persist across all desktop spaces

# Show window
window.makeKeyAndOrderFront_(None)

# Save PID for cleanup
pid = os.getpid()
with open('/tmp/overlay_${display_id}_process.pid', 'w') as f:
    f.write(str(pid))

# Handle cleanup
def cleanup_handler(signum, frame):
    try:
        os.remove('/tmp/overlay_${display_id}_process.pid')
    except:
        pass
    window.close()
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup_handler)
signal.signal(signal.SIGINT, cleanup_handler)

# Run the application
try:
    app.run()
except KeyboardInterrupt:
    cleanup_handler(0, None)
" &
    
    # Store the Python process ID
    local python_pid=$!
    echo $python_pid > "/tmp/overlay_${display_id}_process.pid"
    
    sleep 0.5
    echo "✓ Successfully created overlay on display $display_id"
}

# Function to remove overlay from a specific display
remove_overlay() {
    local display_id=$1
    
    # Check if overlay exists
    if [[ ! -f "/tmp/overlay_${display_id}_process.pid" ]]; then
        return 0  # No overlay to remove
    fi
    
    echo "Removing overlay from display $display_id"
    
    # Get the process PID
    local process_pid=$(cat "/tmp/overlay_${display_id}_process.pid" 2>/dev/null)
    
    if [[ -n "$process_pid" ]] && ps -p "$process_pid" > /dev/null 2>&1; then
        # Send termination signal
        kill -TERM "$process_pid" 2>/dev/null
        sleep 0.1
        # Force kill if still running
        if ps -p "$process_pid" > /dev/null 2>&1; then
            kill -9 "$process_pid" 2>/dev/null
        fi
    fi
    
    # Remove PID file
    rm "/tmp/overlay_${display_id}_process.pid" 2>/dev/null
    
    echo "✓ Overlay removed from display $display_id"
}

# Function to remove all overlays (cleanup)
remove_all_overlays() {
    echo "Removing all overlays..."
    
    # Find and kill all overlay processes
    for pid_file in /tmp/overlay_*_process.pid; do
        if [[ -f "$pid_file" ]]; then
            local process_pid=$(cat "$pid_file" 2>/dev/null)
            if [[ -n "$process_pid" ]] && ps -p "$process_pid" > /dev/null 2>&1; then
                kill -TERM "$process_pid" 2>/dev/null
                sleep 0.1
                kill -9 "$process_pid" 2>/dev/null
            fi
            rm "$pid_file" 2>/dev/null
        fi
    done
    
    # Clean up any remaining PID files
    rm -f /tmp/overlay_*.pid 2>/dev/null
    
    echo "✓ All overlays removed"
}

# Function to determine if a display is the built-in display
is_builtin_display() {
    local display_index=$1
    
    # Use m1ddc to identify built-in display (usually has null name and disp0 IO location)
    if command -v m1ddc &> /dev/null; then
        local display_info=$(m1ddc display list detailed 2>/dev/null | grep -A 10 "^\[$display_index\]")
        if [[ "$display_info" =~ "Product name:  (null)" ]] && [[ "$display_info" =~ "disp0@" ]]; then
            echo "true"
            return
        fi
    fi
    
    # Fallback: check if this is a MacBook and display 1
    if [[ $display_index -eq 1 ]]; then
        local model=$(system_profiler SPHardwareDataType | grep "Model Name" | cut -d: -f2 | xargs)
        if [[ "$model" == *"MacBook"* ]]; then
            echo "true"
        else
            echo "false"
        fi
    else
        echo "false"
    fi
}

# Function to get total display count
get_display_count() {
    system_profiler SPDisplaysDataType | grep -c "Resolution:"
}

# Function to handle disconnected displays
handle_disconnected_displays() {
    local -n current_displays_ref=$1
    local -n last_focused_display_ref=$2
    
    # Get current available displays
    local new_displays=($(get_available_displays))
    
    # Check if display list has changed
    if [[ "${current_displays_ref[*]}" != "${new_displays[*]}" ]]; then
        echo ""
        echo "🔌 Display configuration changed!"
        echo "Previous displays: ${current_displays_ref[*]}"
        echo "Current displays: ${new_displays[*]}"
        
        # Find displays that were disconnected
        local disconnected_displays=()
        for old_display in "${current_displays_ref[@]}"; do
            local found=false
            for new_display in "${new_displays[@]}"; do
                if [[ "$old_display" == "$new_display" ]]; then
                    found=true
                    break
                fi
            done
            if [[ "$found" == false ]]; then
                disconnected_displays+=("$old_display")
            fi
        done
        
        # Clean up overlays for disconnected displays
        if [[ ${#disconnected_displays[@]} -gt 0 ]]; then
            echo "🔌 Cleaning up overlays for disconnected displays: ${disconnected_displays[*]}"
            for display_id in "${disconnected_displays[@]}"; do
                echo "🧹 Removing overlay from disconnected display $display_id"
                remove_overlay $display_id
            done
        fi
        
        # Check if the currently focused display was disconnected
        local focused_display_disconnected=false
        for disconnected_display in "${disconnected_displays[@]}"; do
            if [[ "$disconnected_display" == "$last_focused_display_ref" ]]; then
                focused_display_disconnected=true
                break
            fi
        done
        
        # If focused display was disconnected, reset to primary display
        if [[ "$focused_display_disconnected" == true ]]; then
            echo "⚠️  Currently focused display $last_focused_display_ref was disconnected"
            if [[ ${#new_displays[@]} -gt 0 ]]; then
                last_focused_display_ref=${new_displays[0]}
                echo "🔄 Switching focus to display $last_focused_display_ref"
            else
                echo "❌ No displays remaining!"
                return 1
            fi
        fi
        
        # Update the available displays list
        current_displays_ref=("${new_displays[@]}")
        
        # Recache display bounds since configuration changed
        echo "🔄 Recaching display bounds..."
        cache_display_bounds
        
        echo "✅ Display configuration updated"
        echo ""
        
        # Return 1 to indicate display list changed (for caller to handle)
        return 1
    fi
    
    # No change in display configuration
    return 0
}

# Main monitoring function
monitor_and_dim() {
    local last_focused_display=0
    local available_displays=($(get_available_displays))
    local display_check_counter=0
    local display_check_interval=10  # Check for display changes every 10 cycles
    
    echo "=================== AUTO MONITOR DIMMER ==================="
    echo "Found ${#available_displays[@]} total displays"
    echo "Available displays: ${available_displays[*]}"
    echo "Focused display stays clear, others dimmed to 30% brightness"
    echo "Native Cocoa overlays - no app interference, click-through enabled"
    echo "Monitors display disconnection and automatically cleans up overlays"
    echo "Press Ctrl+C to stop and remove all overlays"
    echo "==========================================================="
    
    if [[ ${#available_displays[@]} -eq 0 ]]; then
        echo "❌ No displays found. Cannot proceed."
        return 1
    fi
    
    # Cache display bounds once at startup to avoid repeated Python calls
    cache_display_bounds
    
    while true; do
        # Periodically check for display changes (every 10 seconds by default)
        if [[ $display_check_counter -ge $display_check_interval ]]; then
            display_check_counter=0
            
            # Check for disconnected displays
            if ! handle_disconnected_displays available_displays last_focused_display; then
                # Display configuration changed
                if [[ ${#available_displays[@]} -eq 0 ]]; then
                    echo "❌ All displays disconnected. Exiting."
                    break
                fi
                
                # Force a focus check since display configuration changed
                last_focused_display=0
                echo "🔄 Forcing focus recheck due to display configuration change"
            fi
        fi
        
        # Get currently focused app and window position
        local app_info=$(get_focused_app_and_window)
        IFS='|' read -r current_app window_pos <<< "$app_info"
        IFS=',' read -r win_x win_y <<< "$window_pos"
        
        # Debug: Show coordinates being tested
        echo "DEBUG: Testing coordinates ($win_x, $win_y) for app: $current_app"
        
        # Determine which display has focus
        local current_display=$(detect_display_for_position $win_x $win_y)
        
        # Debug: Show detection result
        echo "DEBUG: Detected display: $current_display"
        
        # Validate that the detected display is still available
        local display_found=false
        for available_display in "${available_displays[@]}"; do
            if [[ "$current_display" == "$available_display" ]]; then
                display_found=true
                break
            fi
        done
        
        # If detected display is not available, default to first available display
        if [[ "$display_found" == false ]]; then
            echo "⚠️  Detected display $current_display is not available. Using first available display."
            current_display=${available_displays[0]}
        fi
        
        # Only update if display focus changed
        if [[ "$current_display" != "$last_focused_display" ]]; then
            echo ""
            echo "$(date '+%H:%M:%S') - Focus changed: $current_app on display $current_display (window at $win_x,$win_y)"
            
            # Manage overlays for all available displays
            for display_id in "${available_displays[@]}"; do
                if [[ $display_id -eq $current_display ]]; then
                    # This display has focus - remove overlay
                    echo "🔆 Display $display_id: FOCUSED - removing overlay"
                    remove_overlay $display_id
                else
                    # This display is not focused - add overlay
                    echo "🔅 Display $display_id: unfocused - creating overlay"
                    create_overlay $display_id
                fi
            done
            
            last_focused_display=$current_display
        fi
        
        # Increment display check counter
        display_check_counter=$((display_check_counter + 1))
        
        sleep $CHECK_INTERVAL
    done
}

# Function to restore all displays (remove all overlays)
restore_all_displays() {
    echo ""
    echo "🔄 Removing all overlays..."
    
    remove_all_overlays
    
    echo "✅ All displays restored to normal"
}

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping monitor dimmer..."
    restore_all_displays
    exit 0
}

# Trap Ctrl+C for cleanup
trap cleanup INT

# Check dependencies
echo "Checking dependencies..."

if ! command -v osascript &> /dev/null; then
    echo "❌ AppleScript not available - this is required for overlay creation"
    echo "This should be available on all macOS systems"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found - this is required for display position detection and overlay creation"
    echo "Install with: brew install python3"
    exit 1
fi

# Check for PyObjC which is needed for native macOS overlays
if ! python3 -c "from Cocoa import NSApplication" &> /dev/null; then
    echo "⚠️  PyObjC not found - falling back to basic overlay tracking"
    echo "For better visual overlays, install with: pip3 install pyobjc"
    echo "Current implementation will track focus without visual dimming"
    echo ""
else
    echo "✅ PyObjC found - native overlay windows enabled"
fi

if command -v m1ddc &> /dev/null; then
    echo "✅ m1ddc found - will be used for display enumeration"
else
    echo "ℹ️  m1ddc not found - using system_profiler fallback for display detection"
    echo "  Install m1ddc for better display info: brew install m1ddc"
fi

echo "✅ Dependencies checked"
echo ""

# Test display detection
echo "Testing display detection..."
available_displays=($(get_available_displays))
if [[ ${#available_displays[@]} -gt 0 ]]; then
    echo "✅ Found displays: ${available_displays[*]}"
else
    echo "❌ No displays found"
    echo "Cannot proceed without display detection"
    exit 1
fi

echo ""
echo "🚀 Starting in 3 seconds..."
sleep 3

# Start the monitoring loop
monitor_and_dim