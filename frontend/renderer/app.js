/**
 * QuickDimmer Frontend Application
 * Connects UI to Python backend via WebSocket and HTTP APIs
 */

class QuickDimmerUI {
    constructor() {
        // Configuration
        this.config = {
            backend: {
                host: 'localhost',
                port: 8080,
                reconnectDelay: 3000,
                maxReconnectAttempts: 10
            }
        };

        // State management
        this.state = {
            connected: false,
            enabled: false,
            opacity: 0.7,
            focusedDisplay: null,
            displays: [],
            connecting: false,
            backendReady: false
        };

        // WebSocket and connection management
        this.ws = null;
        this.reconnectCount = 0;
        this.reconnectTimer = null;
        this.statusUpdateTimer = null;

        // UI Elements
        this.elements = {};
        
        // Event handlers
        this.boundHandlers = new Map();

        console.log('QuickDimmer UI initialized');
    }

    async init() {
        console.log('Initializing QuickDimmer UI...');
        
        try {
            // Initialize UI elements
            this.initElements();
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Load saved settings
            this.loadSettings();
            
            // Show loading overlay
            this.showLoadingOverlay(true);
            
            // Connect to backend
            await this.connectToBackend();
            
            console.log('QuickDimmer UI initialization complete');
            
        } catch (error) {
            console.error('Failed to initialize UI:', error);
            this.showMessage('Connection Error', 'Failed to connect to QuickDimmer backend', 'error');
            this.showLoadingOverlay(false);
        }
    }

    initElements() {
        // Cache all UI elements
        this.elements = {
            // Connection status
            connectionStatus: document.getElementById('connectionStatus'),
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),
            
            // Power control
            toggleBtn: document.getElementById('toggleBtn'),
            powerText: document.getElementById('powerText'),
            powerDescription: document.getElementById('powerDescription'),
            
            // Opacity control
            opacitySlider: document.getElementById('opacitySlider'),
            opacityValue: document.getElementById('opacityValue'),
            presetBtns: document.querySelectorAll('.preset-btn'),
            
            // Display status
            displaysContainer: document.getElementById('displaysContainer'),
            refreshDisplays: document.getElementById('refreshDisplays'),
            
            // Status information
            currentStatus: document.getElementById('currentStatus'),
            focusedDisplay: document.getElementById('focusedDisplay'),
            totalDisplays: document.getElementById('totalDisplays'),
            activeOverlays: document.getElementById('activeOverlays'),
            
            // Settings
            toggleAdvanced: document.getElementById('toggleAdvanced'),
            advancedSettings: document.getElementById('advancedSettings'),
            keepWindowOpen: document.getElementById('keepWindowOpen'),
            debugMode: document.getElementById('debugMode'),
            startOnLogin: document.getElementById('startOnLogin'),
            resetSettings: document.getElementById('resetSettings'),
            exportSettings: document.getElementById('exportSettings'),
            
            // Footer
            aboutBtn: document.getElementById('aboutBtn'),
            helpBtn: document.getElementById('helpBtn'),
            
            // Per-monitor controls
            toggleMonitorSettings: document.getElementById('toggleMonitorSettings'),
            monitorSettings: document.getElementById('monitorSettings'),
            monitorControlsContainer: document.getElementById('monitorControlsContainer'),
            applyToAllMonitors: document.getElementById('applyToAllMonitors'),
            resetAllMonitors: document.getElementById('resetAllMonitors'),
            monitorControlTemplate: document.getElementById('monitorControlTemplate'),
            
            // Messages and loading
            messageContainer: document.getElementById('messageContainer'),
            messageContent: document.getElementById('messageContent'),
            messageIcon: document.getElementById('messageIcon'),
            messageText: document.getElementById('messageText'),
            messageClose: document.getElementById('messageClose'),
            loadingOverlay: document.getElementById('loadingOverlay')
        };

