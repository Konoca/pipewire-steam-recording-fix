#!/usr/bin/env python3

import json
import re
import subprocess
import time
from helpers import run_cmd, notify, load_settings

CFG = load_settings()
DESTS = CFG.get('destinations', [])
DESTS_RE = [re.compile(pattern) for pattern in DESTS]

SRCS = CFG.get('sources', [])
SRCS_RE = [re.compile(pattern) for pattern in SRCS]

PROPS = CFG.get('fields', [])
FREQ = CFG.get('monitor frequency', 1)
WRITE_JSON = CFG.get('write json file', False)


def get_graph() -> list[dict]:
    raw = run_cmd('pw-dump').decode(encoding='utf-8')
    js = json.loads(raw)

    if WRITE_JSON:
        with open('pw-dump.json', 'w') as f:
            json.dump(js, f, indent=4)
    return js

def get_all_nodes(graph: list[dict]) -> list[dict]:
    nodes = []
    for node in graph:
        if node.get('type', '') != 'PipeWire:Interface:Node':
            continue

        nodes.append({
            'id': str(node.get('id', 0)),
            'info': node.get('info', {}),
            'props': node.get('info', {}).get('props', {})
        })
    return nodes


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
    for prop in PROPS:
        value = node['props'].get(prop)

        if not value:
            continue

        for pattern in patterns:
            if pattern.search(value):
                return True

    return False


def get_all_links(graph: list[dict]) -> list[dict]:
    links = []
    for link in graph:
        if link.get('type', '') != 'PipeWire:Interface:Link':
            continue

        info = link.get('info', {})
        links.append({
            'id': str(link.get('id', 0)),
            'input id': str(info.get('input-node-id', '')), # audio is going into, DEST
            'output id': str(info.get('output-node-id', '')), # audio is coming from, SRC
        })
    return links

def update_graph():
    graph = get_graph()
    nodes = get_all_nodes(graph)
    links = get_all_links(graph)

    dest_ids = [get_id_from_re(nodes, dest_re) for dest_re in DESTS_RE]
    dest_ids = [dest_id for dest_id in dest_ids if dest_id]

    src_ids = [get_ids_from_re(nodes, src_re) for src_re in SRCS_RE]
    src_ids = [src_id for src_sub_ids in src_ids for src_id in src_sub_ids]

    initial_ids = []
    for link in links:
        outputid = link['output id']
        is_going_into_dest = link['input id'] in dest_ids
        is_coming_from_src = outputid in src_ids

        if is_coming_from_src:
            continue

        if is_going_into_dest and outputid not in initial_ids:
            initial_ids.append(outputid)

    print('Init IDs:', initial_ids)
    print('Src IDs:', src_ids)
    print('Dest IDs:', dest_ids)

    for init_id in initial_ids:
        for dest_id in dest_ids:
            try:
                print(f'Unlinking {init_id} and {dest_id}')
                run_cmd('pw-link', '-d', init_id, dest_id)
                notify(f'Unlinked {init_id} and {dest_id}')
            except Exception as e:
                print(
                    'Encountered error, ' +
                    'link probably already got removed or one id doesn\'t exist. ' +
                    f'InitID={init_id} DestID={dest_id}'
                )
                print(e)

    for src_id in src_ids:
        for dest_id in dest_ids:
            try:
                print(f'Linking {src_id} and {dest_id}')
                run_cmd('pw-link', src_id, dest_id)
                notify(f'Linked IDs {src_id} and {dest_id}')
            except Exception as e:
                print(
                    'Encountered error, link probably already exists. ' +
                    f'SrcID={src_id} DestID={dest_id}. '
                )
                print(e)


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

