"""Firestore -> PostgreSQL ETL for the v3 migration.

Pure transforms live here (testable without any live database); the load and
parity steps wrap them with I/O. See the migration plan for the wave sequence.
"""
