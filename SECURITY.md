# Security, Privacy & Non-Inspection Policy

## 🔒 Zero-Payload Principle

This research system is explicitly designed for **Encrypted Network Traffic Classification without payload decryption or content inspection**.

### Guarantees:
1. **No Deep Packet Inspection (DPI)**: The pipeline strictly inspects Layer-3 (IP), Layer-4 (TCP/UDP), and unencrypted initial handshake headers (TLS ClientHello metadata where present).
2. **No Payload Decryption**: The system does not perform SSL/TLS interception, man-in-the-middle decryption, or private key extraction.
3. **No Payload Storage**: Packet buffers and application payload contents are discarded immediately after header length and timing extraction.
4. **Metadata Sanitization**: Network identifiers (raw IP addresses) are scrubbed from machine-learning feature vectors to ensure privacy and prevent models from learning spurious network topology shortcuts.
5. **Dashboard Privacy**: The real-time monitoring console presents anonymized Flow IDs, protocol types, ports, packet rates, and statistical traffic categories without displaying sensitive user endpoints.
