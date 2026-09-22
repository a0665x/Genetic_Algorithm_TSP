"""Ordered-node editor adapter. Preview does not run or score a genetic algorithm."""
from __future__ import annotations
import copy
import math
import threading
from .api import Jobs
from .building import (validate_scene, prepare_building, demo_scene, ExplainedObjective,
                       MODEL_VERSION, FORMULAS, FEATURE_KEYS)
from .core import weights, sigmoid, evolve
from .portals import normalise_portals, inspect_topology, SceneIssues


def editor_demo():
    scene = demo_scene()
    scene['schema_version'] = 3
    scene['nodes'] = [dict(id='S', **scene.pop('start'))] + scene.pop('orders') + [
        dict(id='G', floor='F2', x=96, y=112)]
    scene.pop('end', None)
    scene['settings']['return_to_start'] = False
    return scene


def validate_editor(data, planning=True, clearance=True):
    if not isinstance(data, dict) or data.get('schema_version') != 3:
        raise ValueError('請提供 schema_version 3 的節點場景。')
    nodes = data.get('nodes')
    minimum = 3 if planning else 0
    if not isinstance(nodes, list) or not minimum <= len(nodes) <= 32:
        raise ValueError('GA 需要起點、終點與至少一個中間節點；最多 32 個節點。' if planning else '最多 32 個節點。')
    labels = []
    for node in nodes:
        if not isinstance(node, dict): raise ValueError('節點必須是物件。')
        label = node.get('id')
        if not isinstance(label, str) or not label.strip() or len(label) > 40 or label in labels:
            raise ValueError('節點名稱需唯一，長度為 1–40 字。')
        labels.append(label)
    scene = copy.deepcopy(data)
    scene['schema_version'] = 2
    if not isinstance(scene.get('settings', {}), dict): raise ValueError('settings 必須是物件。')
    scene['settings'] = dict(scene.get('settings', {}), return_to_start=False)
    floors = scene.get('floors')
    if not isinstance(floors, list) or not floors or not isinstance(floors[0], dict):
        raise ValueError('請提供至少一張樓層地圖。')
    # Map-only editing also works with an empty node list. The temporary point
    # is never a route node or a fall-back path; clearance is not checked for it.
    scene['start'] = nodes[0] if nodes else dict(floor=floors[0].get('id'), x=0, y=0)
    scene['end'] = nodes[-1] if len(nodes) > 1 else None
    scene['orders'] = []
    for i, node in enumerate(nodes[1:-1], 1):
        order = dict(node, id=f'order_{i}')  # labels cannot collide with engine sentinel names
        if not planning: order['forbidden'] = []  # route preview is independent of GA constraints
        scene['orders'].append(order)
    portal_drafts = normalise_portals(scene.get('portals', []))
    scene['portals'] = []
    v = validate_scene(scene, require_orders=planning, check_clearance=clearance and bool(nodes))
    preflight = inspect_topology(v['grids'], portal_drafts, nodes)
    if planning and not preflight['ok']:
        raise SceneIssues(preflight['issues'])
    # Invalid/disabled drafts remain visible but never enter the routing graph.
    states = {p['id']: p['state'] for p in preflight['portals']}
    v['portals'] = [p for p in portal_drafts if states[p['id']] == 'complete']
    v['portal_drafts'] = portal_drafts
    v['preflight'] = preflight
    v['labels'] = labels
    v['editor_nodes'] = copy.deepcopy(nodes)
    return v


# Bounded expensive previews. The browser coalesces edits and ignores stale
# responses by revision; this guard also bounds independent clients.
_preview_lock = threading.Lock()


