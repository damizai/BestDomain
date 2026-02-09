import os
import requests

def get_ip_list(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return [ip.strip() for ip in response.text.splitlines() if ip.strip()]

def get_cloudflare_zone(api_token):
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json',
    }
    response = requests.get(
        'https://api.cloudflare.com/client/v4/zones',
        headers=headers
    )
    response.raise_for_status()
    zones = response.json().get('result', [])
    if not zones:
        raise Exception("No zones found")
    return zones[0]['id'], zones[0]['name']

def delete_existing_dns_records(api_token, zone_id, subdomain, domain):
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json',
    }
    record_name = domain if subdomain == '@' else f'{subdomain}.{domain}'

    for record_type in ("A", "AAAA"):
        while True:
            resp = requests.get(
                f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records',
                headers=headers,
                params={
                    "type": record_type,
                    "name": record_name
                }
            )
            resp.raise_for_status()
            records = resp.json().get('result', [])
            if not records:
                break

            for record in records:
                del_resp = requests.delete(
                    f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record["id"]}',
                    headers=headers
                )
                del_resp.raise_for_status()
                print(f"Del {record_type} {record_name} → {record['content']}")

def detect_record_type(ip):
    return "AAAA" if ":" in ip else "A"

def update_cloudflare_dns(ip_list, api_token, zone_id, subdomain, domain):
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json',
    }
    record_name = domain if subdomain == '@' else f'{subdomain}.{domain}'

    for ip in ip_list:
        record_type = detect_record_type(ip)
        data = {
            "type": record_type,
            "name": record_name,
            "content": ip,
            "ttl": 1,
            "proxied": False
        }

        resp = requests.post(
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records',
            headers=headers,
            json=data
        )

        if resp.status_code == 200:
            print(f"Add {record_type} {record_name} → {ip}")
        else:
            print(
                f"Failed {record_type} {record_name} → {ip} | "
                f"{resp.status_code} {resp.text}"
            )

if __name__ == "__main__":
    api_token = os.getenv("CF_API_TOKEN")
    if not api_token:
        raise Exception("CF_API_TOKEN not set")

    subdomain_ip_mapping = {
        "bestcf": "https://ipdb.api.030101.xyz/?type=bestcfv6;bestcfv4;bestproxy",
    }

    zone_id, domain = get_cloudflare_zone(api_token)

    for subdomain, url in subdomain_ip_mapping.items():
        print(f"\n=== Updating {subdomain}.{domain} ===")
        ip_list = get_ip_list(url)
        delete_existing_dns_records(api_token, zone_id, subdomain, domain)
        update_cloudflare_dns(ip_list, api_token, zone_id, subdomain, domain)
