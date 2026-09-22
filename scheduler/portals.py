"""Editable two-ended elevator links with cheap, fail-closed topology preflight.

Unplaced coordinates remain None. IDs identify a link; names never infer edges.
Component labelling checks reachability before A* or GA is started.
"""
from __future__ import annotations
from collections import defaultdict, deque

from scipy.ndimage import label
from .api import number


class SceneIssues(ValueError):
    def __init__(self, issues):
        self.issues = issues
        self.code = 'validation.links'
        self.params = {'count': sum(i['severity'] == 'error' for i in issues)}
        super().__init__('Incomplete or invalid elevator topology')


def issue(code, *, severity='error', **params):
    return dict(code=code, params=params, severity=severity)


def endpoint_label(portal, side):
    p = portal.get(side) or {}
    return f"{portal['id']}_{p.get('floor') or side.upper()}"


def normalise_portals(raw):
    if not isinstance(raw, list) or len(raw) > 12:
        raise ValueError('最多 12 條電梯連線。')
    result, seen = [], set()
    for p in raw:
        if not isinstance(p, dict):
            raise ValueError('電梯連線必須是物件。')
        pid = p.get('id')
        if not isinstance(pid, str) or not pid.strip() or len(pid) > 40:
            raise ValueError('電梯 ID 必須為 1–40 字元。')
        if pid in seen:
            raise ValueError('電梯 ID 不可重複。')
        seen.add(pid)
        enabled = p.get('enabled', True)
        if not isinstance(enabled, bool):
            raise ValueError('電梯 enabled 必須是布林值。')
        endpoints = {}
        for side in ('a', 'b'):
            point = p.get(side)
            if point is not None and not isinstance(point, dict):
                raise ValueError('電梯端點必須是物件或 null。')
            point = point or {}
            fid = point.get('floor')
            if fid is not None and (not isinstance(fid, str) or len(fid) > 40):
                raise ValueError('端點樓層必須是字串或 null。')
            q = {'floor': fid}
            for axis in ('x', 'y'):
                value = point.get(axis)
                # Invalid integers remain editable (e.g. old coordinates after
                # replacing a map); nonnumeric/nonfinite input is rejected.
                if value is not None:
                    value = number(value, axis, -100000, 100000, True)
                q[axis] = value
            endpoints[side] = q
        timing = {k: number(p.get(k, d), k, 0, 3600) for k, d in (
            ('wait', 15), ('reverse_wait', p.get('wait', 15)), ('door', 6), ('ride', 8))}
        result.append(dict(id=pid, enabled=enabled, **endpoints, **timing))
    return result


def inspect_topology(grids, portals, nodes):
    """Return serializable diagnostics; never manufacture or repair endpoints."""
    issues, states = [], []
    complete = []
    for p in portals:
        local = []
        severity = 'error' if p['enabled'] else 'warning'
        for side in ('a', 'b'):
            q = p[side]
            params = dict(portal=p['id'], side=side, endpoint=endpoint_label(p, side),
                          floor=q['floor'] or '—')
            if not q['floor'] or q['x'] is None or q['y'] is None:
                local.append(issue('portal.missing', severity=severity, **params))
            elif q['floor'] not in grids:
                local.append(issue('portal.floor_missing', severity=severity, **params))
            elif not grids[q['floor']].valid((q['x'], q['y'])):
                local.append(issue('portal.blocked', severity=severity, **params))
        if p['a']['floor'] is not None and p['a']['floor'] == p['b']['floor']:
            local.append(issue('portal.same_floor', severity=severity, portal=p['id']))
        issues.extend(local)
        state = ('disabled' if not p['enabled'] else
                 'incomplete' if any(i['code'] == 'portal.missing' for i in local) else
                 'invalid' if local else 'complete')
        states.append(dict(id=p['id'], state=state, issues=local,
                           labels={s: endpoint_label(p, s) for s in ('a', 'b')}))
        if p['enabled'] and not local:
            complete.append(p)

    # A safe diagonal requires both orthogonal cells to be free, so 4-connected
    # components have exactly the reachability of the no-corner-cutting grid.
    components = {fid: label(~g.blocked)[0] for fid, g in grids.items()}
    def component(q):
        g = grids.get(q.get('floor'))
        x, y = q.get('x'), q.get('y')
        if g is None or not isinstance(x, int) or not isinstance(y, int) or not g.valid((x, y)):
            return None
        return q['floor'], int(components[q['floor']][y, x])
    graph = defaultdict(set)
    for p in complete:
        a, b = component(p['a']), component(p['b'])
        graph[a].add(b)
        graph[b].add(a)
    node_components = []
    for n in nodes:
        c = component(n)
        node_components.append(c)
        if c is None:
            issues.append(issue('node.blocked', node=n['id'], floor=n.get('floor', '—')))
    if nodes and node_components[0] is not None:
        seen = {node_components[0]}
        queue = deque(seen)
        while queue:
            for target in graph[queue.popleft()]:
                if target not in seen:
                    seen.add(target); queue.append(target)
        # Suppress duplicate reachability errors caused by an already reported
        # incomplete elevator; keep the endpoint issue actionable.
        if not any(i['severity'] == 'error' and i['code'].startswith('portal.') for i in issues):
            for n, c in zip(nodes[1:], node_components[1:]):
                if c is not None and c not in seen:
                    issues.append(issue('route.disconnected', node=n['id'], floor=n['floor'],
                                        start=nodes[0]['id']))
    return dict(ok=not any(i['severity'] == 'error' for i in issues), issues=issues, portals=states)
