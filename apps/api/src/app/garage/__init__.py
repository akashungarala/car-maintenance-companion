"""The garage: what a person drives.

A module boundary, not a service boundary (ADR-0005). Vehicles and their
maintenance plans share a transactional boundary -- creating a vehicle seeds
its plan in the same transaction -- so separating them across a network would
manufacture a distributed transaction to solve a problem that does not exist.
"""
