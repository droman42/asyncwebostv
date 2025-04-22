# AsyncWebOSTV Examples

This directory contains examples showing how to use the AsyncWebOSTV library to control WebOS TVs.

## Client Key Management

The library no longer stores client keys to files by default. Instead, client keys are:
1. Received during registration and returned to the caller
2. Can be provided directly to the client as a parameter
3. Should be stored by the application that uses the library if persistence is needed

## Available Examples

### 1. Discover TVs on the Network

Simple script to discover WebOS TVs on your local network:

```bash
python discover_tv.py
```

### 2. Simple Control Example

Basic example showing how to connect to a TV and control it:

```bash
# Using discovery to find TVs
python simple_example.py

# With explicit IP and client key
python simple_example.py --ip 192.168.1.100 --client-key YOUR_CLIENT_KEY
```

### 3. Subscription Example

Example showing how to subscribe to TV events:

```bash
python subscription_example.py --ip 192.168.1.100
```

### 4. Client Test Example

Comprehensive test showing client connection without file storage:

```bash
python client_test.py 192.168.1.100

# With a previously obtained client key
python client_test.py 192.168.1.100 --client-key YOUR_CLIENT_KEY
```

### 5. Secure Client Example

Example showing how to use the SecureWebOSClient for secure connections:

```bash
# Extract a certificate from a TV
python secure_client_example.py 192.168.1.100 --get-cert

# Verify if the certificate is still valid
python secure_client_example.py 192.168.1.100 --verify-cert

# Connect with certificate verification
python secure_client_example.py 192.168.1.100 --cert-file ~/192.168.1.100_cert.pem --client-key YOUR_CLIENT_KEY

# Debug mode for more verbose logging
python secure_client_example.py 192.168.1.100 --debug
```

### 6. Secure TV Example

Example showing how to use the high-level SecureWebOSTV client:

```bash
# Extract a certificate from a TV
python secure_tv_example.py 192.168.1.100 --extract-cert ~/tv_cert.pem

# Connect using a certificate
python secure_tv_example.py 192.168.1.100 --cert-file ~/tv_cert.pem --client-key YOUR_CLIENT_KEY

# Connect without certificate verification (less secure)
python secure_tv_example.py 192.168.1.100 --client-key YOUR_CLIENT_KEY
```

## Getting a Client Key

When you run any of these examples for the first time, you will be prompted to accept the connection on your TV. After accepting, a client key will be displayed. You can save this key and use it in subsequent connections to avoid the TV prompt.

Example:
```
2023-10-20 15:30:45 - root - INFO - Client key for future use: 123abc456def789
```

## SSL Certificate Management

For secure connections, the library provides methods to extract and verify certificates from WebOS TVs:

1. Extract a certificate from a TV:
```bash
python secure_client_example.py 192.168.1.100 --get-cert
```

2. Use the certificate for secure connections:
```bash
python secure_client_example.py 192.168.1.100 --cert-file ~/192.168.1.100_cert.pem --client-key YOUR_CLIENT_KEY
```

The certificate file is in PEM format and can be examined with standard OpenSSL tools:
```bash
openssl x509 -in tv_cert.pem -text -noout
``` 