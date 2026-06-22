#!/usr/bin/env python3
"""
POPO 文档只读工具库。

加载方式（在临时脚本里按绝对路径加载）：
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "popo_io", "<SKILL_DIR>/scripts/popo_io.py")
    pio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pio)

使用：
    text, doc_id = pio.read_doc_from_url("https://docs.popo.netease.com/lingxi/xxx")
    text, doc_id = pio.read_doc_from_url("https://docs.popo.netease.com/team/pc/xxx/pageDetail/yyy")

依赖：环境中可执行的 popo-cli。
默认按 PATH 查找；如不在 PATH，用环境变量 POPO_CLI 指定其绝对路径。
"""

import json
import os
import re
import shutil
import subprocess

# popo-cli 可执行文件：优先环境变量 POPO_CLI，其次 PATH 中的 popo-cli。
POPO_CLI = os.environ.get('POPO_CLI') or shutil.which('popo-cli') or 'popo-cli'


def popo_call(body_dict):
    """调用 POPO CLI，返回解析后的 JSON 对象。失败返回 {}。"""
    body_json = json.dumps(body_dict, ensure_ascii=False)
    result = subprocess.run(
        [POPO_CLI, 'call', 'POST',
         '/api/v1/open-apis/gateway/appcode/popo/_invoke',
         '--body', body_json],
        capture_output=True, text=True, timeout=30
    )
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if line.startswith('{'):
            return json.loads(line)
    return {}


def _find_key(d, key):
    """从任意深度嵌套 JSON 中递归找第一个匹配 key 的值。"""
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            r = _find_key(v, key)
            if r:
                return r
    return None


# 支持的 POPO URL 格式：
#   个人空间：https://docs.popo.netease.com/lingxi/{docId}
#   团队空间：https://docs.popo.netease.com/team/pc/{teamId}/pageDetail/{docId}
#             （含 ?xxx 查询参数，忽略）
_URL_PATTERNS = [
    re.compile(r'pageDetail/([a-f0-9]{32})'),   # 团队空间
    re.compile(r'/lingxi/([a-f0-9]{32})'),       # 个人空间
]


def url_to_doc_id(url):
    """
    从任意 POPO URL 中提取 docId（32位十六进制字符串）。
    支持个人空间和团队空间两种格式。解析失败抛 ValueError。
    """
    url = url.strip().split('?')[0]  # 去掉查询参数
    for pat in _URL_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    raise ValueError(f'无法从 URL 中提取 docId: {url}')


def _strip_html(html_str):
    """去除 HTML 标签，还原可读纯文本。保留换行结构。"""
    if not html_str:
        return ''
    text = re.sub(r'</(h[1-6]|p|li|blockquote|code-block|hr|br)>', '\n', html_str, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_text_from_resp(resp):
    """
    从 popo_doc_get_doc_detail 响应中提取可读文本。
    尝试多种已知响应结构，逐层降级；全部失败则返回原始 JSON 供调试。
    """
    data = resp.get('data') or {}
    if isinstance(data, dict):
        content = data.get('content') or data.get('body') or data.get('text')
        if content and isinstance(content, str):
            return _strip_html(content)

    result = resp.get('result') or {}
    if isinstance(result, dict):
        content = result.get('content') or result.get('body')
        if content and isinstance(content, str):
            return _strip_html(content)

    content = _find_key(resp, 'content')
    if content and isinstance(content, str):
        return _strip_html(content)

    return json.dumps(resp, ensure_ascii=False, indent=2)


def read_doc(doc_id):
    """读取文档内容，返回 (可读纯文本, 原始响应)。"""
    resp = popo_call({
        'tool': 'popo_doc_get_doc_detail',
        'params': {'docId': doc_id}
    })
    return _extract_text_from_resp(resp), resp


def read_doc_from_url(url):
    """
    一步到位：URL → 读取文档 → 返回 (可读纯文本, doc_id)。
    url 支持个人空间或团队空间任意格式。
    """
    doc_id = url_to_doc_id(url)
    text, _ = read_doc(doc_id)
    print(f'[popo_io] 已读取文档 {doc_id}，长度 {len(text)} 字符')
    return text, doc_id


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f'[popo_io] 读取文档: {url}')
        text, doc_id = read_doc_from_url(url)
        print(f'--- 内容预览（前500字）---\n{text[:500]}')
    else:
        print('[popo_io] URL 解析测试:')
        for t in [
            'https://docs.popo.netease.com/lingxi/382f0a27686947b4a46733846347cf4e',
            'https://docs.popo.netease.com/team/pc/7tqv43du/pageDetail/11acd823c5df410ba86f5549b4a2485f?foo=bar',
        ]:
            try:
                print(f'  {t[:60]}... → {url_to_doc_id(t)}')
            except ValueError as e:
                print(f'  ✗ {e}')
