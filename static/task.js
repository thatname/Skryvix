document.addEventListener('DOMContentLoaded', () => {
    // Parse task_id from URL
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id');
    
    if (!taskId) {
        document.getElementById('status').textContent = 'Error: Missing task_id parameter';
        document.getElementById('status').className = 'error';
        return;
    }

    document.getElementById('task-id').textContent = taskId;
    const historyContainer = document.getElementById('history-container');
    
    // Connect to SSE endpoint
    const eventSource = new EventSource(`/task-history/${taskId}`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'initial_history') {
            historyContainer.textContent = data.history;
            document.getElementById('status').textContent = 'Connected to history stream';
        } else if (data.type === 'history_update') {
            historyContainer.textContent += data.tokens;
        }
    };

    eventSource.onerror = () => {
        document.getElementById('status').textContent = 'Error: Connection lost';
        document.getElementById('status').className = 'error';
        eventSource.close();
    };
});
