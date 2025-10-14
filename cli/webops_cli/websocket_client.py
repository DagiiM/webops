"""
WebSocket client for real-time updates from the WebOps control panel.
"""

import asyncio
import json
import time
from typing import Any, Callable, Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .config import Config


class WebSocketClient:
    """WebSocket client for real-time communication with WebOps control panel."""
    
    def __init__(self, config: Config) -> None:
        """Initialize WebSocket client.
        
        Args:
            config: Configuration object containing server details.
        """
        self.config = config
        self.console = Console()
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2.0
        
    def get_websocket_url(self, endpoint: str) -> str:
        """Build WebSocket URL from config and endpoint.
        
        Args:
            endpoint: WebSocket endpoint path.
            
        Returns:
            Complete WebSocket URL.
        """
        base_url = self.config.get_url()
        if not base_url:
            raise ValueError("WebOps URL not configured")
        
        ws_url = base_url.replace('http://', 'ws://').replace('https://', 'wss://')
        return f"{ws_url.rstrip('/')}/{endpoint.lstrip('/')}"
    
    async def connect(self, endpoint: str) -> bool:
        """Connect to WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint to connect to.
            
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            url = self.get_websocket_url(endpoint)
            headers = {}
            
            if self.config.get_token():
                headers['Authorization'] = f'Bearer {self.config.get_token()}'
            
            self.websocket = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to connect to WebSocket: {e}[/red]")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        self.is_connected = False
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send message to WebSocket.
        
        Args:
            message: Message to send as dictionary.
        """
        if not self.websocket or not self.is_connected:
            raise ConnectionError("WebSocket not connected")
        
        try:
            await self.websocket.send(json.dumps(message))
        except ConnectionClosed:
            self.is_connected = False
            raise
    
    async def receive_message(self) -> Dict[str, Any] | None:
        """Receive message from WebSocket.
        
        Returns:
            Received message as dictionary, or None if connection closed.
        """
        if not self.websocket or not self.is_connected:
            return None
        
        try:
            message = await self.websocket.recv()
            return json.loads(message)
        except ConnectionClosed:
            self.is_connected = False
            return None
        except json.JSONDecodeError as e:
            self.console.print(f"[yellow]Invalid JSON received: {e}[/yellow]")
            return None
    
    async def listen_for_updates(
        self, 
        endpoint: str, 
        message_handler: Callable[[Dict[str, Any]], None],
        auto_reconnect: bool = True
    ) -> None:
        """Listen for real-time updates from WebSocket.
        
        Args:
            endpoint: WebSocket endpoint to connect to.
            message_handler: Function to handle received messages.
            auto_reconnect: Whether to automatically reconnect on failure.
        """
        while True:
            try:
                if not self.is_connected:
                    success = await self.connect(endpoint)
                    if not success:
                        if auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
                            self.reconnect_attempts += 1
                            await asyncio.sleep(self.reconnect_delay)
                            continue
                        else:
                            break
                
                # Send ping to keep connection alive
                await self.send_message({'type': 'ping', 'timestamp': time.time()})
                
                # Listen for messages
                while self.is_connected:
                    message = await self.receive_message()
                    if message:
                        message_handler(message)
                    else:
                        break
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.console.print(f"[red]WebSocket error: {e}[/red]")
                self.is_connected = False
                
                if auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    break
        
        await self.disconnect()


