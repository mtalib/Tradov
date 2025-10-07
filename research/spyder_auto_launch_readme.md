# 🕷️ SPYDER Auto-Launch Setup Guide

**One-shot automated launcher: Gateway + Auto-Login + SPYDER Dashboard**

---

## 📋 Quick Start (5 Minutes)

### **Step 1: Setup Credentials in Bashrc**

```bash
cd ~/Projects/Spyder
python3 setup_bashrc_credentials.py
```

This will:
- ✅ Prompt for your IB username & password
- ✅ Add credentials to ~/.bashrc (encrypted in environment)
- ✅ Create convenient aliases (`spyder-launch`, `gateway-restart`, etc.)
- ✅ Setup SPYDER paths and environment

### **Step 2: Reload Bashrc**

```bash
source ~/.bashrc
```

### **Step 3: Launch SPYDER!**

```bash
spyder-launch
```

That's it! The launcher will:
1. ✅ Check if Gateway is running
2. ✅ Do nuclear restart if needed (clean state)
3. ✅ Launch Gateway with IBC auto-login
4. ✅ Wait for API to be ready
5. ✅ Launch SPYDER Dashboard
6. ✅ You start trading!

---

## 🚀 Launch Options

### **Normal Launch** (Smart - Uses Existing Gateway if Available)
```bash
spyder-launch
```

### **Clean Start** (Nuclear Restart + Fresh Gateway)
```bash
spyder-launch --clean-start
```

### **Use Existing Gateway** (Skip Gateway Launch)
```bash
spyder-launch --skip-gateway
```

---

## 🔧 Convenient Aliases

After setup, you have these commands available:

### **Quick Launch**
```bash
spyder-launch          # Smart launch (handles everything)
spyder-launch-clean    # Force clean restart
spyder-start           # Interactive mode with options
```

### **Gateway Management**
```bash
gateway-start          # Start Gateway only
gateway-restart        # Nuclear restart (fix stuck Gateway)
gateway-status         # Show Gateway processes
gateway-logs           # View Gateway logs in real-time
gateway-test           # Quick API connection test
```

### **SPYDER Components**
```bash
spyder-dashboard       # Launch Dashboard GUI only
spyder-main            # Launch Main System only
spyder-status          # Show SPYDER processes
spyder-logs            # View SPYDER logs
```

### **Navigation & Help**
```bash
spyder                 # cd to SPYDER directory
spyder-env             # Activate Python virtual environment
spyder-help            # Show all commands
```

---

## 💡 Common Scenarios

### **Morning Startup Routine**
```bash
# Option 1: One command (smart mode)
spyder-launch

# Option 2: Ensure clean start
spyder-launch --clean-start
```

### **Gateway Got Stuck?**
```bash
gateway-restart
```

Then wait for it to restart, or if still stuck:
```bash
spyder-launch --clean-start
```

### **Test Gateway API**
```bash
gateway-test
```

Output:
- ✅ Gateway API working
- ❌ Gateway API not responding

### **View Logs**
```bash
# Gateway logs
gateway-logs

# SPYDER logs  
spyder-logs

# Gateway status
gateway-status
```

---

## 🔐 Security Notes

### **Credentials Storage**

Your IB credentials are stored in `~/.bashrc` as environment variables:
```bash
export IB_USERNAME="your_username"
export IB_PASSWORD="your_password"
```

**Security Measures:**
1. ✅ Only readable by your user account
2. ✅ Not committed to git (bashrc is in gitignore)
3. ✅ Used only by your local scripts
4. ⚠️  Stored in plain text (standard for env variables)

**For Production:**
- Consider using encrypted credential storage
- Use OS keychain (keyring library)
- Or environment variable encryption tools

### **Securing Your Bashrc**
```bash
chmod 600 ~/.bashrc
```

---

## 🛠️ Troubleshooting

### **"Credentials not found"**

```bash
# Re-run setup
python3 setup_bashrc_credentials.py

# Reload bashrc
source ~/.bashrc

# Verify
echo $IB_USERNAME
```

### **Gateway Won't Start**

```bash
# Nuclear restart
gateway-restart

# Or force clean
spyder-launch --clean-start

# Check logs
gateway-logs
```

### **API Connection Timeout**

```bash
# Test API
gateway-test

# If failed, do nuclear restart
gateway-restart

# Wait 30 seconds, test again
sleep 30 && gateway-test
```

### **SPYDER Dashboard Won't Launch**

```bash
# Check if Gateway API is working
gateway-test

# Activate virtual environment
cd ~/Projects/Spyder
source .venv/bin/activate

# Launch manually
python3 SpyderG_GUI/SpyderG02_GUIEntry.py
```

---

## 📁 Files Created

### **In ~/Projects/Spyder/**
- `spyder_launch.py` - Main auto-launcher
- `setup_bashrc_credentials.py` - Credential setup
- `gateway_nuclear_restart.py` - Nuclear restart tool

### **Modified**
- `~/.bashrc` - Added SPYDER configuration

### **Backups**
- `~/.spyder_backups/bashrc_backup_*` - Bashrc backups

---

## 🎯 What Happens During Launch

```
🕷️  SPYDER AUTOMATED LAUNCHER
======================================================================

🔐 Checking credentials... ✅
🔍 Checking Gateway status...

Option: Using existing Gateway
OR
🔥 Nuclear restart: Cleaning Gateway state...
   1️⃣  Killing processes... ✅
   2️⃣  Clearing temp files... ✅  
   3️⃣  Port availability... ✅

🚀 Launching IB Gateway with auto-login...
   ✅ IBC started

⏳ Waiting for Gateway to be ready...
   [15s] Starting...
   [30s] Logging in...
   [45s] Initializing API...
   ✅ Port 4002 is listening!
   Waiting 10 seconds for API...

🧪 Verifying API connection...
   ✅ API CONNECTION SUCCESSFUL!
   Accounts: ['DU5361048']

🕷️  Launching SPYDER Dashboard...
   ✅ SPYDER Dashboard launched!

🎉 SPYDER IS NOW OPERATIONAL!
======================================================================
```

---

## 🏆 Production Tips

### **Daily Workflow**
```bash
# Morning: Start everything
spyder-launch

# During day: Monitor
gateway-status
spyder-status

# Evening: Check logs
spyder-logs
gateway-logs
```

### **Weekly Maintenance**
```bash
# Monday morning: Clean start
spyder-launch --clean-start

# Check for updates
cd ~/Projects/Spyder
git pull
```

### **If Issues Arise**
```bash
# Step 1: Nuclear restart
gateway-restart

# Step 2: If still broken
spyder-launch --clean-start

# Step 3: Check logs
gateway-logs
```

---

## 📞 Quick Reference

| Command | What It Does |
|---------|-------------|
| `spyder-launch` | Smart launch everything |
| `spyder-launch --clean-start` | Nuclear restart + launch |
| `gateway-restart` | Fix stuck Gateway |
| `gateway-test` | Test API connection |
| `gateway-logs` | View logs |
| `spyder-help` | Show all commands |

---

## 🎉 You're Ready!

Your SPYDER system is now configured for one-command automated launches!

**Just run:**
```bash
spyder-launch
```

**And start trading!** 🕷️💰

---

*For issues: Check logs with `gateway-logs` or `spyder-logs`*  
*For help: Run `spyder-help`*
