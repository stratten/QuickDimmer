#!/usr/bin/env python3
"""
QuickDimmer Backend - Monitor Focus Dimming Service
Provides HTTP API for Electron frontend
"""
import asyncio
import signal
import sys
import os
import atexit
from pathlib import Path

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from display_manager import DisplayManager
from api_server import APIServer
from focus_detector import FocusDetector


class QuickDimmerApp:
    def __init__(self, port=None):
        self.display_manager = DisplayManager()
        self.focus_detector = FocusDetector(self.display_manager)
        self.api_server = APIServer(self.display_manager)
        self.monitoring_task = None
        self.running = False
        
        # Get port from parameter, environment variable, or default
        self.port = port or int(os.getenv('BACKEND_PORT', 8080))
    
    async def start(self):
        """Start all components of the QuickDimmer application"""
        print("Starting QuickDimmer backend...", flush=True)
        
        try:
            # Initialize display information
            self.display_manager.cache_display_info()
            print(f"Found {len(self.display_manager.display_bounds)} displays", flush=True)
            
            # Start API server for frontend communication
            await self.api_server.start(port=self.port)
            print(f"API server started on http://localhost:{self.port}", flush=True)
            
            # Start display monitoring
            await self.start_monitoring()
            print("Display monitoring started", flush=True)
            
            # Perform initial focus detection (but defer overlay creation)
            initial_focused_display = self.focus_detector.get_focused_display()
            self.display_manager.current_focused_display = initial_focused_display
            print(f"Initial focus detection: Display {initial_focused_display}", flush=True)
            
            self.running = True
            print("QuickDimmer backend ready!", flush=True)
            
            # Create initial overlays asynchronously after startup
            asyncio.create_task(self._create_initial_overlays(initial_focused_display))
            
            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"Error starting QuickDimmer: {e}")
            await self.stop()
            raise
    
    async def start_monitoring(self):
        """Start the focus monitoring loop"""
        self.monitoring_task = asyncio.create_task(self._monitor_focus())
    
    async def _create_initial_overlays(self, focused_display_id: int):
        """Create initial overlays asynchronously after startup"""
        try:
            print("Creating initial overlays asynchronously...", flush=True)
            # Small delay to let frontend finish initialization
            await asyncio.sleep(0.5)
            self.display_manager.update_overlays(focused_display_id)
            print("Initial overlays created", flush=True)
        except Exception as e:
            print(f"Error creating initial overlays: {e}", flush=True)
    
    async def _monitor_focus(self):
        """Monitor focus changes and update overlays accordingly"""
        while self.running:
            try:
                # Check which display has focus
                focused_display = self.focus_detector.get_focused_display()
                
                # Update overlays if focus changed
                if focused_display != self.display_manager.current_focused_display:
                    self.display_manager.current_focused_display = focused_display
                    self.display_manager.update_overlays(focused_display)
                    
                    # Notify frontend of focus change
                    await self.api_server.broadcast({
                        'type': 'focus_changed',
                        'focused_display': focused_display
                    })
                
                # Check every 500ms for responsiveness
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Error in focus monitoring: {e}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop all components and cleanup"""
        print("Stopping QuickDimmer backend...")
        self.running = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.display_manager.stop_monitoring()
        await self.api_server.stop()
        print("QuickDimmer backend stopped")


def cleanup_overlays():
    """Emergency cleanup function for overlays"""
    try:
        import subprocess
        import glob
        
        # Kill any remaining overlay processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'python' in line and 'overlay_' in line and '_process.pid' in line:
                try:
                    pid = int(line.split()[1])
                    os.kill(pid, signal.SIGKILL)
                except:
                    pass
        
        # Clean up PID files
        for pid_file in glob.glob('/tmp/overlay_*_process.pid'):
            try:
                os.remove(pid_file)
            except:
                pass
        
        print("Emergency overlay cleanup completed")
    except Exception as e:
        print(f"Error in emergency cleanup: {e}")


def signal_handler(app):
    """Handle shutdown signals gracefully"""
    def handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        # Synchronous cleanup
        app.display_manager.stop_monitoring()
        cleanup_overlays()
        sys.exit(0)
    return handler


async def main():
    app = QuickDimmerApp()
    
    # Register emergency cleanup for all exit scenarios
    atexit.register(cleanup_overlays)
    
    # Set up signal handlers for graceful shutdown
    if sys.platform != 'win32':
        signal.signal(signal.SIGINT, signal_handler(app))
        signal.signal(signal.SIGTERM, signal_handler(app))
    
    try:
        await app.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    # Ensure we're running on macOS
    if sys.platform != 'darwin':
        print("QuickDimmer is designed for macOS only")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 