package id.jaylabb.climategesture;

import android.util.Base64;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.math.BigInteger;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.PrivateKey;
import java.security.interfaces.RSAPublicKey;

import javax.crypto.Cipher;

/** Minimal ADB wire-protocol client (CNXN / AUTH / OPEN shell) over TCP. */
final class AdbClient {
    static final int CNXN = 0x4e584e43, AUTH = 0x48545541, OPEN = 0x4e45504f,
            OKAY = 0x59414b4f, CLSE = 0x45534c43, WRTE = 0x45545257;
    static final int VERSION = 0x01000001, MAXDATA = 256 * 1024;
    static final int AUTH_TOKEN = 1, AUTH_SIGNATURE = 2, AUTH_RSAPUBLICKEY = 3;

    static final class Msg { int cmd, a0, a1; byte[] data; }

    private final Socket sock;
    private final DataInputStream in;
    private final OutputStream out;
    private int nextId = 1;

    AdbClient(String host, int port, int timeoutMs) throws IOException {
        sock = new Socket();
        sock.connect(new InetSocketAddress(host, port), timeoutMs);
        sock.setSoTimeout(timeoutMs);
        in = new DataInputStream(new BufferedInputStream(sock.getInputStream()));
        out = new BufferedOutputStream(sock.getOutputStream());
    }

    void close() {
        try { sock.close(); } catch (IOException ignored) { }
    }

    private void send(int cmd, int a0, int a1, byte[] data) throws IOException {
        if (data == null) data = new byte[0];
        int sum = 0;
        for (byte b : data) sum += b & 0xff;
        ByteBuffer h = ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN);
        h.putInt(cmd).putInt(a0).putInt(a1).putInt(data.length).putInt(sum).putInt(~cmd);
        out.write(h.array());
        out.write(data);
        out.flush();
    }

    private Msg read() throws IOException {
        byte[] hb = new byte[24];
        in.readFully(hb);
        ByteBuffer h = ByteBuffer.wrap(hb).order(ByteOrder.LITTLE_ENDIAN);
        Msg m = new Msg();
        m.cmd = h.getInt(); m.a0 = h.getInt(); m.a1 = h.getInt();
        int len = h.getInt(); h.getInt();
        int magic = h.getInt();
        if (magic != ~m.cmd) throw new IOException("bad adb magic");
        if (len < 0 || len > 4 * MAXDATA) throw new IOException("bad adb length " + len);
        m.data = new byte[len];
        in.readFully(m.data);
        return m;
    }

    /** Handshake. If adbd does not know our key yet it shows "Allow debugging?" on screen. */
    void connect(KeyPair kp, String keyName, Runnable onPrompt) throws Exception {
        send(CNXN, VERSION, MAXDATA, "host::\0".getBytes(StandardCharsets.UTF_8));
        boolean signed = false;
        while (true) {
            Msg m = read();
            if (m.cmd == CNXN) return;
            if (m.cmd != AUTH || m.a0 != AUTH_TOKEN)
                throw new IOException("unexpected adb reply 0x" + Integer.toHexString(m.cmd));
            if (!signed) {
                send(AUTH, AUTH_SIGNATURE, 0, sign(kp.getPrivate(), m.data));
                signed = true;
            } else {
                String pub = encodePublicKey((RSAPublicKey) kp.getPublic()) + " " + keyName + "\0";
                send(AUTH, AUTH_RSAPUBLICKEY, 0, pub.getBytes(StandardCharsets.UTF_8));
                if (onPrompt != null) onPrompt.run();
                sock.setSoTimeout(120_000); // give the user time to tap Allow
            }
        }
    }

    /** Runs one shell command and returns its output. */
    String shell(String cmd) throws IOException {
        int id = nextId++;
        send(OPEN, id, 0, ("shell:" + cmd + "\0").getBytes(StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        while (true) {
            Msg m = read();
            if (m.a1 != id) continue; // late packet of an earlier stream
            if (m.cmd == WRTE) {
                sb.append(new String(m.data, StandardCharsets.UTF_8));
                send(OKAY, id, m.a0, null);
            } else if (m.cmd == CLSE) {
                send(CLSE, id, m.a0, null);
                return sb.toString();
            }
            // OKAY: stream opened / write acked, nothing to do
        }
    }

    interface Sink { void onData(byte[] b) throws IOException; }

    /** Opens a long-running shell command and hands every WRTE payload to sink until the stream closes. */
    void stream(String cmd, Sink sink) throws IOException {
        sock.setSoTimeout(0);
        int id = nextId++;
        send(OPEN, id, 0, ("shell:" + cmd + "\0").getBytes(StandardCharsets.UTF_8));
        while (true) {
            Msg m = read();
            if (m.a1 != id) continue;
            if (m.cmd == WRTE) {
                sink.onData(m.data);
                send(OKAY, id, m.a0, null);
            } else if (m.cmd == CLSE) {
                return;
            }
        }
    }

    // adbd verifies RSA_verify(NID_sha1, token): PKCS#1 v1.5 type-1 over SHA-1 DigestInfo + raw token.
    private static final byte[] SHA1_DIGESTINFO = {0x30, 0x21, 0x30, 0x09, 0x06, 0x05, 0x2b, 0x0e,
            0x03, 0x02, 0x1a, 0x05, 0x00, 0x04, 0x14};

    private static byte[] sign(PrivateKey key, byte[] token) throws Exception {
        Cipher c = Cipher.getInstance("RSA/ECB/PKCS1Padding");
        c.init(Cipher.ENCRYPT_MODE, key);
        c.update(SHA1_DIGESTINFO);
        return c.doFinal(token);
    }

    /** Android's adb public key format (android_pubkey_encode), base64. */
    static String encodePublicKey(RSAPublicKey pk) {
        BigInteger n = pk.getModulus();
        BigInteger r32 = BigInteger.ONE.shiftLeft(32);
        BigInteger n0inv = n.mod(r32).modInverse(r32).negate().mod(r32);
        BigInteger rr = BigInteger.ONE.shiftLeft(4096).mod(n);
        ByteBuffer b = ByteBuffer.allocate(4 + 4 + 256 + 256 + 4).order(ByteOrder.LITTLE_ENDIAN);
        b.putInt(64);
        b.putInt(n0inv.intValue());
        b.put(littleEndian(n, 256));
        b.put(littleEndian(rr, 256));
        b.putInt(pk.getPublicExponent().intValue());
        return Base64.encodeToString(b.array(), Base64.NO_WRAP);
    }

    private static byte[] littleEndian(BigInteger v, int len) {
        byte[] be = v.toByteArray();
        byte[] o = new byte[len];
        for (int i = 0; i < len && i < be.length; i++) o[i] = be[be.length - 1 - i];
        return o;
    }
}
