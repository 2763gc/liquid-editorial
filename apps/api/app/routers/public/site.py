from fastapi import APIRouter

router = APIRouter(tags=["site"])

@router.get("/site")
async def get_site_config():
    return {
        "title": "Luntrix's Editorial",
        "subtitle": "空间化与特稿级个人技术手记",
        "description": "以杂志级排版 × 空间化交互 × 电影级动效为核心的软件开发者个人技术博客",
        "author": {
            "name": "Luntrix",
            "bio": "全栈工程师 & 系统架构探索者",
            "avatar_url": "/avatar.png",
        },
        "social": {
            "github": "https://github.com",
            "twitter": "https://x.com",
            "email": "contact@example.com",
        },
        "appearance": {
            "default_theme": "auto",
            "accent_color": "#FF4D2E",
            "diurnal_lighting": True,
            "film_grain": True,
        },
        "icp": "粤ICP备00000000号",
        "police_icp": "公安网安备00000000号",
        "copyright": "CC BY-NC-SA 4.0",
    }
