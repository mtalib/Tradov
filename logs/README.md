# Logs Directory

This directory contains runtime logs for the Spyder trading system.

## Log Files

- `spyder.log` - Main application log (created automatically)
- Other log files are created based on system configuration

## Configuration

Logging is configured in `config/config.py`:
- Log level: Controlled by `LOG_LEVEL` environment variable (default: INFO)
- Log rotation: Daily
- Retention: 30 days

## Viewing Logs

```bash
# View latest logs
tail -f logs/spyder.log

# View with timestamp filtering
grep "2025-11-25" logs/spyder.log

# View errors only
grep "ERROR" logs/spyder.log
```

## Note

Log files are automatically ignored by git (see `.gitignore` in this directory).
