from datetime import datetime
import time
from typing import Dict, Any, List, Optional
from firebase_admin import firestore
from config import db_firestore, db_realtime
from models import UserRankItem, CurrentUserRank, RankingResponse

def get_current_week_key() -> str:
    """Trả về format năm-tuần, ví dụ: '2026-W33'"""
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"

class RankingService:
    @staticmethod
    def add_xp(uid: str, xp_to_add: int) -> Dict[str, Any]:
        if xp_to_add <= 0:
            raise ValueError("Số XP thêm vào phải lớn hơn 0")

        now_ms = int(time.time() * 1000)
        week_key = get_current_week_key()
        
        # 1. Cập nhật Realtime Database (weekly_ranking/{current_week}/{uid})
        weekly_user_ref = db_realtime.child('weekly_ranking').child(week_key).child(uid)
        
        # Transaction cập nhật cả XP lẫn thời điểm đạt được điểm số này (updated_at)
        def update_user_ranking_transaction(current_data):
            if current_data is None:
                current_data = {'xp': 0, 'updated_at': now_ms}
            elif isinstance(current_data, int):
                # Tương thích nếu trước đó chỉ lưu int
                current_data = {'xp': current_data, 'updated_at': now_ms}
            
            new_xp = (current_data.get('xp') or 0) + xp_to_add
            return {
                'xp': new_xp,
                'updated_at': now_ms  # 👈 Ghi nhận thời điểm đạt mốc điểm này
            }

        weekly_user_ref.transaction(update_user_ranking_transaction)
        
        # Lấy lại data sau transaction
        user_weekly_data = weekly_user_ref.get() or {}
        weekly_xp = user_weekly_data.get('xp', 0) if isinstance(user_weekly_data, dict) else (user_weekly_data or 0)

        # 2. Đọc tổng XP từ Firestore để phản hồi
        user_ref = db_firestore.collection('users').document(uid)
        user_doc = user_ref.get()
        total_xp = 0
        if user_doc.exists:
            user_data = user_doc.to_dict() or {}
            total_xp = user_data.get('gamification', {}).get('totalExp', 0)

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
        weekly_data: Optional[Dict[str, Any]] = db_realtime.child('weekly_ranking').child(week_key).get()

        # Lấy thông tin Pro của Current User từ Firestore
        current_user_doc = db_firestore.collection('users').document(current_uid).get()
        current_user_is_pro = False
        if current_user_doc.exists:
            current_user_data = current_user_doc.to_dict() or {}
            current_user_is_pro = current_user_data.get('subscription', {}).get('isPro', False)

        if not weekly_data:
            return RankingResponse(
                top10=[],
                current_user=CurrentUserRank(rank=None, xp=0, is_pro=current_user_is_pro)
            )

        # 2. Chuẩn hóa format dữ liệu ({uid: {'xp': ..., 'updated_at': ...}})
        normalized_users = []
        for uid, val in weekly_data.items():
            if isinstance(val, dict):
                xp = val.get('xp', 0)
                updated_at = val.get('updated_at', 0)
            else:
                # Fallback nếu dữ liệu cũ chỉ là integer
                xp = val or 0
                updated_at = 0
            normalized_users.append((uid, {'xp': xp, 'updated_at': updated_at}))

        # 3. Sắp xếp chuẩn:
        # - XP lớn hơn xếp trước (-xp)
        # - Nếu XP bằng nhau: Ai cập nhật đạt mốc trước (updated_at nhỏ hơn) xếp trước (+updated_at)
        sorted_users = sorted(
            normalized_users,
            key=lambda item: (-item[1]['xp'], item[1]['updated_at'])
        )

        # 4. Tìm thứ hạng của Current User
        current_user_rank: Optional[int] = None
        current_user_xp: int = 0

        for index, (uid, data) in enumerate(sorted_users):
            if uid == current_uid:
                current_user_rank = index + 1
                current_user_xp = data.get('xp', 0)
                break

        # 5. Lấy Top 10 UIDs
        top10_tuples = sorted_users[:10]
        top10_uids = [item[0] for item in top10_tuples]

        # 6. Đọc Firestore để lấy profile và trạng thái Pro
        user_profiles: Dict[str, Dict[str, Any]] = {}
        if top10_uids:
            for uid in top10_uids:
                doc = db_firestore.collection('users').document(uid).get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    total_exp = data.get('gamification', {}).get('totalExp', 0)
                    is_pro = data.get('subscription', {}).get('isPro', False)
                    user_profiles[doc.id] = {
                        'name': data.get('fullName', 'Người dùng'),
                        'avatar': data.get('avatarUrl', ''),
                        'level': (total_exp // 1000) + 1,
                        'is_pro': is_pro
                    }

        # 7. Tạo danh sách Top 10
        top10_items: List[UserRankItem] = []
        for index, (uid, data) in enumerate(top10_tuples):
            profile = user_profiles.get(uid, {
                'name': 'Người dùng',
                'avatar': '',
                'level': 1,
                'is_pro': False
            })
            
            top10_items.append(UserRankItem(
                rank=index + 1,
                uid=uid,
                name=profile['name'],
                avatar=profile['avatar'],
                xp=data.get('xp', 0),
                level=profile['level'],
                is_pro=profile['is_pro']
            ))

        return RankingResponse(
            top10=top10_items,
            current_user=CurrentUserRank(
                rank=current_user_rank,
                xp=current_user_xp,
                is_pro=current_user_is_pro
            )
        )