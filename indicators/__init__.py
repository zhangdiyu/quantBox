# -*- coding: utf-8 -*-
"""
技术指标动态加载器
自动发现并加载 indicators/ 目录下所有指标模块
"""
import os
import importlib
import inspect

_REGISTRY = {}  # name -> indicator_info


def _discover():
    """扫描当前目录，注册所有带 INDICATORS 列表的模块"""
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in sorted(os.listdir(pkg_dir)):
        if fname.startswith('_') or not fname.endswith('.py'):
            continue
        mod_name = fname[:-3]
        mod = importlib.import_module(f'.{mod_name}', package=__name__)
        for ind in getattr(mod, 'INDICATORS', []):
            _REGISTRY[ind['name']] = ind


def get_all():
    """返回所有已注册指标，按分类分组
    Returns: dict[category] -> list[indicator_info]
    """
    if not _REGISTRY:
        _discover()
    grouped = {}
    for info in _REGISTRY.values():
        cat = info.get('category', '其他')
        grouped.setdefault(cat, []).append(info)
    return grouped


def get(name):
    """按名称获取单个指标信息"""
    if not _REGISTRY:
        _discover()
    return _REGISTRY.get(name)


def list_names():
    """返回所有指标名称列表"""
    if not _REGISTRY:
        _discover()
    return list(_REGISTRY.keys())


def reload_all():
    """重新扫描并加载所有指标（用于热更新）"""
    _REGISTRY.clear()
    _discover()
