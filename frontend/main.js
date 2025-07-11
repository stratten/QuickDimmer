const { app, BrowserWindow, Menu, Tray, dialog, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const Store = require('electron-store');
const windowStateKeeper = require('electron-window-state');

class QuickDimmerElectron {
    constructor() {
        this.mainWindow = null;
        this.tray = null;
        this.pythonProcess = null;
        this.store = new Store();
        this.isQuitting = false;
        this.backendReady = false;
        this.retryCount = 0;
        this.maxRetries = 5;
        
        // App configuration
        this.config = {
            backend: {
                host: 'localhost',
                port: parseInt(process.env.BACKEND_PORT || '8080'),
                startupTimeout: 10000
            },
            window: {
                width: 400,
                height: 600,
                minWidth: 350,
                minHeight: 500
            }
        };
        
        console.log('QuickDimmer Electron initialized');
    }

    async init() {
        // Single instance enforcement
        const gotTheLock = app.requestSingleInstanceLock();
        if (!gotTheLock) {
            console.log('Another instance is already running');
            app.quit();
            return;
        }

        app.on('second-instance', () => {
            // Focus existing window if user tries to run again
            if (this.mainWindow) {
                if (this.mainWindow.isMinimized()) this.mainWindow.restore();
                this.mainWindow.focus();
                this.mainWindow.show();
            }
        });

        // Wait for Electron to be ready
        await app.whenReady();
        
        console.log('Electron ready, initializing QuickDimmer...');
        
        // Set app properties
        app.setName('QuickDimmer');
        if (process.platform === 'darwin') {
            app.dock.hide(); // Hide from dock initially
        }
        
        try {
            // Start Python backend first
            await this.startPythonBackend();
            
            // Create UI components
            this.createWindow();
            this.createTray();
            this.setupAppEventHandlers();
            
            // Wait for backend to be ready
            await this.waitForBackend();
            
            console.log('QuickDimmer fully initialized and ready');
            
            // Show window briefly to indicate successful startup
            this.mainWindow.show();
            setTimeout(() => {
                if (!this.store.get('keepWindowOpen', false)) {
                    this.mainWindow.hide();
                }
            }, 2000);
            
        } catch (error) {
            console.error('Failed to initialize QuickDimmer:', error);
            await this.showErrorDialog('Startup Error', 
                `Failed to start QuickDimmer: ${error.message}\n\nPlease check that Python 3 and required dependencies are installed.`);
            app.quit();
        }
    }

    createWindow() {
        // Load saved window state
        let mainWindowState = windowStateKeeper({
            defaultWidth: this.config.window.width,
            defaultHeight: this.config.window.height
        });

        // Create the browser window
        this.mainWindow = new BrowserWindow({
            x: mainWindowState.x,
            y: mainWindowState.y,
            width: mainWindowState.width,
            height: mainWindowState.height,
            minWidth: this.config.window.minWidth,
            minHeight: this.config.window.minHeight,
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
                enableRemoteModule: true
            },
            titleBarStyle: 'default',  // Use default title bar for focus and movability
            title: 'QuickDimmer',
            icon: path.join(__dirname, 'assets', 'icon.png'),
            show: false, // Don't show immediately
            resizable: true,
            maximizable: false,
            fullscreenable: false,
            acceptFirstMouse: true  // Allow window to focus on first click
        });

        // Manage window state
        mainWindowState.manage(this.mainWindow);

        // Load the renderer
        this.mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

        // Window event handlers
        this.mainWindow.on('ready-to-show', () => {
            console.log('Main window ready to show');
        });

        this.mainWindow.on('close', (event) => {
            if (!this.isQuitting) {
                event.preventDefault();
                this.mainWindow.hide();
                
                // Show notification on first hide (macOS style)
                if (process.platform === 'darwin' && !this.store.get('hideNotificationShown', false)) {
                    this.showNotification('QuickDimmer', 'App is still running in the menu bar');
                    this.store.set('hideNotificationShown', true);
                }
            }
        });

        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });

        // Open external links in default browser
        this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
            shell.openExternal(url);
            return { action: 'deny' };
        });

        console.log('Main window created');
    }

    createTray() {
        const trayIconPath = path.join(__dirname, 'assets', 'tray-icon.png');
        
        // Fallback to a simple icon if file doesn't exist
        let iconPath = trayIconPath;
        if (!fs.existsSync(trayIconPath)) {
            // Create a simple fallback - you'd typically have actual icon files
            iconPath = path.join(__dirname, 'assets', 'icon.png');
        }

        this.tray = new Tray(iconPath);
        
        this.updateTrayMenu();
        
        this.tray.setToolTip('QuickDimmer - Monitor Focus Dimming');
        
        // Double-click to show/hide window
        this.tray.on('double-click', () => {
            this.toggleWindow();
        });

        console.log('System tray created');
    }

    updateTrayMenu(status = null) {
        const contextMenu = Menu.buildFromTemplate([
            {
                label: 'QuickDimmer',
                type: 'normal',
                enabled: false
            },
            { type: 'separator' },
            {
                label: status ? (status.enabled ? 'Disable Dimming' : 'Enable Dimming') : 'Toggle Dimming',
                click: () => this.toggleDimming(),
                accelerator: 'CommandOrControl+D'
            },
            {
                label: 'Show Window',
                click: () => this.showWindow(),
                accelerator: 'CommandOrControl+Shift+D'
            },
            { type: 'separator' },
            {
                label: 'Status',
                submenu: status ? [
                    { label: `Enabled: ${status.enabled ? 'Yes' : 'No'}`, enabled: false },
                    { label: `Opacity: ${Math.round(status.opacity * 100)}%`, enabled: false },
                    { label: `Displays: ${status.displays}`, enabled: false },
                    { label: `Focused: Display ${status.focused_display || 'Unknown'}`, enabled: false }
                ] : [
                    { label: 'Backend starting...', enabled: false }
                ]
            },
            { type: 'separator' },
            {
                label: 'Preferences',
                click: () => this.showWindow()
            },
            {
                label: 'About',
                click: () => this.showAbout()
            },
            { type: 'separator' },
            {
                label: 'Quit QuickDimmer',
                click: () => this.quit(),
                accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q'
            }
        ]);
        
        this.tray.setContextMenu(contextMenu);
    }

    setupAppEventHandlers() {
        // macOS specific handlers
        if (process.platform === 'darwin') {
            app.on('activate', () => {
                if (this.mainWindow === null) {
                    this.createWindow();
                } else {
                    this.showWindow();
                }
            });
        }

        app.on('before-quit', () => {
            this.isQuitting = true;
        });

        app.on('window-all-closed', () => {
            // On macOS, keep app running even with no windows
            if (process.platform !== 'darwin') {
                this.quit();
            }
        });

        // Handle app menu (macOS)
        if (process.platform === 'darwin') {
            this.createApplicationMenu();
        }
    }

    createApplicationMenu() {
        const template = [
            {
                label: 'QuickDimmer',
                submenu: [
                    { label: 'About QuickDimmer', click: () => this.showAbout() },
                    { type: 'separator' },
                    { label: 'Preferences...', accelerator: 'Cmd+,', click: () => this.showWindow() },
                    { type: 'separator' },
                    { label: 'Hide QuickDimmer', accelerator: 'Cmd+H', role: 'hide' },
                    { label: 'Hide Others', accelerator: 'Cmd+Alt+H', role: 'hideothers' },
                    { label: 'Show All', role: 'unhide' },
                    { type: 'separator' },
                    { label: 'Quit', accelerator: 'Cmd+Q', click: () => this.quit() }
                ]
            },
            {
                label: 'Edit',
                submenu: [
                    { label: 'Undo', accelerator: 'CmdOrCtrl+Z', role: 'undo' },
                    { label: 'Redo', accelerator: 'Shift+CmdOrCtrl+Z', role: 'redo' },
                    { type: 'separator' },
                    { label: 'Cut', accelerator: 'CmdOrCtrl+X', role: 'cut' },
                    { label: 'Copy', accelerator: 'CmdOrCtrl+C', role: 'copy' },
                    { label: 'Paste', accelerator: 'CmdOrCtrl+V', role: 'paste' }
                ]
            },
            {
                label: 'View',
                submenu: [
                    { label: 'Reload', accelerator: 'CmdOrCtrl+R', role: 'reload' },
                    { label: 'Force Reload', accelerator: 'CmdOrCtrl+Shift+R', role: 'forceReload' },
                    { label: 'Toggle Developer Tools', accelerator: 'F12', role: 'toggleDevTools' },
                    { type: 'separator' },
                    { label: 'Actual Size', accelerator: 'CmdOrCtrl+0', role: 'resetZoom' },
                    { label: 'Zoom In', accelerator: 'CmdOrCtrl+Plus', role: 'zoomIn' },
                    { label: 'Zoom Out', accelerator: 'CmdOrCtrl+-', role: 'zoomOut' }
                ]
            }
        ];

        const menu = Menu.buildFromTemplate(template);
        Menu.setApplicationMenu(menu);
    }

    async startPythonBackend() {
        return new Promise((resolve, reject) => {
            console.log('Starting Python backend...');
            
            // Determine Python backend path
            const backendPath = this.getBackendPath();
            const mainPyPath = path.join(backendPath, 'main.py');
            
            console.log(`Backend path: ${backendPath}`);
            console.log(`main.py path: ${mainPyPath}`);
            
            if (!fs.existsSync(mainPyPath)) {
                reject(new Error(`Backend not found at ${mainPyPath}`));
                return;
            }
            
            // Start Python process using Poetry with unbuffered output
            this.pythonProcess = spawn('poetry', ['run', 'python', '-u', 'main.py'], {
                cwd: backendPath,
                stdio: ['pipe', 'pipe', 'pipe'],
                env: { 
                    ...process.env,
                    BACKEND_PORT: this.config.backend.port.toString(),
                    PYTHONUNBUFFERED: '1'
                }
            });
            
            let startupOutput = '';
            
            this.pythonProcess.stdout.on('data', (data) => {
                const output = data.toString();
                startupOutput += output;
                console.log(`Backend stdout: ${output.trim()}`);
                
                // Check for successful startup message
                if (output.includes('QuickDimmer backend ready!')) {
                    this.backendReady = true;
                    resolve();
                }
            });
            
            this.pythonProcess.stderr.on('data', (data) => {
                const output = data.toString();
                console.error(`Backend stderr: ${output.trim()}`);
                
                // Don't reject on warnings, only on actual errors
                if (output.includes('Error') && output.includes('Fatal')) {
                    reject(new Error(`Backend startup error: ${output}`));
                }
            });
            
            this.pythonProcess.on('error', (error) => {
                console.error('Failed to start Python backend:', error);
                reject(error);
            });
            
            this.pythonProcess.on('close', (code) => {
                console.log(`Python backend exited with code ${code}`);
                this.pythonProcess = null;
                this.backendReady = false;
                
                if (code !== 0 && !this.isQuitting) {
                    // Backend crashed, try to restart
                    this.handleBackendCrash(code);
                }
            });
            
            // Timeout if backend doesn't start
            setTimeout(() => {
                if (!this.backendReady) {
                    reject(new Error('Backend startup timeout'));
                }
            }, this.config.backend.startupTimeout);
        });
    }

    getBackendPath() {
        // In development
        if (process.env.NODE_ENV === 'development' || !app.isPackaged) {
            return path.join(__dirname, '..', 'backend');
        }
        
        // In packaged app
        return path.join(process.resourcesPath, 'backend');
    }

    async waitForBackend() {
        const maxAttempts = 20;
        const delayMs = 500;
        
        for (let i = 0; i < maxAttempts; i++) {
            try {
                // Try to connect to backend API
                const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/status`);
                if (response.ok) {
                    console.log('Backend API is responding');
                    return;
                }
            } catch (error) {
                // Backend not ready yet
            }
            
            await new Promise(resolve => setTimeout(resolve, delayMs));
        }
        
        throw new Error('Backend API not responding after startup');
    }

    async handleBackendCrash(exitCode) {
        console.log(`Backend crashed with exit code ${exitCode}`);
        
        if (this.retryCount < this.maxRetries && !this.isQuitting) {
            this.retryCount++;
            console.log(`Attempting to restart backend (attempt ${this.retryCount}/${this.maxRetries})`);
            
            try {
                await this.startPythonBackend();
                await this.waitForBackend();
                console.log('Backend successfully restarted');
                this.retryCount = 0; // Reset on success
            } catch (error) {
                console.error('Failed to restart backend:', error);
                
                if (this.retryCount >= this.maxRetries) {
                    await this.showErrorDialog('Backend Error', 
                        'The QuickDimmer backend has crashed and could not be restarted. The application will now quit.');
                    this.quit();
                }
            }
        }
    }

    // UI interaction methods
    showWindow() {
        if (this.mainWindow) {
            this.mainWindow.show();
            this.mainWindow.focus();
        }
    }

    toggleWindow() {
        if (this.mainWindow) {
            if (this.mainWindow.isVisible()) {
                this.mainWindow.hide();
            } else {
                this.showWindow();
            }
        }
    }

    async toggleDimming() {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/toggle`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log(`Dimming ${data.enabled ? 'enabled' : 'disabled'}`);
                
                // Update tray menu with new status
                const status = await this.getBackendStatus();
                this.updateTrayMenu(status);
            }
        } catch (error) {
            console.error('Failed to toggle dimming:', error);
        }
    }

    async getBackendStatus() {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/status`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to get backend status:', error);
        }
        return null;
    }

    showAbout() {
        dialog.showMessageBox(this.mainWindow, {
            type: 'info',
            title: 'About QuickDimmer',
            message: 'QuickDimmer',
            detail: 'Monitor Focus Dimming Tool\n\nAutomatically dims unfocused displays to help you focus on the active screen.\n\nVersion 1.0.0',
            buttons: ['OK']
        });
    }

    showNotification(title, body) {
        if (this.tray) {
            this.tray.displayBalloon({
                title: title,
                content: body,
                icon: path.join(__dirname, 'assets', 'icon.png')
            });
        }
    }

    async showErrorDialog(title, message) {
        return dialog.showMessageBox(this.mainWindow, {
            type: 'error',
            title: title,
            message: title,
            detail: message,
            buttons: ['OK']
        });
    }

    async quit() {
        console.log('Quitting QuickDimmer...');
        this.isQuitting = true;
        
        // Stop Python backend
        if (this.pythonProcess) {
            console.log('Stopping Python backend...');
            this.pythonProcess.kill('SIGTERM');
            
            // Give it a moment to clean up
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Force kill if still running
            if (this.pythonProcess && !this.pythonProcess.killed) {
                this.pythonProcess.kill('SIGKILL');
            }
        }
        
        app.quit();
    }
}

// Create and initialize the app
const quickDimmer = new QuickDimmerElectron();

// Handle app startup
app.whenReady().then(() => {
    quickDimmer.init().catch(console.error);
});

// Prevent default behavior on macOS
app.on('window-all-closed', () => {
    // Don't quit on macOS when all windows are closed
    if (process.platform !== 'darwin') {
        quickDimmer.quit();
    }
});

app.on('before-quit', () => {
    quickDimmer.quit();
}); 