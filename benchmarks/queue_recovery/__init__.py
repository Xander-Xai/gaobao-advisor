"""Isolated Redis delivery-model comparison for Issue #40.

Import adapters from their modules so this package does not initialize the
application database before ``DATABASE_URL`` is set.
"""
