"""Private media transport: ephemeral runner RSA keys and AES-GCM envelopes.

Only ciphertext and public keys may enter the public repository/artifacts.
Provider credentials are never used as transport keys or exported.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import time
import zipfile

import httpx
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT=Path(__file__).resolve().parent


def encode(data):return base64.b64encode(data).decode('ascii')
def decode(data):return base64.b64decode(data,validate=True)
def oaep():return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None)


def write_private(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data)
    path.chmod(0o600)


def seal(data,public_pem,aad):
    public=serialization.load_pem_public_key(public_pem)
    if not isinstance(public,rsa.RSAPublicKey) or public.key_size<3072:
        raise ValueError('RSA public key must be at least 3072 bits')
    key=AESGCM.generate_key(bit_length=256);nonce=secrets.token_bytes(12)
    cipher=AESGCM(key).encrypt(nonce,data,aad.encode())
    return {'version':1,'algorithm':'RSA-OAEP-SHA256+AES-256-GCM','aad':aad,
            'recipient_sha256':hashlib.sha256(public_pem).hexdigest(),
            'wrapped_key':encode(public.encrypt(key,oaep())),
            'nonce':encode(nonce),'ciphertext':encode(cipher)}


def unseal(envelope,private_pem,expected_aad=None):
    if envelope.get('version')!=1 or envelope.get('algorithm')!='RSA-OAEP-SHA256+AES-256-GCM':
        raise ValueError('Unsupported encrypted envelope')
    if expected_aad is not None and envelope['aad']!=expected_aad:
        raise ValueError('Envelope belongs to a different run, part or session')
    private=serialization.load_pem_private_key(private_pem,password=None)
    key=private.decrypt(decode(envelope['wrapped_key']),oaep())
    return AESGCM(key).decrypt(decode(envelope['nonce']),decode(envelope['ciphertext']),envelope['aad'].encode())


def init(private_dir,ready_dir,run_id):
    private_dir.mkdir(parents=True,exist_ok=True);private_dir.chmod(0o700)
    key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    write_private(private_dir/'input-private.pem',key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    ready={'version':1,'run_id':run_id,'session_nonce':secrets.token_hex(24),
           'input_public_key_pem':public.decode(),'parts':[2,3,4],
           'transport':'Only authenticated encryption envelopes are accepted; private key stays on this runner.'}
    ready_dir.mkdir(parents=True,exist_ok=True)
    (ready_dir/'ready.json').write_text(json.dumps(ready,indent=2))
    print('Private input channel initialized; only public key metadata is exported.',flush=True)


def receive(private_dir,ready_file,repository,run_id,wait_seconds):
    ready=json.loads(ready_file.read_text())
    if ready['run_id']!=run_id:raise ValueError('Ready metadata run mismatch')
    private=(private_dir/'input-private.pem').read_bytes()
    headers={'Accept':'application/vnd.github+json','User-Agent':'C01-private-input-receiver'}
    token=os.environ.get('GITHUB_TOKEN')
    if token:headers['Authorization']='Bearer '+token
    pending={2,3,4};deadline=time.monotonic()+wait_seconds
    with httpx.Client(headers=headers,timeout=60,follow_redirects=False) as client:
        while pending and time.monotonic()<deadline:
            for n in sorted(pending):
                path=f'protoface/ep01-c01/private-inputs/{run_id}/part-{n:02}.enc.json'
                response=client.get(f'https://api.github.com/repos/{repository}/contents/{path}',params={'ref':'main'})
                if response.status_code==404:continue
                response.raise_for_status()
                record=response.json()
                if record.get('encoding')!='base64':raise ValueError('Encrypted input exceeds the inline file limit')
                envelope=json.loads(base64.b64decode(record['content']))
                aad=f'c01-private-input-v1:{run_id}:{n}:{ready["session_nonce"]}'
                data=unseal(envelope,private,aad)
                packet=json.loads(data)
                if 'speech_guide' in packet:raise ValueError('Unexpected standalone recording')
                write_private(ROOT/'packed-fresh'/f'part-{n:02}.json',data)
                write_private(ROOT/'prompts-fresh'/f'part-{n:02}.txt',packet['prompt'].encode())
                pending.remove(n);print('Received private input part',n,flush=True)
            if pending:time.sleep(8)
    if pending:raise TimeoutError('Private input channel expired before receiving all three parts')


def seal_results(return_public,run_id,destination):
    public=return_public.read_bytes()
    destination.mkdir(parents=True,exist_ok=True)
    groups={
        'movies':['native-user-prompt/*.mp4','native-collected/*.mp4','fresh-output/*.mp4','fresh-output/render-info.json'],
        'checkpoint':['checkpoint-user-prompt/*.json','checkpoint-user-prompt/*.mp4','fresh-preflight/preflight.json']}
    for kind,patterns in groups.items():
        paths=sorted({p for pattern in patterns for p in ROOT.glob(pattern) if p.is_file()})
        if not paths:continue
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in paths:archive.write(p,p.relative_to(ROOT))
        envelope=seal(memory.getvalue(),public,f'c01-private-result-v1:{run_id}:{kind}')
        (destination/f'{kind}.sealed.json').write_text(json.dumps(envelope,separators=(',',':')))
        print('Encrypted',kind,'bundle with',len(paths),'files; no unencrypted media exported.',flush=True)


def open_archive(source,private_file,destination):
    data=unseal(json.loads(source.read_text()),private_file.read_bytes())
    destination.mkdir(parents=True,exist_ok=True)
    base=destination.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            resolved=(base/name).resolve()
            if not resolved.is_relative_to(base):raise ValueError('Invalid archive path')
        archive.extractall(destination)
    print('Decrypted bundle locally:',source.name)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['init','receive','seal-results','open'])
    p.add_argument('--private-dir',type=Path);p.add_argument('--ready-dir',type=Path)
    p.add_argument('--ready-file',type=Path);p.add_argument('--run-id',type=int)
    p.add_argument('--repository');p.add_argument('--wait-seconds',type=int,default=900)
    p.add_argument('--return-public',type=Path);p.add_argument('--destination',type=Path)
    p.add_argument('--source',type=Path);p.add_argument('--private-file',type=Path)
    a=p.parse_args()
    if a.mode=='init':init(a.private_dir,a.ready_dir,a.run_id)
    elif a.mode=='receive':receive(a.private_dir,a.ready_file,a.repository,a.run_id,a.wait_seconds)
    elif a.mode=='seal-results':seal_results(a.return_public,a.run_id,a.destination)
    else:open_archive(a.source,a.private_file,a.destination)


if __name__=='__main__':main()
