import os
import re
import json
import random
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 1. 환경 변수 및 금고 키 설정
gemini_api_key = os.environ.get("GEMINI_API_KEY")
public_data_key = os.environ.get("DATA_GO_KR_KEY")
blogger_id = os.environ.get("BLOGGER_ID")
client_id = os.environ.get("GOOGLE_CLIENT_ID")
client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

HISTORY_FILE = "posted_history.txt"

# 복사 시 마크다운 링크 자동 변환([https...])을 원천 차단하기 위한 주소 조합 변수
SCHEME = "https" + "://"

def clean_url(u):
    """주소 문자열에 마크다운 기호([, ], (, ))가 섞여 들어와도 순수 URL만 안전하게 추출"""
    if not u:
        return ""
    u = str(u).strip()
    if "](" in u:
        u = u.split("](")[0]
    return u.strip("[]() \"'")

if not gemini_api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

# 2. 고정 첫인삿말 & 맺음말 설정 (옵션 3: 깔끔하고 경쾌한 톤)
FIXED_INTRO_TEXT = (
    "다들 오늘 하루도 정말 고생 많으셨어요!<br />"
    "집으로 향하는 발걸음 조금이라도 가벼워지시길 바라며, 오늘의 알짜배기 지원금 소식 바로 전해드립니다."
)

FIXED_OUTRO_TEXT = (
    "오늘도 <b>퇴근길 지원금 줍줍</b>과 함께해 주셔서 감사합니다.<br />"
    "오늘 하루도 고생 많으셨고, 내일 퇴근길에도 쏠쏠한 혜택 한 보따리 들고 찾아올게요!"
)