class DeploymentStatusMonitor:
    """Monitor deployment status via WebSocket."""
    
    def __init__(self, config: Config) -> None:
        """Initialize deployment status monitor.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.client = WebSocketClient(config)
        self.console = Console()
        self.current_status: Dict[str, Any] = {}
        
    async def monitor_deployment(self, deployment_id: str) -> None:
        """Monitor specific deployment status.
        
        Args:
            deployment_id: ID of deployment to monitor.
        """
        endpoint = f"ws/deployments/{deployment_id}/"
        
        def handle_message(message: Dict[str, Any]) -> None:
            """Handle incoming WebSocket messages."""
            msg_type = message.get('type')
            
            if msg_type == 'deployment_status':
                self.current_status = message.get('deployment', {})
                self._display_status_update()
            elif msg_type == 'deployment_status_update':
                self.current_status.update({
                    'status': message.get('status'),
                    'message': message.get('message', '')
                })
                self._display_status_update()
            elif msg_type == 'deployment_logs':
                self._display_logs(message.get('logs', []))
            elif msg_type == 'pong':
                # Keep-alive response
                pass
        
        self.console.print(f"[blue]Monitoring deployment {deployment_id}...[/blue]")
        self.console.print("[dim]Press Ctrl+C to stop monitoring[/dim]")
        
        try:
            await self.client.listen_for_updates(endpoint, handle_message)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Monitoring stopped[/yellow]")
        finally:
            await self.client.disconnect()
    
    def _display_status_update(self) -> None:
        """Display deployment status update."""
        if not self.current_status:
            return
        
        status = self.current_status.get('status', 'unknown')
        name = self.current_status.get('name', 'Unknown')
        message = self.current_status.get('message', '')
        
        # Color code status
        status_colors = {
            'running': 'green',
            'stopped': 'red',
            'starting': 'yellow',
            'stopping': 'yellow',
            'error': 'red',
            'deploying': 'blue'
        }
        
        color = status_colors.get(status.lower(), 'white')
        status_text = Text(f"[{color}]{status.upper()}[/{color}]")
        
        panel_content = f"**{name}**\\n"
        panel_content += f"Status: {status_text}\\n"
        if message:
            panel_content += f"Message: {message}"
        
        panel = Panel(
            panel_content,
            title="Deployment Status",
            border_style="blue"
        )
        
        self.console.print(panel)
    
    def _display_logs(self, logs: list[str]) -> None:
        """Display deployment logs.
        
        Args:
            logs: List of log lines to display.
        """
        if logs:
            self.console.print("[dim]--- New Logs ---[/dim]")
            for log_line in logs:
                self.console.print(log_line)


class DeploymentListMonitor:
    """Monitor all deployments via WebSocket."""
    
    def __init__(self, config: Config) -> None:
        """Initialize deployment list monitor.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.client = WebSocketClient(config)
        self.console = Console()
        
    async def monitor_deployments(self) -> None:
        """Monitor all deployment updates."""
        endpoint = "ws/deployments/"
        
        def handle_message(message: Dict[str, Any]) -> None:
            """Handle incoming WebSocket messages."""
            msg_type = message.get('type')
            
            if msg_type == 'deployment_update':
                deployment = message.get('deployment', {})
                self._display_deployment_update(deployment)
            elif msg_type == 'deployment_status':
                deployment_id = message.get('deployment_id')
                status = message.get('status')
                msg = message.get('message', '')
                self._display_status_change(deployment_id, status, msg)
        
        self.console.print("[blue]Monitoring all deployments...[/blue]")
        self.console.print("[dim]Press Ctrl+C to stop monitoring[/dim]")
        
        try:
            await self.client.listen_for_updates(endpoint, handle_message)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Monitoring stopped[/yellow]")
        finally:
            await self.client.disconnect()
    
    def _display_deployment_update(self, deployment: Dict[str, Any]) -> None:
        """Display deployment update.
        
        Args:
            deployment: Deployment data dictionary.
        """
        name = deployment.get('name', 'Unknown')
        status = deployment.get('status', 'unknown')
        
        self.console.print(f"[blue]📦 {name}[/blue] - Status: [green]{status}[/green]")
    
    def _display_status_change(self, deployment_id: str, status: str, message: str) -> None:
        """Display deployment status change.
        
        Args:
            deployment_id: ID of the deployment.
            status: New status.
            message: Status message.
        """
        timestamp = time.strftime("%H:%M:%S")
        self.console.print(f"[dim]{timestamp}[/dim] [blue]{deployment_id}[/blue]: {status}")
        if message:
            self.console.print(f"  └─ {message}")