        console.log('UI elements initialized');
    }

    setupEventListeners() {
        // Power toggle
        this.addEventHandler(this.elements.toggleBtn, 'click', () => this.toggleDimming());
        
        // Opacity controls
        this.addEventHandler(this.elements.opacitySlider, 'input', (e) => this.handleOpacityChange(e));
        this.addEventHandler(this.elements.opacitySlider, 'change', (e) => this.setOpacity(parseFloat(e.target.value)));
        
        // Opacity presets
        this.elements.presetBtns.forEach(btn => {
            this.addEventHandler(btn, 'click', () => {
                const opacity = parseFloat(btn.dataset.opacity);
                this.setOpacity(opacity);
            });
        });
        
        // Display controls
        this.addEventHandler(this.elements.refreshDisplays, 'click', () => this.refreshDisplays());
        
        // Settings
        this.addEventHandler(this.elements.toggleAdvanced, 'click', () => this.toggleAdvancedSettings());
        this.addEventHandler(this.elements.keepWindowOpen, 'change', (e) => this.saveSetting('keepWindowOpen', e.target.checked));
        this.addEventHandler(this.elements.debugMode, 'change', (e) => this.saveSetting('debugMode', e.target.checked));
        this.addEventHandler(this.elements.resetSettings, 'click', () => this.resetSettings());
        this.addEventHandler(this.elements.exportSettings, 'click', () => this.exportSettings());
        
        // Per-monitor controls
        this.addEventHandler(this.elements.toggleMonitorSettings, 'click', () => this.toggleMonitorSettings());
        this.addEventHandler(this.elements.applyToAllMonitors, 'click', () => this.applyToAllMonitors());
        this.addEventHandler(this.elements.resetAllMonitors, 'click', () => this.resetAllMonitors());
        
        // Footer actions
        this.addEventHandler(this.elements.aboutBtn, 'click', () => this.showAbout());
        this.addEventHandler(this.elements.helpBtn, 'click', () => this.showHelp());
        
        // Message close
        this.addEventHandler(this.elements.messageClose, 'click', () => this.hideMessage());
        
        // Global keyboard shortcuts
        this.addEventHandler(document, 'keydown', (e) => this.handleKeyboard(e));

        console.log('Event listeners setup complete');
    }

    addEventHandler(element, event, handler) {
        if (element) {
            element.addEventListener(event, handler);
            // Store for cleanup if needed
            if (!this.boundHandlers.has(element)) {
                this.boundHandlers.set(element, []);
            }
            this.boundHandlers.get(element).push({ event, handler });
        }
    }

    async connectToBackend() {
        try {
            this.updateConnectionStatus('connecting', 'Connecting...');
            
            // First, try HTTP connection to ensure backend is ready
            await this.waitForBackendReady();
            
            // Then establish WebSocket connection
            await this.connectWebSocket();
            
            // Initial data load
            await this.loadInitialData();
            
            this.showLoadingOverlay(false);
            
        } catch (error) {
            console.error('Backend connection failed:', error);
            this.updateConnectionStatus('disconnected', 'Connection failed');
            this.handleConnectionError();
        }
    }

    async waitForBackendReady() {
        const maxAttempts = 20;
        const delayMs = 500;
        
        for (let i = 0; i < maxAttempts; i++) {
            try {
                const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/status`);
                
                if (response.ok) {
                    console.log('Backend HTTP API is ready');
                    this.state.backendReady = true;
                    return;
                }
            } catch (error) {
                // Backend not ready yet
            }
            
            await this.delay(delayMs);
        }
        
        throw new Error('Backend HTTP API not responding');
    }

    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            try {
                const wsUrl = `ws://${this.config.backend.host}:${this.config.backend.port}/ws`;
                console.log(`Connecting to WebSocket: ${wsUrl}`);
                
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.state.connected = true;
                    this.reconnectCount = 0;
                    this.updateConnectionStatus('connected', 'Connected');
                    resolve();
                };
                
                this.ws.onmessage = (event) => {
                    this.handleWebSocketMessage(event);
                };
                
                this.ws.onclose = (event) => {
                    console.log('WebSocket disconnected:', event.code, event.reason);
                    this.state.connected = false;
                    this.updateConnectionStatus('disconnected', 'Disconnected');
                    
                    if (!event.wasClean) {
                        this.handleWebSocketDisconnect();
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(error);
                };
                
                // Timeout for connection
                setTimeout(() => {
                    if (this.ws.readyState !== WebSocket.OPEN) {
                        reject(new Error('WebSocket connection timeout'));
                    }
                }, 5000);
                
            } catch (error) {
                reject(error);
            }
        });
    }

    handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
                case 'initial_status':
                    this.updateStateFromBackend(data.data);
                    break;
                    
                case 'status_update':
                    this.updateStateFromBackend(data.data);
                    break;
                    
                case 'enabled_changed':
                    this.state.enabled = data.enabled;
                    this.updatePowerUI();
                    this.showMessage('Status Update', `Dimming ${data.enabled ? 'enabled' : 'disabled'}`, 'success');
                    break;
                    
                case 'opacity_changed':
                    this.state.opacity = data.opacity;
                    this.updateOpacityUI();
                    if (data.display_id) {
                        this.showMessage('Monitor Update', `Display ${data.display_id} opacity: ${Math.round(data.opacity * 100)}%`, 'success');
                    } else {
                        this.showMessage('Opacity Update', `Global opacity: ${Math.round(data.opacity * 100)}%`, 'success');
                    }
                    break;
                    
                case 'monitor_opacity_changed':
                    // Update specific monitor opacity in UI
                    this.updateMonitorOpacityUI(data.display_id, data.opacity);
                    this.showMessage('Monitor Update', `Display ${data.display_id} opacity: ${Math.round(data.opacity * 100)}%`, 'success');
                    break;
                    
                case 'monitor_enabled_changed':
                    // Update specific monitor enabled state in UI
                    this.updateMonitorEnabledUI(data.display_id, data.enabled);
                    this.showMessage('Monitor Update', `Display ${data.display_id} ${data.enabled ? 'enabled' : 'disabled'}`, 'success');
                    break;
                    
                case 'focus_changed':
                    this.state.focusedDisplay = data.focused_display;
                    this.updateStatusUI();
                    this.updateDisplaysUI();
                    // Refresh monitor settings to update status
                    if (this.elements.monitorSettings.style.display !== 'none') {
                        this.loadMonitorSettings();
                    }
                    break;
                    
                case 'pong':
                    // Heartbeat response
                    break;
                    
                case 'error':
                    console.error('Backend error:', data.message);
                    this.showMessage('Backend Error', data.message, 'error');
                    break;
                    
                default:
                    console.log('Unknown WebSocket message type:', data.type);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }
    
    updateMonitorOpacityUI(displayId, opacity) {
        const monitorControl = this.elements.monitorControlsContainer.querySelector(`[data-display-id="${displayId}"]`);
        if (monitorControl) {
            const slider = monitorControl.querySelector('.monitor-opacity-slider');
            const value = monitorControl.querySelector('.monitor-opacity-value');
            
            if (slider) slider.value = opacity;
            if (value) value.textContent = `${Math.round(opacity * 100)}%`;
        }
        
        // Update local state
        if (this.state.monitorSettings[displayId]) {
            this.state.monitorSettings[displayId].opacity = opacity;
        }
    }
    
    updateMonitorEnabledUI(displayId, enabled) {
        const monitorControl = this.elements.monitorControlsContainer.querySelector(`[data-display-id="${displayId}"]`);
        if (monitorControl) {
            const toggle = monitorControl.querySelector('.monitor-enabled');
            if (toggle) toggle.checked = enabled;
        }
        
        // Update local state
        if (this.state.monitorSettings[displayId]) {
            this.state.monitorSettings[displayId].enabled = enabled;
        }
    }

    handleWebSocketDisconnect() {
        if (this.reconnectCount < this.config.backend.maxReconnectAttempts) {
            this.reconnectCount++;
            console.log(`Attempting to reconnect (${this.reconnectCount}/${this.config.backend.maxReconnectAttempts})`);
            
            this.updateConnectionStatus('connecting', 'Reconnecting...');
            
            this.reconnectTimer = setTimeout(() => {
                this.connectWebSocket().catch(() => {
                    this.handleWebSocketDisconnect();
                });
            }, this.config.backend.reconnectDelay);
        } else {
            console.error('Max reconnection attempts reached');
            this.updateConnectionStatus('disconnected', 'Connection lost');
            this.showMessage('Connection Lost', 'Unable to reconnect to backend', 'error');
        }
    }

    async loadInitialData() {
        try {
            // Load status
            const status = await this.fetchBackendStatus();
            if (status) {
                this.updateStateFromBackend(status);
            }
            
            // Load displays
            await this.loadDisplays();
            
            // Load monitor settings
            await this.loadMonitorSettings();
            
            // Enable UI controls
            this.enableControls(true);
            
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showMessage('Data Load Error', 'Failed to load initial data', 'error');
        }
    }

    async fetchBackendStatus() {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/status`);
            
            if (response.ok) {
                return await response.json();
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error fetching backend status:', error);
            return null;
        }
    }

    async loadDisplays() {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/displays`);
            
            if (response.ok) {
                const data = await response.json();
                this.state.displays = data.displays || [];
                this.updateDisplaysUI();
            }
        } catch (error) {
            console.error('Error loading displays:', error);
        }
    }

    async loadMonitorSettings() {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/monitors`);
            if (response.ok) {
                const data = await response.json();
                this.state.monitorSettings = data.monitors || {};
                this.updateMonitorSettingsUI();
            }
        } catch (error) {
            console.error('Error loading monitor settings:', error);
        }
    }

    updateStateFromBackend(backendState) {
        this.state.enabled = backendState.enabled || false;
        this.state.opacity = backendState.opacity || 0.7;
        this.state.focusedDisplay = backendState.focused_display;
        
        // Update monitor settings if available
        if (backendState.monitor_settings) {
            this.state.monitorSettings = backendState.monitor_settings;
            this.updateMonitorSettingsUI();
        }
        
        // Update all UI components
        this.updatePowerUI();
        this.updateOpacityUI();
        this.updateStatusUI();
    }

    // UI Update Methods
    updateConnectionStatus(status, text) {
        this.elements.statusDot.className = `status-dot ${status}`;
        this.elements.statusText.textContent = text;
    }

    updatePowerUI() {
        const btn = this.elements.toggleBtn;
        const text = this.elements.powerText;
        const desc = this.elements.powerDescription;
        
        if (this.state.enabled) {
            btn.classList.add('enabled');
            text.textContent = 'Disable Dimming';
            desc.textContent = 'Currently dimming unfocused displays';
        } else {
            btn.classList.remove('enabled');
            text.textContent = 'Enable Dimming';
            desc.textContent = 'Automatically dims unfocused displays';
        }
    }

    updateOpacityUI() {
        const slider = this.elements.opacitySlider;
        const value = this.elements.opacityValue;
        
        slider.value = this.state.opacity;
        value.textContent = `${Math.round(this.state.opacity * 100)}%`;
        
        // Update preset buttons
        this.elements.presetBtns.forEach(btn => {
            const presetOpacity = parseFloat(btn.dataset.opacity);
            if (Math.abs(presetOpacity - this.state.opacity) < 0.05) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    updateStatusUI() {
        this.elements.currentStatus.textContent = this.state.enabled ? 'Enabled' : 'Disabled';
        this.elements.focusedDisplay.textContent = this.state.focusedDisplay ? `Display ${this.state.focusedDisplay}` : 'Unknown';
        this.elements.totalDisplays.textContent = this.state.displays.length.toString();
        
        const activeOverlays = this.state.displays.filter(d => d.has_overlay).length;
        this.elements.activeOverlays.textContent = activeOverlays.toString();
    }

    updateDisplaysUI() {
        const container = this.elements.displaysContainer;
        
        if (this.state.displays.length === 0) {
            container.innerHTML = `
                <div class="loading-displays">
                    <span>No display information available</span>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.state.displays.map(display => `
            <div class="display-item ${display.is_focused ? 'focused' : ''} ${display.has_overlay ? 'dimmed' : ''}">
                <div class="display-info">
                    <span class="display-name">Display ${display.id}</span>
                    <span class="display-bounds">${display.bounds.width}×${display.bounds.height}</span>
                </div>
                <span class="display-status ${display.is_focused ? 'focused' : (display.has_overlay ? 'dimmed' : '')}">
                    ${display.is_focused ? 'Focused' : (display.has_overlay ? 'Dimmed' : 'Clear')}
                </span>
            </div>
        `).join('');
    }

    updateMonitorSettingsUI() {
        const container = this.elements.monitorControlsContainer;
        if (!container) return;

        // Clear loading message
        container.innerHTML = '';

        const monitors = this.state.monitorSettings;
        if (Object.keys(monitors).length === 0) {
            container.innerHTML = `
                <div class="no-monitors-message">
                    No monitor settings available
                </div>
            `;
            return;
        }

        // Create controls for each monitor
        Object.entries(monitors).forEach(([displayId, settings]) => {
            const monitorControl = this.createMonitorControl(displayId, settings);
            container.appendChild(monitorControl);
        });
    }

    createMonitorControl(displayId, settings) {
        const template = this.elements.monitorControlTemplate.content.cloneNode(true);
        const control = template.querySelector('.monitor-control');
        
        // Set display ID
        control.setAttribute('data-display-id', displayId);
        
        // Set monitor info
        const monitorId = control.querySelector('.monitor-id');
        const monitorResolution = control.querySelector('.monitor-resolution');
        const monitorStatus = control.querySelector('.monitor-status');
        
        monitorId.textContent = displayId;
        if (settings.bounds) {
            monitorResolution.textContent = `${settings.bounds.width}×${settings.bounds.height}`;
        }
        
        let statusText = [];
        if (settings.is_focused) statusText.push('Focused');
        if (settings.has_overlay) statusText.push('Dimmed');
        if (!settings.enabled) statusText.push('Disabled');
        monitorStatus.textContent = statusText.length > 0 ? statusText.join(' • ') : 'Ready';
        
        // Set up enabled toggle
        const enabledToggle = control.querySelector('.monitor-enabled');
        enabledToggle.checked = settings.enabled;
        enabledToggle.addEventListener('change', (e) => {
            this.setMonitorEnabled(displayId, e.target.checked);
        });
        
        // Set up opacity slider
        const opacitySlider = control.querySelector('.monitor-opacity-slider');
        const opacityValue = control.querySelector('.monitor-opacity-value');
        
        opacitySlider.value = settings.opacity;
        opacityValue.textContent = `${Math.round(settings.opacity * 100)}%`;
        
        opacitySlider.addEventListener('input', (e) => {
            const opacity = parseFloat(e.target.value);
            opacityValue.textContent = `${Math.round(opacity * 100)}%`;
        });
        
        opacitySlider.addEventListener('change', (e) => {
            this.setMonitorOpacity(displayId, parseFloat(e.target.value));
        });
        
        // Set up preset buttons
        const presetButtons = control.querySelectorAll('.monitor-preset-btn');
        presetButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const opacity = parseFloat(btn.dataset.opacity);
                this.setMonitorOpacity(displayId, opacity);
            });
        });
        
        return control;
    }

    async setMonitorOpacity(displayId, opacity) {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/monitor/${displayId}/opacity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ opacity })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Response handled by WebSocket message
            
        } catch (error) {
            console.error('Error setting monitor opacity:', error);
            this.showMessage('Control Error', `Failed to set monitor ${displayId} opacity`, 'error');
        }
    }

    async setMonitorEnabled(displayId, enabled) {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/monitor/${displayId}/enabled`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ enabled })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Response handled by WebSocket message
            
        } catch (error) {
            console.error('Error setting monitor enabled:', error);
            this.showMessage('Control Error', `Failed to ${enabled ? 'enable' : 'disable'} monitor ${displayId}`, 'error');
        }
    }

    async applyToAllMonitors() {
        try {
            const currentOpacity = this.state.opacity;
            
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/opacity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ opacity: currentOpacity })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.showMessage('Settings Applied', 'Applied current opacity to all monitors', 'success');
            
        } catch (error) {
            console.error('Error applying to all monitors:', error);
            this.showMessage('Error', 'Failed to apply settings to all monitors', 'error');
        }
    }

    async resetAllMonitors() {
        try {
            // Reset to default opacity (70%)
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/opacity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ opacity: 0.7 })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.showMessage('Settings Reset', 'Reset all monitors to default settings', 'success');
            
        } catch (error) {
            console.error('Error resetting all monitors:', error);
            this.showMessage('Error', 'Failed to reset all monitor settings', 'error');
        }
    }

    toggleMonitorSettings() {
        const isVisible = this.elements.monitorSettings.style.display !== 'none';
        this.elements.monitorSettings.style.display = isVisible ? 'none' : 'block';
        this.elements.toggleMonitorSettings.textContent = isVisible ? '▼' : '▲';
        
        if (!isVisible) {
            // Refresh monitor settings when showing
            this.loadMonitorSettings();
        }
    }

    enableControls(enabled) {
        const controls = [
            this.elements.toggleBtn,
            this.elements.opacitySlider,
            this.elements.refreshDisplays,
            this.elements.applyToAllMonitors,
            this.elements.resetAllMonitors,
            ...this.elements.presetBtns
        ];
        
        controls.forEach(control => {
            if (control) {
                control.disabled = !enabled;
            }
        });
        
        // Enable/disable individual monitor controls
        const monitorControls = this.elements.monitorControlsContainer.querySelectorAll('input, button');
        monitorControls.forEach(control => {
            control.disabled = !enabled;
        });
    }

    // User Interaction Handlers
    async toggleDimming() {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/toggle`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Response handled by WebSocket message
            
        } catch (error) {
            console.error('Error toggling dimming:', error);
            this.showMessage('Control Error', 'Failed to toggle dimming', 'error');
        }
    }

    handleOpacityChange(event) {
        const opacity = parseFloat(event.target.value);
        this.elements.opacityValue.textContent = `${Math.round(opacity * 100)}%`;
        
        // Update preset button states immediately for responsiveness
        this.elements.presetBtns.forEach(btn => {
            const presetOpacity = parseFloat(btn.dataset.opacity);
            if (Math.abs(presetOpacity - opacity) < 0.05) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    async setOpacity(opacity) {
        try {
            const response = await fetch(`http://${this.config.backend.host}:${this.config.backend.port}/opacity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ opacity })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Update state immediately for responsiveness
            this.state.opacity = opacity;
            this.updateOpacityUI();
            
        } catch (error) {
            console.error('Error setting opacity:', error);
            this.showMessage('Control Error', 'Failed to set opacity', 'error');
        }
    }

    async refreshDisplays() {
        try {
            await this.loadDisplays();
            this.showMessage('Success', 'Display information refreshed', 'success');
        } catch (error) {
            console.error('Error refreshing displays:', error);
            this.showMessage('Refresh Error', 'Failed to refresh displays', 'error');
        }
    }

    toggleAdvancedSettings() {
        const settings = this.elements.advancedSettings;
        const btn = this.elements.toggleAdvanced;
        
        if (settings.style.display === 'none') {
            settings.style.display = 'block';
            btn.textContent = '▲';
        } else {
            settings.style.display = 'none';
            btn.textContent = '▼';
        }
    }

    handleKeyboard(event) {
        // Cmd/Ctrl + D: Toggle dimming
        if ((event.metaKey || event.ctrlKey) && event.key === 'd') {
            event.preventDefault();
            this.toggleDimming();
        }
        
        // Escape: Hide message or close window
        if (event.key === 'Escape') {
            if (this.elements.messageContainer.style.display !== 'none') {
                this.hideMessage();
            }
        }
    }

    // Settings Management
    loadSettings() {
        try {
            const keepWindowOpen = localStorage.getItem('keepWindowOpen') === 'true';
            const debugMode = localStorage.getItem('debugMode') === 'true';
            
            this.elements.keepWindowOpen.checked = keepWindowOpen;
            this.elements.debugMode.checked = debugMode;
            
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }

    saveSetting(key, value) {
        try {
            localStorage.setItem(key, value.toString());
            console.log(`Setting saved: ${key} = ${value}`);
        } catch (error) {
            console.error('Error saving setting:', error);
        }
    }

    resetSettings() {
        try {
            localStorage.clear();
            this.loadSettings();
            this.showMessage('Settings Reset', 'All settings have been reset to defaults', 'success');
        } catch (error) {
            console.error('Error resetting settings:', error);
            this.showMessage('Error', 'Failed to reset settings', 'error');
        }
    }

    exportSettings() {
        try {
            const settings = {
                keepWindowOpen: this.elements.keepWindowOpen.checked,
                debugMode: this.elements.debugMode.checked,
                opacity: this.state.opacity,
                exportDate: new Date().toISOString()
            };
            
            const dataStr = JSON.stringify(settings, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            
            const exportFileDefaultName = 'quickdimmer-settings.json';
            
            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportFileDefaultName);
            linkElement.click();
            
            this.showMessage('Export Complete', 'Settings exported successfully', 'success');
            
        } catch (error) {
            console.error('Error exporting settings:', error);
            this.showMessage('Export Error', 'Failed to export settings', 'error');
        }
    }

    // UI Helper Methods
    showMessage(title, text, type = 'info') {
        const container = this.elements.messageContainer;
        const content = this.elements.messageContent;
        const icon = this.elements.messageIcon;
        const textEl = this.elements.messageText;
        
        // Set icon based on type
        const icons = {
            info: 'ℹ',
            success: '✓',
            warning: '⚠',
            error: '✗'
        };
        
        icon.textContent = icons[type] || icons.info;
        textEl.textContent = text;
        
        // Set message class
        content.className = `message ${type}`;
        
        // Show message
        container.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            this.hideMessage();
        }, 5000);
    }

    hideMessage() {
        this.elements.messageContainer.style.display = 'none';
    }

    showLoadingOverlay(show) {
        this.elements.loadingOverlay.style.display = show ? 'flex' : 'none';
    }

    showAbout() {
        this.showMessage('About QuickDimmer', 'Version 1.0.0 - Monitor Focus Dimming Tool for macOS', 'info');
    }

    showHelp() {
        this.showMessage('Help', 'Use Cmd+D to toggle dimming. Adjust opacity with the slider or preset buttons.', 'info');
    }

    handleConnectionError() {
        this.enableControls(false);
        this.showLoadingOverlay(false);
        
        // Show retry option
        const retryBtn = document.createElement('button');
        retryBtn.textContent = 'Retry Connection';
        retryBtn.className = 'action-btn';
        retryBtn.onclick = () => {
            retryBtn.remove();
            this.reconnectCount = 0;
            this.connectToBackend();
        };
        
        this.elements.displaysContainer.innerHTML = `
            <div class="loading-displays">
                <span>Backend connection failed</span>
            </div>
        `;
        this.elements.displaysContainer.appendChild(retryBtn);
    }

    // Utility Methods
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    cleanup() {
        // Clean up WebSocket
        if (this.ws) {
            this.ws.close();
        }
        
        // Clear timers
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        if (this.statusUpdateTimer) {
            clearInterval(this.statusUpdateTimer);
        }
        
        // Remove event listeners
        this.boundHandlers.forEach((handlers, element) => {
            handlers.forEach(({ event, handler }) => {
                element.removeEventListener(event, handler);
            });
        });
        this.boundHandlers.clear();
        
        console.log('QuickDimmer UI cleanup complete');
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing QuickDimmer UI...');
    
    window.quickDimmerUI = new QuickDimmerUI();
    window.quickDimmerUI.init().catch(console.error);
    
    // Cleanup on window unload
    window.addEventListener('beforeunload', () => {
        if (window.quickDimmerUI) {
            window.quickDimmerUI.cleanup();
        }
    });
});

// Handle window focus/blur for connection management
window.addEventListener('focus', () => {
    if (window.quickDimmerUI && !window.quickDimmerUI.state.connected) {
        console.log('Window focused, attempting to reconnect...');
        window.quickDimmerUI.connectToBackend();
    }
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    if (window.quickDimmerUI) {
        window.quickDimmerUI.showMessage('Application Error', 'An unexpected error occurred', 'error');
    }
}); 