# 3. 100% 실제 촬영 사진(Real Photo) 카테고리별 DB (AI 생성 이미지 배제)
THEME_IMAGES = {
    "육아_출산": {
        "keywords": ["출산", "육아", "아동", "보육", "임신", "양육", "어린이", "유아", "첫만남", "신생아", "산모", "기저귀", "돌봄"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=1000&q=80",
                "alt": "아기와 부모가 함께 시간을 보내는 실제 가정 사진",
                "credit": "출처: Unsplash (@dakotacorbin) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1542037104857-ffbb0b9155fb?auto=format&fit=crop&w=1000&q=80",
                "alt": "아이와 가족이 함께 웃고 있는 육아 일상 사진",
                "credit": "출처: Unsplash (@natalie_pedigo) / 실제 촬영 사진"
            }
        ]
    },
    "청년_취업": {
        "keywords": ["청년", "취업", "구직", "채용", "일자리", "인턴", "면접", "직장인", "근로자", "내일채움"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1000&q=80",
                "alt": "청년들이 카페와 오피스에서 노트북으로 협업하는 실제 사진",
                "credit": "출처: Unsplash (@brookecagle) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=1000&q=80",
                "alt": "노트북과 다이어리를 펼쳐놓고 지원 서류를 작성하는 실제 모습",
                "credit": "출처: Unsplash (@andrewtneel) / 실제 촬영 사진"
            }
        ]
    },
    "교육_장학": {
        "keywords": ["교육", "장학", "학비", "등록금", "대학생", "학교", "초등", "중등", "고등", "수강", "학습", "유학", "대학원"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1000&q=80",
                "alt": "캠퍼스에서 학생들이 함께 공부하며 대화하는 실제 사진",
                "credit": "출처: Unsplash (@priscilladupreez) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1000&q=80",
                "alt": "책상 위에서 노트에 필기하며 학업을 준비하는 실제 사진",
                "credit": "출처: Unsplash (@unseenhistories) / 실제 촬영 사진"
            }
        ]
    },
    "주거_생활": {
        "keywords": ["주거", "전세", "월세", "주택", "임대", "이사", "보증금", "내집마련", "청약", "집수리", "리모델링"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=1000&q=80",
                "alt": "집 열쇠와 주택 모형을 들고 있는 실제 부동산·주거 사진",
                "credit": "출처: Unsplash (@tierramallorca) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1000&q=80",
                "alt": "가계부와 계산기로 주거비 예산을 점검하는 실제 사진",
                "credit": "출처: Unsplash (@kellysikkema) / 실제 촬영 사진"
            }
        ]
    },
    "의료_건강": {
        "keywords": ["의료", "건강", "치료", "병원", "검진", "진료", "약제비", "수술", "보건", "질환", "재활", "심리"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1000&q=80",
                "alt": "청진기와 의료 차트가 놓인 실제 병원 진료실 사진",
                "credit": "출처: Unsplash (@hush52) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1000&q=80",
                "alt": "의료진이 환자와 건강 상담을 진행하는 실제 사진",
                "credit": "출처: Unsplash (@nationalcancerinstitute) / 실제 촬영 사진"
            }
        ]
    },
    "어르신_복지": {
        "keywords": ["어르신", "노인", "고령", "연금", "요양", "경로", "치매", "은퇴", "기초연금", "장수"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1581579438747-1dc8d17bbce4?auto=format&fit=crop&w=1000&q=80",
                "alt": "밝게 미소 짓는 어르신 부부의 따뜻한 실제 일상 사진",
                "credit": "출처: Unsplash (@anniespratt) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1516307365426-bea591f05011?auto=format&fit=crop&w=1000&q=80",
                "alt": "어르신의 손을 따뜻하게 잡고 안내를 돕는 실제 복지 현장 사진",
                "credit": "출처: Unsplash (@matthiaszomer) / 실제 촬영 사진"
            }
        ]
    },
    "소상공인_기업": {
        "keywords": ["소상공인", "자영업", "중소기업", "사업자", "매출", "점포", "창업", "상인", "소기업", "폐업"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1556740758-90de374c12ad?auto=format&fit=crop&w=1000&q=80",
                "alt": "매장에서 결제 단말기로 고객을 응대하는 실제 소상공인 사진",
                "credit": "출처: Unsplash (@blakewisz) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1000&q=80",
                "alt": "사무실에서 사업 계획서와 재무 서류를 검토하는 실제 사진",
                "credit": "출처: Unsplash (@homajob) / 실제 촬영 사진"
            }
        ]
    },
    "농어업_지역": {
        "keywords": ["농업", "어업", "농가", "어가", "어선", "양식", "축산", "임업", "귀농", "귀어", "농촌", "어촌", "비료", "친환경"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=1000&q=80",
                "alt": "푸른 들판과 농작물이 자라는 실제 농어촌 풍경 사진",
                "credit": "출처: Unsplash (@goian) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=1000&q=80",
                "alt": "수확한 신선한 농산물을 손으로 들고 있는 실제 농가 사진",
                "credit": "출처: Unsplash (@sippakorn) / 실제 촬영 사진"
            }
        ]
    },
    "문화_체육_여가": {
        "keywords": ["문화", "체육", "스포츠", "공연", "전시", "여행", "관광", "체육인", "예술", "도서", "선수"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=1000&q=80",
                "alt": "활기차게 야외 체육 및 스포츠 활동을 즐기는 실제 사진",
                "credit": "출처: Unsplash (@fitnish) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1000&q=80",
                "alt": "여유롭게 문화 및 여가 시간을 보내는 실제 일상 사진",
                "credit": "출처: Unsplash (@sidekix) / 실제 촬영 사진"
            }
        ]
    },
    "일반_금융": {
        "keywords": ["지원금", "보조금", "급여", "수당", "감면", "환급", "바우처", "세금", "공과금", "생활비", "외국인", "피해자", "법률"],
        "photos": [
            {
                "url": SCHEME + "images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1000&q=80",
                "alt": "서류와 노트북을 놓고 정부 지원금 혜택을 확인하는 실제 사진",
                "credit": "출처: Unsplash (@towfiqu999999) / 실제 촬영 사진"
            },
            {
                "url": SCHEME + "images.unsplash.com/photo-1434626881859-194d67b2b86f?auto=format&fit=crop&w=1000&q=80",
                "alt": "스마트폰과 PC로 온라인 신청 절차를 밟는 실제 사진",
                "credit": "출처: Unsplash (@firmbee) / 실제 촬영 사진"
            }
        ]
    }
}

