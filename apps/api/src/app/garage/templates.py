"""The maintenance items every vehicle starts with.

Generic rather than manufacturer-specific: no free source of OEM schedules
exists (ADR-0006), and these intervals barely vary across mainstream vehicles.

Defined in code, not in a table. They are constants that change when a product
decision changes, not data that changes on its own -- a templates table would
add a join to every plan query and a migration to every interval tweak, and
would still need copying per vehicle to make the values editable. Copying at
creation gives editability without the join.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MaintenanceTemplate:
    name: str
    interval_miles: int | None
    interval_months: int | None


#: Order matters: it is the order the dashboard lists items within a band, and
#: it runs roughly from "most often" to "least often" so the top of the list is
#: the part that changes.
DEFAULT_TEMPLATES: tuple[MaintenanceTemplate, ...] = (
    MaintenanceTemplate("Engine oil & filter", 5_000, 6),
    MaintenanceTemplate("Tire rotation", 6_000, None),
    # 21 days. Not maintenance in the mechanical sense, and included on purpose:
    # it is the item that gets used most often, which is what keeps somebody
    # opening the app between oil changes.
    MaintenanceTemplate("Wash & interior clean", None, None),
    MaintenanceTemplate("Cabin air filter", 15_000, 12),
    MaintenanceTemplate("Engine air filter", 30_000, None),
    MaintenanceTemplate("Brake fluid", 30_000, 36),
    MaintenanceTemplate("Registration / inspection", None, 12),
    MaintenanceTemplate("Coolant", 60_000, 60),
)

#: The wash interval is days rather than months, and months is the only
#: time unit the engine takes. Rather than add a third interval column used by
#: exactly one row, it is stored as days here and converted at seed time.
WASH_INTERVAL_DAYS = 21
