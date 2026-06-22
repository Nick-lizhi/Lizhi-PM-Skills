#!/usr/bin/env python3
"""
popo_writer.py — 向后兼容包装，实际逻辑已迁移到 popo_io.py
请直接使用 popo_io.py。
"""
import importlib.util, os

_spec = importlib.util.spec_from_file_location(
    "popo_io",
    os.path.join(os.path.dirname(__file__), "popo_io.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# 导出所有公开符号，保持原有调用不变
popo_call       = _mod.popo_call
extract_doc_id  = _mod.extract_doc_id
create_doc      = _mod.create_doc
get_doc         = _mod.read_doc        # get_doc → read_doc
write_sections  = _mod.write_sections
doc_url         = _mod.doc_url
create_and_write = _mod.create_and_write
