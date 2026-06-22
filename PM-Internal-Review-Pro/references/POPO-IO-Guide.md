# POPO IO Guide

> 本文档是 POPO 文档**读写**的唯一操作参考。所有 Skill 凡需要读取或写入 POPO 的，均引用此文档，不在 Skill 内重复描述操作细节。
>
> 权威路径：`/Users/nick/cuocuo_design/workspace/6723d1b6-602f-40e0-9a52-9f9557cc2dfe/POPO-IO-Guide.md`

---

## 1. 固定工具库（必须使用，不要手写）

```
主库路径：/Users/nick/cuocuo_design/workspace/6723d1b6-602f-40e0-9a52-9f9557cc2dfe/popo_io.py
兼容别名：/Users/nick/cuocuo_design/workspace/6723d1b6-602f-40e0-9a52-9f9557cc2dfe/popo_writer.py（转发到 popo_io）
```

加载方式（固定 3 行，不变）：
```python
import importlib.util
spec = importlib.util.spec_from_file_location(
    "popo_io",
    "/Users/nick/cuocuo_design/workspace/6723d1b6-602f-40e0-9a52-9f9557cc2dfe/popo_io.py"
)
pio = importlib.util.module_from_spec(spec); spec.loader.exec_module(pio)
```

### 读取

```python
# 一步到位：URL → 纯文本（支持个人空间和团队空间两种 URL 格式）
text, doc_id = pio.read_doc_from_url("https://docs.popo.netease.com/...")

# 分步：先解析 URL，再读取
doc_id = pio.url_to_doc_id(url)
text, raw_resp = pio.read_doc(doc_id)
```

### 写入

```python
# 一步到位：创建文档 + 串行写入所有 sections
doc_id = pio.create_and_write("文档标题", [html1, html2, html3, ...])
print(pio.doc_url(doc_id))

# 分步
doc_id = pio.create_doc("文档标题")
pio.write_sections(doc_id, sections)
print(pio.doc_url(doc_id))
```

### 完整 API 一览

| 函数 | 方向 | 用途 |
|------|------|------|
| `read_doc_from_url(url)` | 读 | URL → 纯文本 + doc_id，一步到位 |
| `url_to_doc_id(url)` | 读 | 从任意 POPO URL 提取 docId |
| `read_doc(doc_id)` | 读 | 读文档，返回 (纯文本, 原始 JSON) |
| `create_and_write(title, sections)` | 写 | 创建 + 串行写入，返回 doc_id |
| `create_doc(title)` | 写 | 仅创建文档，返回 doc_id |
| `write_sections(doc_id, sections)` | 写 | 串行写入，返回 (成功数, 总数) |
| `doc_url(doc_id)` | 工具 | 返回文档可访问 URL |
| `popo_call(body_dict)` | 工具 | 底层 CLI 调用，供特殊场景用 |
| `extract_doc_id(resp)` | 工具 | 从嵌套 JSON 递归提取 docId |

---

## 2. 底层实现要点（仅供理解）

- `docType` 必须是整数 `1`，传字符串 `"doc"` 会报错
- `doc_id` 用递归 `extract_doc_id` 提取，直接 `.get('docId')` 通常取不到
- 写入必须串行 for 循环，并发导致 sections 随机乱序

---

## 3. Markdown → POPO HTML 转换规则

| Markdown 元素 | POPO HTML 标签 | 注意事项 |
|--------------|---------------|---------|
| `# 标题` | `<h1>标题</h1>` | 层级对应 h1–h6 |
| `**加粗**` | `<strong>加粗</strong>` | |
| `*斜体*` | `<em>斜体</em>` | |
| `` `行内代码` `` | `<code>行内代码</code>` | |
| 代码块 / ASCII 树形图 | `<code-block>...</code-block>` | **不能用 `<pre><code>`，POPO 不渲染** |
| `- 列表项` | `<ul><li>列表项</li></ul>` | 嵌套列表同样用 `<ul><li>` |
| `1. 列表项` | `<ol><li>列表项</li></ol>` | |
| `[链接文字](url)` | `<a href="url">链接文字</a>` | `<a href>` 可正常渲染为可点击链接 |
| `> 引用` | `<blockquote>引用</blockquote>` | |
| `---` 分隔线 | `<hr/>` | |
| 诊断灯色 🟢🟡🔴 | 直接写 emoji，放 `<p>` 或 `<strong>` 里 | emoji 可正常渲染 |

### 特别注意：`<code-block>` 的用途

凡是需要等宽对齐、树形缩进、多行代码的内容，**一律用 `<code-block>`**，包括：
- 骨架地图（ASCII 树形图，必须带 `├──` / `└──` / `│` 连接符，不能用纯缩进空格）
- 假设树 / 根因溯源链
- 替代方案对比块
- 增长路径示意图
- 断言校验代码块
- 评审结论结构化块

### 特别注意：多子项内容的换行

**用 `<br/>` 在同一个 `<p>` 内拼接多项内容，POPO 渲染不稳定，会出现内容黏连。**

凡是一个逻辑单元下有多个子项（如断言的「引文 / 基础校验 / 交叉推断 / 跨断言一致性 / 诊断」），**每个子项必须独立成一个 `<p>`**：

```html
<!-- ✅ 正确：每项独立 <p> -->
<p><strong>[断言 N]</strong> "..."</p>
<p>基础校验：...</p>
<p>交叉推断：...</p>
<p>跨断言一致性：...</p>
<p><strong>诊断</strong> 🟢 <strong>[结论]</strong> — 说明</p>

<!-- ❌ 错误：用 <br/> 拼在同一 <p> 里 -->
<p><strong>[断言 N]</strong> "..."<br/>基础校验：...<br/>诊断 🟢 ...</p>
```

同理适用于：Pre-mortem 各路径（路径标题、描述、诊断各自独立 `<p>`）、任何含多个平行子项的段落。

---

## 4. 串行分段写入

直接调用 `pw.write_sections(doc_id, sections)` 即可，内部已封装串行逻辑。

所有写入必须在 **同一个 Bash 调用** 里完成——`doc.insert_after` 服务器按到达顺序写入，并发会导致 sections 随机乱序。`popo_writer.py` 已处理这一约束，不需要手写循环。

---

## 5. 已知坑（持续追加）

| # | 坑描述 | 正确做法 |
|---|--------|---------|
| 1 | 用 `ThreadPoolExecutor` 并行写入 | 必须串行 for 循环，并行导致顺序随机乱序 |
| 2 | 骨架地图/树形图用 `<pre><code>` 或列表 | 必须用 `<code-block>` 包裹，否则不渲染等宽 |
| 3 | ~~链接用 `<a href="...">` 标签会被过滤~~ | 已验证可用，直接用 `<a href="url">文字</a>` |
| 4 | `docType` 传字符串 `"doc"` | 必须传整数 `1` |
| 5 | 用 `resp.get('docId')` 直接取 doc_id | 用递归 `extract_doc_id`，嵌套 JSON 层级不固定 |
| 6 | 每个 section 单独一次 Bash 工具调用 | 所有写入在同一个 Bash 调用里完成 |
| 7 | 先写测试内容再追加正式内容 | 调试和正式写入严格分离，不在同一文档混用 |
| 8 | `popo-cli` 直接用命令名 | 用完整路径 `/Users/nick/cuocuo_design/resource/bin/node/bin/popo-cli` |
| 9 | 用 `<br/>` 在同一 `<p>` 内拼接多个子项 | 每个子项独立成一个 `<p>`，见第 3 节「多子项内容的换行」 |

