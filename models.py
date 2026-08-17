from pydantic import BaseModel
from typing import List, Optional

class AddXPRequest(BaseModel):
    xp: int

class AddXPResponse(BaseModel):
    success: bool
    message: str
    new_total_xp: int
    weekly_xp: int

class UserRankItem(BaseModel):
    rank: Optional[int] = None
    uid: str
    name: str
    avatar: str
    xp: int
    level: int
    is_pro: bool = False

class CurrentUserRank(BaseModel):
    rank: Optional[int] = None
    xp: int
    is_pro: bool = False

class RankingResponse(BaseModel):
    top10: List[UserRankItem]
    current_user: CurrentUserRank