def is_image_url_valid(url):
    """실제 사진 URL이 깨지지 않고 정상 응답(HTTP 200 & image 타입)하는지 체크"""
    target_url = clean_url(url)
    try:
        req = urllib.request.Request(target_url, method="HEAD", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "")
            return resp.status == 200 and "image" in content_type
    except Exception:
        return True

def select_and_verify_images(service_title, post_title, official_facts, post_body):
    """
    [2단계 이미지 매칭 검수]
    1차: 제목/서비스명 가중치(5배) + 본문 키워드 스코어링으로 후보 선정
    2차: 제미나이에게 글의 핵심 주제와 실제 사진 설명이 잘 맞는지 재검수 요청
    """
    title_text = f"{service_title} {post_title}"
    body_text = f"{official_facts} {post_body}"

    scores = {}
    for category, data in THEME_IMAGES.items():
        score = 0
        for kw in data["keywords"]:
            if kw in title_text:
                score += 5
            if kw in body_text:
                score += 1
        scores[category] = score

    best_category = max(scores, key=scores.get)
    if scores[best_category] == 0:
        best_category = "일반_금융"

    category_descriptions = "\n".join(
        [f"- {cat}: {data['photos'][0]['alt']} / {data['photos'][1]['alt']}" for cat, data in THEME_IMAGES.items()]
    )
    verify_prompt = f"""
    아래 블로그 글 제목과 정책 정보에 가장 잘 어울리는 실제 사진 카테고리를 1개만 골라줘.
    글의 핵심 대상과 사진의 분위기(설명)가 어색하지 않고 잘 들어맞는지 꼼꼼히 체크해.

    [정책명]: {service_title}
    [블로그 제목]: {post_title}
    [글 요약]: {official_facts[:300]}
    [1차 추천 카테고리]: {best_category}

    [선택 가능한 실제 사진 카테고리 목록]
    {category_descriptions}

    다른 설명 없이 가장 알맞은 카테고리 이름(육아_출산, 청년_취업, 교육_장학, 주거_생활, 의료_건강, 어르신_복지, 소상공인_기업, 농어업_지역, 문화_체육_여가, 일반_금융 중 하나)만 정확히 출력해.
    """
    ai_choice = call_gemini(verify_prompt, temperature=0.0)
    if ai_choice:
        cleaned_choice = ai_choice.strip().replace("'", "").replace('"', "")
        for cat in THEME_IMAGES.keys():
            if cat in cleaned_choice:
                best_category = cat
                break

    print(f"🖼️ [이미지 매칭 검수 완료] 선택된 사진 테마: {best_category}")
    selected_photos = THEME_IMAGES[best_category]["photos"]

    verified_photos = []
    for idx, photo in enumerate(selected_photos):
        if is_image_url_valid(photo["url"]):
            verified_photos.append(photo)
        else:
            verified_photos.append(THEME_IMAGES["일반_금융"]["photos"][idx % 2])

    return verified_photos

def make_image_html(img_info):
    img_url = clean_url(img_info['url'])
    return f"""
<figure style="margin: 28px 0; text-align: center;">
  <img src="{img_url}" alt="{img_info['alt']}" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />
  <figcaption style="margin-top: 8px; font-size: 14.5px !important; line-height: 1.5 !important; color: #64748b !important;">
    📷 {img_info['alt']} ({img_info['credit']})
  </figcaption>
</figure>
""".strip()

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_history(service_name):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(service_name + "\n")

