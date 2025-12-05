# Implementation Plan: Email Notification

## Goal
Add functionality to automatically send the generated CANSLIM report to the user's email address.

## Proposed Changes

### 1. Configuration (`v2_optimized/config.py`)
- Add `EmailConfig` class to store SMTP settings and credentials.
- Add `EMAIL` section to `UnifiedConfig`.

### 2. Email Utility (`v2_optimized/email_notifier.py`) [NEW]
- Create a `EmailNotifier` class.
- Implement `send_report(subject, content_markdown)` method.
- Use `markdown` library (if available) or simple text formatting to convert Markdown to HTML for the email body.
- Support sending the report as an attachment as well.

### 3. Pipeline Integration (`v2_optimized/run_full_pipeline.py`)
- Import `EmailNotifier`.
- In `main()`, after report generation, call `EmailNotifier.send_report()`.
- Add a check to only send if email config is valid.

## Verification Plan
- Create `v2_optimized/test_email.py` to send a test email.
- User will need to provide their SMTP credentials (e.g., Gmail App Password) in `config.py`.
