"""Vehicle endpoints."""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.garage.completion import CompletionService
from app.garage.models import MAX_YEAR, MIN_YEAR
from app.garage.plan import PlanService
from app.garage.repository import VehicleRepository
from app.identity.dependencies import CurrentUser

router = APIRouter(prefix="/vehicles", tags=["garage"])


class VehicleCreate(BaseModel):
    # extra="forbid": a field the client should not be sending is a mistake
    # worth reporting, not one to ignore. odometer_recorded_at is the case that
    # matters -- accepting it would let a caller backdate a reading and move
    # every projected due date on that vehicle.
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=MIN_YEAR, le=MAX_YEAR)
    make: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=64)
    odometer: int = Field(ge=0)
    annual_mileage: int = Field(ge=0)
    nickname: str | None = Field(default=None, max_length=64)

    @field_validator("make", "model")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    year: int
    make: str
    model: str
    nickname: str | None
    display_name: str
    odometer: int
    odometer_recorded_at: datetime
    annual_mileage: int
    created_at: datetime


@router.get("", summary="The signed-in user's vehicles")
async def list_vehicles(request: Request, user: CurrentUser) -> list[VehicleOut]:
    async with request.app.state.database.session() as session:
        vehicles = await VehicleRepository(session, user.id).list()
        return [VehicleOut.model_validate(v) for v in vehicles]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add a vehicle")
async def create_vehicle(payload: VehicleCreate, request: Request, user: CurrentUser) -> VehicleOut:
    async with request.app.state.database.session() as session:
        vehicle = await VehicleRepository(session, user.id).create(
            year=payload.year,
            make=payload.make,
            model=payload.model,
            odometer=payload.odometer,
            annual_mileage=payload.annual_mileage,
            nickname=payload.nickname,
        )
        return VehicleOut.model_validate(vehicle)


@router.get("/{vehicle_id}", summary="One vehicle")
async def get_vehicle(vehicle_id: uuid.UUID, request: Request, user: CurrentUser) -> VehicleOut:
    async with request.app.state.database.session() as session:
        vehicle = await VehicleRepository(session, user.id).get(vehicle_id)

    # 404, never 403. "Forbidden" confirms the record exists, which is half of
    # what somebody guessing ids wants to learn.
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleOut.model_validate(vehicle)


class PlanEntryOut(BaseModel):
    id: uuid.UUID
    name: str
    due_at: date | None
    due_mileage: int | None
    status: str
    #: True while the last-done date is our assumption rather than the user's
    #: fact. The interface says so; presenting an assumption as a fact is the
    #: dishonest version of this feature.
    is_assumed: bool


class PlanOut(BaseModel):
    vehicle_id: uuid.UUID
    #: The number the user cannot otherwise get without walking outside and
    #: reading the dashboard.
    estimated_mileage: int
    items: list[PlanEntryOut]


@router.get("/{vehicle_id}/plan", summary="What this vehicle needs, and when")
async def get_plan(vehicle_id: uuid.UUID, request: Request, user: CurrentUser) -> PlanOut:
    async with request.app.state.database.session() as session:
        vehicle = await VehicleRepository(session, user.id).get(vehicle_id)
        if vehicle is None:
            # 404 for "not yours" as well as "does not exist", for the same
            # reason as the vehicle endpoint.
            raise HTTPException(status_code=404, detail="Vehicle not found")

        # Today is computed once, here, rather than inside the engine -- which
        # is what keeps the engine pure and testable at any point in a
        # vehicle's life.
        entries = await PlanService(session).project(vehicle, today=datetime.now(UTC).date())

    return PlanOut(
        vehicle_id=vehicle.id,
        estimated_mileage=entries[0].estimated_mileage if entries else vehicle.odometer,
        items=[
            PlanEntryOut(
                id=e.id,
                name=e.name,
                due_at=e.due_at,
                due_mileage=e.due_mileage,
                status=str(e.status),
                is_assumed=e.is_assumed,
            )
            for e in entries
        ],
    )


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The one number we ask for, because it is the one they are standing next
    #: to. Not the cost, not the garage, not a note -- every extra field is a
    #: reason to close the sheet.
    odometer: int = Field(ge=0)
    #: Defaults to today at the caller's discretion; the API requires it
    #: explicitly so "when did you do this" is answerable for a service being
    #: recorded a week late.
    performed_at: date


class ServiceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    performed_at: date
    odometer: int


@router.post(
    "/{vehicle_id}/items/{item_id}/complete",
    status_code=status.HTTP_201_CREATED,
    summary="Mark maintenance done",
)
async def complete_item(
    vehicle_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: CompleteRequest,
    request: Request,
    user: CurrentUser,
) -> ServiceRecordOut:
    async with request.app.state.database.session() as session:
        vehicle = await VehicleRepository(session, user.id).get(vehicle_id)
        if vehicle is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        try:
            record = await CompletionService(session).complete(
                vehicle=vehicle,
                item_id=item_id,
                odometer=payload.odometer,
                performed_at=payload.performed_at,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Item not found") from exc
        except ValueError as exc:
            # 422 with the reason: this one is worth telling the user about,
            # because it is almost always a typo they can see and fix.
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return ServiceRecordOut.model_validate(record)


@router.get("/{vehicle_id}/history", summary="What has been done to this vehicle")
async def get_history(
    vehicle_id: uuid.UUID, request: Request, user: CurrentUser
) -> list[ServiceRecordOut]:
    async with request.app.state.database.session() as session:
        vehicle = await VehicleRepository(session, user.id).get(vehicle_id)
        if vehicle is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        records = await CompletionService(session).history(vehicle.id)
        return [ServiceRecordOut.model_validate(r) for r in records]
