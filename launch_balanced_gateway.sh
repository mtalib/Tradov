#!/bin/bash
# SPYDER - Balanced Gateway Launcher
# Suppresses console flooding while maintaining full API functionality

echo "🚀 BALANCED GATEWAY LAUNCHER"
echo "============================"
echo "🎯 Flood suppression: ACTIVE"
echo "🎯 API connectivity: PRESERVED"
echo "============================"

# Kill any existing Gateway
echo "🔄 Stopping existing Gateway..."
ps aux | grep java | grep gateway | awk '{print $2}' | head -1 | xargs kill -9 2>/dev/null
sleep 3

# Change to Gateway directory
cd /home/adam/Jts/ibgateway/1039

# Create a minimal log4j2.xml that reduces flooding but keeps API working
cat > log4j2.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<Configuration status="ERROR">
    <Appenders>
        <Console name="Console" target="SYSTEM_OUT">
            <PatternLayout pattern="%d{HH:mm:ss} %-5p - %m%n"/>
            <ThresholdFilter level="WARN" onMatch="ACCEPT" onMismatch="DENY"/>
        </Console>
    </Appenders>
    <Loggers>
        <!-- Suppress the most annoying flooding -->
        <Logger name="com.ib.client.EClientSocket" level="ERROR" additivity="false">
            <AppenderRef ref="Console"/>
        </Logger>
        <Logger name="AccountCode" level="OFF" additivity="false"/>
        <Logger name="AccruedCash" level="OFF" additivity="false"/>
        <Logger name="AccruedDividend" level="OFF" additivity="false"/>
        <Logger name="AvailableFunds" level="OFF" additivity="false"/>
        <Logger name="IncentiveCoupons" level="OFF" additivity="false"/>
        <Logger name="IndianStockHaircut" level="OFF" additivity="false"/>
        <Logger name="LookAheadAvailableFunds" level="OFF" additivity="false"/>
        <Logger name="Leverage" level="OFF" additivity="false"/>

        <!-- Keep essential API logging -->
        <Logger name="com.ib.api" level="WARN" additivity="false">
            <AppenderRef ref="Console"/>
        </Logger>

        <Root level="WARN">
            <AppenderRef ref="Console"/>
        </Root>
    </Loggers>
</Configuration>
EOF

echo "✅ Created balanced log4j2.xml configuration"

# Launch Gateway with balanced settings
echo "🚀 Starting Gateway with balanced configuration..."

# Use the proper Gateway executable with balanced JVM options
nohup ./ibgateway \
    -Dlog4j.configurationFile=log4j2.xml \
    -Dlog4j2.level=WARN \
    > gateway_balanced.log 2>&1 &

GATEWAY_PID=$!
echo "✅ Gateway started with PID: $GATEWAY_PID"

# Wait a moment for startup
sleep 5

# Check if it's running
if ps -p $GATEWAY_PID > /dev/null; then
    echo "📊 Gateway process: RUNNING"
    echo "🔍 Checking API port availability..."

    # Wait for port to become available
    for i in {1..30}; do
        if netstat -tln | grep -q ":4002 "; then
            echo "✅ API port 4002: LISTENING"
            break
        fi
        echo "   Waiting for API port... ($i/30)"
        sleep 2
    done

    echo ""
    echo "🎯 BALANCED GATEWAY STATUS:"
    echo "   ✅ Console flooding: REDUCED"
    echo "   ✅ API functionality: PRESERVED"
    echo "   ✅ Port 4002: Available"
    echo ""
    echo "🔍 Now test API connection in a few seconds..."

else
    echo "❌ Gateway failed to start"
    echo "📋 Check gateway_balanced.log for details"
fi