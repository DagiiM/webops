/* Moved from templates/deployments/editor.html (ui-skill rule 17: no inline <script>). */
'use strict';

class WebOpsCodeEditor {
    constructor() {
        this.deploymentId = document.getElementById('deploymentId').value;
        this.deploymentName = document.getElementById('deploymentName').value;
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        this.openFiles = new Map();
        this.activeFile = null;
        this.fileTree = null;
        this.expandedFolders = new Set();

        this.elements = {
            loadingState: document.getElementById('loadingState'),
            errorState: document.getElementById('errorState'),
            emptyState: document.getElementById('emptyState'),
            fileTree: document.getElementById('fileTree'),
            errorMessage: document.getElementById('errorMessage'),
            editorTabs: document.getElementById('editorTabs'),
            editorContent: document.getElementById('editorContent'),
            statusMessage: document.getElementById('statusMessage'),
            fileInfo: document.getElementById('fileInfo'),
            cursorPosition: document.getElementById('cursorPosition'),
            connectionStatus: document.getElementById('connectionStatus')
        };

        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        await this.loadFileTree();
    }

    setupEventListeners() {
        // Refresh button
        document.getElementById('refreshFiles').addEventListener('click', () => {
            this.loadFileTree();
        });

        // Collapse all button
        document.getElementById('collapseAll').addEventListener('click', () => {
            this.collapseAllFolders();
        });

        // Retry button
        document.getElementById('retryLoad').addEventListener('click', () => {
            this.loadFileTree();
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + S - Save
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                if (this.activeFile) {
                    this.saveFile(this.activeFile);
                }
            }

            // Ctrl/Cmd + W - Close tab
            if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
                e.preventDefault();
                if (this.activeFile) {
                    this.closeFile(this.activeFile);
                }
            }
        });
    }

    async loadFileTree() {
        this.showState('loading');

        try {
            const response = await fetch(`/api/deployments/${this.deploymentId}/files/tree/`, {
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            if (!data.tree || data.tree.length === 0) {
                this.showState('empty');
                return;
            }

            this.fileTree = data.tree;
            this.renderFileTree(this.fileTree);
            this.showState('tree');
            this.setConnectionStatus(true);

        } catch (error) {
            console.error('Error loading file tree:', error);
            this.elements.errorMessage.textContent = error.message;
            this.showState('error');
            this.setConnectionStatus(false, error.message);
        }
    }

    showState(state) {
        // Hide all states
        this.elements.loadingState.classList.add('hidden');
        this.elements.errorState.classList.add('hidden');
        this.elements.emptyState.classList.add('hidden');
        this.elements.fileTree.classList.add('hidden');

        // Show requested state
        switch (state) {
            case 'loading':
                this.elements.loadingState.classList.remove('hidden');
                break;
            case 'error':
                this.elements.errorState.classList.remove('hidden');
                break;
            case 'empty':
                this.elements.emptyState.classList.remove('hidden');
                break;
            case 'tree':
                this.elements.fileTree.classList.remove('hidden');
                break;
        }
    }

    renderFileTree(tree, parentElement = null, level = 0) {
        const container = parentElement || this.elements.fileTree;
        if (!parentElement) container.innerHTML = '';

        tree.forEach(item => {
            if (item.type === 'directory') {
                this.renderFolder(item, container, level);
            } else {
                this.renderFile(item, container, level);
            }
        });
    }

    renderFolder(folder, container, level) {
        const folderDiv = document.createElement('div');
        folderDiv.className = 'file-tree-item folder';
        folderDiv.style.paddingLeft = `${level * 12 + 12}px`;

        if (this.expandedFolders.has(folder.path)) {
            folderDiv.classList.add('expanded');
        }

        folderDiv.innerHTML = `
            <span class="material-icons chevron">chevron_right</span>
            <span class="material-icons folder-icon">folder</span>
            <span>${folder.name}</span>
        `;

        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'file-tree-children';

        if (this.expandedFolders.has(folder.path)) {
            childrenDiv.classList.add('expanded');
        }

        folderDiv.addEventListener('click', (e) => {
            e.stopPropagation();
            const isExpanded = folderDiv.classList.toggle('expanded');
            childrenDiv.classList.toggle('expanded');

            if (isExpanded) {
                this.expandedFolders.add(folder.path);
            } else {
                this.expandedFolders.delete(folder.path);
            }
        });

        container.appendChild(folderDiv);
        container.appendChild(childrenDiv);

        if (folder.children && folder.children.length > 0) {
            this.renderFileTree(folder.children, childrenDiv, level + 1);
        }
    }

    renderFile(file, container, level) {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'file-tree-item';
        fileDiv.style.paddingLeft = `${level * 12 + 12}px`;

        const icon = this.getFileIcon(file.name);
        fileDiv.innerHTML = `
            <span class="material-icons">${icon}</span>
            <span>${file.name}</span>
        `;

        fileDiv.addEventListener('click', () => {
            this.openFile(file.path);
        });

        container.appendChild(fileDiv);
    }

    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const iconMap = {
            'py': 'code',
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'javascript',
            'tsx': 'javascript',
            'html': 'html',
            'css': 'style',
            'json': 'data_object',
            'md': 'description',
            'txt': 'description',
            'yml': 'settings',
            'yaml': 'settings',
            'xml': 'code',
            'sql': 'storage',
            'sh': 'terminal',
            'env': 'vpn_key'
        };
        return iconMap[ext] || 'insert_drive_file';
    }

    async openFile(path) {
        if (this.openFiles.has(path)) {
            this.switchToFile(path);
            return;
        }

        try {
            this.setStatus(`Loading ${path}...`);

            const response = await fetch(`/api/deployments/${this.deploymentId}/files/read/?path=${encodeURIComponent(path)}`, {
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
                throw new Error(errorData.error || `Failed to load file`);
            }

            const data = await response.json();

            // Create editor panel
            const editorPanel = document.createElement('div');
            editorPanel.className = 'editor-panel';
            editorPanel.id = `editor-${this.sanitizePath(path)}`;
            this.elements.editorContent.appendChild(editorPanel);

            // Local editor (textarea with line numbers); see static/js/webops-code-editor.js
            const editor = WebopsCodeEditor(editorPanel, {
                value: data.content,
                tabSize: 4,
                label: `Contents of ${path}`
            });

            // Track changes
            editor.on('change', () => {
                this.markFileModified(path);
            });

            // Update cursor position
            editor.on('cursorActivity', () => {
                const cursor = editor.getCursor();
                this.elements.cursorPosition.textContent = `Ln ${cursor.line + 1}, Col ${cursor.ch + 1}`;
            });

            this.openFiles.set(path, {
                editor: editor,
                modified: false,
                originalContent: data.content,
                panel: editorPanel
            });

            this.createTab(path);
            this.switchToFile(path);
            this.setStatus(`Loaded ${path}`, 'success');

        } catch (error) {
            console.error('Error opening file:', error);
            this.setStatus(`Failed to open ${path}: ${error.message}`, 'error');
        }
    }

    createTab(path) {
        const tab = document.createElement('div');
        tab.className = 'editor-tab';
        tab.dataset.path = path;

        const fileName = path.split('/').pop();

        tab.innerHTML = `
            <span class="editor-tab-name">${fileName}</span>
            <div class="editor-tab-close">
                <span class="material-icons">close</span>
            </div>
        `;

        tab.querySelector('.editor-tab-close').addEventListener('click', (e) => {
            e.stopPropagation();
            this.closeFile(path);
        });

        tab.addEventListener('click', () => {
            this.switchToFile(path);
        });

        this.elements.editorTabs.appendChild(tab);
    }

    switchToFile(path) {
        // Hide welcome screen
        const welcome = this.elements.editorContent.querySelector('.editor-welcome');
        if (welcome) welcome.style.display = 'none';

        // Deactivate all tabs and panels
        document.querySelectorAll('.editor-tab').forEach(tab => tab.classList.remove('active'));
        document.querySelectorAll('.editor-panel').forEach(panel => panel.classList.remove('active'));

        // Activate selected tab and panel
        const tab = document.querySelector(`.editor-tab[data-path="${path}"]`);
        if (tab) tab.classList.add('active');

        const fileData = this.openFiles.get(path);
        if (fileData) {
            fileData.panel.classList.add('active');
            fileData.editor.refresh();
            fileData.editor.focus();
            this.activeFile = path;

            const fileName = path.split('/').pop();
            this.elements.fileInfo.textContent = fileName;
        }
    }

    async saveFile(path) {
        const fileData = this.openFiles.get(path);
        if (!fileData) return;

        try {
            this.setStatus(`Saving ${path}...`);

            const content = fileData.editor.getValue();

            const response = await fetch(`/api/deployments/${this.deploymentId}/files/write/`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    path: path,
                    content: content
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
                throw new Error(errorData.error || 'Failed to save file');
            }

            fileData.modified = false;
            fileData.originalContent = content;

            const tab = document.querySelector(`.editor-tab[data-path="${path}"]`);
            if (tab) tab.classList.remove('modified');

            this.setStatus(`Saved ${path}`, 'success');

        } catch (error) {
            console.error('Error saving file:', error);
            this.setStatus(`Failed to save ${path}: ${error.message}`, 'error');
        }
    }

    closeFile(path) {
        const fileData = this.openFiles.get(path);
        if (!fileData) return;

        if (fileData.modified) {
            if (!confirm(`${path} has unsaved changes. Close anyway?`)) {
                return;
            }
        }

        // Remove tab
        const tab = document.querySelector(`.editor-tab[data-path="${path}"]`);
        if (tab) tab.remove();

        // Remove panel
        fileData.panel.remove();

        // Remove from open files
        this.openFiles.delete(path);

        // Switch to another file or show welcome
        if (this.openFiles.size > 0) {
            const firstPath = this.openFiles.keys().next().value;
            this.switchToFile(firstPath);
        } else {
            const welcome = this.elements.editorContent.querySelector('.editor-welcome');
            if (welcome) welcome.style.display = 'flex';
            this.activeFile = null;
            this.elements.fileInfo.textContent = '';
            this.elements.cursorPosition.textContent = 'Ln 1, Col 1';
        }
    }

    markFileModified(path) {
        const fileData = this.openFiles.get(path);
        if (!fileData || fileData.modified) return;

        const currentContent = fileData.editor.getValue();
        if (currentContent !== fileData.originalContent) {
            fileData.modified = true;
            const tab = document.querySelector(`.editor-tab[data-path="${path}"]`);
            if (tab) tab.classList.add('modified');
        }
    }

    collapseAllFolders() {
        this.expandedFolders.clear();
        document.querySelectorAll('.file-tree-item.folder').forEach(folder => {
            folder.classList.remove('expanded');
        });
        document.querySelectorAll('.file-tree-children').forEach(children => {
            children.classList.remove('expanded');
        });
    }

    getModeForFile(path) {
        const ext = path.split('.').pop().toLowerCase();
        const modeMap = {
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'javascript',
            'tsx': 'javascript',
            'py': 'python',
            'html': 'htmlmixed',
            'htm': 'htmlmixed',
            'css': 'css',
            'scss': 'css',
            'less': 'css',
            'json': 'javascript',
            'md': 'markdown',
            'xml': 'xml',
            'sql': 'sql',
            'sh': 'shell',
            'bash': 'shell',
            'yaml': 'yaml',
            'yml': 'yaml',
            'dockerfile': 'dockerfile'
        };
        return modeMap[ext] || 'text/plain';
    }

    sanitizePath(path) {
        return path.replace(/[^a-zA-Z0-9]/g, '-');
    }

    setStatus(message, type = 'info') {
        this.elements.statusMessage.textContent = message;

        const statusBar = document.querySelector('.editor-statusbar');
        statusBar.classList.remove('success', 'error', 'warning');

        if (type === 'success') {
            statusBar.classList.add('success');
            setTimeout(() => statusBar.classList.remove('success'), 3000);
        } else if (type === 'error') {
            statusBar.classList.add('error');
            setTimeout(() => statusBar.classList.remove('error'), 5000);
        }
    }

    setConnectionStatus(connected, errorMsg = '') {
        const statusEl = this.elements.connectionStatus;
        if (connected) {
            statusEl.innerHTML = '<span class="material-icons">cloud_done</span> Connected';
            statusEl.style.color = '#ffffff';
        } else {
            statusEl.innerHTML = '<span class="material-icons">cloud_off</span> Disconnected';
            statusEl.style.color = '#ffcccc';
            if (errorMsg) {
                statusEl.title = errorMsg;
            }
        }
    }
}

// Initialize editor on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    new WebOpsCodeEditor();
});
