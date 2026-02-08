## 2026-02-06 - Missing Dashboard Restoration
**Learning:** The FastAPI server was missing its primary governance dashboard template, leading to 500 errors. Restoring it with an accessible, Tailwind-based UI immediately improved the usability of the entire project.
**Action:** Always check for missing templates when a server is present, and ensure they follow accessibility standards (ARIA, focus states).
## 2026-02-08 - Notification System & Keyboard Shortcuts
**Learning:** Adding visible keyboard shortcuts (like <kbd>Alt+S</kbd>) and functional notifications with proper ARIA attributes significantly improves both power-user efficiency and accessibility.
**Action:** Always include keyboard shortcut hints and use `aria-live` containers for asynchronous feedback.
