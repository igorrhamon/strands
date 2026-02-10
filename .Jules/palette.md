## 2026-02-06 - Missing Dashboard Restoration
**Learning:** The FastAPI server was missing its primary governance dashboard template, leading to 500 errors. Restoring it with an accessible, Tailwind-based UI immediately improved the usability of the entire project.
**Action:** Always check for missing templates when a server is present, and ensure they follow accessibility standards (ARIA, focus states).

## 2026-02-08 - Notification System & Keyboard Shortcuts
**Learning:** Adding visible keyboard shortcuts (like <kbd>Alt+S</kbd>) and functional notifications with proper ARIA attributes significantly improves both power-user efficiency and accessibility.
**Action:** Always include keyboard shortcut hints and use `aria-live` containers for asynchronous feedback.

## 2026-10-27 - Contextual Copy & Destructive Confirmation
**Learning:** Providing a "Copy to Clipboard" button for key technical content (like hypotheses) and a confirmation dialog for destructive actions (like Reject) significantly reduces friction and prevents accidental data loss in SRE workflows.
**Action:** Identify core data fields that users might need to share and add micro-copy buttons; always guard destructive state changes with confirmation.
