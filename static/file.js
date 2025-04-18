document.addEventListener('DOMContentLoaded', () => {
    // --- Folder Browser Elements ---
    const currentPathDisplay = document.getElementById('current-path');
    const folderUpBtn = document.getElementById('folder-up-btn');
    const folderContents = document.getElementById('folder-contents');
    let currentPath = '';

    // Get initial subdir from URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const initialSubdir = urlParams.get('subdir') || '';

    // --- WebSocket Setup ---
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    let socket;

    function connectWebSocket() {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('WebSocket connection established');
        };

        socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'directory_changed') {
                    // If current directory or parent was changed, refresh
                    if (currentPath === '' || currentPath === '.' ||
                        message.path.startsWith(currentPath) ||
                        message.path.includes(currentPath)) {
                        loadFolder(currentPath);
                    }
                }
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        socket.onclose = (event) => {
            console.log('WebSocket connection closed:', event.reason);
            setTimeout(connectWebSocket, 5000);
        };
    }

    // --- Folder Browser Functions ---
    async function fetchDirectoryContents(path = '') {
        try {
            const response = await fetch(`/api/directory?path=${encodeURIComponent(path)}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching directory contents:', error);
            return null;
        }
    }

    function renderDirectoryContents(data) {
        if (!data) return;
        
        currentPath = data.path;
        currentPathDisplay.textContent = currentPath || '/';
        
        folderContents.innerHTML = '';
        
        // Add folders first
        data.contents.filter(item => item.type === 'directory').forEach(folder => {
            const folderEl = document.createElement('div');
            folderEl.className = 'folder-item';
            folderEl.innerHTML = `
                <span class="folder-icon">📁</span>
                <span class="folder-name">${folder.name}</span>
            `;
            folderEl.addEventListener('click', () => {
                navigateToFolder(folder.name);
            });
            folderContents.appendChild(folderEl);
        });

        // Then add files
        data.contents.filter(item => item.type === 'file').forEach(file => {
            const fileEl = document.createElement('div');
            fileEl.className = 'file-item';
            fileEl.innerHTML = `
                <span class="file-icon">📄</span>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${formatFileSize(file.size)}</span>
            `;
            fileEl.addEventListener('click', () => {
                window.open(`/workspace_root/${currentPath}/${file.name}`, '_blank');
            });
            folderContents.appendChild(fileEl);
        });
    }

    function navigateToFolder(folderName) {
        const newPath = currentPath ? `${currentPath}/${folderName}` : folderName;
        loadFolder(newPath);
    }

    function navigateUp() {
        if (!currentPath) return;
        const pathParts = currentPath.split('/');
        pathParts.pop();
        loadFolder(pathParts.join('/'));
    }

    async function loadFolder(path) {
        const data = await fetchDirectoryContents(path);
        renderDirectoryContents(data);
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // --- Initialization ---
    connectWebSocket();
    loadFolder(initialSubdir);

    // --- Event Listeners ---
    folderUpBtn.addEventListener('click', navigateUp);
});
