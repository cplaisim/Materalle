// Function to get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Set up CSRF token for AJAX requests
document.addEventListener('DOMContentLoaded', function() {
    const csrftoken = getCookie('csrftoken');
    console.log('CSRF Token:', csrftoken); // Debug output to check if token exists
    
    // Add CSRF token to all AJAX requests
    if (window.jQuery) {
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!(/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type)) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                }
            }
        });
    }
    
    // Also add CSRF token to fetch requests
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        // Only add CSRF token for same-origin POST/PUT/DELETE requests
        if (url.indexOf(window.location.origin) === 0 && 
            options && options.method && 
            ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method)) {
            
            if (!options.headers) {
                options.headers = {};
            }
            
            // Convert Headers object to plain object if needed
            if (options.headers instanceof Headers) {
                const headers = {};
                for (let [key, value] of options.headers.entries()) {
                    headers[key] = value;
                }
                options.headers = headers;
            }
            
            options.headers['X-CSRFToken'] = csrftoken;
        }
        return originalFetch(url, options);
    };
    
    // Debug button to test CSRF token
    const debugButton = document.createElement('button');
    debugButton.id = 'csrf-debug';
    debugButton.style.position = 'fixed';
    debugButton.style.bottom = '10px';
    debugButton.style.right = '10px';
    debugButton.style.zIndex = '9999';
    debugButton.style.display = 'none'; // Hidden by default
    debugButton.textContent = 'Test CSRF';
    debugButton.onclick = function() {
        console.log('Current CSRF token:', getCookie('csrftoken'));
        alert('CSRF token logged to console');
    };
    document.body.appendChild(debugButton);
    
    // Enable debug with Ctrl+Shift+C
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.shiftKey && e.key === 'C') {
            const button = document.getElementById('csrf-debug');
            button.style.display = button.style.display === 'none' ? 'block' : 'none';
        }
    });
});