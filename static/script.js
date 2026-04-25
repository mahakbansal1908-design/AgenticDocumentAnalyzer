const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const docList = document.getElementById('doc-list');
const linkInput = document.getElementById('link-input');
const addLinkBtn = document.getElementById('add-link-btn');
const promptInput = document.getElementById('prompt-input');
const sendBtn = document.getElementById('send-btn');
const chatArea = document.getElementById('chat-area');
const clearBtn = document.getElementById('clear-btn');

// Drag & Drop functionality
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    handleFiles(files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

clearBtn.addEventListener('click', async () => {
    if (confirm('Are you sure you want to clear the session? All documents and chat history will be lost.')) {
        try {
            const response = await fetch('/clear', { method: 'POST' });
            if (response.ok) {
                docList.innerHTML = '';
                chatArea.innerHTML = '<div class="message agent">Session cleared. Upload new documents or provide links to start afresh!</div>';
                alert('Session cleared successfully!');
            } else {
                alert('Failed to clear session.');
            }
        } catch (error) {
            console.error('Error clearing session:', error);
            alert('Error clearing session.');
        }
    }
});

function handleFiles(files) {
    for (const file of files) {
        const ext = file.name.split('.').pop().toLowerCase();
        const allowedExts = ['pdf', 'docx', 'xlsx', 'png', 'jpg', 'jpeg', 'webp'];
        if (!allowedExts.includes(ext)) {
            alert('Unsupported file type. Supported: PDF, Word, Excel, Images.');
            continue;
        }

        uploadFile(file);
    }
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const item = createDocItem(file.name);
    docList.appendChild(item);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.detail) {
            item.querySelector('.status').textContent = '❌';
            alert(data.detail);
        } else {
            item.querySelector('.status').textContent = '✅';
            item.dataset.id = data.doc_id;
            const removeBtn = item.querySelector('.remove-btn');
            removeBtn.style.display = 'inline';
            removeBtn.addEventListener('click', () => deleteDocument(data.doc_id, item));
        }
    })
    .catch(err => {
        item.querySelector('.status').textContent = '❌';
        console.error(err);
    });
}

function createDocItem(name) {
    const div = document.createElement('div');
    div.className = 'doc-item';
    div.innerHTML = `
        <span>${name}</span>
        <div>
            <span class="status">⏳</span>
            <button class="remove-btn" style="display: none; background: none; border: none; cursor: pointer; margin-left: 10px;">🗑️</button>
        </div>
    `;
    return div;
}

function deleteDocument(docId, element) {
    fetch(`/document/${docId}`, {
        method: 'DELETE'
    })
    .then(res => res.json())
    .then(data => {
        if (data.message) {
            element.remove();
        } else {
            alert('Failed to remove document.');
        }
    })
    .catch(err => {
        console.error(err);
        alert('Error removing document.');
    });
}

addLinkBtn.addEventListener('click', () => {
    const url = linkInput.value.trim();
    if (!url) return;

    const item = createDocItem(url);
    docList.appendChild(item);

    const formData = new FormData();
    formData.append('url', url);

    fetch('/add_link', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.detail) {
            item.querySelector('.status').textContent = '❌';
            alert(data.detail);
            item.remove();
        } else {
            item.querySelector('.status').textContent = '✅';
            item.dataset.id = data.doc_id;
            linkInput.value = '';
            const removeBtn = item.querySelector('.remove-btn');
            removeBtn.style.display = 'inline';
            removeBtn.addEventListener('click', () => deleteDocument(data.doc_id, item));
        }
    })
    .catch(err => {
        item.querySelector('.status').textContent = '❌';
        console.error(err);
        item.remove();
    });
});

sendBtn.addEventListener('click', sendMessage);
promptInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function sendMessage() {
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    appendMessage('user', prompt);
    promptInput.value = '';

    const loadingDiv = appendMessage('agent', '<div class="loading"></div>');

    const formData = new FormData();
    formData.append('prompt', prompt);

    fetch('/chat', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        loadingDiv.remove();
        if (data.error) {
            appendMessage('system', `Error: ${data.error}`);
        } else if (data.answer) {
            appendMessage('agent', formatResponse(data.answer));
        }
    })
    .catch(err => {
        loadingDiv.remove();
        appendMessage('system', 'Failed to communicate with agent.');
        console.error(err);
    });
}

function appendMessage(sender, content) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.innerHTML = content;
    
    if (sender === 'agent') {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.innerText = 'Copy';
        copyBtn.addEventListener('click', () => {
            const textToCopy = div.innerText.replace('Copy', '').trim();
            navigator.clipboard.writeText(textToCopy);
            copyBtn.innerText = 'Copied!';
            setTimeout(() => copyBtn.innerText = 'Copy', 2000);
        });
        div.appendChild(copyBtn);
    }
    
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
    return div;
}

function formatResponse(text) {
    return text.replace(/\n/g, '<br>');
}
