"""
QuickDimmer Focus Detector - Window Focus Detection
Detects which display contains the currently focused window using AppleScript
Based on the proven approach from monitor_dimmer.sh
"""
import subprocess
import sys
from typing import Optional, Tuple, Dict


class FocusDetector:
    """Detects which display has the focused window"""
    
    def __init__(self, display_manager):
        self.display_manager = display_manager
        self.last_focused_display: Optional[int] = None
        self.main_screen_height: Optional[int] = None
        
        print("FocusDetector initialized", flush=True)
    
    def get_focused_display(self) -> int:
        """
        Detect which display has the focused window
        Returns display ID, defaults to 1 if detection fails
        """
        try:
            # Get focused app and window position using AppleScript
            app_info = self._get_focused_app_info()
            if not app_info:
                return self._get_fallback_display()
            
            x, y = app_info['window_position']
            app_name = app_info['app_name']
            
            # Convert coordinates and find containing display
            display_id = self._find_display_for_position(x, y)
            
            # Debug output (matching bash script behavior)
            print(f"DEBUG: App '{app_name}' at ({x}, {y}) -> Display {display_id}")
            
            return display_id
            
        except Exception as e:
            print(f"Error detecting focused display: {e}")
            return self._get_fallback_display()
    
    def _get_focused_app_info(self) -> Optional[Dict]:
        """
        Get focused app and window position using AppleScript
        Replicates the get_focused_app_and_window() function from monitor_dimmer.sh
        """
        try:
            # Same AppleScript as in the working bash script
            script = '''
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
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', script], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print(f"AppleScript error: {result.stderr.strip()}")
                return None
            
            # Parse result: "AppName|x,y"
            output = result.stdout.strip()
            if '|' not in output:
                return None
                
            parts = output.split('|', 1)
            if len(parts) != 2:
                return None
                
            app_name = parts[0]
            coords_str = parts[1]
            
            if ',' not in coords_str:
                return None
                
            coord_parts = coords_str.split(',')
            if len(coord_parts) != 2:
                return None
                
            try:
                x = int(coord_parts[0])
                y = int(coord_parts[1])
            except ValueError:
                return None
            
            return {
                'app_name': app_name,
                'window_position': (x, y)
            }
            
        except subprocess.TimeoutExpired:
            print("AppleScript timeout")
            return None
        except Exception as e:
            print(f"Error getting focused app info: {e}")
            return None
    
    def _find_display_for_position(self, x: int, y: int) -> int:
        """
        Find which display contains the given position
        Replicates detect_display_for_position() from monitor_dimmer.sh
        """
        try:
            # Convert AppleScript coordinates to Cocoa coordinates
            # This matches the coordinate conversion from the bash script
            converted_y = self._convert_applescript_to_cocoa_y(y)
            
            print(f"DEBUG: Converted AppleScript coords ({x}, {y}) to Cocoa coords ({x}, {converted_y})")
            
            # Test against display bounds (same logic as bash script)
            print(f"DEBUG: Testing point ({x}, {converted_y}) against display bounds:")
            
            for display_id, (left, top, width, height) in self.display_manager.display_bounds.items():
                right = left + width
                bottom = top + height
                
                print(f"DEBUG: Display {display_id}: bounds=({left}, {top}) to ({right}, {bottom})")
                
                # Check if point is within this display's bounds
                if left <= x < right and top <= converted_y < bottom:
                    print(f"DEBUG: Point ({x}, {converted_y}) is inside display {display_id}")
                    return display_id
            
            # No display found, default to main display
            print(f"DEBUG: Point ({x}, {converted_y}) not found in any display, defaulting to 1")
            return 1
            
        except Exception as e:
            print(f"Error finding display for position ({x}, {y}): {e}")
            return 1
    
    def _convert_applescript_to_cocoa_y(self, applescript_y: int) -> int:
        """
        Convert AppleScript Y coordinate to Cocoa coordinate system
        AppleScript uses top-left origin, Cocoa uses bottom-left origin
        """
        try:
            # Get main screen height for conversion (cache it)
            if self.main_screen_height is None:
                self.main_screen_height = self._get_main_screen_height()
            
            if self.main_screen_height is not None:
                return self.main_screen_height - applescript_y
            else:
                return applescript_y  # Fallback if we can't get main height
                
        except Exception as e:
            print(f"Error converting coordinates: {e}")
            return applescript_y
    
    def _get_main_screen_height(self) -> Optional[int]:
        """Get the main screen height for coordinate conversion"""
        try:
            # Find display 1 (main display) in the cached bounds
            for display_id, (left, top, width, height) in self.display_manager.display_bounds.items():
                if display_id == 1:  # Main display
                    return height
            
            # Fallback: use the first display we find
            if self.display_manager.display_bounds:
                first_display = list(self.display_manager.display_bounds.values())[0]
                return first_display[3]  # height is index 3
            
            return None
            
        except Exception as e:
            print(f"Error getting main screen height: {e}")
            return None
    
    def _get_fallback_display(self) -> int:
        """Return fallback display when detection fails"""
        # Return the first available display, or 1 as ultimate fallback
        if self.display_manager.display_bounds:
            return list(self.display_manager.display_bounds.keys())[0]
        return 1
    
    def get_focus_info(self) -> Dict:
        """Get detailed focus information for debugging/status"""
        try:
            app_info = self._get_focused_app_info()
            focused_display = self.get_focused_display()
            
            return {
                'focused_display': focused_display,
                'app_name': app_info['app_name'] if app_info else 'Unknown',
                'window_position': app_info['window_position'] if app_info else (0, 0),
                'available_displays': list(self.display_manager.display_bounds.keys()),
                'main_screen_height': self.main_screen_height
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'focused_display': self._get_fallback_display(),
                'app_name': 'Unknown',
                'window_position': (0, 0),
                'available_displays': list(self.display_manager.display_bounds.keys()),
                'main_screen_height': self.main_screen_height
            }


# Utility function for testing
def test_focus_detector():
    """Test function for development"""
    print("Testing FocusDetector...")
    
    # Create a mock display manager for testing
    class MockDisplayManager:
        def __init__(self):
            self.display_bounds = {
                1: (0, 0, 1920, 1080),     # Main display
                2: (1920, 0, 1920, 1080)   # Secondary display
            }
    
    mock_dm = MockDisplayManager()
    detector = FocusDetector(mock_dm)
    
    # Test focus detection
    focused_display = detector.get_focused_display()
    focus_info = detector.get_focus_info()
    
    print(f"Focused display: {focused_display}")
    print(f"Focus info: {focus_info}")
    
    print("FocusDetector test complete")


if __name__ == "__main__":
    test_focus_detector() 