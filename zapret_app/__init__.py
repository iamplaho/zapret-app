"""zapret-app — графическая оболочка для обхода блокировок Discord и YouTube.

Версия берётся из тега релиза: при сборке CI записывает файл _build_version.py.
Без этого файла (запуск из исходников) используется значение ниже.
"""
__version__ = "0.3.0"

try:
    from ._build_version import VERSION as __version__  # noqa: F811
except ImportError:
    pass
