"""Car Maintenance Companion API service.

Module layout (kept deliberately modular so a future service split is mechanical
rather than a rewrite — see docs/adr/0005-modular-monolith-not-microservices.md):

    app/identity/     authentication and the user record
    app/vehicles/     the garage
    app/maintenance/  plans, intervals and the projection engine

None of these exist yet. Phase 0 ships infrastructure only.
"""

__version__ = "0.1.1"