def get_working_model_name():
    candidate_models = []
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods and "gemini" in m.name:
                if not any(skip in m.name.lower() for skip in ["vision", "imagen", "veo", "tts", "audio", "embedding", "image"]):
                    candidate_models.append(m.name)
    except Exception as e:
        print(f"모델 목록 조회 에러: {e}")

    priority_models = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-2.5-pro",
    ]
    for pm in reversed(priority_models):
        if pm in candidate_models:
            candidate_models.remove(pm)
        candidate_models.insert(0, pm)
    return candidate_models

def fetch_from_data_go_kr(history_set):
    if not public_data_key:
        return None, None, None
    try:
        encoded_key = urllib.parse.quote(public_data_key) if "%" not in public_data_key else public_data_key
        page = random.randint(1, 20)
        url = clean_url(f"{SCHEME}api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage=20&serviceKey={encoded_key}")
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        items = data.get("data", [])
        if not items:
            return None, None, None
            
        valid_items = [
            item for item in items 
            if item.get("지원내용") and item.get("지원대상") and item.get("서비스명", "") not in history_set
        ]
        
        if not valid_items:
            return None, None, None
            
        chosen = random.choice(valid_items)
        service_name = chosen.get('서비스명', '정부 지원 혜택')
        default_gov_url = SCHEME + "www.gov.kr"
        detail_url = clean_url(chosen.get('상세조회URL') or default_gov_url)
        
        fact_sheet = f"""
[대한민국 행정안전부 보조금24 공식 데이터]
- 정책(서비스)명: {service_name}
- 소관기관명: {chosen.get('소관기관명', '관할 지자체 및 정부 부처')}
- 부서명: {chosen.get('부서명', '담당 부서')}
- 지원유형: {chosen.get('지원유형', '현금/바우처/서비스 지원')}
- 사용자구분: {chosen.get('사용자구분', '개인/가구')}
- 서비스목적요약: {chosen.get('서비스목적요약', '국민 생활 안정 및 복지 향상')}
- 신청대상(지원대상): {chosen.get('지원대상', '공고문 확인')}
- 선정기준: {chosen.get('선정기준', '지원대상 요건 충족 시 선정 (세부사항 공고문 참조)')}
- 지원내용(혜택 상세): {chosen.get('지원내용', '정보 없음')}
- 신청방법: {chosen.get('신청방법', '정부24 온라인 신청 또는 관할 주민센터 방문 신청')}
- 신청기한: {chosen.get('신청기한', '예산 소진 시 또는 별도 공고 기간까지')}
- 접수기관명: {chosen.get('접수기관명', '관할 행정복지센터 및 정부24')}
- 문의처: {chosen.get('문의처', '정부민원안내콜센터(110)')}
- 정부24 공식 상세안내 링크: {detail_url}
""".strip()
        return fact_sheet, service_name, detail_url
    except Exception as e:
        print(f"공공데이터 API 호출 에러: {e}")
        return None, None, None

def fetch_from_korea_kr_official():
    url = clean_url(SCHEME + "www.korea.kr/rss/policy.xml")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        items = root.findall('./channel/item')[:10]
        if not items:
            return None, None, None
        chosen = random.choice(items)
        title = chosen.find('title').text if chosen.find('title') is not None else ""
        desc = chosen.find('description').text if chosen.find('description') is not None else ""
        default_kr_url = SCHEME + "www.korea.kr"
        link = clean_url(chosen.find('link').text if chosen.find('link') is not None else default_kr_url)
        
        fact = f"[대한민국 정책브리핑 공식 발표 자료]\n- 제목: {title}\n- 상세내용: {desc}\n- 공식 원문 링크: {link}"
        return fact, title, link
    except Exception as e:
        print(f"정책브리핑 수집 에러: {e}")
        return None, None, None

def call_gemini(prompt, temperature=0.3):
    models = get_working_model_name()
    config = {
        "temperature": temperature,
        "max_output_tokens": 8192
    }
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name, generation_config=config)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception:
            continue
    return None

def step1_generate_draft(source_facts):
    prompt = f"""
    너는 '퇴근길 지원금 줍줍' 블로그를 운영하는 깔끔하고 경쾌한 스타일의 전문 에
