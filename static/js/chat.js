document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const crawlForm = document.getElementById('crawl-form');
    const urlInput = document.getElementById('url');
    const crawlBtn = document.getElementById('crawl-btn');
    const crawlStatus = document.getElementById('crawl-status');
    const crawlProgress = document.getElementById('crawl-progress');
    const crawlMessage = document.getElementById('crawl-message');
    const crawlResult = document.getElementById('crawl-result');
    const resultMessage = document.getElementById('result-message');
    const crawlError = document.getElementById('crawl-error');
    const errorMessage = document.getElementById('error-message');
    
    const chatForm = document.getElementById('chat-form');
    const queryInput = document.getElementById('query');
    const sendBtn = document.getElementById('send-btn');
    const messagesContainer = document.getElementById('messages');
    
    // Check system status on page load
    checkStatus();
    
    // Crawl form submission
    crawlForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Reset UI
        crawlResult.classList.add('d-none');
        crawlError.classList.add('d-none');
        
        // Show crawling status
        crawlStatus.classList.remove('d-none');
        crawlProgress.style.width = '10%';
        crawlMessage.textContent = 'Starting crawler...';
        
        // Disable form controls
        crawlBtn.disabled = true;
        urlInput.disabled = true;
        
        // Get form values
        const url = urlInput.value;
        
        // Make API request to extract content
        fetch('/crawl', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url
            })
        })
        .then(response => response.json())
        .then(data => {
            // Update progress
            crawlProgress.style.width = '100%';
            
            // Hide status after a delay
            setTimeout(() => {
                crawlStatus.classList.add('d-none');
                
                if (data.success) {
                    // Show success message
                    crawlResult.classList.remove('d-none');
                    resultMessage.textContent = data.message;
                    
                    // Enable chat
                    queryInput.disabled = false;
                    sendBtn.disabled = false;
                    
                    // Add system message
                    addSystemMessage('Website has been crawled! You can now ask questions about the content.');
                } else {
                    // Show error message
                    crawlError.classList.remove('d-none');
                    errorMessage.textContent = data.error || 'An error occurred while crawling the website.';
                }
                
                // Re-enable form controls
                crawlBtn.disabled = false;
                urlInput.disabled = false;
                maxDepthInput.disabled = false;
                maxPagesInput.disabled = false;
            }, 1000);
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Hide status
            crawlStatus.classList.add('d-none');
            
            // Show error message
            crawlError.classList.remove('d-none');
            errorMessage.textContent = 'An error occurred while crawling the website.';
            
            // Re-enable form controls
            crawlBtn.disabled = false;
            urlInput.disabled = false;
            maxDepthInput.disabled = false;
            maxPagesInput.disabled = false;
        });
    });
    
    // Chat form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const query = queryInput.value.trim();
        if (!query) return;
        
        // Clear input
        queryInput.value = '';
        
        // Add user message to chat
        addUserMessage(query);
        
        // Disable input while waiting for response
        queryInput.disabled = true;
        sendBtn.disabled = true;
        
        // Add typing indicator
        const typingIndicator = addTypingIndicator();
        
        // Make API request to chat endpoint
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query
            })
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            typingIndicator.remove();
            
            if (data.success) {
                // Add bot message to chat
                addBotMessage(data.response);
            } else {
                // Add error message to chat
                addSystemMessage('Error: ' + (data.error || 'An error occurred while generating a response.'));
            }
            
            // Re-enable input
            queryInput.disabled = false;
            sendBtn.disabled = false;
            queryInput.focus();
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Remove typing indicator
            typingIndicator.remove();
            
            // Add error message to chat
            addSystemMessage('Error: An error occurred while communicating with the server.');
            
            // Re-enable input
            queryInput.disabled = false;
            sendBtn.disabled = false;
        });
    });
    
    // Helper function to check system status
    function checkStatus() {
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                if (data.has_documents) {
                    // Enable chat
                    queryInput.disabled = false;
                    sendBtn.disabled = false;
                    
                    // Show crawl result
                    if (data.crawled_url) {
                        crawlResult.classList.remove('d-none');
                        resultMessage.textContent = `Successfully crawled ${data.pages_count} pages from ${data.crawled_url}`;
                        
                        // Add system message
                        addSystemMessage(`Website ${data.crawled_url} has been crawled! You can now ask questions about the content.`);
                    }
                }
            })
            .catch(error => {
                console.error('Error checking status:', error);
            });
    }
    
    // Helper function to add user message to chat
    function addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'user-message text-end mb-3';
        messageElement.innerHTML = `
            <div class="message-content bg-primary text-white p-3 rounded d-inline-block">
                <p class="m-0">${escapeHtml(message)}</p>
            </div>
        `;
        messagesContainer.appendChild(messageElement);
        scrollToBottom();
    }
    
    // Helper function to add bot message to chat
    function addBotMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'bot-message mb-3';
        
        // Convert markdown-like syntax for links, bold, etc.
        const formattedMessage = formatMessage(message);
        
        messageElement.innerHTML = `
            <div class="message-content bg-dark p-3 rounded d-inline-block">
                <p class="m-0">${formattedMessage}</p>
            </div>
        `;
        messagesContainer.appendChild(messageElement);
        scrollToBottom();
    }
    
    // Helper function to add system message to chat
    function addSystemMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'system-message mb-3';
        messageElement.innerHTML = `
            <div class="message-content bg-secondary text-white p-2 rounded text-center">
                <p class="m-0"><i class="fas fa-info-circle me-2"></i>${escapeHtml(message)}</p>
            </div>
        `;
        messagesContainer.appendChild(messageElement);
        scrollToBottom();
    }
    
    // Helper function to add typing indicator
    function addTypingIndicator() {
        const typingElement = document.createElement('div');
        typingElement.className = 'bot-message typing-indicator mb-3';
        typingElement.innerHTML = `
            <div class="message-content bg-dark p-3 rounded d-inline-block">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        messagesContainer.appendChild(typingElement);
        scrollToBottom();
        return typingElement;
    }
    
    // Helper function to scroll chat to bottom
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Helper function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Helper function to format message (convert URLs to links, etc.)
    function formatMessage(text) {
        // Convert URLs to links
        text = text.replace(
            /(https?:\/\/[^\s]+)/g, 
            '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
        );
        
        // Convert markdown-like syntax for sources
        if (text.includes('Sources:')) {
            const parts = text.split('Sources:');
            if (parts.length === 2) {
                const mainContent = parts[0];
                let sources = parts[1].split('\n').filter(s => s.trim().length > 0);
                
                // Format sources as links if they look like URLs
                sources = sources.map(source => {
                    const trimmedSource = source.trim();
                    if (trimmedSource.startsWith('http')) {
                        return `<a href="${trimmedSource}" target="_blank" rel="noopener noreferrer">${trimmedSource}</a>`;
                    }
                    return trimmedSource;
                });
                
                text = `${mainContent}<strong>Sources:</strong><ul>${sources.map(s => `<li>${s}</li>`).join('')}</ul>`;
            }
        }
        
        // Convert newlines to <br>
        text = text.replace(/\n/g, '<br>');
        
        return text;
    }
});
