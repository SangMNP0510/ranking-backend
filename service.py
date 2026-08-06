from datetime import datetime
from typing import Dict, Any, List, Optional
from firebase_admin import firestore
from config import db_firestore, db_realtime
from models import UserRankItem, CurrentUserRank, RankingResponse

def get_current_week_key() -> str:
    """Trả về format năm-tuần, ví dụ: '2026-W32'"""
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"

class RankingService:
    @staticmethod
    def add_xp(uid: str, xp_to_add: int) -> Dict[str, Any]:
        if xp_to_add <= 0:
            raise ValueError("Số XP thêm vào phải lớn hơn 0")

        # 1. Cập nhật Firestore (users/{uid})
        user_ref = db_firestore.collection('users').document(uid)
        
        # Dùng Transaction/FieldValue để cộng dồn an toàn
        user_ref.update({
            'gamification.totalExp': firestore.Increment(xp_to_add)
        })
        
        # Lấy lại total_xp mới
        user_doc = user_ref.get()
        total_xp = 0
        if user_doc.exists:
            user_data = user_doc.to_dict() or {}
            total_xp = user_data.get('gamification', {}).get('totalExp', 0)

        # 2. Cập nhật Realtime Database (weekly_ranking/{current_week}/{uid})
        week_key = get_current_week_key()
        weekly_user_ref = db_realtime.child('weekly_ranking').child(week_key).child(uid).child('xp')
        
        # Transaction trên Realtime DB để tránh xung đột concurrent request
        def update_xp_transaction(current_val):
            return (current_val or 0) + xp_to_add

        weekly_user_ref.transaction(update_xp_transaction)
        
        # Lấy weekly_xp hiện tại
        weekly_xp = weekly_user_ref.get() or 0

        return {
            "success": True,
            "message": "Cộng XP thành công",
            "new_total_xp": total_xp,
            "weekly_xp": weekly_xp
        }

    @staticmethod
    def get_ranking(current_uid: str) -> RankingResponse:
        week_key = get_current_week_key()
        
        # 1. Đọc dữ liệu Realtime Database của tuần hiện tại
        weekly_data: Optional[Dict[str, Dict[str, int]]] = db_realtime.child('weekly_ranking').child(week_key).get()

        if not weekly_data:
            # Nếu tuần này chưa có ai học
            return RankingResponse(
                top10=[],
                current_user=CurrentUserRank(rank=None, xp=0)
            )

        # 2. Convert & Sort danh sách giảm dần theo XP
        # Sắp xếp danh sách tuples: [(uid1, 520), (uid2, 480), ...]
        sorted_users = sorted(
            weekly_data.items(),
            key=lambda item: item[1].get('xp', 0),
            reverse=True
        )

        # 3. Tìm thông tin Current User trong danh sách đã sort
        current_user_rank: Optional[int] = None
        current_user_xp: int = 0

        for index, (uid, data) in enumerate(sorted_users):
            if uid == current_uid:
                current_user_rank = index + 1
                current_user_xp = data.get('xp', 0)
                break

        # 4. Lấy Top 10 UIDs
        top10_tuples = sorted_users[:10]
        top10_uids = [item[0] for item in top10_tuples]

        # 5. Đọc Firestore để Enrich (ghép name, avatar, level) cho Top 10
        user_profiles: Dict[str, Dict[str, Any]] = {}
        if top10_uids:
            # Dùng FieldPath.document_id() để query nhiều doc 1 lúc
            docs = db_firestore.collection('users').where(
                field_path=firestore.FieldPath.document_id(),
                op_string='in',
                value=top10_uids
            ).stream()

            for doc in docs:
                data = doc.to_dict()
                total_exp = data.get('gamification', {}).get('totalExp', 0)
                user_profiles[doc.id] = {
                    'name': data.get('fullName', 'Người dùng'),
                    'avatar': data.get('avatarUrl', ''),
                    'level': (total_exp // 1000) + 1  # Ví dụ công thức level
                }

        # 6. Build danh sách Top 10 trả về
        top10_items: List[UserRankItem] = []
        for index, (uid, data) in enumerate(top10_tuples):
            profile = user_profiles.get(uid, {
                'name': 'Người dùng',
                'avatar': '',
                'level': 1
            })
            
            top10_items.append(UserRankItem(
                rank=index + 1,
                uid=uid,
                name=profile['name'],
                avatar=profile['avatar'],
                xp=data.get('xp', 0),
                level=profile['level']
            ))

        return RankingResponse(
            top10=top10_items,
            current_user=CurrentUserRank(
                rank=current_user_rank,
                xp=current_user_xp
            )
        )