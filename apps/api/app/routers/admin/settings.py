import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.setting import Setting
from app.models.user import User
from app.core.security import get_current_user
from app.core.config import settings as app_settings

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])

class SettingsUpdateRequest(BaseModel):
    site_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    accent_color: str | None = None
    icp: str | None = None
    police_icp: str | None = None
    diurnal_lighting: bool | None = None

@router.get("")
async def get_admin_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Setting))
    db_settings = {s.key: json.loads(s.value_json) for s in res.scalars().all()}

    return {
        "site_title": db_settings.get("site_title", "Luntrix's Editorial"),
        "subtitle": db_settings.get("subtitle", "空间化与特稿级个人技术手记"),
        "description": db_settings.get("description", "以杂志级排版 × 空间化交互 × 电影级动效为核心的技术博客"),
        "accent_color": db_settings.get("accent_color", "#FF4D2E"),
        "icp": db_settings.get("icp", "粤ICP备00000000号"),
        "police_icp": db_settings.get("police_icp", "公安网安备00000000号"),
        "diurnal_lighting": db_settings.get("diurnal_lighting", True),
        "integrations": {
            "cos": bool(app_settings.COS_SECRET_ID and app_settings.COS_BUCKET),
            "github": bool(app_settings.GITHUB_TOKEN),
            "smtp": bool(app_settings.SMTP_HOST),
        }
    }

@router.patch("")
async def update_admin_settings(
    req: SettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        res = await db.execute(select(Setting).where(Setting.key == key))
        setting_obj = res.scalar_one_or_none()
        if setting_obj:
            setting_obj.value_json = json.dumps(value, ensure_ascii=False)
        else:
            db.add(Setting(key=key, value_json=json.dumps(value, ensure_ascii=False)))

    await db.commit()
    return {"message": "站点配置更新成功"}
