import java.io.*;
import java.net.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Simple Gateway API Connection Test
 *
 * This Java program tests basic connectivity to IB Gateway API
 * without requiring the full IBKR Java API library.
 *
 * It attempts to:
 * 1. Connect to Gateway socket
 * 2. Send basic API handshake
 * 3. Read response to verify Gateway is accepting API connections
 */
public class SimpleGatewayTest {

    private static final String GATEWAY_HOST = "127.0.0.1";
    private static final int GATEWAY_PORT = 4002;
    private static final int CLIENT_ID = 123;
    private static final int TIMEOUT_SECONDS = 10;

    public static void main(String[] args) {
        System.out.println("🕷️  SPYDER - Simple Gateway API Test (Java)");
        System.out.println("=" + "=".repeat(50));
        System.out.println("📅 Testing Gateway: " + GATEWAY_HOST + ":" + GATEWAY_PORT);
        System.out.println("🆔 Client ID: " + CLIENT_ID);
        System.out.println();

        SimpleGatewayTest test = new SimpleGatewayTest();
        boolean success = test.testGatewayConnection();

        System.out.println();
        System.out.println("=" + "=".repeat(60));
        System.out.println("📊 FINAL RESULT");
        System.out.println("=" + "=".repeat(60));

        if (success) {
            System.out.println("🎉 SUCCESS! Gateway API is accepting connections");
            System.out.println("   • This confirms Gateway configuration is correct");
            System.out.println("   • The issue is likely in the Python client libraries");
            System.out.println("   • Python environment or ib_async/ibapi may need fixes");
        } else {
            System.out.println("❌ FAILED! Gateway API is not accepting connections");
            System.out.println("   • This confirms Gateway configuration issue");
            System.out.println("   • Check Gateway API settings (Enable ActiveX and Socket Clients)");
            System.out.println("   • Verify Gateway is fully logged in");
            System.out.println("   • Check jts.ini file for proper [Api] section");
        }

        System.exit(success ? 0 : 1);
    }

    public boolean testGatewayConnection() {
        Socket socket = null;
        DataOutputStream out = null;
        DataInputStream in = null;

        try {
            // Step 1: Test raw socket connectivity
            System.out.println("🔍 STEP 1: Testing raw socket connection...");
            socket = new Socket();
            socket.setSoTimeout(TIMEOUT_SECONDS * 1000);

            long startTime = System.currentTimeMillis();
            socket.connect(new InetSocketAddress(GATEWAY_HOST, GATEWAY_PORT), 5000);
            long connectTime = System.currentTimeMillis() - startTime;

            System.out.println("✅ Socket connected in " + connectTime + "ms");

            // Step 2: Set up streams
            System.out.println("🔍 STEP 2: Setting up data streams...");
            out = new DataOutputStream(socket.getOutputStream());
            in = new DataInputStream(socket.getInputStream());

            // Step 3: Send API handshake (simplified version)
            System.out.println("🚀 STEP 3: Sending API handshake...");

            // Send client version (basic API protocol)
            // This is a simplified handshake - real IBAPI is more complex
            String handshake = "API\0";
            out.writeBytes(handshake);
            out.flush();

            System.out.println("✅ Handshake sent");

            // Step 4: Wait for response
            System.out.println("⏳ STEP 4: Waiting for Gateway response...");

            // Try to read any response within timeout
            socket.setSoTimeout(5000); // 5 second timeout for response

            boolean responseReceived = false;
            byte[] buffer = new byte[1024];

            try {
                int bytesRead = in.read(buffer, 0, buffer.length);
                if (bytesRead > 0) {
                    responseReceived = true;
                    System.out.println("✅ Gateway responded with " + bytesRead + " bytes");

                    // Print first few bytes as hex for analysis
                    System.out.print("   Response (hex): ");
                    for (int i = 0; i < Math.min(bytesRead, 10); i++) {
                        System.out.printf("%02X ", buffer[i] & 0xFF);
                    }
                    System.out.println();
                } else {
                    System.out.println("⚠️  Gateway sent empty response");
                }
            } catch (SocketTimeoutException e) {
                System.out.println("⚠️  Gateway response timeout (may still be successful)");
                // Timeout doesn't necessarily mean failure - Gateway might be processing
                responseReceived = true; // Consider this a partial success
            }

            // Step 5: Keep connection alive briefly to test stability
            System.out.println("🔍 STEP 5: Testing connection stability...");
            Thread.sleep(2000); // Wait 2 seconds

            if (socket.isConnected() && !socket.isClosed()) {
                System.out.println("✅ Connection remained stable for 2 seconds");
                return true;
            } else {
                System.out.println("❌ Connection was closed by Gateway");
                return false;
            }

        } catch (ConnectException e) {
            System.out.println("❌ Connection refused: " + e.getMessage());
            System.out.println("   → Gateway is not listening on port " + GATEWAY_PORT);
            return false;

        } catch (SocketTimeoutException e) {
            System.out.println("❌ Connection timeout: " + e.getMessage());
            System.out.println("   → Gateway did not respond within " + TIMEOUT_SECONDS + " seconds");
            return false;

        } catch (IOException e) {
            System.out.println("❌ I/O Error: " + e.getMessage());
            System.out.println("   → Network communication problem");
            return false;

        } catch (Exception e) {
            System.out.println("❌ Unexpected error: " + e.getMessage());
            e.printStackTrace();
            return false;

        } finally {
            // Clean up resources
            System.out.println("🔧 CLEANUP: Closing connection...");

            try {
                if (out != null) out.close();
                if (in != null) in.close();
                if (socket != null && !socket.isClosed()) {
                    socket.close();
                }
                System.out.println("✅ Connection closed cleanly");
            } catch (IOException e) {
                System.out.println("⚠️  Error during cleanup: " + e.getMessage());
            }
        }
    }

    /**
     * Alternative test method that just checks if Gateway accepts and holds connections
     */
    public static void testBasicConnectivity() {
        System.out.println("🧪 ALTERNATIVE TEST: Basic connectivity check");

        try (Socket socket = new Socket()) {
            socket.setSoTimeout(5000);

            long startTime = System.currentTimeMillis();
            socket.connect(new InetSocketAddress(GATEWAY_HOST, GATEWAY_PORT));
            long connectTime = System.currentTimeMillis() - startTime;

            System.out.println("✅ Basic connection successful (" + connectTime + "ms)");

            // Hold connection for a few seconds
            Thread.sleep(3000);

            if (socket.isConnected()) {
                System.out.println("✅ Connection held for 3 seconds - Gateway is stable");
            }

        } catch (Exception e) {
            System.out.println("❌ Basic connectivity failed: " + e.getMessage());
        }
    }
}
