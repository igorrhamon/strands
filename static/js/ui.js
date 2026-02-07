/**
 * UI controller for Strands Governance Dashboard
 * Handles all user interactions and DOM updates
 */

class UI {
    static BUTTON_STATES = {
        IDLE: 'idle',
        LOADING: 'loading',
        SUCCESS: 'success',
        ERROR: 'error'
    };

    /**
     * Simulate alert button click
     */
    static async simulateAlert(btn) {
        // Use provided button or fall back to the header one
        const targetBtn = (btn instanceof HTMLElement) ? btn : document.getElementById('simulate-alert-btn');
        if (!targetBtn) return;

        const originalContent = targetBtn.innerHTML;
        targetBtn.disabled = true;
        targetBtn.innerHTML = '⏳ Generating...';

        try {
            await StrandsAPI.simulateAlert();
            targetBtn.innerHTML = '✓ Alert Sent';
            
            // Reload page after 1 second
            setTimeout(() => {
                location.reload();
            }, 1000);
        } catch (error) {
            console.error('Error simulating alert:', error);
            targetBtn.innerHTML = '✗ Failed';
            
            // Reset button after 3 seconds
            setTimeout(() => {
                targetBtn.innerHTML = originalContent;
                targetBtn.disabled = false;
            }, 3000);
        }
    }

    /**
     * Handle review button click (approve/reject)
     */
    static async handleReview(decisionId, isApproved, button) {
        const originalText = button.innerText;
        const originalClass = button.className;

        // Disable button and show loading state
        button.disabled = true;
        button.innerText = '⏳ Processing...';
        button.classList.add('loading');

        try {
            const result = await StrandsAPI.submitReview(decisionId, isApproved);

            if (result.status === 'success') {
                // Show success state
                button.innerText = isApproved ? '✓ Approved' : '✗ Rejected';
                button.classList.add('success');

                // Reload page after 1.5 seconds
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                throw new Error(result.message || 'Review submission failed');
            }
        } catch (error) {
            console.error('Error submitting review:', error);

            // Show error state
            button.innerText = '✗ Error';
            button.classList.add('error');

            // Reset button after 3 seconds
            setTimeout(() => {
                button.innerText = originalText;
                button.className = originalClass;
                button.disabled = false;
                button.classList.remove('loading', 'error');
            }, 3000);

            // Show error notification
            UI.showNotification('Error submitting review. Please try again.', 'error');
        }
    }

    /**
     * Show notification toast
     */
    static showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        // Add to DOM
        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Remove after 5 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 5000);
    }

    /**
     * Format timestamp
     */
    static formatTime(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleString();
        } catch (error) {
            console.error('Error formatting time:', error);
            return dateString;
        }
    }

    /**
     * Initialize UI on page load
     */
    static init() {
        // Add event listeners
        const simulateBtn = document.getElementById('simulate-alert-btn');
        if (simulateBtn) {
            simulateBtn.addEventListener('click', () => this.simulateAlert());
        }

        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Alt+S to simulate alert (handles both 's' and 'S')
            if (e.altKey && (e.key === 's' || e.key === 'S')) {
                e.preventDefault();
                this.simulateAlert();
            }
        });

        console.log('UI initialized');
    }

    /**
     * Refresh decisions
     */
    static async refreshDecisions() {
        try {
            const response = await fetch('/');
            const html = await response.text();
            
            // Parse and update decisions container
            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, 'text/html');
            const newContainer = newDoc.querySelector('.decisions-container');
            const currentContainer = document.querySelector('.decisions-container');

            if (newContainer && currentContainer) {
                currentContainer.innerHTML = newContainer.innerHTML;
            }
        } catch (error) {
            console.error('Error refreshing decisions:', error);
        }
    }

    /**
     * Poll for new decisions
     */
    static startPolling(interval = 5000) {
        setInterval(() => {
            this.refreshDecisions();
        }, interval);
    }
}

// Initialize UI when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => UI.init());
} else {
    UI.init();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UI;
}
