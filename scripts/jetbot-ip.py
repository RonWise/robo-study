#!/usr/bin/env python3
"""Update a narrowly scoped Jetbot DDS firewall rule on the laptop."""
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def validate(record):
    address = ipaddress.IPv4Address(record['ip'])
    if address.is_multicast or address.is_unspecified or address.is_loopback or address.is_reserved:
        raise ValueError('Укажите IPv4-адрес Jetbot, например 10.11.139.31.')
    domain = int(record['domain'])
    if not 0 <= domain <= 232:
        raise ValueError('ROS_DOMAIN_ID должен быть от 0 до 232.')
    zone = record['zone']
    if not isinstance(zone, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', zone):
        raise ValueError('Некорректная зона firewall.')
    return {'ip': str(address), 'domain': domain, 'zone': zone}


def rule(record):
    first = 7400 + 250 * record['domain']
    last = min(first + 249, 65535)
    return (f'rule family="ipv4" source address="{record["ip"]}/32" '
            f'port port="{first}-{last}" protocol="udp" accept')


def apply(new, old):
    new = validate(new)
    old = validate(old) if old is not None else None
    # Add both copies first; a failure must not remove the previous access rule.
    for scope in ([], ['--permanent']):
        subprocess.run(['/usr/bin/firewall-cmd', *scope,
                        '--zone=' + new['zone'], '--add-rich-rule=' + rule(new)], check=True)
    if old is not None and old != new:
        for scope in ([], ['--permanent']):
            subprocess.run(['/usr/bin/firewall-cmd', *scope,
                            '--zone=' + old['zone'], '--remove-rich-rule=' + rule(old)], check=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--apply':
        if os.geteuid() != 0:
            raise ValueError('Применение firewall требует прав администратора.')
        plan = json.loads(sys.argv[2])
        apply(plan['new'], plan['old'])
        return
    if len(sys.argv) != 1:
        raise ValueError('Используйте make new_ip IP=10.11.139.31')
    if os.geteuid() == 0:
        raise ValueError('Запускайте make new_ip от обычного пользователя, без sudo.')
    address = os.environ.get('IP', '').strip()
    if not address:
        if not sys.stdin.isatty():
            raise ValueError('Укажите адрес: make new_ip IP=10.11.139.31')
        address = input('IPv4-адрес Jetbot: ').strip()
    env = {}
    for line in (ROOT / '.env').read_text().splitlines():
        match = re.fullmatch(r'\s*(ROS_DOMAIN_ID|ROS_LOCALHOST_ONLY)\s*=\s*([0-9]+)\s*(?:#.*)?', line)
        if match:
            env[match[1]] = match[2]
    domain = os.environ.get('ROS_DOMAIN_ID', env.get('ROS_DOMAIN_ID', '0'))
    localhost = os.environ.get('ROS_LOCALHOST_ONLY', env.get('ROS_LOCALHOST_ONLY', '1'))
    # Validate before passing the address to external commands.
    validate({'ip': address, 'domain': domain, 'zone': 'public'})
    if localhost != '0':
        raise ValueError('Сначала задайте ROS_LOCALHOST_ONLY=0 в .env и выполните make up.')
    route = json.loads(run('/usr/bin/ip', '-j', 'route', 'get', address))[0]
    interface = route['dev']
    zone = run('/usr/bin/firewall-cmd', '--get-zone-of-interface=' + interface)
    if zone in ('', 'no zone'):
        zone = run('/usr/bin/firewall-cmd', '--get-default-zone')
    new = validate({'ip': address, 'domain': domain, 'zone': zone})
    state = ROOT / '.runtime' / 'jetbot-firewall.json'
    old = validate(json.loads(state.read_text())) if state.exists() else None
    print(f'Jetbot {new["ip"]}; интерфейс {interface}; зона {zone}; ROS_DOMAIN_ID={new["domain"]}', flush=True)
    print('Разрешение: ' + rule(new), flush=True)
    if old is not None and old != new:
        print(f'Прежнее сохранённое разрешение для {old["ip"]} будет удалено.', flush=True)
    plan = json.dumps({'new': new, 'old': old})
    subprocess.run(['/usr/bin/pkexec', '/usr/bin/python3', str(Path(__file__).resolve()), '--apply', plan], check=True)
    state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = state.with_suffix('.tmp')
    temporary.write_text(json.dumps(new, indent=2) + '\n')
    temporary.replace(state)
    print('Готово: правило применено и сохранено после перезагрузки.')
    print('Проверка: make run CMD="ros2 topic list --no-daemon --spin-time 5"')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Ошибка: {exc}', file=sys.stderr)
        sys.exit(1)