def preview_editor(data):
    v = validate_editor(data, planning=False, clearance=False)
    output = dict(floors=v['views'], portals=v['portal_drafts'], preflight=v['preflight'], labels=v['labels'],
                  legs=[], distance=0., time=0., error=None, kind='ordered-preview')
    if not v['preflight']['ok']:
        return dict(output, error='Elevator or route preflight failed', error_code='validation.preflight',
                    error_params={}, legs=[])
    if len(data['nodes']) < 2: return output
    if not _preview_lock.acquire(blocking=False):
        return dict(output, retry=True)
    try:
        v = validate_editor(data, planning=False, clearance=True)
        n = len(v['points'])
        pairs = [(i, i+1) for i in range(n-1)]
        m = prepare_building(v, terminal_pairs=pairs)
        for i, j in pairs:
            output['legs'].append(dict(source=i, target=j, segments=m['segments'][f'{i}:{j}'],
                                       distance=float(m['distance'][i,j]), time=float(m['travel'][i,j])))
        output['distance'] = sum(leg['distance'] for leg in output['legs'])
        output['time'] = sum(leg['time'] for leg in output['legs'])
        return output
    except ValueError as exc:
        # All-or-nothing route, rather than drawing a straight line through a wall.
        return dict(output, error=str(exc), legs=[])
    finally:
        _preview_lock.release()


class EditorObjective(ExplainedObjective):
    def __init__(self, *args, labels, **kwargs):
        super().__init__(*args, **kwargs)
        self.labels = labels

    def evaluate(self, route, details=False):
        value = super().evaluate(route, details)
        if details and math.isfinite(value['loss']):
            for stop in value['schedule']:
                stop['id'] = self.labels[stop['node']]
        return value


class EditorJobs(Jobs):
    validate = staticmethod(validate_editor)

    def _run(self, id, v):
        item = self.items[id]
        cancelled = item['cancel'].is_set
        def update(**kw):
            with self.lock: item.update(kw)
        try:
            update(status='running', phase='A* 與跨樓層路徑')
            m = prepare_building(v, lambda done,total: update(progress=30*done/max(1,total)), cancelled)
            cfg, c, orders = v['cfg'], v['coefficients'], v['orders']
            rows = weights(orders, m, cfg['cruise'], c)
            for i, row in enumerate(rows, 1):
                row.update(id=v['labels'][i], node=i, bias=c['bias'], sigmoid=sigmoid(row['z']),
                           contributions={k:c[k]*x for k,x in zip(FEATURE_KEYS,row['features'])})
            n = len(m['points'])
            w = [[rows[j-1]['weight'] if i != j and 1 <= j <= len(orders) else 0.
                  for j in range(n)] for i in range(n)]
            meta = dict(model_version=MODEL_VERSION, formulas=FORMULAS, weights=rows,
                        weight_matrix=w, distance_matrix=m['distance'].tolist(), time_matrix=m['travel'].tolist(),
                        points=m['points'], segments=m['segments'], labels=v['labels'],
                        coefficients=c, settings=cfg, portals=v['portals'], input_nodes=v['editor_nodes'])
            update(meta=meta, phase='GA 進化中')
            obj = EditorObjective(orders,m,rows,False,True,cfg['priority'],cfg['risk_penalty'],
                                  cfg['distance_penalty'],labels=v['labels'])
            def callback(record):
                with self.lock:
                    item['history'].append(record)
                    item['progress'] = 30 + 70*record['generation']/cfg['generations']
            result = evolve(obj, **{k:cfg[k] for k in ('population','generations','worlds','sower','interval','migration','mutation','seed')},
                            callback=callback, cancelled=cancelled, elite_tracking=True)
            result.pop('history')
            if cancelled(): raise InterruptedError('已停止規劃')
            update(status='done',phase='GA 規劃完成',progress=100,result=result)
        except InterruptedError as exc: update(status='cancelled',error=str(exc),phase='已停止')
        except ValueError as exc: update(status='error',error=str(exc),phase='無法規劃')
        except Exception:
            import traceback
            traceback.print_exc()
            update(status='error',error='內部錯誤，請查看終端機。',phase='計算失敗')


def preflight_editor(data):
    v = validate_editor(data, planning=False, clearance=False)
    return dict(v['preflight'], floors=v['views'], portal_drafts=v['portal_drafts'])
