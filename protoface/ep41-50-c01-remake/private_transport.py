"""Generic RSA-OAEP/AES-GCM transport; no provider credentials are transport keys."""
from pathlib import Path
import base64
import hashlib
import json
import os
import secrets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encode(data):
    return base64.b64encode(data).decode('ascii')


def decode(data):
    return base64.b64decode(data, validate=True)


def oaep():
    return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


def write_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def seal(data, public_pem, aad):
    public = serialization.load_pem_public_key(public_pem)
    if not isinstance(public, rsa.RSAPublicKey) or public.key_size < 3072:
        raise ValueError('RSA public key must be at least 3072 bits')
    key = AESGCM.generate_key(bit_length=256)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, aad.encode())
    return {'version': 1, 'algorithm': 'RSA-OAEP-SHA256+AES-256-GCM', 'aad': aad,
            'recipient_sha256': hashlib.sha256(public_pem).hexdigest(),
            'wrapped_key': encode(public.encrypt(key, oaep())),
            'nonce': encode(nonce), 'ciphertext': encode(ciphertext)}


def unseal(envelope, private_pem, expected_aad=None):
    if envelope.get('version') != 1 or envelope.get('algorithm') != 'RSA-OAEP-SHA256+AES-256-GCM':
        raise ValueError('Unsupported encrypted envelope')
    if expected_aad is not None and envelope.get('aad') != expected_aad:
        raise ValueError('Envelope belongs to a different series, run, part or session')
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, rsa.RSAPrivateKey) or private.key_size < 3072:
        raise ValueError('RSA private key must be at least 3072 bits')
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    if envelope.get('recipient_sha256') != hashlib.sha256(public).hexdigest():
        raise ValueError('Envelope recipient mismatch')
    nonce = decode(envelope['nonce'])
    if len(nonce) != 12:
        raise ValueError('Invalid envelope nonce')
    key = private.decrypt(decode(envelope['wrapped_key']), oaep())
    return AESGCM(key).decrypt(nonce, decode(envelope['ciphertext']), envelope['aad'].encode())


def init(private_dir, ready_dir, run_id):
    private_dir, ready_dir = Path(private_dir), Path(ready_dir)
    private_dir.mkdir(parents=True, exist_ok=True)
    private_dir.chmod(0o700)
    if (private_dir / 'input-private.pem').exists() or (ready_dir / 'ready.json').exists():
        raise FileExistsError('Input session already exists; preserve its original key and metadata')
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    write_private(private_dir / 'input-private.pem', key.private_bytes(serialization.Encoding.PEM,
                  serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    ready = {'version': 1, 'run_id': run_id, 'session_nonce': secrets.token_hex(24),
             'input_public_key_pem': public.decode(), 'parts': list(range(1, 13)),
             'transport': 'Authenticated encrypted inputs only; private key stays on runner.'}
    ready_dir.mkdir(parents=True, exist_ok=True)
    (ready_dir / 'ready.json').write_text(json.dumps(ready, indent=2))
    print('Ephemeral private input channel initialized; only public metadata is exported.', flush=True)

