"""Identity: who someone is, and how they prove it.

A module boundary rather than a service boundary (ADR-0005). Vehicles and
maintenance share a transactional boundary with nothing here, so the separation
is enforced by imports and directory structure, not by a network hop.
"""
