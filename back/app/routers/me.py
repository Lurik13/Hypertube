from fastapi import APIRouter

from app.deps import CurrentUser
from app.models import User
from app.schemas import UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    """The logged-in user; 401 when logged out."""
    return user
