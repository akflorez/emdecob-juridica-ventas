import requests

base = 'https://juricob.emdecob.com'

print('=== PROBING LIVE SERVER ===')
paths = ['/api/', '/api/docs', '/auth/login', '/api/auth/login', '/docs', '/api/auth/register-company']
for path in paths:
    try:
        r = requests.get(base + path, timeout=6)
        ct = r.headers.get('content-type', '')[:40]
        print(f'GET {path} => {r.status_code} | ct={ct} | body={r.text[:80]}')
    except Exception as e:
        print(f'GET {path} => ERROR: {e}')

print()
print('=== POST /api/auth/register-company ===')
try:
    payload = {
        'company_name': 'TestProbe',
        'company_nit': '111222333',
        'admin_name': 'Admin Probe',
        'email': 'probe@testprobe.com',
        'password': 'Probe1234!',
        'confirm_password': 'Probe1234!'
    }
    r = requests.post(base + '/api/auth/register-company', json=payload, timeout=10)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text[:400]}')
except Exception as e:
    print(f'ERROR: {e}')

print()
print('=== POST /auth/register-company ===')
try:
    payload = {
        'company_name': 'TestProbe',
        'company_nit': '111222333',
        'admin_name': 'Admin Probe',
        'email': 'probe@testprobe.com',
        'password': 'Probe1234!',
        'confirm_password': 'Probe1234!'
    }
    r = requests.post(base + '/auth/register-company', json=payload, timeout=10)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text[:400]}')
except Exception as e:
    print(f'ERROR: {e}')

print()
print('=== What does Nginx return for /api/ ===')
try:
    r = requests.get(base + '/api/', timeout=6)
    print(f'Server header: {r.headers.get("server", "n/a")}')
    print(f'Full response body: {r.text[:500]}')
except Exception as e:
    print(f'ERROR: {e}')
