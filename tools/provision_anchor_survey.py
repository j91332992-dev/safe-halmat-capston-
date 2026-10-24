"""Provision the shared survey device key locally; never prints the key."""
import argparse
from pathlib import Path
import re
import secrets


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-env',type=Path,default=root/'backend/.env')
    parser.add_argument('--wifi-header',type=Path,default=root/'firmware/uwb_multi_test/include/wifi_secrets.h')
    parser.add_argument('--site-id')
    args=parser.parse_args()
    if not args.wifi_header.is_file():
        parser.error('Create local wifi_secrets.h with the current network/server settings first.')
    env=args.backend_env.read_text(encoding='utf-8-sig') if args.backend_env.exists() else ''
    header=args.wifi_header.read_text(encoding='utf8')
    match=re.search(r'^UWB_SURVEY_DEVICE_TOKEN=(.+)$',env,re.M)
    old=re.search(r'^#define HANMIR_SURVEY_TOKEN "([^"]+)"',header,re.M)
    token=match[1].strip().strip('"') if match else old[1] if old and len(old[1])>=20 else secrets.token_urlsafe(32)
    if len(token)<20 or not re.fullmatch(r'[A-Za-z0-9_-]+',token):
        parser.error('Existing device key is too short or has unsupported characters; fix the local key explicitly.')
    old_site=re.search(r'^UWB_SURVEY_SITE_ID=(.+)$',env,re.M)
    site=args.site_id or (old_site[1].strip() if old_site else 'site-001')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',site):parser.error('Invalid site ID')
    for key,value in {'UWB_SURVEY_DEVICE_TOKEN':token,'UWB_SURVEY_SITE_ID':site}.items():
        pattern=rf'(?m)^{key}=.*$'
        env=re.sub(pattern,key+'='+value,env) if re.search(pattern,env) else env.rstrip()+'\n'+key+'='+value+'\n'
    header=re.sub(r'(?m)^#define HANMIR_SURVEY_TOKEN .*\n?','',header)
    args.backend_env.parent.mkdir(parents=True,exist_ok=True)
    args.backend_env.write_text(env,encoding='utf8')
    args.wifi_header.write_text(header.rstrip()+'\n#define HANMIR_SURVEY_TOKEN "'+token+'"\n',encoding='utf8')
    print('Survey credential configured locally for site '+site+'. Key not printed.')
    print('Restart backend and build anchor-01-survey. Keep .env and wifi_secrets.h out of Git.')


if __name__=='__main__':main()
