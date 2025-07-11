"""
QuickDimmer API Server - HTTP/WebSocket API for Frontend Communication
Provides REST endpoints and real-time WebSocket updates for the Electron frontend
"""
import asyncio
import json
import logging
from typing import Set, Dict, Any
from pathlib import Path

try:
    from aiohttp import web, WSMsgType, ClientWebSocketResponse
    from aiohttp.web_ws import WebSocketResponse
    AIOHTTP_AVAILABLE = True
except ImportError:
    print("Warning: aiohttp not available. Install with: pip install aiohttp")
    AIOHTTP_AVAILABLE = False


class APIServer:
    """HTTP API server with WebSocket support for frontend communication"""
    
    def __init__(self, display_manager):
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for API server")
        
        self.display_manager = display_manager
        self.app = web.Application()
        self.websockets: Set[WebSocketResponse] = set()
        self.runner = None
        self.site = None
        
        # Configure logging
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
        
        self._setup_routes()
        print("APIServer initialized", flush=True)
    
    def _setup_routes(self):
        """Set up HTTP routes and WebSocket endpoint"""
        # API endpoints
        self.app.router.add_get('/', self._handle_status)
        self.app.router.add_get('/status', self._handle_status)
        self.app.router.add_post('/opacity', self._handle_set_opacity)
        self.app.router.add_post('/toggle', self._handle_toggle_enabled)
        self.app.router.add_get('/displays', self._handle_get_displays)
        self.app.router.add_get('/focus', self._handle_get_focus_info)
        
        # Per-monitor endpoints
        self.app.router.add_get('/monitors', self._handle_get_all_monitors)
        self.app.router.add_get('/monitor/{display_id}', self._handle_get_monitor)
        self.app.router.add_post('/monitor/{display_id}/opacity', self._handle_set_monitor_opacity)
        self.app.router.add_post('/monitor/{display_id}/enabled', self._handle_set_monitor_enabled)
        
        # WebSocket endpoint for real-time updates
        self.app.router.add_get('/ws', self._handle_websocket)
        
        # CORS support for development
        self.app.router.add_options('/{path:.*}', self._handle_options)
        
        print("API routes configured")
    
    async def _handle_status(self, request) -> web.Response:
        """Get current application status"""
        try:
            status = self.display_manager.get_status()
            
            # Add some additional runtime info
            status.update({
                'api_version': '1.0.0',
                'websocket_connections': len(self.websockets),
                'backend_running': True
            })
            
            return web.json_response(status, headers=self._cors_headers())
            
        except Exception as e:
            print(f"Error getting status: {e}")
            return web.json_response(
                {'error': str(e), 'backend_running': False}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_set_opacity(self, request) -> web.Response:
        """Set overlay opacity - supports optional display_id for per-monitor settings"""
        try:
            data = await request.json()
            
            if 'opacity' not in data:
                return web.json_response(
                    {'error': 'opacity parameter required'}, 
                    status=400,
                    headers=self._cors_headers()
                )
            
            opacity = float(data['opacity'])
            display_id = data.get('display_id')  # Optional per-monitor setting
            
            if not 0.0 <= opacity <= 1.0:
                return web.json_response(
                    {'error': 'opacity must be between 0.0 and 1.0'}, 
                    status=400,
                    headers=self._cors_headers()
                )
            
            # Convert display_id to int if provided
            if display_id is not None:
                try:
                    display_id = int(display_id)
                except ValueError:
                    return web.json_response(
                        {'error': 'display_id must be an integer'}, 
                        status=400,
                        headers=self._cors_headers()
                    )
            
            success = self.display_manager.set_opacity(opacity, display_id)
            
            if success:
                # Broadcast change to all connected WebSocket clients
                await self.broadcast({
                    'type': 'opacity_changed',
                    'opacity': opacity,
                    'display_id': display_id,
                    'timestamp': asyncio.get_event_loop().time()
                })
                
                response_data = {'status': 'ok', 'opacity': opacity}
                if display_id is not None:
                    response_data['display_id'] = display_id
                
                return web.json_response(response_data, headers=self._cors_headers())
            else:
                return web.json_response(
                    {'error': 'Failed to set opacity'}, 
                    status=500,
                    headers=self._cors_headers()
                )
                
        except ValueError:
            return web.json_response(
                {'error': 'Invalid opacity value'}, 
                status=400,
                headers=self._cors_headers()
            )
        except Exception as e:
            print(f"Error setting opacity: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_toggle_enabled(self, request) -> web.Response:
        """Toggle dimming enabled/disabled"""
        try:
            enabled = self.display_manager.toggle_enabled()
            
            # Broadcast change to all connected WebSocket clients
            await self.broadcast({
                'type': 'enabled_changed',
                'enabled': enabled,
                'timestamp': asyncio.get_event_loop().time()
            })
            
            return web.json_response(
                {'status': 'ok', 'enabled': enabled},
                headers=self._cors_headers()
            )
            
        except Exception as e:
            print(f"Error toggling enabled: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_get_displays(self, request) -> web.Response:
        """Get information about all displays"""
        try:
            displays = []
            
            for display_id, (x, y, width, height) in self.display_manager.display_bounds.items():
                displays.append({
                    'id': display_id,
                    'bounds': {
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height
                    },
                    'has_overlay': display_id in self.display_manager.overlay_processes,
                    'is_focused': display_id == self.display_manager.current_focused_display
                })
            
            return web.json_response(
                {
                    'displays': displays,
                    'total_displays': len(displays),
                    'focused_display': self.display_manager.current_focused_display
                },
                headers=self._cors_headers()
            )
            
        except Exception as e:
            print(f"Error getting displays: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_get_focus_info(self, request) -> web.Response:
        """Get detailed focus information (for debugging)"""
        try:
            focus_info = {
                'focused_display': self.display_manager.current_focused_display,
                'defaults': {
                    'enabled': self.display_manager.default_enabled,
                    'opacity': self.display_manager.default_opacity
                },
                'active_overlays': list(self.display_manager.overlay_processes.keys()),
                'monitor_settings': self.display_manager.get_all_monitor_settings()
            }
            
            return web.json_response(focus_info, headers=self._cors_headers())
            
        except Exception as e:
            print(f"Error getting focus info: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_get_all_monitors(self, request) -> web.Response:
        """Get settings for all monitors"""
        try:
            monitor_settings = self.display_manager.get_all_monitor_settings()
            
            return web.json_response(
                {
                    'monitors': monitor_settings,
                    'total_monitors': len(monitor_settings),
                    'defaults': {
                        'opacity': self.display_manager.default_opacity,
                        'enabled': self.display_manager.default_enabled
                    }
                },
                headers=self._cors_headers()
            )
            
        except Exception as e:
            print(f"Error getting monitor settings: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_get_monitor(self, request) -> web.Response:
        """Get settings for a specific monitor"""
        try:
            display_id = int(request.match_info['display_id'])
            
            if display_id not in self.display_manager.display_bounds:
                return web.json_response(
                    {'error': f'Display {display_id} not found'}, 
                    status=404,
                    headers=self._cors_headers()
                )
            
            monitor_settings = self.display_manager.get_monitor_settings(display_id)
            
            return web.json_response(monitor_settings, headers=self._cors_headers())
            
        except ValueError:
            return web.json_response(
                {'error': 'Invalid display_id'}, 
                status=400,
                headers=self._cors_headers()
            )
        except Exception as e:
            print(f"Error getting monitor settings: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_set_monitor_opacity(self, request) -> web.Response:
        """Set opacity for a specific monitor"""
        try:
            display_id = int(request.match_info['display_id'])
            data = await request.json()
            
            if 'opacity' not in data:
                return web.json_response(
                    {'error': 'opacity parameter required'}, 
                    status=400,
                    headers=self._cors_headers()
                )
            
            opacity = float(data['opacity'])
            
            if not 0.0 <= opacity <= 1.0:
                return web.json_response(
                    {'error': 'opacity must be between 0.0 and 1.0'}, 
                    status=400,
                    headers=self._cors_headers()
                )
            
            success = self.display_manager.set_opacity(opacity, display_id)
            
            if success:
                # Broadcast change to all connected WebSocket clients
                await self.broadcast({
                    'type': 'monitor_opacity_changed',
                    'display_id': display_id,
                    'opacity': opacity,
                    'timestamp': asyncio.get_event_loop().time()
                })
                
                return web.json_response(
                    {'status': 'ok', 'display_id': display_id, 'opacity': opacity},
                    headers=self._cors_headers()
                )
            else:
                return web.json_response(
                    {'error': 'Failed to set monitor opacity'}, 
                    status=500,
                    headers=self._cors_headers()
                )
                
        except ValueError:
            return web.json_response(
                {'error': 'Invalid display_id or opacity value'}, 
                status=400,
                headers=self._cors_headers()
            )
        except Exception as e:
            print(f"Error setting monitor opacity: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_set_monitor_enabled(self, request) -> web.Response:
        """Enable/disable dimming for a specific monitor"""
        try:
            display_id = int(request.match_info['display_id'])
            data = await request.json()
            
            if 'enabled' not in data:
                return web.json_response(
                    {'error': 'enabled parameter required'}, 
                    status=400,
                    headers=self._cors_headers()
                )
            
            enabled = bool(data['enabled'])
            
            success = self.display_manager.set_monitor_enabled(display_id, enabled)
            
            if success:
                # Broadcast change to all connected WebSocket clients
                await self.broadcast({
                    'type': 'monitor_enabled_changed',
                    'display_id': display_id,
                    'enabled': enabled,
                    'timestamp': asyncio.get_event_loop().time()
                })
                
                return web.json_response(
                    {'status': 'ok', 'display_id': display_id, 'enabled': enabled},
                    headers=self._cors_headers()
                )
            else:
                return web.json_response(
                    {'error': 'Failed to set monitor enabled state'}, 
                    status=500,
                    headers=self._cors_headers()
                )
                
        except ValueError:
            return web.json_response(
                {'error': 'Invalid display_id or enabled value'}, 
                status=400,
                headers=self._cors_headers()
            )
        except Exception as e:
            print(f"Error setting monitor enabled: {e}")
            return web.json_response(
                {'error': str(e)}, 
                status=500,
                headers=self._cors_headers()
            )
    
    async def _handle_websocket(self, request) -> WebSocketResponse:
        """Handle WebSocket connections for real-time updates"""
        ws = WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.add(ws)
        print(f"WebSocket client connected. Total connections: {len(self.websockets)}")
        
        try:
            # Send initial status to new client
            await ws.send_str(json.dumps({
                'type': 'initial_status',
                'data': self.display_manager.get_status(),
                'timestamp': asyncio.get_event_loop().time()
            }))
            
            # Listen for messages from client
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_websocket_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({
                            'type': 'error',
                            'message': 'Invalid JSON'
                        }))
                elif msg.type == WSMsgType.ERROR:
                    print(f'WebSocket error: {ws.exception()}')
                    break
                elif msg.type == WSMsgType.CLOSE:
                    break
                    
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self.websockets.discard(ws)
            print(f"WebSocket client disconnected. Total connections: {len(self.websockets)}")
        
        return ws
    
    async def _handle_websocket_message(self, ws: WebSocketResponse, data: Dict[Any, Any]):
        """Handle incoming WebSocket messages from client"""
        try:
            msg_type = data.get('type')
            
            if msg_type == 'ping':
                await ws.send_str(json.dumps({'type': 'pong'}))
            elif msg_type == 'request_status':
                status = self.display_manager.get_status()
                await ws.send_str(json.dumps({
                    'type': 'status_update',
                    'data': status,
                    'timestamp': asyncio.get_event_loop().time()
                }))
            else:
                await ws.send_str(json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {msg_type}'
                }))
                
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
    
    async def _handle_options(self, request) -> web.Response:
        """Handle CORS preflight requests"""
        return web.Response(headers=self._cors_headers())
    
    def _cors_headers(self) -> Dict[str, str]:
        """Return CORS headers for development"""
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '86400'
        }
    
    async def broadcast(self, data: Dict[Any, Any]):
        """Send data to all connected WebSocket clients"""
        if not self.websockets:
            return
        
        message = json.dumps(data)
        
        # Send to all connected clients
        disconnected = set()
        
        for ws in self.websockets:
            try:
                if ws.closed:
                    disconnected.add(ws)
                else:
                    await ws.send_str(message)
            except Exception as e:
                print(f"Error broadcasting to WebSocket client: {e}")
                disconnected.add(ws)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.websockets.discard(ws)
        
        if disconnected:
            print(f"Cleaned up {len(disconnected)} disconnected WebSocket clients")
    
    async def start(self, host='localhost', port=8080):
        """Start the API server"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()
            
            print(f"API server started on http://{host}:{port}")
            print(f"WebSocket endpoint: ws://{host}:{port}/ws")
            
        except Exception as e:
            print(f"Error starting API server: {e}")
            raise
    
    async def stop(self):
        """Stop the API server and cleanup"""
        try:
            print("Stopping API server...")
            
            # Close all WebSocket connections
            if self.websockets:
                close_tasks = []
                for ws in self.websockets:
                    if not ws.closed:
                        close_tasks.append(ws.close())
                
                if close_tasks:
                    await asyncio.gather(*close_tasks, return_exceptions=True)
                
                self.websockets.clear()
            
            # Stop the server
            if self.site:
                await self.site.stop()
                self.site = None
            
            if self.runner:
                await self.runner.cleanup()
                self.runner = None
            
            print("API server stopped")
            
        except Exception as e:
            print(f"Error stopping API server: {e}")


# Utility function for testing
async def test_api_server():
    """Test function for development"""
    print("Testing APIServer...")
    
    # Create a mock display manager for testing
    class MockDisplayManager:
        def __init__(self):
            self.default_opacity = 0.7
            self.default_enabled = True
            self.current_focused_display = 1
            self.display_bounds = {1: (0, 0, 1920, 1080), 2: (1920, 0, 1920, 1080)}
            self.overlay_processes = {}
            self.monitor_opacity = {1: 0.7, 2: 0.7}
            self.monitor_enabled = {1: True, 2: True}
        
        def get_status(self):
            return {
                'enabled': self.default_enabled,
                'opacity': self.default_opacity,
                'focused_display': self.current_focused_display,
                'displays': 2,
                'active_overlays': len(self.overlay_processes),
                'monitor_settings': self.get_all_monitor_settings()
            }
        
        def set_opacity(self, opacity, display_id=None):
            if display_id is not None:
                self.monitor_opacity[display_id] = opacity
            else:
                self.default_opacity = opacity
                for display_id in self.display_bounds:
                    self.monitor_opacity[display_id] = opacity
            return True
        
        def set_monitor_enabled(self, display_id, enabled):
            self.monitor_enabled[display_id] = enabled
            return True
        
        def get_monitor_settings(self, display_id):
            return {
                'display_id': display_id,
                'opacity': self.monitor_opacity.get(display_id, self.default_opacity),
                'enabled': self.monitor_enabled.get(display_id, self.default_enabled),
                'has_overlay': display_id in self.overlay_processes,
                'is_focused': display_id == self.current_focused_display,
                'bounds': self.display_bounds.get(display_id)
            }
        
        def get_all_monitor_settings(self):
            return {display_id: self.get_monitor_settings(display_id) 
                   for display_id in self.display_bounds}
        
        def toggle_enabled(self):
            self.default_enabled = not self.default_enabled
            return self.default_enabled
    
    if not AIOHTTP_AVAILABLE:
        print("Cannot test: aiohttp not available")
        return
    
    mock_dm = MockDisplayManager()
    server = APIServer(mock_dm)
    
    try:
        await server.start('localhost', 8081)
        print("Test server started on http://localhost:8081")
        print("Press Ctrl+C to stop...")
        
        # Keep running for manual testing
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping test server...")
    finally:
        await server.stop()
        print("APIServer test complete")


if __name__ == "__main__":
    if AIOHTTP_AVAILABLE:
        asyncio.run(test_api_server())
    else:
        print("aiohttp not available for testing") 