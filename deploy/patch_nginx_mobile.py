"""
Patch the nginx erp site config to allow plain HTTP for /api/mobile/.

The mobile app uses HTTP (self-signed HTTPS cert is rejected by Dio).
This script inserts a proxy location for /api/mobile/ into the HTTP
server block so the mobile app bypasses the HTTPS redirect.

Run as root: python3 deploy/patch_nginx_mobile.py /etc/nginx/sites-available/erp
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else '/etc/nginx/sites-available/erp'

with open(path) as f:
    conf = f.read()

if 'location /api/mobile/' in conf:
    print('[OK] nginx already has /api/mobile/ HTTP passthrough')
    sys.exit(0)

old = (
    '    location / {\n'
    '        return 301 https://$host$request_uri;\n'
    '    }\n'
    '}'
)
new = (
    '    location /api/mobile/ {\n'
    '        proxy_pass http://erp_backend;\n'
    '        proxy_set_header Host $host;\n'
    '        proxy_set_header X-Real-IP $remote_addr;\n'
    '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n'
    '        proxy_set_header X-Forwarded-Proto http;\n'
    '        proxy_connect_timeout 60s;\n'
    '        proxy_read_timeout 120s;\n'
    '        proxy_redirect off;\n'
    '    }\n\n'
    '    location / {\n'
    '        return 301 https://$host$request_uri;\n'
    '    }\n'
    '}'
)

patched = conf.replace(old, new, 1)
if patched == conf:
    print('[WARN] Could not find expected pattern — nginx config may differ from template')
    sys.exit(1)

with open(path, 'w') as f:
    f.write(patched)

print('[OK] Patched nginx config — /api/mobile/ now proxied over HTTP')
