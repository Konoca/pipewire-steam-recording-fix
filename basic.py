#!/usr/bin/env python3

import re
import subprocess
import time
from helpers import run_cmd, notify, load_settings

CFG = load_settings()

DESTS = CFG.get('destinations', [])
DESTS_RE = [re.compile(pattern) for pattern in DESTS]

SRCS = CFG.get('sources', [])
SRCS_RE = [re.compile(pattern) for pattern in SRCS]

FIELDS = CFG.get('fields', [])
FREQ = CFG.get('monitor frequency', 1)


def get_all_nodes() -> list[dict]:
    raw = run_cmd('pw-cli', 'ls', 'Node')
    data = raw.decode(encoding='utf-8').split('\tid ')
    data = data[1:] # 0 is always blank
    return [get_node_from_str(d) for d in data]

def get_node_from_str(d: str) -> dict:
    node = {}
    node['id'] = d.split(',')[0]
    for field in FIELDS:
        value = re.search(re.compile(field + r' = ".*"\n'), d)
        if not value:
            continue
        remove_len = len(f'{field} = "')
        node[field] = value.group()[remove_len:-2]
    print(node)

    return node


def get_id_from_re(nodes: list[dict], name: re.Pattern) -> int | None:
    for node in nodes:
        if node_has_pattern(node, [name]):
            return node.get('id')
    return None
def get_ids_from_re(nodes: list[dict], name: re.Pattern) -> list[int]:
    ids = []
    for node in nodes:
        if node_has_pattern(node, [name]):
            ids.append(node.get('id'))
    return ids


def node_has_pattern(node: dict, patterns: list) -> bool:
    for f in FIELDS:
        field = node.get(f)

        if not field:
            continue

        for pattern in patterns:
            if pattern.search(field):
                return True
    return False


def get_all_links() -> dict[str, dict[str, list[str]]]:
    raw = run_cmd('pw-link', '-l')
    data = raw.decode(encoding='utf-8').split('\n')

    last_node = ''
    links = {}
    for d in data:
        print(d)
        if not d.startswith('  '):
            last_node = d.split(':')[0]
            continue

        name = d.split(':')[0][6:]
        if links.get(last_node) is None:
            links[last_node] = { 'inputs': set(), 'outputs': set()}

        if d.startswith('  |->'):
            links[last_node]['outputs'].add(name)
        if d.startswith('  |<-'):
            links[last_node]['inputs'].add(name)

    print(links)

    return links

def link_has_pattern(links: list[str], patterns: list) -> bool:
    for link in links:
        for pattern in patterns:
            if pattern.search(link):
                return True
    return False


def update_graph():
    nodes = get_all_nodes()
    links = get_all_links()

    dest_ids = [get_id_from_re(nodes, dest_re) for dest_re in DESTS_RE]
    dest_ids = [dest_id for dest_id in dest_ids if dest_id]

    src_ids = [get_ids_from_re(nodes, src_re) for src_re in SRCS_RE]
    src_ids = [src_id for src_sub_ids in src_ids for src_id in src_sub_ids]

    initial_ids = []
    for name, link in links.items():
        node_ids = get_ids_from_re(nodes, re.compile(name))
        output_to_dest = link_has_pattern(link['outputs'], DESTS_RE)
        for node_id in node_ids:
            is_src = node_id in src_ids

            if output_to_dest and not is_src:
                initial_ids.append(node_id)

    print('Init IDs:', initial_ids)
    print('Src IDs:', src_ids)
    print('Dest IDs:', dest_ids)

    if not dest_ids or not src_ids:
        print('Dest or Src IDs is blank, skipping')
        return

    for init_id in initial_ids:
        for dest_id in dest_ids:
            try:
                run_cmd('pw-link', '-d', init_id, dest_id)
                notify(f'Unlinked {init_id} and {dest_id}')
            except Exception as _:
                print(
                    'Encountered error, ' +
                    'link probably already got removed or one id doesn\'t exist. ' +
                    f'InitID={init_id} DestID={dest_id}'
                )

    for src_id in src_ids:
        for dest_id in dest_ids:
            try:
                run_cmd('pw-link', src_id, dest_id)
                notify(f'Linked IDs {src_id} and {dest_id}')
            except Exception as _:
                print(
                    'Encountered error, link probably already exists. ' +
                    f'SrcID={src_id} DestID={dest_id}'
                )


def monitor():
    notify('Started')

    proc = subprocess.Popen(
        ['pw-mon'],
        stdout=subprocess.PIPE,
        text=True,
    )

    last = 0
    for _ in proc.stdout:
        now = time.time()
        if now - last < FREQ:
            continue
        last = now

        print('Updating configuration...')

        update_graph()


if __name__ == '__main__':
    monitor()

