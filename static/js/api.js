/**
 * API client for Strands Governance Dashboard
 * Handles all communication with the backend
 */

class StrandsAPI {
    static BASE_URL = '/api';
    static TIMEOUT = 10000; // 10 seconds

    /**
     * Make a fetch request with timeout
     */
    static async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.TIMEOUT);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            console.error(`API Error: ${endpoint}`, error);
            throw error;
        }
    }

    /**
     * Simulate a new alert
     */
    static async simulateAlert(forceAmbiguous = false) {
        try {
            const params = new URLSearchParams();
            params.append('active', 'true');
            if (forceAmbiguous) {
                params.append('force_ambiguous', 'true');
            }

            const response = await fetch(`/simulate/alert?${params}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`Failed to simulate alert: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error simulating alert:', error);
            throw error;
        }
    }

    /**
     * Get all pending decisions
     */
    static async getDecisions() {
        return this.request('/decisions');
    }

    /**
     * Submit a review for a decision
     */
    static async submitReview(decisionId, isApproved, feedback = null) {
        return this.request(`/decisions/${decisionId}/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                decision_id: decisionId,
                is_approved: isApproved,
                feedback: feedback,
                validated_by: 'Human Operator'
            })
        });
    }

    /**
     * Get decision details
     */
    static async getDecisionDetails(decisionId) {
        return this.request(`/decisions/${decisionId}`);
    }

    /**
     * Get metrics
     */
    static async getMetrics() {
        return this.request('/metrics');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StrandsAPI;
}
