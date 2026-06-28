# 2026-05-04 Telegram Incident Response Runbook

## Scope
This runbook covers Telegram command/control incidents for Tradov when running from desktop launcher or direct A01 startup.

## 1. No Telegram Response
1. Send `/help`, then `/status`.
2. If no reply:
   1. Verify process is running:
      - `ps -ef | grep TradovA01_Main.py | grep -v grep`
   2. Check launcher log:
      - `tail -n 80 logs/launcher/tradov-desktop-launch.log`
   3. Confirm log lines exist:
      - `Telegram operator command polling enabled`
      - `Telegram bot initialized from A01`
3. If missing, restart Tradov from icon and retry `/status`.

## 2. Session Running: NO
1. Send `/status` to verify current state.
2. If `Resume Failed Gates: session_supervisor`:
   1. Restart Tradov from icon (A01 autostarts paper SessionSupervisor).
   2. Re-check `/status`.

## 3. Kill Lock Stuck ACTIVE
1. Stop Tradov.
2. Remove lock:
   - `rm -f ~/.tradov_kill_lock`
3. Start Tradov again.
4. Send `/status` and verify `Kill Lock: INACTIVE`.

## 4. Resume Denied
1. Send `/status`.
2. Read `Resume Failed Gates` and resolve listed items.
3. Retry:
   1. `/resume`
   2. `/confirm resume TOKEN`

## 5. Emergency Halt
1. Send `/halt`.
2. Confirm with `/confirm halt TOKEN`.
3. Verify with `/status`:
   1. Kill lock is active.
   2. Session state transitions safely.

## 6. Flatten Immediately
1. Send `/flatten`.
2. Confirm with `/confirm flatten TOKEN`.
3. Verify via dashboard and `/status`.

## 7. Repeated Started/Stopping Messages
1. Usually indicates repeated restarts or multiple instances.
2. Reset to one instance:
   1. `pkill -f TradovA01_Main.py`
   2. Start once from icon.
   3. Re-check `/status`.

## 8. Token/Chat/User-ID Mismatch
1. Validate token:
   - `https://api.telegram.org/bot<token>/getMe`
2. Validate updates:
   - `https://api.telegram.org/bot<token>/getUpdates`
3. Ensure `.env` values match Telegram payload:
   1. `TELEGRAM_CHAT_ID = message.chat.id`
   2. `TELEGRAM_ALLOWED_USER_IDS = message.from.id`

## 9. Token Exposed (Security Event)
1. Rotate token in BotFather immediately.
2. Update `.env` with new token.
3. Restart Tradov.
4. Validate with `/status`.

## Quick Daily Safe Sequence
1. `/status` at startup.
2. Midday `/status` check.
3. Use `/halt` + confirm token for emergency stop.
4. Use `/resume` + confirm token after gates pass.
5. End-day `/status` confirmation.

## Notes
1. `Bot Running: YES` means Telegram command polling is alive.
2. `Session Running: YES` means backend session supervisor is running.
3. `Resume Failed Gates: none` is the target precondition for clean resume behavior.
