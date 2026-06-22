#!/usr/bin/env python3
"""
POPO IO — POPO 文档读写工具库（读写双向）
路径：/Users/nick/cuocuo_design/workspace/6723d1b6-602f-40e0-9a52-9f9557cc2dfe/popo_io.py

加载方式（任意临时脚本里）：
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "popo_io",
        "/Users/nick/cuocuo_design/workspace/6723d1b6-602f-40e0-9a52-9f9557cc2dfe/popo_io.py"
    )
    pio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pio)

读取：
    text = pio.read_doc_from_url("https://docs.popo.netease.com/lingxi/xxx")
    text = pio.read_doc_from_url("https://docs.popo.netease.com/team/pc/xxx/pageDetail/yyy")

写入 HTML：
    doc_id = pio.create_and_write("文档标题", [html1, html2, html3])
    print(pio.doc_url(doc_id))

写入 Markdown（自动转换）：
    doc_id = pio.create_and_write_md("文档标题", markdown_text)
    print(pio.doc_url(doc_id))
"""

import json
import re
import subprocess

# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

POPO_CLI = '/Users/nick/cuocuo_design/resource/bin/node/bin/popo-cli'
POPO_URL_BASE = 'https://docs.popo.netease.com/lingxi/'

# ──────────────────────────────────────────────
# 底层 CLI 调用
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# 通用递归提取工具
# ──────────────────────────────────────────────

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


def extract_doc_id(resp):
    """从嵌套响应 JSON 中提取 docId。"""
    return _find_key(resp, 'docId')


