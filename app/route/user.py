from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.dependencies import get_db
from app.service.user_service import UserService
from app.model.schema import User, UserCreate
from app.types.request import (
    UserCreateRequest,
    UserUpdateRequest,
    UserFilterParams,
    PaginationParams,
)
from app.types.response import UserResponse, UserListResponse, ErrorResponse

router = APIRouter()


@router.post(
    "/users", response_model=UserResponse, responses={400: {"model": ErrorResponse}}
)
async def create_user(request: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        db_user = await UserService.create(db, request.model_dump())
        return UserService.to_schema(db_user)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    try:
        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserService.to_schema(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
