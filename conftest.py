"""
conftest.py — repo-root pytest configuration.

Placing this file at the repo root puts the root on sys.path during
collection, so test modules can `import parser.*` regardless of how pytest
is invoked. Without it, each test file has to insert the root path itself,
and forgetting that line aborts the whole suite at collection time.
"""
