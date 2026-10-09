---
id: SCALE-0004
title: Cryptography, hashing and random values
status: enforced
domain: security
artifacts: [diff, code, spec]
languages: [any]
owner: security
review_by: 2027-02-28
supersedes: []
summary: >
  Approved algorithms and libraries for hashing, encryption, signatures and random
  values in application code.
applies_when: >
  The content hashes, encrypts, decrypts or signs data, generates random tokens or ids,
  or configures TLS or a cryptographic library.
not_applies_when: >
  No hashing, encryption, signing, random token generation or TLS configuration is added,
  changed or described.
---

# SCALE-0004: Cryptography, hashing and random values

## Context

Weak or home-made cryptography is still found in code reviews: MD5 checksums used as
password hashes, `Math.random()` tokens, hard-coded IVs. This RFC lists what is allowed so
reviewers can check it without a security specialist.

## Requirements

### SCALE-0004.1 Password hashing algorithm
Passwords MUST be hashed with Argon2id, or with bcrypt at cost 12 or higher for existing
stores, and MUST NOT be hashed with MD5, SHA-1 or unsalted SHA-256.

- Applies when: the content hashes, stores or compares a user password or PIN.
- Enforcement: agent

### SCALE-0004.2 Secure random generator
Tokens, reset codes, session ids and nonces MUST be generated with a cryptographically
secure generator (`crypto.randomBytes`, `secrets`, `SecureRandom`, `crypto/rand`).

- Applies when: the content generates a token, code, nonce, salt or id used for authentication, authorization or unguessable links.
- Enforcement: agent

### SCALE-0004.3 Banned random functions
`Math.random()`, Python `random` and `java.util.Random` MUST NOT be used for any
security-relevant value.

- Applies when: the content calls `Math.random`, `random.random`, `random.randint`, `random.choice`, `kotlin.random.Random` or `java.util.Random`.
- Enforcement: linter

### SCALE-0004.4 Authenticated encryption
Symmetric encryption MUST use an authenticated mode such as AES-256-GCM or
ChaCha20-Poly1305, with a unique random nonce for each message.

- Applies when: the content encrypts or decrypts data with a symmetric cipher, or chooses a cipher mode, key size or IV.
- Enforcement: agent

### SCALE-0004.5 No custom cryptography
Code MUST use the platform library or the shared `crypto-kit` wrappers, and MUST NOT
implement its own cipher, padding scheme or signature algorithm.

- Applies when: the content implements bitwise encryption logic, custom padding, XOR obfuscation or a hand-written signature scheme.
- Enforcement: agent

### SCALE-0004.6 Constant-time comparison
Signatures, MACs and tokens MUST be compared with a constant-time function
(`hmac.compare_digest`, `crypto.timingSafeEqual`, `MessageDigest.isEqual`).

- Applies when: the content compares a received signature, HMAC, API token or reset code with an expected value.
- Enforcement: agent

### SCALE-0004.7 Keys from KMS
Encryption keys for data at rest SHOULD be data keys wrapped by the cloud KMS, so that the
key-encryption key never leaves the KMS.

- Applies when: the content creates, loads or stores an encryption key for data at rest, or encrypts a database column or file.
- Enforcement: agent

### SCALE-0004.8 TLS versions
Servers and clients SHOULD accept TLS 1.2 and TLS 1.3 only, and SHOULD NOT disable
certificate verification outside local tests.

- Applies when: the content configures TLS versions, cipher suites or certificate verification (`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify`).
- Enforcement: agent

### SCALE-0004.9 Hashing for identifiers
Pseudonymous identifiers derived from emails or phone numbers SHOULD use a keyed HMAC-SHA256
rather than a plain hash, so they cannot be reversed with a dictionary.

- Applies when: the content hashes an email, phone number or other personal identifier to build a lookup key or analytics id.
- Enforcement: agent

### SCALE-0004.10 Checksums
Non-security checksums such as cache keys or file deduplication MAY use fast hashes like
xxHash or CRC32.

- Applies when: the content hashes data only to build a cache key, detect duplicates or check file integrity in transit.
- Enforcement: agent
