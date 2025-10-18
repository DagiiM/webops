/**
 * Workflow Canvas - Custom Canvas Implementation for Visual Workflow Builder
 *
 * Features:
 * - Drag & drop nodes from palette
 * - Pan and zoom canvas
 * - Connect nodes with curved connections
 * - Select and edit nodes
 * - Undo/redo support
 * - Minimap navigation
 */

class WorkflowCanvas {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');

        // Canvas state
        this.nodes = [];
        this.connections = [];
        this.selectedNode = null;
        this.selectedConnection = null;

        // View state
        this.offset = { x: 0, y: 0 };
        this.zoom = 1;
        this.isDragging = false;
        this.isPanning = false;
        this.dragStart = { x: 0, y: 0 };
        
        // UI state
        this.showGrid = true;

        // Connection state
        this.isConnecting = false;
        this.connectionStart = null;
        this.connectionEnd = { x: 0, y: 0 };

        // History for undo/redo
        this.history = [];
        this.historyIndex = -1;

        // Node counter for unique IDs
        this.nodeIdCounter = 1;

        // Minimap setup
        this.minimapContainer = document.getElementById('minimap');
        this.minimapCanvas = document.getElementById('minimap-canvas');
        this.minimapCtx = this.minimapCanvas.getContext('2d');
        this.minimapVisible = false;
        this.setupMinimap();