# ──────────────────────────────────────────────
# ── 读取侧 ──────────────────────────────────
# ──────────────────────────────────────────────

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
    支持个人空间和团队空间两种格式。
    若解析失败抛出 ValueError。
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
    # 块级标签前后加换行
    text = re.sub(r'</(h[1-6]|p|li|blockquote|code-block|hr|br)>', '\n', html_str, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # 去掉所有剩余标签
    text = re.sub(r'<[^>]+>', '', text)
    # 合并连续空行（最多保留一个空行）
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_text_from_resp(resp):
    """
    从 popo_doc_get_doc_detail 响应中提取可读文本。
    尝试多种已知响应结构，逐层降级。
    返回纯文本字符串。
    """
    # 尝试路径 1：resp.data.content（部分版本）
    data = resp.get('data') or {}
    if isinstance(data, dict):
        content = data.get('content') or data.get('body') or data.get('text')
        if content and isinstance(content, str):
            return _strip_html(content)

    # 尝试路径 2：resp.result.content
    result = resp.get('result') or {}
    if isinstance(result, dict):
        content = result.get('content') or result.get('body')
        if content and isinstance(content, str):
            return _strip_html(content)

    # 尝试路径 3：递归找 content 字段
    content = _find_key(resp, 'content')
    if content and isinstance(content, str):
        return _strip_html(content)

    # 兜底：返回整个 JSON 的 pretty print，供调试
    return json.dumps(resp, ensure_ascii=False, indent=2)


def read_doc(doc_id):
    """
    读取文档内容，返回可读纯文本。
    同时返回原始响应供调试：(text, raw_resp)
    """
    resp = popo_call({
        'tool': 'popo_doc_get_doc_detail',
        'params': {'docId': doc_id}
    })
    text = _extract_text_from_resp(resp)
    return text, resp


def read_doc_from_url(url):
    """
    一步到位：URL → 读取文档 → 返回可读纯文本。
    url 可以是个人空间或团队空间的任意格式。
    返回 (text, doc_id)。
    """
    doc_id = url_to_doc_id(url)
    text, _ = read_doc(doc_id)
    print(f'[popo_io] 已读取文档 {doc_id}，长度 {len(text)} 字符')
    return text, doc_id


# ──────────────────────────────────────────────
# ── 写入侧 ──────────────────────────────────
# ──────────────────────────────────────────────

def create_doc(title, doc_type=1):
    """
    创建新 POPO 文档，返回 doc_id 字符串。
    doc_type 必须是整数 1（传字符串 "doc" 会报错）。
    """
    resp = popo_call({
        'tool': 'popo_doc_create_doc',
        'params': {'title': title, 'docType': doc_type}
    })
    doc_id = extract_doc_id(resp)
    if not doc_id:
        raise RuntimeError(f'create_doc 失败，响应：{resp}')
    print(f'[popo_io] 文档已创建: {doc_id}')
    return doc_id


def write_sections(doc_id, sections, verbose=True):
    """
    串行写入多个 HTML section 到指定文档。
    sections: list[str | dict]
      - str：合法的 POPO HTML 片段
      - dict：{'title': str, 'content': str}，自动拼接为 <h2>title</h2>content
    返回 (成功数, 总数)。
    """
    results = []
    total = len(sections)
    for i, item in enumerate(sections, 1):
        if isinstance(item, dict):
            t = item.get('title', '')
            c = item.get('content', '')
            html_content = (f'<h2>{t}</h2>{c}' if t else c)
        else:
            html_content = item
        r = popo_call({
            'tool': 'popo_doc_update_doc',
            'params': {
                'docId': doc_id,
                'command': {'type': 'doc.insert_after', 'content': html_content}
            }
        })
        ok = bool(r.get('ok') or r.get('code') == 'FABRIC_OK')
        results.append(ok)
        if verbose:
            status = '✓' if ok else f'✗ {str(r)[:80]}'
            print(f'[popo_io] section {i}/{total}: {status}')
    success = sum(results)
    print(f'[popo_io] 写入完成: {success}/{total} 成功')
    return success, total


def doc_url(doc_id):
    """返回文档的可访问 URL。"""
    return f'{POPO_URL_BASE}{doc_id}'


def create_and_write(title, sections):
    """
    创建文档 + 串行写入所有 sections，返回 doc_id。
        doc_id = pio.create_and_write("标题", [html1, html2, ...])
        print(pio.doc_url(doc_id))
    """
    doc_id = create_doc(title)
    write_sections(doc_id, sections)
    url = doc_url(doc_id)
    print(f'[popo_io] 文档地址: {url}')
    return doc_id


# ──────────────────────────────────────────────
# ── Markdown → POPO HTML 转换 ────────────────
# ──────────────────────────────────────────────

# 与 POPO-IO-Guide.md 中的转换规则一一对应，统一维护。
# 规则速查：
#   # → <h1>  |  ## → <h2>  |  ### → <h3>  |  #### → <h4>
#   ** → <strong>  |  ` → <code>
#   [text](url) → <a href>
#   --- → <hr/>
#   代码块 / ASCII 树形图 → <code-block>（不能用 <pre><code>）
#   表格 → <table>
#   列表 → <ul><li> / <ol><li>
#   引用 → <blockquote>
#   空行 → 跳过（由块级标签本身提供间距，不额外插入 <br/>）

def _inline_md(text):
    """行内元素转换：加粗、行内代码、链接。"""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def _build_table(table_lines):
    """将 Markdown 表格行列表转为 POPO <table> HTML。"""
    rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().split('|')]
        if cells and cells[0] == '': cells = cells[1:]
        if cells and cells[-1] == '': cells = cells[:-1]
        if all(re.match(r'^[-:\s]+$', c) for c in cells if c): continue
        rows.append(cells)

    html = '<table border="1" style="border-collapse:collapse;">\n'
    for ri, row in enumerate(rows):
        tag = 'th' if ri == 0 else 'td'
        html += '<tr>\n'
        for cell in row:
            html += f'<{tag} style="padding:4px 8px;">{_inline_md(cell)}</{tag}>\n'
        html += '</tr>\n'
    html += '</table>'
    return html

# ──────────────────────────────────────────────

