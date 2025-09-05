from typing import List, Optional
import httpx
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class VoixLanguageModel(BaseModel):
    id: str = ""
    title: str = ""
    lang_iso_code: str = ""


class ModelMatchLanguage(VoixLanguageModel):
    match_id: str = ""
    model_name: str = ""


class TimbreModel(BaseModel):
    id: str = ""
    size: int = 0
    index_file_size: int = 0
    value: str = ""
    title: str = ""
    description: str = ""
    is_enable: bool = False
    algorithm_name: str = "harvest"
    filter_radius: int = 3
    rms_mix_rate: float = 0.21
    protect_value: float = 0.33
    crepe_hop_length: int = 98

    voice_category: str = ""
    voice_gender: str = ""
    created_date: datetime = Field(default_factory=datetime.utcnow)

    model_type_id: str = ""
    model_product_id: str = ""
    timbre_lang_list: List[ModelMatchLanguage] = Field(default_factory=list)
    using_site_list: List[str] = Field(default_factory=list)


class TimbreModelType(BaseModel):
    model_type_id: str = ""
    model_type_name: str = ""
    model_type_color: str = ""


# 응답 형태가 래퍼일 수도 있어서 두 가지 케이스를 지원
class TimbreListData(BaseModel):
    model_list: List[TimbreModel]
    total_count: int


class ApiWrappedResponse(BaseModel):
    # 래퍼 안에 data 키가 있고, 그 안에 model_list / total_count가 있는 형태 지원
    model_config = ConfigDict(extra="allow")
    data: Optional[TimbreListData] = None


async def fetch_models():
    import os

    run_env = os.getenv("RUN_ENV")
    service_api_url = (
        "https://rcbrbeak6c.ap-northeast-1.awsapprunner.com/api"
        if run_env == "production"
        else "https://c3ng6xetsu.ap-northeast-1.awsapprunner.com/api"
    )

    timbre_api_url = f"{service_api_url}/timbre/raw-list"  # 실제 URL로 교체
    search_text = ""
    voice_category = None  # 혹은 문자열
    voice_gender = None  # 혹은 문자열
    page = 1
    current_page_size = 20
    now_order = {
        "date_order": "desc",
        "text_order": "asc",
    }

    params = {
        "search_text": search_text,
        "voice_category": voice_category or "",
        "voice_gender": voice_gender or "",
        "page": page,
        "page_size": current_page_size,
        "date_order": now_order["date_order"],
        "text_order": now_order["text_order"],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(timbre_api_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        data_wrapper = ApiWrappedResponse(**data)
        return data_wrapper.data