        // Initialize
        this.init();
        this.setupEventListeners();
        this.loadWorkflowData();
        this.initPaletteState();
        this.setupToolbarOverflowHandling();
        this.initSidebarState();
        this.render();
    }

    init() {
        // Set canvas size
        this.resize();
        window.addEventListener('resize', () => this.resize());
        
        // Set minimap size
        this.resizeMinimap();
    }

    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.render();
    }
    
    resizeMinimap() {
        if (!this.minimapCanvas) return;
        
        this.minimapCanvas.width = 220;
        this.minimapCanvas.height = 160;
        this.renderMinimap();
    }
    
    setupMinimap() {
        if (!this.minimapCanvas) return;
        
        this.minimapCanvas.addEventListener('click', (e) => {
            const rect = this.minimapCanvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) / this.minimapCanvas.width;
            const y = (e.clientY - rect.top) / this.minimapCanvas.height;
            
            // Calculate content bounds
            const bounds = this.getContentBounds();
            if (!bounds) return;
            
            // Center view on clicked position
            const targetX = bounds.minX + x * (bounds.maxX - bounds.minX);
            const targetY = bounds.minY + y * (bounds.maxY - bounds.minY);
            
            this.offset.x = this.canvas.width / 2 - targetX * this.zoom;
            this.offset.y = this.canvas.height / 2 - targetY * this.zoom;
            
            this.render();
        });
        
        // Initially hide minimap if no nodes
        this.updateMinimapVisibility();
    }
    
    getContentBounds() {
        if (this.nodes.length === 0) return null;
        
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        this.nodes.forEach(node => {
            minX = Math.min(minX, node.x);
            minY = Math.min(minY, node.y);
            maxX = Math.max(maxX, node.x + node.width);
            maxY = Math.max(maxY, node.y + node.height);
        });
        
        return { minX, minY, maxX, maxY };
    }
    
    updateMinimapVisibility() {
        const shouldShow = this.nodes.length > 0;
        
        if (shouldShow !== this.minimapVisible) {
            this.minimapVisible = shouldShow;
            this.minimapContainer.style.display = shouldShow ? 'block' : 'none';
        }
    }
    
    renderMinimap() {
        if (!this.minimapCanvas || !this.minimapVisible) return;
        
        const ctx = this.minimapCtx;
        const width = this.minimapCanvas.width;
        const height = this.minimapCanvas.height;
        
        // Clear minimap
        ctx.clearRect(0, 0, width, height);
        
        // Get content bounds
        const bounds = this.getContentBounds();
        if (!bounds) return;
        
        // Calculate scale to fit content in minimap
        const padding = 20;
        const scaleX = (width - padding * 2) / (bounds.maxX - bounds.minX || 100);
        const scaleY = (height - padding * 2) / (bounds.maxY - bounds.minY || 100);
        const scale = Math.min(scaleX, scaleY);
        
        // Calculate offset to center content
        const offsetX = (width - (bounds.maxX - bounds.minX) * scale) / 2;
        const offsetY = (height - (bounds.maxY - bounds.minY) * scale) / 2;
        
        // Draw background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
        ctx.fillRect(0, 0, width, height);
        
        // Draw connections
        ctx.strokeStyle = 'rgba(107, 114, 128, 0.5)';
        ctx.lineWidth = 1;
        
        this.connections.forEach(conn => {
            const startX = offsetX + (conn.source.x - bounds.minX) * scale + conn.source.width * scale;
            const startY = offsetY + (conn.source.y - bounds.minY) * scale + conn.source.height * scale / 2;
            const endX = offsetX + (conn.target.x - bounds.minX) * scale;
            const endY = offsetY + (conn.target.y - bounds.minY) * scale + conn.target.height * scale / 2;
            
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
            ctx.stroke();
        });
        
        // Draw nodes
        this.nodes.forEach(node => {
            const x = offsetX + (node.x - bounds.minX) * scale;
            const y = offsetY + (node.y - bounds.minY) * scale;
            const nodeWidth = node.width * scale;
            const nodeHeight = node.height * scale;
            
            // Node background
            ctx.fillStyle = node === this.selectedNode ?
                'rgba(59, 130, 246, 0.3)' : 'rgba(255, 255, 255, 0.8)';
            ctx.fillRect(x, y, nodeWidth, nodeHeight);
            
            // Node border
            ctx.strokeStyle = this.getNodeColor(node.type);
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y, nodeWidth, nodeHeight);
        });
        
        // Draw viewport indicator
        const viewX = offsetX + (-this.offset.x / this.zoom - bounds.minX) * scale;
        const viewY = offsetY + (-this.offset.y / this.zoom - bounds.minY) * scale;
        const viewWidth = (this.canvas.width / this.zoom) * scale;
        const viewHeight = (this.canvas.height / this.zoom) * scale;
        
        ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
        ctx.lineWidth = 2;
        ctx.strokeRect(viewX, viewY, viewWidth, viewHeight);
        
        // Draw viewport corners
        ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
        const cornerSize = 4;
        ctx.fillRect(viewX - cornerSize/2, viewY - cornerSize/2, cornerSize, cornerSize);
        ctx.fillRect(viewX + viewWidth - cornerSize/2, viewY - cornerSize/2, cornerSize, cornerSize);
        ctx.fillRect(viewX - cornerSize/2, viewY + viewHeight - cornerSize/2, cornerSize, cornerSize);
        ctx.fillRect(viewX + viewWidth - cornerSize/2, viewY + viewHeight - cornerSize/2, cornerSize, cornerSize);
    }

    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));

        // Context menu
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        // Keyboard events
        document.addEventListener('keydown', (e) => this.onKeyDown(e));

        // Toolbar buttons
        document.getElementById('btn-save').addEventListener('click', () => this.saveWorkflow());
        document.getElementById('btn-execute').addEventListener('click', () => this.executeWorkflow());
        document.getElementById('btn-undo').addEventListener('click', () => this.undo());
        document.getElementById('btn-redo').addEventListener('click', () => this.redo());
        document.getElementById('btn-zoom-in').addEventListener('click', () => this.zoomIn());
        document.getElementById('btn-zoom-out').addEventListener('click', () => this.zoomOut());
        document.getElementById('btn-fit-view').addEventListener('click', () => this.fitView());

        // Palette drag and drop
        this.setupPaletteDragDrop();

        // Properties panel
        document.getElementById('btn-close-properties').addEventListener('click', () => {
            this.selectedNode = null;
            this.render();
            this.hidePropertiesPanel();
        });
        
        // Properties panel toggle
        document.getElementById('properties-toggle').addEventListener('click', () => {
            this.togglePropertiesPanel();
        });
        
        // Properties panel size toggle
        document.getElementById('btn-toggle-properties-size').addEventListener('click', () => {
            this.togglePropertiesPanelMinimize();
        });
        
        // Grid toggle
        document.getElementById('btn-toggle-grid').addEventListener('click', () => {
            this.toggleGrid();
        });
        
        // Palette toggle
        document.getElementById('btn-toggle-palette').addEventListener('click', () => {
            this.togglePalette();
        });
        
        // Toolbar dropdown
        document.getElementById('btn-more').addEventListener('click', () => {
            this.toggleToolbarDropdown();
        });
        
        // Toolbar dropdown items
        document.getElementById('btn-export').addEventListener('click', () => {
            this.exportWorkflow();
        });
        
        document.getElementById('btn-import').addEventListener('click', () => {
            this.importWorkflow();
        });
        
        document.getElementById('btn-duplicate').addEventListener('click', () => {
            this.duplicateWorkflow();
        });
        
        document.getElementById('btn-clear').addEventListener('click', () => {
            this.clearCanvas();
        });
        
        document.getElementById('btn-settings').addEventListener('click', () => {
            this.openSettings();
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('toolbar-dropdown');
            const moreButton = document.getElementById('btn-more');
            
            if (!dropdown.contains(e.target) && e.target !== moreButton) {
                dropdown.classList.remove('webops-toolbar-dropdown--open');
                moreButton.setAttribute('aria-expanded', 'false');
            }
        });
    }
    
    initSidebarState() {
        // Restore sidebar state from localStorage
        const isMinimized = localStorage.getItem('sidebar-minimized') === 'true';
        const sidebar = document.querySelector('.webops-sidebar');
        const mainContent = document.querySelector('.webops-main-content');
        
        if (isMinimized && sidebar && mainContent) {
            sidebar.classList.add('minimized');
            mainContent.classList.add('expanded');
        }
        
        // Setup sidebar toggle
        const toggleBtn = document.querySelector('.sidebar-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                this.toggleSidebar();
            });
        }
    }
    
    toggleSidebar() {
        const sidebar = document.querySelector('.webops-sidebar');
        const mainContent = document.querySelector('.webops-main-content');
        
        if (!sidebar || !mainContent) return;
        
        sidebar.classList.toggle('minimized');
        mainContent.classList.toggle('expanded');
        const isMinimized = sidebar.classList.contains('minimized');
        localStorage.setItem('sidebar-minimized', isMinimized);
        
        // Resize canvas after sidebar toggle
        setTimeout(() => {
            this.resize();
            this.render();
        }, 300); // Wait for transition to complete
    }

    setupPaletteDragDrop() {
        const paletteNodes = document.querySelectorAll('.webops-palette-node');

        paletteNodes.forEach(node => {
            node.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('nodeType', node.dataset.nodeType);
                e.dataTransfer.effectAllowed = 'copy';
            });
        });

        this.canvas.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        });

        this.canvas.addEventListener('drop', (e) => {
            e.preventDefault();
            const nodeType = e.dataTransfer.getData('nodeType');
            if (nodeType) {
                const rect = this.canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left - this.offset.x) / this.zoom;
                const y = (e.clientY - rect.top - this.offset.y) / this.zoom;
                this.addNode(nodeType, x, y);
            }
        });
    }

    loadWorkflowData() {
        const dataScript = document.getElementById('workflow-data');
        if (dataScript) {
            const data = JSON.parse(dataScript.textContent);
            this.workflowId = data.workflow_id;

            // Load nodes
            data.nodes.forEach(nodeData => {
                this.nodes.push({
                    id: nodeData.id,
                    type: nodeData.type,
                    label: nodeData.label,
                    x: nodeData.position.x,
                    y: nodeData.position.y,
                    config: nodeData.config || {},
                    enabled: nodeData.enabled !== false,
                    width: 180,
                    height: 60
                });
            });

            // Load connections
            data.connections.forEach(connData => {
                const source = this.nodes.find(n => n.id === connData.source);
                const target = this.nodes.find(n => n.id === connData.target);
                if (source && target) {
                    this.connections.push({
                        source: source,
                        target: target,
                        sourceHandle: connData.sourceHandle || 'output',
                        targetHandle: connData.targetHandle || 'input'
                    });
                }
            });

            // Update node counter
            const maxId = Math.max(...this.nodes.map(n => {
                const match = n.id.match(/node-(\d+)/);
                return match ? parseInt(match[1]) : 0;
            }), 0);
            this.nodeIdCounter = maxId + 1;
        }
    }

    addNode(type, x, y) {
        const node = {
            id: `node-${this.nodeIdCounter++}`,
            type: type,
            label: this.getNodeLabel(type),
            x: x,
            y: y,
            config: {},
            enabled: true,
            width: 180,
            height: 60
        };

        this.nodes.push(node);
        this.saveHistory();
        this.updateMinimapVisibility();
        this.render();
    }

    getNodeLabel(type) {
        const labels = {
            'DATA_SOURCE_GOOGLE_DOCS': 'Google Docs',
            'DATA_SOURCE_GOOGLE_SHEETS': 'Google Sheets',
            'DATA_SOURCE_WEBHOOK': 'Webhook Input',
            'DATA_SOURCE_DATABASE': 'Database Query',
            'DATA_SOURCE_API': 'API Request',
            'DATA_SOURCE_CUSTOM_URL': 'Custom URL',
            'PROCESSOR_LLM': 'LLM Processor',
            'PROCESSOR_TRANSFORM': 'Transform',
            'PROCESSOR_FILTER': 'Filter',
            'PROCESSOR_AGGREGATE': 'Aggregate',
            'PROCESSOR_CODE': 'Custom Code',
            'OUTPUT_EMAIL': 'Send Email',
            'OUTPUT_WEBHOOK': 'Webhook Output',
            'OUTPUT_DATABASE': 'Database Write',
            'OUTPUT_SLACK': 'Slack Message',
            'OUTPUT_NOTIFICATION': 'Notification',
            'CONTROL_CONDITION': 'Condition',
            'CONTROL_LOOP': 'Loop',
            'CONTROL_DELAY': 'Delay'
        };
        return labels[type] || type;
    }

    getNodeColor(type) {
        if (type.startsWith('DATA_SOURCE_')) return '#3B82F6'; // Blue
        if (type.startsWith('PROCESSOR_')) return '#8B5CF6'; // Purple
        if (type.startsWith('OUTPUT_')) return '#10B981'; // Green
        if (type.startsWith('CONTROL_')) return '#F59E0B'; // Orange
        return '#6B7280'; // Gray
    }

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.offset.x) / this.zoom;
        const y = (e.clientY - rect.top - this.offset.y) / this.zoom;

        // Check if clicking on a node
        const clickedNode = this.getNodeAt(x, y);

        if (e.button === 0) { // Left click
            if (clickedNode) {
                // Check if clicking on connection handle
                if (this.isClickOnOutputHandle(clickedNode, x, y)) {
                    this.isConnecting = true;
                    this.connectionStart = clickedNode;
                    this.connectionEnd = { x, y };
                } else {
                    // Select and start dragging node
                    this.selectedNode = clickedNode;
                    this.isDragging = true;
                    this.dragStart = { x: x - clickedNode.x, y: y - clickedNode.y };
                    this.showPropertiesPanel(clickedNode);
                }
            } else {
                // Start panning
                this.isPanning = true;
                this.dragStart = { x: e.clientX - this.offset.x, y: e.clientY - this.offset.y };
                this.selectedNode = null;
                this.hidePropertiesPanel();
            }
        }

        this.render();
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.offset.x) / this.zoom;
        const y = (e.clientY - rect.top - this.offset.y) / this.zoom;

        if (this.isDragging && this.selectedNode) {
            this.selectedNode.x = x - this.dragStart.x;
            this.selectedNode.y = y - this.dragStart.y;
            this.render();
        } else if (this.isPanning) {
            this.offset.x = e.clientX - this.dragStart.x;
            this.offset.y = e.clientY - this.dragStart.y;
            this.render();
        } else if (this.isConnecting) {
            this.connectionEnd = { x, y };
            this.render();
        }
    }

    onMouseUp(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.offset.x) / this.zoom;
        const y = (e.clientY - rect.top - this.offset.y) / this.zoom;

        if (this.isConnecting) {
            const targetNode = this.getNodeAt(x, y);
            if (targetNode && targetNode !== this.connectionStart) {
                if (this.isClickOnInputHandle(targetNode, x, y)) {
                    this.addConnection(this.connectionStart, targetNode);
                }
            }
            this.isConnecting = false;
            this.connectionStart = null;
        }

        if (this.isDragging && this.selectedNode) {
            this.saveHistory();
        }

        this.isDragging = false;
        this.isPanning = false;
        this.render();
    }

    onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const newZoom = Math.min(Math.max(this.zoom * delta, 0.1), 3);

        // Zoom towards mouse position
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        this.offset.x = mouseX - (mouseX - this.offset.x) * (newZoom / this.zoom);
        this.offset.y = mouseY - (mouseY - this.offset.y) * (newZoom / this.zoom);

        this.zoom = newZoom;
        this.updateZoomDisplay();
        this.render();
    }

    onKeyDown(e) {
        if (e.key === 'Delete' && this.selectedNode) {
            this.deleteNode(this.selectedNode);
        } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            if (e.shiftKey) {
                this.redo();
            } else {
                this.undo();
            }
        }
    }

    getNodeAt(x, y) {
        return this.nodes.find(node =>
            x >= node.x && x <= node.x + node.width &&
            y >= node.y && y <= node.y + node.height
        );
    }

    isClickOnOutputHandle(node, x, y) {
        const handleX = node.x + node.width;
        const handleY = node.y + node.height / 2;
        const dist = Math.sqrt((x - handleX) ** 2 + (y - handleY) ** 2);
        return dist < 8;
    }

    isClickOnInputHandle(node, x, y) {
        const handleX = node.x;
        const handleY = node.y + node.height / 2;
        const dist = Math.sqrt((x - handleX) ** 2 + (y - handleY) ** 2);
        return dist < 8;
    }

    addConnection(source, target) {
        // Check if connection already exists
        const exists = this.connections.some(conn =>
            conn.source === source && conn.target === target
        );

        if (!exists) {
            this.connections.push({
                source: source,
                target: target,
                sourceHandle: 'output',
                targetHandle: 'input'
            });
            this.saveHistory();
        }
    }

    deleteNode(node) {
        // Remove node
        this.nodes = this.nodes.filter(n => n !== node);

        // Remove connections
        this.connections = this.connections.filter(conn =>
            conn.source !== node && conn.target !== node
        );

        this.selectedNode = null;
        this.hidePropertiesPanel();
        this.saveHistory();
        this.updateMinimapVisibility();
        this.render();
    }

    render() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Save context state
        this.ctx.save();

        // Apply transformations
        this.ctx.translate(this.offset.x, this.offset.y);
        this.ctx.scale(this.zoom, this.zoom);

        // Draw grid if enabled
        if (this.showGrid) {
            this.drawGrid();
        }

        // Draw connections first (so they're behind nodes)
        this.drawConnections();

        // Draw temporary connection while connecting
        if (this.isConnecting && this.connectionStart) {
            this.drawConnection(
                { x: this.connectionStart.x + this.connectionStart.width, y: this.connectionStart.y + this.connectionStart.height / 2 },
                this.connectionEnd,
                '#9CA3AF',
                true
            );
        }

        // Draw nodes
        this.nodes.forEach(node => this.drawNode(node));

        // Restore context
        this.ctx.restore();
        
        // Update minimap
        this.renderMinimap();
    }
    
    drawGrid() {
        const gridSize = 30;
        const startX = Math.floor(-this.offset.x / this.zoom / gridSize) * gridSize;
        const startY = Math.floor(-this.offset.y / this.zoom / gridSize) * gridSize;
        const endX = startX + Math.ceil(this.canvas.width / this.zoom / gridSize) * gridSize + gridSize;
        const endY = startY + Math.ceil(this.canvas.height / this.zoom / gridSize) * gridSize + gridSize;
        
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        this.ctx.lineWidth = 1;
        
        // Draw vertical lines
        for (let x = startX; x <= endX; x += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, startY);
            this.ctx.lineTo(x, endY);
            this.ctx.stroke();
        }
        
        // Draw horizontal lines
        for (let y = startY; y <= endY; y += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(startX, y);
            this.ctx.lineTo(endX, y);
            this.ctx.stroke();
        }
    }

    drawNode(node) {
        const isSelected = node === this.selectedNode;
        const color = this.getNodeColor(node.type);

        // Node shadow
        if (isSelected) {
            this.ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
            this.ctx.shadowBlur = 10;
            this.ctx.shadowOffsetX = 0;
            this.ctx.shadowOffsetY = 4;
        }

        // Node background
        this.ctx.fillStyle = node.enabled ? '#FFFFFF' : '#F3F4F6';
        this.ctx.strokeStyle = isSelected ? color : '#E5E7EB';
        this.ctx.lineWidth = isSelected ? 3 : 2;
        this.roundRect(node.x, node.y, node.width, node.height, 8);
        this.ctx.fill();
        this.ctx.stroke();

        // Reset shadow
        this.ctx.shadowColor = 'transparent';
        this.ctx.shadowBlur = 0;
        this.ctx.shadowOffsetX = 0;
        this.ctx.shadowOffsetY = 0;

        // Header bar
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.moveTo(node.x + 8, node.y);
        this.ctx.lineTo(node.x + node.width - 8, node.y);
        this.ctx.arcTo(node.x + node.width, node.y, node.x + node.width, node.y + 8, 8);
        this.ctx.lineTo(node.x + node.width, node.y + 30);
        this.ctx.lineTo(node.x, node.y + 30);
        this.ctx.lineTo(node.x, node.y + 8);
        this.ctx.arcTo(node.x, node.y, node.x + 8, node.y, 8);
        this.ctx.closePath();
        this.ctx.fill();

        // Node label
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.font = 'bold 13px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(node.label, node.x + node.width / 2, node.y + 15);

        // Node type
        this.ctx.fillStyle = '#6B7280';
        this.ctx.font = '11px sans-serif';
        const typeLabel = node.type.split('_').pop().toLowerCase();
        this.ctx.fillText(typeLabel, node.x + node.width / 2, node.y + 45);

        // Connection handles
        this.drawHandle(node.x, node.y + node.height / 2, 'input');
        this.drawHandle(node.x + node.width, node.y + node.height / 2, 'output');

        // Disabled overlay
        if (!node.enabled) {
            this.ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
            this.roundRect(node.x, node.y, node.width, node.height, 8);
            this.ctx.fill();
        }
    }

    drawHandle(x, y, type) {
        this.ctx.fillStyle = type === 'input' ? '#10B981' : '#3B82F6';
        this.ctx.strokeStyle = '#FFFFFF';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.arc(x, y, 6, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.stroke();
    }

    drawConnections() {
        this.connections.forEach(conn => {
            const start = {
                x: conn.source.x + conn.source.width,
                y: conn.source.y + conn.source.height / 2
            };
            const end = {
                x: conn.target.x,
                y: conn.target.y + conn.target.height / 2
            };
            this.drawConnection(start, end, '#6B7280');
        });
    }

    drawConnection(start, end, color, dashed = false) {
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 2;

        if (dashed) {
            this.ctx.setLineDash([5, 5]);
        } else {
            this.ctx.setLineDash([]);
        }

        // Curved connection
        const dx = end.x - start.x;
        const cp1x = start.x + Math.max(dx * 0.5, 50);
        const cp2x = end.x - Math.max(dx * 0.5, 50);

        this.ctx.beginPath();
        this.ctx.moveTo(start.x, start.y);
        this.ctx.bezierCurveTo(cp1x, start.y, cp2x, end.y, end.x, end.y);
        this.ctx.stroke();

        this.ctx.setLineDash([]);
    }

    roundRect(x, y, width, height, radius) {
        this.ctx.beginPath();
        this.ctx.moveTo(x + radius, y);
        this.ctx.lineTo(x + width - radius, y);
        this.ctx.arcTo(x + width, y, x + width, y + radius, radius);
        this.ctx.lineTo(x + width, y + height - radius);
        this.ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
        this.ctx.lineTo(x + radius, y + height);
        this.ctx.arcTo(x, y + height, x, y + height - radius, radius);
        this.ctx.lineTo(x, y + radius);
        this.ctx.arcTo(x, y, x + radius, y, radius);
        this.ctx.closePath();
    }

    showPropertiesPanel(node) {
        const panel = document.getElementById('properties-panel');
        const title = document.getElementById('properties-title');
        const body = document.getElementById('properties-body');

        title.textContent = node.label;
        body.innerHTML = this.generatePropertiesForm(node);

        // Setup form listeners
        this.setupPropertiesFormListeners(node);
    }

    hidePropertiesPanel() {
        const body = document.getElementById('properties-body');
        body.innerHTML = '<p class="webops-text-muted">Select a node to edit its properties</p>';
    }
    
    togglePropertiesPanel() {
        const panel = document.getElementById('properties-panel');
        panel.classList.toggle('collapsed');
        
        // Resize canvas after panel toggle
        setTimeout(() => {
            this.resize();
            this.render();
        }, 300); // Wait for transition to complete
    }
    
    togglePropertiesPanelMinimize() {
        const panel = document.getElementById('properties-panel');
        const isMinimized = panel.classList.contains('minimized');
        
        if (isMinimized) {
            panel.classList.remove('minimized');
            localStorage.setItem('properties-minimized', 'false');
        } else {
            panel.classList.add('minimized');
            localStorage.setItem('properties-minimized', 'true');
        }
        
        // Resize canvas after panel toggle
        setTimeout(() => {
            this.resize();
            this.render();
        }, 300); // Wait for transition to complete
    }
    
    toggleGrid() {
        this.showGrid = !this.showGrid;
        const btn = document.getElementById('btn-toggle-grid');
        const icon = btn.querySelector('.material-icons');
        
        if (this.showGrid) {
            icon.textContent = 'grid_on';
            btn.setAttribute('aria-label', 'Hide grid');
        } else {
            icon.textContent = 'grid_off';
            btn.setAttribute('aria-label', 'Show grid');
        }
        
        this.render();
    }
    
    togglePalette() {
        const palette = document.getElementById('node-palette');
        const isMinimized = palette.classList.contains('minimized');
        
        if (isMinimized) {
            palette.classList.remove('minimized');
            localStorage.setItem('palette-minimized', 'false');
        } else {
            palette.classList.add('minimized');
            localStorage.setItem('palette-minimized', 'true');
        }
        
        // Resize canvas after palette toggle
        setTimeout(() => {
            this.resize();
            this.render();
        }, 300); // Wait for transition to complete
    }
    
    initPaletteState() {
        // Restore palette state from localStorage
        const isMinimized = localStorage.getItem('palette-minimized') === 'true';
        const palette = document.getElementById('node-palette');
        
        if (isMinimized) {
            palette.classList.add('minimized');
        }
        
        // Add data-tooltip attributes for minimized palette
        const nodes = document.querySelectorAll('.webops-palette-node');
        nodes.forEach(node => {
            const label = node.querySelector('.node-label').textContent;
            node.setAttribute('data-tooltip', label);
        });
    }
    
    setupToolbarOverflowHandling() {
        // Check toolbar overflow on window resize
        window.addEventListener('resize', () => {
            this.checkToolbarOverflow();
        });
        
        // Initial check
        setTimeout(() => {
            this.checkToolbarOverflow();
        }, 100);
    }
    
    checkToolbarOverflow() {
        const toolbar = document.querySelector('.webops-workflow-toolbar');
        const leftSection = document.querySelector('.webops-toolbar-left');
        const rightSection = document.querySelector('.webops-toolbar-right');
        const nameInput = document.getElementById('workflow-name');
        
        if (!toolbar || !leftSection || !rightSection || !nameInput) return;
        
        // Get available width
        const toolbarWidth = toolbar.clientWidth;
        const leftWidth = leftSection.scrollWidth;
        const rightWidth = rightSection.scrollWidth;
        const availableWidth = toolbarWidth - 40; // Account for padding
        
        // Check if toolbar is overflowing
        if (leftWidth + rightWidth > availableWidth) {
            // Calculate how much we need to reduce
            const overflow = (leftWidth + rightWidth) - availableWidth;
            
            // First, try to reduce the workflow name input
            const currentMaxWidth = parseInt(window.getComputedStyle(nameInput).maxWidth) || 500;
            const newMaxWidth = Math.max(120, currentMaxWidth - overflow);
            
            if (newMaxWidth < currentMaxWidth) {
                nameInput.style.maxWidth = `${newMaxWidth}px`;
                
                // If still overflowing, start hiding toolbar text
                setTimeout(() => {
                    this.checkToolbarOverflow();
                }, 100);
            }
        } else {
            // Reset max-width if there's enough space
            nameInput.style.maxWidth = '';
        }
    }
    
    toggleToolbarDropdown() {
        const dropdown = document.getElementById('toolbar-dropdown');
        const moreButton = document.getElementById('btn-more');
        const isOpen = dropdown.classList.contains('webops-toolbar-dropdown--open');
        
        if (isOpen) {
            dropdown.classList.remove('webops-toolbar-dropdown--open');
            moreButton.setAttribute('aria-expanded', 'false');
        } else {
            dropdown.classList.add('webops-toolbar-dropdown--open');
            moreButton.setAttribute('aria-expanded', 'true');
        }
    }
    
    exportWorkflow() {
        const data = {
            name: document.getElementById('workflow-name').value,
            nodes: this.nodes.map(node => ({
                id: node.id,
                type: node.type,
                label: node.label,
                position: { x: node.x, y: node.y },
                config: node.config,
                enabled: node.enabled
            })),
            connections: this.connections.map(conn => ({
                source: conn.source.id,
                target: conn.target.id,
                sourceHandle: conn.sourceHandle,
                targetHandle: conn.targetHandle
            }))
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${data.name.replace(/\s+/g, '_')}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showNotification('Workflow exported successfully', 'success');
        this.toggleToolbarDropdown();
    }
    
    importWorkflow() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const data = JSON.parse(event.target.result);
                    
                    // Clear existing workflow
                    this.nodes = [];
                    this.connections = [];
                    this.selectedNode = null;
                    
                    // Load imported data
                    data.nodes.forEach(nodeData => {
                        this.nodes.push({
                            id: nodeData.id,
                            type: nodeData.type,
                            label: nodeData.label,
                            x: nodeData.position.x,
                            y: nodeData.position.y,
                            config: nodeData.config || {},
                            enabled: nodeData.enabled !== false,
                            width: 180,
                            height: 60
                        });
                    });
                    
                    data.connections.forEach(connData => {
                        const source = this.nodes.find(n => n.id === connData.source);
                        const target = this.nodes.find(n => n.id === connData.target);
                        if (source && target) {
                            this.connections.push({
                                source: source,
                                target: target,
                                sourceHandle: connData.sourceHandle || 'output',
                                targetHandle: connData.targetHandle || 'input'
                            });
                        }
                    });
                    
                    // Update workflow name
                    document.getElementById('workflow-name').value = data.name;
                    
                    this.saveHistory();
                    this.updateMinimapVisibility();
                    this.render();
                    
                    this.showNotification('Workflow imported successfully', 'success');
                } catch (error) {
                    this.showNotification('Failed to import workflow: ' + error.message, 'error');
                }
            };
            
            reader.readAsText(file);
        });
        
        input.click();
        this.toggleToolbarDropdown();
    }
    
    duplicateWorkflow() {
        // Create a copy of all nodes with new IDs
        const oldToNewId = {};
        const newNodes = [];
        
        this.nodes.forEach(node => {
            const newId = `node-${this.nodeIdCounter++}`;
            oldToNewId[node.id] = newId;
            
            newNodes.push({
                id: newId,
                type: node.type,
                label: node.label,
                x: node.x + 20, // Offset slightly
                y: node.y + 20,
                config: JSON.parse(JSON.stringify(node.config)), // Deep copy
                enabled: node.enabled,
                width: node.width,
                height: node.height
            });
        });
        
        // Create connections between duplicated nodes
        const newConnections = [];
        this.connections.forEach(conn => {
            const newSourceId = oldToNewId[conn.source.id];
            const newTargetId = oldToNewId[conn.target.id];
            
            if (newSourceId && newTargetId) {
                const source = newNodes.find(n => n.id === newSourceId);
                const target = newNodes.find(n => n.id === newTargetId);
                
                if (source && target) {
                    newConnections.push({
                        source: source,
                        target: target,
                        sourceHandle: conn.sourceHandle,
                        targetHandle: conn.targetHandle
                    });
                }
            }
        });
        
        // Add duplicated nodes and connections
        this.nodes.push(...newNodes);
        this.connections.push(...newConnections);
        
        this.saveHistory();
        this.updateMinimapVisibility();
        this.render();
        
        this.showNotification('Workflow duplicated successfully', 'success');
        this.toggleToolbarDropdown();
    }
    
    clearCanvas() {
        if (confirm('Are you sure you want to clear the canvas? This action cannot be undone.')) {
            this.nodes = [];
            this.connections = [];
            this.selectedNode = null;
            this.history = [];
            this.historyIndex = -1;
            
            this.updateMinimapVisibility();
            this.render();
            
            this.showNotification('Canvas cleared', 'info');
            this.toggleToolbarDropdown();
        }
    }
    
    openSettings() {
        // Placeholder for settings functionality
        this.showNotification('Settings panel coming soon', 'info');
        this.toggleToolbarDropdown();
    }

    generatePropertiesForm(node) {
        let html = `
            <div class="webops-form">
                <div class="webops-form-group">
                    <label class="webops-label">Node Label</label>
                    <input type="text" class="webops-input" id="node-label" value="${node.label}">
                </div>
                <div class="webops-form-group">
                    <label class="webops-checkbox-label">
                        <input type="checkbox" class="webops-checkbox" id="node-enabled" ${node.enabled ? 'checked' : ''}>
                        <span>Enabled</span>
                    </label>
                </div>
        `;

        // Add type-specific configuration fields
        if (node.type === 'PROCESSOR_LLM') {
            html += `
                <div class="webops-form-group">
                    <label class="webops-label">Prompt Template</label>
                    <textarea class="webops-input" id="node-prompt" rows="4">${node.config.prompt_template || ''}</textarea>
                </div>
                <div class="webops-form-group">
                    <label class="webops-label">Model</label>
                    <input type="text" class="webops-input" id="node-model" value="${node.config.model || 'gpt-3.5-turbo'}">
                </div>
            `;
        } else if (node.type === 'DATA_SOURCE_CUSTOM_URL') {
            html += `
                <div class="webops-form-group">
                    <label class="webops-label">URL</label>
                    <input type="text" class="webops-input" id="node-url" value="${node.config.url || ''}">
                </div>
                <div class="webops-form-group">
                    <label class="webops-label">Method</label>
                    <select class="webops-select" id="node-method">
                        <option value="GET" ${node.config.method === 'GET' ? 'selected' : ''}>GET</option>
                        <option value="POST" ${node.config.method === 'POST' ? 'selected' : ''}>POST</option>
                        <option value="PUT" ${node.config.method === 'PUT' ? 'selected' : ''}>PUT</option>
                        <option value="DELETE" ${node.config.method === 'DELETE' ? 'selected' : ''}>DELETE</option>
                    </select>
                </div>
            `;
        }

        html += `
                <div class="webops-form-group">
                    <button class="webops-btn webops-btn-danger webops-btn-block" id="btn-delete-node">
                        <span class="material-icons">delete</span>
                        Delete Node
                    </button>
                </div>
            </div>
        `;

        return html;
    }

    setupPropertiesFormListeners(node) {
        const labelInput = document.getElementById('node-label');
        const enabledCheckbox = document.getElementById('node-enabled');
        const deleteButton = document.getElementById('btn-delete-node');

        if (labelInput) {
            labelInput.addEventListener('input', (e) => {
                node.label = e.target.value;
                this.render();
            });
        }

        if (enabledCheckbox) {
            enabledCheckbox.addEventListener('change', (e) => {
                node.enabled = e.target.checked;
                this.render();
            });
        }

        if (deleteButton) {
            deleteButton.addEventListener('click', () => {
                this.deleteNode(node);
            });
        }

        // Type-specific listeners
        if (node.type === 'PROCESSOR_LLM') {
            const promptInput = document.getElementById('node-prompt');
            const modelInput = document.getElementById('node-model');

            if (promptInput) {
                promptInput.addEventListener('input', (e) => {
                    node.config.prompt_template = e.target.value;
                });
            }

            if (modelInput) {
                modelInput.addEventListener('input', (e) => {
                    node.config.model = e.target.value;
                });
            }
        } else if (node.type === 'DATA_SOURCE_CUSTOM_URL') {
            const urlInput = document.getElementById('node-url');
            const methodSelect = document.getElementById('node-method');

            if (urlInput) {
                urlInput.addEventListener('input', (e) => {
                    node.config.url = e.target.value;
                });
            }

            if (methodSelect) {
                methodSelect.addEventListener('change', (e) => {
                    node.config.method = e.target.value;
                });
            }
        }
    }

    zoomIn() {
        this.zoom = Math.min(this.zoom * 1.2, 3);
        this.updateZoomDisplay();
        this.render();
    }

    zoomOut() {
        this.zoom = Math.max(this.zoom / 1.2, 0.1);
        this.updateZoomDisplay();
        this.render();
    }

    fitView() {
        if (this.nodes.length === 0) return;

        const margin = 50;
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

        this.nodes.forEach(node => {
            minX = Math.min(minX, node.x);
            minY = Math.min(minY, node.y);
            maxX = Math.max(maxX, node.x + node.width);
            maxY = Math.max(maxY, node.y + node.height);
        });

        const contentWidth = maxX - minX;
        const contentHeight = maxY - minY;

        const scaleX = (this.canvas.width - margin * 2) / contentWidth;
        const scaleY = (this.canvas.height - margin * 2) / contentHeight;
        this.zoom = Math.min(scaleX, scaleY, 1);

        this.offset.x = (this.canvas.width - contentWidth * this.zoom) / 2 - minX * this.zoom;
        this.offset.y = (this.canvas.height - contentHeight * this.zoom) / 2 - minY * this.zoom;

        this.updateZoomDisplay();
        this.render();
    }

    updateZoomDisplay() {
        document.getElementById('zoom-level').textContent = `${Math.round(this.zoom * 100)}%`;
    }

    saveHistory() {
        const state = {
            nodes: JSON.parse(JSON.stringify(this.nodes)),
            connections: JSON.parse(JSON.stringify(this.connections.map(conn => ({
                source: conn.source.id,
                target: conn.target.id
            }))))
        };

        this.history = this.history.slice(0, this.historyIndex + 1);
        this.history.push(state);
        this.historyIndex++;

        this.updateUndoRedoButtons();
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.restoreState(this.history[this.historyIndex]);
        }
    }

    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            this.restoreState(this.history[this.historyIndex]);
        }
    }

    restoreState(state) {
        this.nodes = JSON.parse(JSON.stringify(state.nodes));

        this.connections = state.connections.map(conn => ({
            source: this.nodes.find(n => n.id === conn.source),
            target: this.nodes.find(n => n.id === conn.target),
            sourceHandle: 'output',
            targetHandle: 'input'
        }));

        this.updateUndoRedoButtons();
        this.render();
    }

    updateUndoRedoButtons() {
        document.getElementById('btn-undo').disabled = this.historyIndex <= 0;
        document.getElementById('btn-redo').disabled = this.historyIndex >= this.history.length - 1;
    }

    async saveWorkflow() {
        const workflowName = document.getElementById('workflow-name').value;

        const data = {
            name: workflowName,
            nodes: this.nodes.map(node => ({
                id: node.id,
                type: node.type,
                label: node.label,
                position: { x: node.x, y: node.y },
                config: node.config,
                enabled: node.enabled
            })),
            connections: this.connections.map(conn => ({
                source: conn.source.id,
                target: conn.target.id,
                sourceHandle: conn.sourceHandle,
                targetHandle: conn.targetHandle
            }))
        };

        try {
            const response = await fetch(`/automation/${this.workflowId}/save/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                this.showNotification('Workflow saved successfully', 'success');
            } else {
                this.showNotification('Failed to save workflow: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error saving workflow: ' + error.message, 'error');
        }
    }

    async executeWorkflow() {
        try {
            const response = await fetch(`/automation/${this.workflowId}/execute/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const result = await response.json();
            if (result.success) {
                this.showNotification('Workflow execution started', 'success');
                setTimeout(() => {
                    window.location.href = `/automation/execution/${result.execution_id}/`;
                }, 1000);
            } else {
                this.showNotification('Failed to execute workflow: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error executing workflow: ' + error.message, 'error');
        }
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    showNotification(message, type) {
        // Simple notification implementation
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            padding: 1rem 1.5rem;
            background: ${type === 'success' ? '#10B981' : '#EF4444'};
            color: white;
            border-radius: 6px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// Initialize canvas when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.workflowCanvas = new WorkflowCanvas('workflow-canvas');
});