def md_to_popo(md_text):
    """
    将 Markdown 文本转为 POPO 可渲染的 HTML 字符串。
    按 ## 标题自动切段，每段独立转换。
    返回 list[str]，每个元素为一个 section 的 HTML。
    """
    lines = md_text.split('\n')
    sections_raw = []
    buf = []

    for line in lines:
        if line.startswith('## ') and buf:
            sections_raw.append('\n'.join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        sections_raw.append('\n'.join(buf))

    def _convert_section(text):
        """将单个 section 的 Markdown 转为 POPO HTML。"""
        local_lines = text.split('\n')
        result = []
        i = 0
        in_code = False
        code_buf = []
        in_table = False
        table_buf = []
        in_list = False
        list_tag = None

        def close_list():
            nonlocal in_list, list_tag
            if in_list:
                result.append(f'</{list_tag}>')
                in_list = False
                list_tag = None

        while i < len(local_lines):
            line = local_lines[i]
            s = line.strip()

            # 代码块（含 ASCII 树形图）——用 <code-block>
            if s.startswith('```'):
                if not in_code:
                    in_code = True
                    code_buf = []
                else:
                    in_code = False
                    result.append('<code-block>' + '\n'.join(code_buf) + '</code-block>')
                i += 1
                continue

            if in_code:
                code_buf.append(line)
                i += 1
                continue

            # 标题
            if s.startswith('#### '):
                close_list()
                result.append(f'<h4>{_inline_md(s[5:])}</h4>')
            elif s.startswith('### '):
                close_list()
                result.append(f'<h3>{_inline_md(s[4:])}</h3>')
            elif s.startswith('## '):
                close_list()
                result.append(f'<h2>{_inline_md(s[3:])}</h2>')
            elif s.startswith('# '):
                close_list()
                result.append(f'<h1>{_inline_md(s[2:])}</h1>')

            # 分隔线
            elif s == '---':
                close_list()
                result.append('<hr/>')

            # 表格
            elif s.startswith('|') and s.endswith('|'):
                close_list()
                if not in_table:
                    in_table = True
                    table_buf = []
                table_buf.append(line)
                # 预读：看下一行是否还是表格
                if i + 1 < len(local_lines) and local_lines[i+1].strip().startswith('|') and local_lines[i+1].strip().endswith('|'):
                    i += 1
                    continue
                else:
                    result.append(_build_table(table_buf))
                    in_table = False
                    table_buf = []
            elif in_table:
                in_table = False

            # 引用
            elif s.startswith('> '):
                close_list()
                result.append(f'<blockquote>{_inline_md(s[2:])}</blockquote>')

            # 有序列表
            elif re.match(r'^\d+[\.\)]\s', s):
                if not in_list or list_tag != 'ol':
                    close_list()
                    result.append('<ol>')
                    in_list = True
                    list_tag = 'ol'
                content = re.sub(r'^\d+[\.\)]\s', '', s)
                result.append(f'<li>{_inline_md(content)}</li>')

            # 无序列表
            elif re.match(r'^[-*+]\s', s):
                if not in_list or list_tag != 'ul':
                    close_list()
                    result.append('<ul>')
                    in_list = True
                    list_tag = 'ul'
                result.append(f'<li>{_inline_md(s[2:])}</li>')

            # 空行——跳过，块级标签自带间距
            elif s == '':
                close_list()

            # 普通段落
            else:
                close_list()
                result.append(f'<p>{_inline_md(s)}</p>')

            i += 1

        close_list()
        return '\n'.join(result)

    return [_convert_section(s) for s in sections_raw if s.strip()]


def create_and_write_md(title, md_text):
    """
    创建文档 + 将 Markdown 文本转为 POPO HTML 后串行写入。
    使用方式：
        doc_id = pio.create_and_write_md("文档标题", markdown_text)
        print(pio.doc_url(doc_id))
    """
    sections = md_to_popo(md_text)
    return create_and_write(title, sections)


# ──────────────────────────────────────────────
# 快速验证
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f'[popo_io] 读取文档: {url}')
        text, doc_id = read_doc_from_url(url)
        print(f'--- 内容预览（前500字）---\n{text[:500]}')
    else:
        print('[popo_io] 自检：验证 CLI 可用性...')
        resp = popo_call({'tool': 'popo_doc_get_doc_detail', 'params': {'docId': 'test-ping'}})
        print(f'[popo_io] CLI 响应字段: {list(resp.keys()) if resp else "无响应"}')
        print('[popo_io] URL 解析测试:')
        tests = [
            'https://docs.popo.netease.com/lingxi/382f0a27686947b4a46733846347cf4e',
            'https://docs.popo.netease.com/team/pc/7tqv43du/pageDetail/11acd823c5df410ba86f5549b4a2485f?foo=bar',
        ]
        for t in tests:
            try:
                print(f'  {t[:60]}... → {url_to_doc_id(t)}')
            except ValueError as e:
                print(f'  ✗ {e}')
