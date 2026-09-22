"""Machine-readable diagnostics and the shared English/Traditional Chinese catalogue."""
from functools import lru_cache
import json
from pathlib import Path
import re

@lru_cache(maxsize=1)
def catalogues():
    return json.loads((Path(__file__).resolve().parents[1]/'web/locales.json').read_text())


def locale(value=''):
    return 'zh-Hant' if str(value).lower().startswith('zh') else 'en'


def text(code, params=None, language='en'):
    template = catalogues()[locale(language)].get(code, catalogues()['en']['validation.generic'])
    return re.sub(r'\{(\w+)\}', lambda m: str((params or {}).get(m[1], m[0])), template)


def describe(value):
    if hasattr(value, 'code'):
        return value.code, getattr(value, 'params', {})
    raw = str(value)
    for lang in catalogues().values():
        for key, msg in lang.items():
            if raw == msg and '{' not in msg:
                return key, {}
    aliases = {
        '請提供 schema_version 3 的節點場景。':'error.schema',
        'GA 需要起點、終點與至少一個中間節點；最多 32 個節點。':'error.nodes_for_ga',
        '最多 32 個節點。':'error.max_nodes',
        '電梯 ID 不可重複。':'error.portal_id',
        '樓層 ID 不可重複。':'error.floor_id',
        '電梯連線必須是物件。':'error.portal_shape',
        '電梯端點必須是物件或 null。':'error.endpoint_shape',
        '端點樓層必須是字串或 null。':'error.endpoint_floor',
        '請提供至少一張樓層地圖。':'error.floor_required',
        '節點需含有效的 floor、x、y。':'error.point_shape',
        '場景網格總量超過 524,288 格。':'error.cell_budget',
        '已有規劃執行中，請先停止或等待完成。':'error.busy',
        '規劃不存在或已過期，請重新執行。':'error.job_missing',
        '多樓層介面使用 operational 模式；揭露書比較請用 /legacy。':'error.mode',
        '節點名稱需唯一，長度為 1–40 字。':'validation.name',
        '最多 12 條電梯連線。':'error.max_portals',
        '請設定 1–4 個樓層。':'error.max_floors',
        '每個樓層需要獨立 map_data。':'error.floor_data',
        '內部錯誤，請查看終端機。':'error.internal',
        '內部計算錯誤；詳情請查看終端機。':'error.internal',
        '順位限制互相衝突：不存在能配送全部訂單的排列。':'error.constraints',
        '候選預算超過 300,000，請降低世代、族群或世界數。':'error.ga_budget',
        'after 必須大於等於 0':'error.after',
        '規劃不存在。':'error.job_missing',
        'JSON required':'error.json_required', 'Origin rejected':'error.origin',
        'Not found':'error.not_found', 'Elevator or route preflight failed':'validation.preflight',
        '無法讀取地圖圖片。':'error.image',
        '請上傳 PNG、JPG、PGM 或 BMP 地圖。':'error.image',
        '地圖每邊需為 4–512 px，程式不會自動縮圖以免消除細牆。':'error.image_dimensions',
        '圖片檔案過大，請使用 2 MB 以下圖片。':'error.image_size',
    }
    if raw in aliases: return aliases[raw], {}
    fields = {'起點':'start','終點':'end','電梯 ID':'elevator ID','樓層 ID':'floor ID',
              '樓層名稱':'floor name','訂單 ID':'order ID','禁止順位':'forbidden position',
              '未知區域灰階':'unknown gray','端點樓層':'endpoint floor'}
    def field(s): return fields.get(s, s if not re.search('[\u4e00-\u9fff]',s) else 'field')
    m = re.fullmatch(r'(.*?) 必須介於 ([^–]+)–([^，。]+)(.*)', raw)
    if m:
        return ('error.field_integer' if '整數' in m[4] else 'error.field_range'), dict(field=field(m[1]),min=m[2],max=m[3])
    m = re.fullmatch(r'(.*?) 必須是數值。',raw)
    if m: return 'error.field_number', dict(field=field(m[1]))
    m = re.fullmatch(r'(.*?) 必須是布林值。',raw)
    if m: return 'error.field_bool', dict(field=field(m[1]))
    m = re.fullmatch(r'(.*?) 必須為 1–40 字元。',raw)
    if m: return 'error.identifier', dict(field=field(m[1]))
    m = re.fullmatch(r'(.*?) → (.*?) 不可達.*',raw)
    if m: return 'error.unreachable', dict(source=m[1],target=m[2])
    if '位於牆' in raw or '位於障礙' in raw:
        return 'error.node_blocked', {}
    if raw.startswith('請求大小需小於'): return 'error.scene_size', {}
    return 'validation.generic', {}


def exception_payload(exc):
    code, params = describe(exc)
    data = dict(error=str(exc), error_code=code, error_params=params)
    if hasattr(exc, 'issues'): data['issues'] = exc.issues
    return data


def localize_payload(data, language):
    """Localize only protocol fields; never recurse into user labels or formulas."""
    if not isinstance(data, dict): return data
    value = dict(data)
    for field in ('error','phase'):
        if not isinstance(value.get(field), str) or not value[field]: continue
        code, params = (value.get(field+'_code'), value.get(field+'_params', {}))
        if not code: code, params = describe(value[field])
        value[field+'_code'], value[field+'_params'] = code, params
        value[field] = text(code, params, language)
    return value
