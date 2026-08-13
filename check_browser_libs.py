import sys

sys.stdout.reconfigure(encoding='utf-8')

for mod in ['playwright', 'selenium', 'undetected_chromedriver', 'tls_client', 'cloudscraper', 'curl_cffi']:
    try:
        __import__(mod)
        print(f"✅ {mod} is INSTALLED")
    except ImportError:
        print(f"❌ {mod} is NOT installed")
