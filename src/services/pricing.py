from typing import Dict, Any

# ✅ Пакеты генераций (КАК В NANOBANANA!)
GENERATION_PACKAGES = {
    "small": {
        "generations": 10,
        "bonus": 0,
        "price": 99
    },
    "medium": {
        "generations": 25,
        "bonus": 5,
        "price": 199
    },
    "large": {
        "generations": 50,
        "bonus": 15,
        "price": 349
    },
    "xlarge": {
        "generations": 100,
        "bonus": 35,
        "price": 599
    }
}


def get_package_info(package_id: str) -> Dict[str, Any]:
    """Получить информацию о пакете"""
    return GENERATION_PACKAGES.get(package_id, GENERATION_PACKAGES["small"])


def calculate_stars_amount(rub_amount: int) -> int:
    """
    Конвертация рублей в Telegram Stars
    1 Star ≈ 2 рубля (может меняться)
    """
    from src.core.config import settings
    return int(rub_amount / settings.STARS_CONVERSION_RATE)


# ✅ Модели для изображений
IMAGE_MODELS = {
    "enhance_standard": {
        "description": "Standard V2 — универсальная",
        "endpoint": "enhance",
        "cost": 1.0,
        "params": {
            "model": "Standard V2",
            "output_width": 3840,
            "face_enhancement": True,
            "face_enhancement_strength": 0.8
        }
    },
    "enhance_high_fidelity": {
        "description": "High Fidelity V2 — макс. детали",
        "endpoint": "enhance",
        "cost": 1.5,
        "params": {
            "model": "High Fidelity V2",
            "output_width": 3840,
            "face_enhancement": True,
            "face_enhancement_strength": 0.8
        }
    },
    "sharpen_standard": {
        "description": "Sharpen — убрать размытие",
        "endpoint": "sharpen",
        "cost": 1.0,
        "params": {
            "model": "Standard",
            "strength": 0.7
        }
    },
    "denoise_normal": {
        "description": "Denoise — убрать шум",
        "endpoint": "denoise",
        "cost": 1.0,
        "params": {
            "model": "Normal",
            "strength": 0.7
        }
    },
    "enhance_redefine": {
        "description": "Redefine — AI генеративная",
        "endpoint": "enhance-gen/async",
        "cost": 3.0,
        "params": {
            "model": "Redefine",
            "output_width": 3840,
            "creativity": 3,
            "autoprompt": True
        }
    }
}


# ✅ Модели для видео
VIDEO_MODELS = {
    "proteus_4x": {
        "description": "Proteus — 4K upscale",
        "cost_per_minute": 5.0,
        "output_fps": 30,
        "filters": [
            {
                "model": "prob-4",
                "videoType": "Progressive",
                "auto": "Relative",
                "compression": 0.28,
                "details": 0.2
            }
        ]
    },
    "apollo_60fps": {
        "description": "Apollo — 60 FPS",
        "cost_per_minute": 6.0,
        "output_fps": 60,
        "filters": [
            {
                "model": "apo-8",
                "slowmo": 1,
                "fps": 60,
                "duplicate": True
            }
        ]
    },
    "artemis_denoise": {
        "description": "Artemis — denoise + sharpen",
        "cost_per_minute": 4.0,
        "output_fps": 30,
        "filters": [
            {
                "model": "ahq-12",
                "videoType": "Progressive",
                "auto": "Relative"
            }
        ]
    },
    "nyx_denoise": {
        "description": "Nyx — чистка от шума",
        "cost_per_minute": 3.0,
        "output_fps": 30,
        "filters": [
            {
                "model": "nyx-3",
                "videoType": "Progressive",
                "auto": "Relative"
            }
        ]
    }
}