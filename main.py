from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

from models import AddXPRequest, AddXPResponse, RankingResponse
from service import RankingService

app = FastAPI(
    title="Gamification & Ranking Microservice",
    version="1.0.0"
)

security = HTTPBearer()

def get_current_user_uid(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Middleware xác thực Bearer Token từ Firebase Auth
    """
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token['uid']
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token không hợp lệ hoặc đã hết hạn: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.get("/")
def root():
    return {"status": "online", "service": "Gamification & Ranking API"}

@app.post("/gamification/add-xp", response_model=AddXPResponse)
def add_xp(
    req: AddXPRequest,
    current_uid: str = Depends(get_current_user_uid)
):
    """
    Cộng XP cho user khi học xong bài.
    - Xóa rủi ro gian lận vì UID lấy trực tiếp từ JWT Token.
    """
    try:
        result = RankingService.add_xp(uid=current_uid, xp_to_add=req.xp)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ranking", response_model=RankingResponse)
def get_ranking(
    current_uid: str = Depends(get_current_user_uid)
):
    """
    Lấy Bảng xếp hạng Top 10 và Rank của Current User trong tuần hiện tại.
    """
    try:
        return RankingService.get_ranking(current_uid=current_uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))