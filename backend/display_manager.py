"""
QuickDimmer Display Manager - Core Display Logic
Handles overlay window creation, management, and native macOS display integration
"""
import os
import sys
import subprocess
import signal
import time
from typing import Dict, Tuple, Optional

try:
    from Cocoa import NSScreen
    PYOBJC_AVAILABLE = True
except ImportError:
    print("Warning: PyObjC not available. Install with: pip install pyobjc-framework-Cocoa")
    PYOBJC_AVAILABLE = False


class DisplayManager:
    """Manages display overlays and dimming functionality using separate processes like the shell script"""
    
    def __init__(self):
        if not PYOBJC_AVAILABLE:
            raise RuntimeError("PyObjC is required for macOS display management")
        
        # State management
        self.overlay_processes: Dict[int, int] = {}  # display_id: process_pid
        self.display_bounds: Dict[int, Tuple[int, int, int, int]] = {}  # display_id: (x, y, width, height)
        self.current_focused_display: Optional[int] = None
        
        # Per-monitor settings
        self.monitor_opacity: Dict[int, float] = {}  # display_id: opacity
        self.monitor_enabled: Dict[int, bool] = {}   # display_id: enabled
        
        # Default settings for new monitors
        self.default_opacity: float = 0.83
        self.default_enabled: bool = True
        
        print("DisplayManager initialized with PyObjC", flush=True)
    
    def cache_display_info(self):
        """Cache display bounds information at startup"""
        try:
            screens = NSScreen.screens()
            print(f"Detected {len(screens)} screen(s)")
            
            for i, screen in enumerate(screens):
                frame = screen.frame()
                device_desc = screen.deviceDescription()
                
                # Use screen index as display_id if NSScreenNumber not available
                display_id = device_desc.get('NSScreenNumber', i + 1)
                
                # Store bounds (x, y, width, height)
                self.display_bounds[display_id] = (
                    int(frame.origin.x),
                    int(frame.origin.y), 
                    int(frame.size.width),
                    int(frame.size.height)
                )
                
                # Initialize per-monitor settings with defaults if not already set
                if display_id not in self.monitor_opacity:
                    self.monitor_opacity[display_id] = self.default_opacity
                if display_id not in self.monitor_enabled:
                    self.monitor_enabled[display_id] = self.default_enabled
                
                print(f"Display {display_id}: {self.display_bounds[display_id]}")
                
        except Exception as e:
            print(f"Error caching display info: {e}")
            # Fallback to main screen only
            main_screen = NSScreen.mainScreen()
            if main_screen:
                frame = main_screen.frame()
                self.display_bounds[1] = (
                    int(frame.origin.x),
                    int(frame.origin.y),
                    int(frame.size.width),
                    int(frame.size.height)
                )
                # Initialize settings for main display
                self.monitor_opacity[1] = self.default_opacity
                self.monitor_enabled[1] = self.default_enabled
    
    def create_overlay(self, display_id: int) -> bool:
        """Create overlay window for specific display using simple background process like shell script"""
        if display_id in self.overlay_processes:
            # Check if process is still running
            try:
                os.kill(self.overlay_processes[display_id], 0)
                return True  # Process exists and is running
            except OSError:
                # Process is dead, remove it
                del self.overlay_processes[display_id]
        
        if display_id not in self.display_bounds:
            print(f"Warning: Display {display_id} not found in bounds cache")
            return False
        
        try:
            x, y, width, height = self.display_bounds[display_id]
            # Get per-monitor opacity setting
            opacity = self.monitor_opacity.get(display_id, self.default_opacity)
            print(f"Creating overlay for display {display_id} with opacity {opacity}")
            
            # Adjust for menu bar on main display (like shell script does)
            adjusted_y = y
            if display_id == 1:
                adjusted_y = 25  # Account for menu bar
            
            # Create properly formatted overlay script like the shell script does  
            overlay_script = f"""
import sys
import os
import signal
import time

print(f"OVERLAY_DEBUG: Starting overlay script for display {display_id} at {{time.time():.3f}}", flush=True)

# Set environment to prevent dock registration BEFORE importing Cocoa
os.environ['LSUIElement'] = '1'
print(f"OVERLAY_DEBUG: Set LSUIElement at {{time.time():.3f}}", flush=True)

try:
    print(f"OVERLAY_DEBUG: About to import Cocoa at {{time.time():.3f}}", flush=True)
    from Cocoa import *
    print(f"OVERLAY_DEBUG: Imported Cocoa at {{time.time():.3f}}", flush=True)
    from Foundation import *
    print(f"OVERLAY_DEBUG: Imported Foundation at {{time.time():.3f}}", flush=True)
except ImportError as e:
    print(f"OVERLAY_DEBUG: Import failed at {{time.time():.3f}}: {{e}}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"OVERLAY_DEBUG: Unexpected error during import at {{time.time():.3f}}: {{e}}", flush=True)
    sys.exit(1)

print(f"OVERLAY_DEBUG: Starting NSApplication at {{time.time():.3f}}", flush=True)

try:
    # Create native overlay window using Cocoa with real display coordinates
    # Set activation policy FIRST to prevent any dock appearance
    app = NSApplication.sharedApplication()
    print(f"OVERLAY_DEBUG: Got NSApplication at {{time.time():.3f}}", flush=True)
    
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    print(f"OVERLAY_DEBUG: Set activation policy at {{time.time():.3f}}", flush=True)

    # Create window using actual display coordinates  
    window_rect = NSMakeRect({x}, {adjusted_y}, {width}, {height-(adjusted_y-y)})
    print(f"OVERLAY_DEBUG: Created window rect at {{time.time():.3f}}", flush=True)
    
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        window_rect,
        NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered,
        False
    )
    print(f"OVERLAY_DEBUG: Created window at {{time.time():.3f}}", flush=True)

    # Configure window for overlay
    window.setLevel_(NSFloatingWindowLevel)  # Always on top
    window.setOpaque_(False)  # Allow transparency
    window.setAlphaValue_({opacity})  # Set transparency
    window.setBackgroundColor_(NSColor.blackColor())  # Black background
    window.setIgnoresMouseEvents_(True)  # Click-through!
    window.setAcceptsMouseMovedEvents_(False)
    window.setHasShadow_(False)
    window.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)  # Persist across all desktop spaces
    print(f"OVERLAY_DEBUG: Configured window at {{time.time():.3f}}", flush=True)

    # Show window
    window.makeKeyAndOrderFront_(None)
    print(f"OVERLAY_DEBUG: Showed window at {{time.time():.3f}}", flush=True)

except Exception as e:
    print(f"OVERLAY_DEBUG: Error creating window at {{time.time():.3f}}: {{e}}", flush=True)
    sys.exit(1)

# Save PID for cleanup
try:
    pid = os.getpid()
    with open('/tmp/overlay_{display_id}_process.pid', 'w') as f:
        f.write(str(pid))
    print(f"OVERLAY_DEBUG: Saved PID at {{time.time():.3f}}", flush=True)
except Exception as e:
    print(f"OVERLAY_DEBUG: Error saving PID at {{time.time():.3f}}: {{e}}", flush=True)

# Handle cleanup
def cleanup_handler(signum, frame):
    try:
        os.remove('/tmp/overlay_{display_id}_process.pid')
    except:
        pass
    try:
        window.close()
    except:
        pass
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup_handler)
signal.signal(signal.SIGINT, cleanup_handler)
print(f"OVERLAY_DEBUG: Set signal handlers at {{time.time():.3f}}", flush=True)

# Run the application
try:
    print(f"OVERLAY_DEBUG: About to call app.run() at {{time.time():.3f}}", flush=True)
    app.run()
except KeyboardInterrupt:
    cleanup_handler(0, None)
except Exception as e:
    print(f"OVERLAY_DEBUG: Error in app.run() at {{time.time():.3f}}: {{e}}", flush=True)
    sys.exit(1)
""".strip()
            
            # Record start time for performance measurement
            start_time = time.time()
            print(f"TIMING: Starting overlay creation for display {display_id} at {start_time:.3f}")
            
            # Use simple background process execution like shell script does
            process = subprocess.Popen(
                ['/opt/homebrew/bin/python3', '-c', overlay_script],  # Use Homebrew python3 like shell script
                stdout=subprocess.PIPE,  # Capture debug output
                stderr=subprocess.PIPE,  # Capture debug output
                preexec_fn=os.setsid       # Create new process group for clean termination
            )
            
            # Store process PID (like shell script does)
            self.overlay_processes[display_id] = process.pid
            
            # Give process a moment to start and print debug info
            time.sleep(0.2)
            
            # Try to read any initial debug output (non-blocking)
            try:
                import select
                import fcntl
                
                # Make stdout non-blocking
                fd = process.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
                # Read any available output
                if select.select([process.stdout], [], [], 0.1)[0]:
                    try:
                        output = process.stdout.read(1024)
                        if output:
                            print(f"Overlay {display_id} debug: {output.decode()}")
                    except BlockingIOError:
                        pass
            except Exception as e:
                print(f"Error reading debug output: {e}")
            
            # Simple delay like shell script uses (no complex monitoring)
            time.sleep(0.1)  # Even shorter than shell script's 0.5s
            
            elapsed = time.time() - start_time
            print(f"TIMING: Overlay for display {display_id} started in {elapsed:.3f}s")
            
            return True
            
        except Exception as e:
            print(f"Error creating overlay for display {display_id}: {e}")
            return False
    
    def remove_overlay(self, display_id: int) -> bool:
        """Remove overlay from specific display"""
        if display_id not in self.overlay_processes:
            return True  # Already removed
        
        try:
            process_pid = self.overlay_processes[display_id]
            
            # Send termination signal (faster cleanup)
            try:
                # Kill the entire process group (like shell script does)
                os.killpg(os.getpgid(process_pid), signal.SIGTERM)
                time.sleep(0.01)  # Minimal delay
                # Force kill if still running
                try:
                    os.killpg(os.getpgid(process_pid), signal.SIGKILL)
                except OSError:
                    pass  # Process already dead
            except OSError:
                pass  # Process already dead
            
            # Remove from tracking
            del self.overlay_processes[display_id]
            
            # Clean up PID file
            try:
                os.remove(f'/tmp/overlay_{display_id}_process.pid')
            except:
                pass
            
            print(f"Removed overlay from display {display_id}")
            return True
            
        except Exception as e:
            print(f"Error removing overlay from display {display_id}: {e}")
            return False
    
    def update_overlays(self, focused_display_id: int):
        """Update overlays based on focused display"""
        try:
            for display_id in self.display_bounds:
                if display_id == focused_display_id:
                    # Remove overlay from focused display
                    self.remove_overlay(display_id)
                else:
                    # Add overlay to non-focused displays if enabled for that display
                    if self.monitor_enabled.get(display_id, self.default_enabled):
                        self.create_overlay(display_id)
                    else:
                        self.remove_overlay(display_id)
                        
        except Exception as e:
            print(f"Error updating overlays: {e}")
    
    def set_opacity(self, opacity: float, display_id: Optional[int] = None) -> bool:
        """Update overlay opacity - can set for specific display or all displays"""
        if not 0.0 <= opacity <= 1.0:
            print(f"Invalid opacity value: {opacity}")
            return False
        
        try:
            if display_id is not None:
                # Set opacity for specific display
                if display_id not in self.display_bounds:
                    print(f"Display {display_id} not found")
                    return False
                
                old_opacity = self.monitor_opacity.get(display_id, self.default_opacity)
                self.monitor_opacity[display_id] = opacity
                
                # Recreate overlay if it exists
                if display_id in self.overlay_processes:
                    self.remove_overlay(display_id)
                    self.create_overlay(display_id)
                
                print(f"Updated opacity for display {display_id} from {old_opacity} to {opacity}")
                return True
            else:
                # Set opacity for all displays
                old_opacity = self.default_opacity
                self.default_opacity = opacity
                
                # Update all existing displays
                for display_id in self.display_bounds:
                    self.monitor_opacity[display_id] = opacity
                
                # Recreate existing overlays with new opacity
                active_displays = list(self.overlay_processes.keys())
                for display_id in active_displays:
                    self.remove_overlay(display_id)
                    self.create_overlay(display_id)
                
                print(f"Updated opacity for all displays from {old_opacity} to {opacity}")
                return True
                
        except Exception as e:
            print(f"Error setting opacity: {e}")
            return False
    
    def set_monitor_enabled(self, display_id: int, enabled: bool) -> bool:
        """Enable/disable dimming for a specific monitor"""
        try:
            if display_id not in self.display_bounds:
                print(f"Display {display_id} not found")
                return False
                
            old_enabled = self.monitor_enabled.get(display_id, self.default_enabled)
            self.monitor_enabled[display_id] = enabled
            
            if not enabled:
                # Remove overlay when disabled
                self.remove_overlay(display_id)
            else:
                # Add overlay when enabled (if not focused)
                if display_id != self.current_focused_display:
                    self.create_overlay(display_id)
            
            print(f"Display {display_id} dimming {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            print(f"Error setting monitor enabled state: {e}")
            return False
    
    def get_monitor_settings(self, display_id: int) -> dict:
        """Get settings for a specific monitor"""
        return {
            'display_id': display_id,
            'opacity': self.monitor_opacity.get(display_id, self.default_opacity),
            'enabled': self.monitor_enabled.get(display_id, self.default_enabled),
            'has_overlay': display_id in self.overlay_processes,
            'is_focused': display_id == self.current_focused_display,
            'bounds': self.display_bounds.get(display_id)
        }
    
    def get_all_monitor_settings(self) -> dict:
        """Get settings for all monitors"""
        monitors = {}
        for display_id in self.display_bounds:
            monitors[display_id] = self.get_monitor_settings(display_id)
        return monitors
    
    def toggle_enabled(self) -> bool:
        """Toggle dimming on/off"""
        try:
            self.default_enabled = not self.default_enabled
            
            if not self.default_enabled:
                # Remove all overlays when disabled
                for display_id in list(self.overlay_processes.keys()):
                    self.remove_overlay(display_id)
                print("Dimming disabled")
            else:
                # Re-apply overlays based on current focus when enabled
                if self.current_focused_display is not None:
                    self.update_overlays(self.current_focused_display)
                print("Dimming enabled")
            
            return self.default_enabled
            
        except Exception as e:
            print(f"Error toggling enabled state: {e}")
            return self.default_enabled
    
    def get_status(self) -> dict:
        """Get current status information"""
        return {
            'enabled': self.default_enabled,
            'opacity': self.default_opacity,
            'focused_display': self.current_focused_display,
            'displays': len(self.display_bounds),
            'active_overlays': len(self.overlay_processes),
            'display_bounds': self.display_bounds,
            'monitor_settings': self.get_all_monitor_settings(),
            'defaults': {
                'opacity': self.default_opacity,
                'enabled': self.default_enabled
            }
        }
    
    def stop_monitoring(self):
        """Stop monitoring and cleanup all overlays"""
        try:
            print("Cleaning up display manager...")
            
            # Remove all overlays
            for display_id in list(self.overlay_processes.keys()):
                self.remove_overlay(display_id)
            
            # Clear state
            self.overlay_processes.clear()
            self.current_focused_display = None
            
            print("Display manager cleanup complete")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")


# Utility functions for testing
def test_display_manager():
    """Test function for development"""
    if not PYOBJC_AVAILABLE:
        print("Cannot test: PyObjC not available")
        return
    
    dm = DisplayManager()
    dm.cache_display_info()
    
    print(f"Found displays: {list(dm.display_bounds.keys())}")
    print(f"Status: {dm.get_status()}")
    
    # Test overlay creation
    for display_id in dm.display_bounds:
        if display_id != 1:  # Don't dim main display for testing
            dm.create_overlay(display_id)
    
    print("Test overlays created. Press Ctrl+C to cleanup and exit...")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCleaning up test overlays...")
        dm.stop_monitoring()
        print("Test complete")


if __name__ == "__main__":
    test_display_manager() 