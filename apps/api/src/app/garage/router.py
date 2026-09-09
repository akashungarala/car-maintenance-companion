"""Vehicle endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.garage.models import MAX_YEAR, MIN_YEAR
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
