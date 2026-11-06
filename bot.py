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
SCHEME = "https" + "://"

if not gemini_api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

def clean_url(u):
    if not u:
        return ""
    u = str(u).strip()
    m = re.search(r"\((https?://[^)]+)\)", u)
    if m:
        return m.group(1).strip()
    u = re.sub(r"^\[+", "", u)
    u = re.sub(r"\]+.*$", "", u)
    return u.strip()

# 2. 고정 첫인삿말 & 맺음말 설정 (옵션 3: 깔끔하고 경쾌한 톤)
FIXED_INTRO_TEXT = (
    "다들 오늘 하루도 정말 고생 많으셨어요!<br />"
    "집으로 향하는 발걸음 조금이라도 가벼워지시길 바라며, 오늘의 알짜배기 지원금 소식 바로 전해드립니다."
)

FIXED_OUTRO_TEXT = (
    "오늘도 <b>퇴근길 지원금 줍줍</b>과 함께해 주셔서 감사합니다.<br />"
    "오늘 하루도 고생 많으셨고, 내일 퇴근길에도 쏠쏠한 혜택 한 보따리 들고 찾아올게요!"
)

# 3. 100% 실제 촬영 사진(Real Photo) 카테고리별 DB
IMG_BASE = SCHEME + "images.unsplash.com/"

THEME_IMAGES = {
    "육아_출산": {
        "keywords": ["출산", "육아", "아동", "보육", "임신", "양육", "어린이", "유아", "첫만남", "신생아", "산모", "기저귀", "돌봄"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1519689680058-324335c77eba?auto=format&fit=crop&w=1000&q=80",
                "alt": "아기와 부모가 함께 시간을 보내는 실제 가정 사진",
                "credit": "출처: Unsplash (@dakotacorbin) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1542037104857-ffbb0b9155fb?auto=format&fit=crop&w=1000&q=80",
                "alt": "아이와 가족이 함께 웃고 있는 육아 일상 사진",
                "credit": "출처: Unsplash (@natalie_pedigo) / 실제 촬영 사진"
            }
        ]
    },
    "청년_취업": {
        "keywords": ["청년", "취업", "구직", "채용", "일자리", "인턴", "면접", "직장인", "근로자", "내일채움"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1000&q=80",
                "alt": "청년들이 오피스에서 노트북으로 업무를 보는 실제 사진",
                "credit": "출처: Unsplash (@brookecagle) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=1000&q=80",
                "alt": "노트북과 다이어리를 펼쳐놓고 지원 서류를 작성하는 실제 모습",
                "credit": "출처: Unsplash (@andrewtneel) / 실제 촬영 사진"
            }
        ]
    },
    "교육_장학": {
        "keywords": ["교육", "장학", "학비", "등록금", "대학생", "학교", "초등", "중등", "고등", "수강", "학습", "유학", "대학원"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1000&q=80",
                "alt": "캠퍼스에서 학생들이 함께 공부하며 대화하는 실제 사진",
                "credit": "출처: Unsplash (@priscilladupreez) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1000&q=80",
                "alt": "책상 위에서 노트에 필기하며 학업을 준비하는 실제 사진",
                "credit": "출처: Unsplash (@unseenhistories) / 실제 촬영 사진"
            }
        ]
    },
    "주거_생활": {
        "keywords": ["주거", "전세", "월세", "주택", "임대", "이사", "보증금", "내집마련", "청약", "집수리", "리모델링"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=1000&q=80",
                "alt": "집 열쇠와 주택 모형을 들고 있는 실제 주거 관련 사진",
                "credit": "출처: Unsplash (@tierramallorca) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1000&q=80",
                "alt": "가계부와 계산기로 주거비 예산을 점검하는 실제 사진",
                "credit": "출처: Unsplash (@kellysikkema) / 실제 촬영 사진"
            }
        ]
    },
    "의료_건강": {
        "keywords": ["의료", "건강", "치료", "병원", "검진", "진료", "약제비", "수술", "보건", "질환", "재활", "심리", "장애"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1000&q=80",
                "alt": "청진기와 의료 차트가 놓인 실제 병원 진료실 사진",
                "credit": "출처: Unsplash (@hush52) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1000&q=80",
                "alt": "의료진이 건강 상담을 진행하는 실제 사진",
                "credit": "출처: Unsplash (@nationalcancerinstitute) / 실제 촬영 사진"
            }
        ]
    },
    "어르신_복지": {
        "keywords": ["어르신", "노인", "고령", "연금", "요양", "경로", "치매", "은퇴", "기초연금", "장수"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1581579438747-1dc8d17bbce4?auto=format&fit=crop&w=1000&q=80",
                "alt": "밝게 미소 짓는 어르신 부부의 따뜻한 실제 일상 사진",
                "credit": "출처: Unsplash (@anniespratt) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1516307365426-bea591f05011?auto=format&fit=crop&w=1000&q=80",
                "alt": "어르신의 손을 따뜻하게 잡고 안내를 돕는 실제 복지 현장 사진",
                "credit": "출처: Unsplash (@matthiaszomer) / 실제 촬영 사진"
            }
        ]
    },
    "소상공인_기업": {
        "keywords": ["소상공인", "자영업", "중소기업", "사업자", "매출", "점포", "창업", "상인", "소기업", "폐업"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1556740758-90de374c12ad?auto=format&fit=crop&w=1000&q=80",
                "alt": "매장에서 결제 단말기로 고객을 응대하는 실제 소상공인 사진",
                "credit": "출처: Unsplash (@blakewisz) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1000&q=80",
                "alt": "사무실에서 사업 계획서와 재무 서류를 검토하는 실제 사진",
                "credit": "출처: Unsplash (@homajob) / 실제 촬영 사진"
            }
        ]
    },
    "농어업_지역": {
        "keywords": ["농업", "어업", "농가", "어가", "어선", "양식", "축산", "임업", "귀농", "귀어", "농촌", "어촌", "비료", "친환경"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=1000&q=80",
                "alt": "푸른 들판과 농작물이 자라는 실제 농어촌 풍경 사진",
                "credit": "출처: Unsplash (@goian) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=1000&q=80",
                "alt": "수확한 신선한 농산물을 손으로 들고 있는 실제 농가 사진",
                "credit": "출처: Unsplash (@sippakorn) / 실제 촬영 사진"
            }
        ]
    },
    "문화_체육_여가": {
        "keywords": ["문화", "체육", "스포츠", "공연", "전시", "여행", "관광", "체육인", "예술", "도서"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1517649763962-0c623066013b?auto=format&fit=crop&w=1000&q=80",
                "alt": "활기차게 야외 체육 및 스포츠 활동을 즐기는 실제 사진",
                "credit": "출처: Unsplash (@fitnish) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1000&q=80",
                "alt": "여유롭게 문화 및 여가 시간을 보내는 실제 일상 사진",
                "credit": "출처: Unsplash (@sidekix) / 실제 촬영 사진"
            }
        ]
    },
    "일반_금융": {
        "keywords": ["지원금", "보조금", "급여", "수당", "감면", "환급", "바우처", "세금", "공과금", "생활비"],
        "photos": [
            {
                "url": IMG_BASE + "photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1000&q=80",
                "alt": "서류와 노트북을 놓고 정부 지원금 혜택을 확인하는 실제 사진",
                "credit": "출처: Unsplash (@towfiqu999999) / 실제 촬영 사진"
            },
            {
                "url": IMG_BASE + "photo-1434626881859-194d67b2b86f?auto=format&fit=crop&w=1000&q=80",
                "alt": "스마트폰과 PC로 온라인 신청 절차를 밟는 실제 사진",
                "credit": "출처: Unsplash (@firmbee) / 실제 촬영 사진"
            }
        ]
    }
}

def is_image_url_valid(url):
    try:
        target_url = clean_url(url)
        req = urllib.request.Request(target_url, method="HEAD", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "")
            return resp.status == 200 and "image" in content_type
    except Exception:
        return True

def select_and_verify_images(service_title, post_title, official_facts, post_body):
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
    verify_prompt = (
        "아래 블로그 글 제목과 정책 정보에 가장 잘 어울리는 실제 사진 카테고리를 1개만 골라줘.\n"
        "글의 핵심 대상과 사진의 분위기(설명)가 어색하지 않고 잘 들어맞는지 꼼꼼히 체크해.\n\n"
        f"[정책명]: {service_title}\n"
        f"[블로그 제목]: {post_title}\n"
        f"[글 요약]: {official_facts[:300]}\n"
        f"[1차 추천 카테고리]: {best_category}\n\n"
        "[선택 가능한 실제 사진 카테고리 목록]\n"
        f"{category_descriptions}\n\n"
        "다른 설명 없이 가장 알맞은 카테고리 이름(육아_출산, 청년_취업, 교육_장학, 주거_생활, 의료_건강, 어르신_복지, 소상공인_기업, 농어업_지역, 문화_체육_여가, 일반_금융 중 하나)만 정확히 출력해."
    )
    ai_choice = call_gemini(verify_prompt, temperature=0.0)
    if ai_choice:
        cleaned_choice = ai_choice.strip().replace("'", "").replace('"', "")
        for cat in THEME_IMAGES.keys():
            if cat in cleaned_choice:
                best_category = cat
                break

    print(f"🖼️ [이미지 2중 검수 완료] 최종 선택된 실제 사진 테마: {best_category}")
    selected_photos = THEME_IMAGES[best_category]["photos"]

    verified_photos = []
    for idx, photo in enumerate(selected_photos):
        if is_image_url_valid(photo["url"]):
            verified_photos.append(photo)
        else:
            verified_photos.append(THEME_IMAGES["일반_금융"]["photos"][idx % 2])

    return verified_photos

def make_image_html(img_info):
    safe_url = clean_url(img_info["url"])
    return (
        '<figure style="margin: 28px 0; text-align: center;">'
        f'<img src="{safe_url}" alt="{img_info["alt"]}" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />'
        '<figcaption style="margin-top: 8px; font-size: 14.5px !important; line-height: 1.5 !important; color: #64748b !important;">'
        f'📷 {img_info["alt"]} ({img_info["credit"]})'
        '</figcaption></figure>'
    )

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
        api_url = clean_url(SCHEME + f"api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage=20&serviceKey={encoded_key}")
        
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
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
        detail_url = clean_url(chosen.get('상세조회URL', default_gov_url)) or default_gov_url
        
        fact_sheet = (
            "[대한민국 행정안전부 보조금24 공식 데이터]\n"
            f"- 정책(서비스)명: {service_name}\n"
            f"- 소관기관명: {chosen.get('소관기관명', '관할 지자체 및 정부 부처')}\n"
            f"- 부서명: {chosen.get('부서명', '담당 부서')}\n"
            f"- 지원유형: {chosen.get('지원유형', '현금/바우처/서비스 지원')}\n"
            f"- 사용자구분: {chosen.get('사용자구분', '개인/가구')}\n"
            f"- 서비스목적요약: {chosen.get('서비스목적요약', '국민 생활 안정 및 복지 향상')}\n"
            f"- 신청대상(지원대상): {chosen.get('지원대상', '공고문 확인')}\n"
            f"- 선정기준: {chosen.get('선정기준', '지원대상 요건 충족 시 선정 (세부사항 공고문 참조)')}\n"
            f"- 지원내용(혜택 상세): {chosen.get('지원내용', '정보 없음')}\n"
            f"- 신청방법: {chosen.get('신청방법', '정부24 온라인 신청 또는 관할 주민센터 방문 신청')}\n"
            f"- 신청기한: {chosen.get('신청기한', '예산 소진 시 또는 별도 공고 기간까지')}\n"
            f"- 접수기관명: {chosen.get('접수기관명', '관할 행정복지센터 및 정부24')}\n"
            f"- 문의처: {chosen.get('문의처', '정부민원안내콜센터(110)')}\n"
            f"- 정부24 공식 상세안내 링크: {detail_url}"
        )
        return fact_sheet, service_name, detail_url
    except Exception as e:
        print(f"공공데이터 API 호출 에러: {e}")
        return None, None, None

def fetch_from_korea_kr_official():
    rss_url = clean_url(SCHEME + "www.korea.kr/rss/policy.xml")
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
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
    prompt = (
        "너는 '퇴근길 지원금 줍줍' 블로그를 운영하는 깔끔하고 경쾌한 스타일의 전문 에디터야.\n"
        "아래 [정부 공식 데이터]를 바탕으로, 독자가 퇴근길 스마트폰 화면으로 빠르게 읽고 핵심을 바로 챙길 수 있도록 "
        "공백 제외 1,500자~2,200자 수준의 알차고 경쾌한 해설 글을 작성해줘.\n"
        "원본 데이터의 금액, 조건, 날짜, 전화번호 등 팩트 수치는 절대 왜곡하거나 지어내지 마.\n\n"
        f"[정부 공식 데이터]\n{source_facts}\n\n"
        "[문체 및 톤앤매너 지침]\n"
        "- 깔끔하고 경쾌한 톤: 무겁고 딱딱한 말투나 장황한 설명은 빼고, 친절하고 산뜻한 톤(~해요!, ~챙겨보세요!, ~정리해 드릴게요.)으로 리듬감 있게 작성할 것.\n"
        "- 모바일 가독성 최적화: 한 문단은 2~3문장 이내로 짧고 간결하게 끊어 읽기 편하게 구성할 것.\n"
        "- 별도 첫인사/끝인사 생략: 시스템이 글 맨 위와 맨 아래에 고정 인삿말과 맺음말을 자동으로 붙일 예정이니, 초안에서는 인삿말 없이 곧바로 이 지원금이 왜 매력적인지 경쾌한 배경 설명으로 시작할 것.\n\n"
        "[필수 포함 섹션]\n"
        "1. 경쾌한 오프닝 (약 250자): 이 지원금이 어떤 분들에게 단비 같은 소식인지 핵심 매력을 콕 짚어주며 기분 좋게 시작.\n"
        "2. 바쁜 분들을 위한 1분 핵심 요약: [지원대상 / 지원내용 / 신청기한 / 신청방법 / 문의처] 5가지 핵심 정리.\n"
        "3. 누가 받을 수 있나요? (지원대상 & 선정기준): 조건을 보기 쉽게 쪼개서 설명하고, 헷갈리기 쉬운 포인트 짚어주기.\n"
        "4. 어떤 혜택을 받나요? (지원내용 & 체감 혜택): 실제로 받을 수 있는 금액이나 서비스가 일상에 어떤 보탬이 되는지 구체적으로 설명.\n"
        "5. 어떻게 신청하나요? (단계별 신청 가이드): 온라인/오프라인 신청 절차를 Step 1, Step 2, Step 3로 깔끔하게 안내.\n"
        "6. 헛걸음 방지 체크리스트 3가지: 서류 준비, 기한 확인 등 놓치기 쉬운 실수 방지 꿀팁.\n"
        "7. 자주 묻는 질문 Q&A (3가지): 독자들이 가장 궁금해할 질문과 명쾌한 답변."
    )
    return call_gemini(prompt, temperature=0.25)

def step2_proofread_and_humanize(source_facts, draft_text):
    prompt = (
        "너는 모바일 가독성과 깔끔한 편집을 책임지는 블로그 편집장이야.\n"
        "아래 [1차 초안]을 [정부 공식 데이터]와 대조해 팩트를 검증하고, 스마트폰 화면에서 빠르게 읽고 넘기기 좋은 "
        "깔끔하고 경쾌한 HTML 포스팅으로 완성해줘.\n\n"
        f"[정부 공식 데이터]\n{source_facts}\n\n"
        f"[1차 초안]\n{draft_text}\n\n"
        "[필수 편집 및 HTML 디자인 지침]\n"
        "1. 깔끔하고 경쾌한 호흡 유지: 문장이 늘어지지 않도록 산뜻하고 명쾌하게 다듬되, 본문 분량(1,500자~2,200자)은 충실하게 유지할 것.\n"
        "2. 고정 인삿말/맺음말 중복 방지: 시스템에서 첫인삿말과 맺음말을 상하단에 자동 삽입하므로, 본문 내에서는 중복 인사를 빼고 바로 본론 배경부터 시작해 FAQ로 깔끔하게 마칠 것.\n"
        "3. AI 상투어 금지: 결론적으로, 요약하자면, 지금까지 알아보았습니다 같은 기계적 표현 절대 금지.\n"
        "4. 모바일 친화적 HTML 스타일 (샵 기호나 별표 같은 마크다운 기호는 절대 쓰지 말 것):\n"
        '   - 대소제목: <h2 style="border-left: 6px solid #2563eb; background-color: #f8fafc; padding: 12px 16px; color: #0f172a; margin-top: 38px; margin-bottom: 18px; font-size: 22px; line-height: 1.4; font-weight: 800;">소제목</h2>\n'
        '   - 소소제목: <h3 style="color: #1e3a8a; margin-top: 26px; margin-bottom: 12px; font-size: 19.5px; line-height: 1.5; font-weight: 700;">소제목</h3>\n'
        '   - 일반 문단: <p style="line-height: 1.9; font-size: 18.5px; color: #1e293b; margin-bottom: 20px; word-break: keep-all;">문단 내용</p>\n'
        '   - 목록(리스트): <ul> 또는 <ol> 안의 각 항목은 <li style="line-height: 1.9; font-size: 18.5px; color: #1e293b; margin-bottom: 12px; word-break: keep-all;">항목 내용</li> 적용.\n'
        '   - 핵심 강조 단어: <b style="background-color: #fef08a; padding: 2px 6px; border-radius: 4px; color: #0f172a;">강조 내용</b>\n'
        "5. 한눈에 보는 핵심 요약 표(<table>) 필수 포함:\n"
        "   - 오프닝 문단 다음에 인라인 CSS 표로 신청대상, 지원내용, 신청기한, 신청방법, 문의처를 깔끔하게 정리할 것.\n"
        '   - 표 태그: <table style="width:100%; border-collapse:collapse; margin:24px 0; font-size:17px; line-height:1.65;">\n'
        '   - th 스타일: style="background-color:#f1f5f9; padding:12px 10px; border:1px solid #cbd5e1; width:28%; text-align:left; font-size:17px; color:#0f172a; font-weight:700;"\n'
        '   - td 스타일: style="padding:12px 10px; border:1px solid #cbd5e1; font-size:17px; color:#1e293b;"\n'
        "6. 이미지 삽입 위치 마커 배치:\n"
        "   - 오프닝 문단이 끝난 직후에 [IMAGE_SLOT_1] 을 한 줄 단독으로 넣을 것.\n"
        "   - 신청방법 안내 섹션 시작 직전에 [IMAGE_SLOT_2] 를 한 줄 단독으로 넣을 것.\n"
        "7. 출력 형식:\n"
        "   - 첫 번째 줄에는 HTML 태그 없이 클릭하고 싶어지는 경쾌한 블로그 제목만 한 줄로 출력할 것.\n"
        "   - 두 번째 줄부터 곧바로 본문 HTML 코드를 출력할 것."
    )
    return call_gemini(prompt, temperature=0.35)

def step3_finalize_post(text, service_title, official_facts_text, detail_url):
    backtick_fence = chr(96) * 3
    text = re.sub(backtick_fence + r"[a-zA-Z]*", "", text)
    text = text.replace(backtick_fence, "").replace("**", "")
    banned_phrases = ["결론적으로", "요약하자면", "도움이 되셨기를 바랍니다", "도움이 되셨길 바랍니다", "지금까지 알아보았습니다"]
    for phrase in banned_phrases:
        text = text.replace(phrase, "")
    text = text.strip()

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return None, None

    post_title = re.sub(r"<[^>]+>", "", lines[0]).strip()
    post_body = "\n".join(lines[1:])

    matched_images = select_and_verify_images(service_title, post_title, official_facts_text, post_body)
    img1_html = make_image_html(matched_images[0])
    img2_html = make_image_html(matched_images[1])

    if "[IMAGE_SLOT_1]" in post_body:
        post_body = post_body.replace("[IMAGE_SLOT_1]", img1_html)
    else:
        post_body = img1_html + "\n" + post_body

    if "[IMAGE_SLOT_2]" in post_body:
        post_body = post_body.replace("[IMAGE_SLOT_2]", img2_html)
    else:
        post_body = post_body + "\n" + img2_html

    responsive_style_html = (
        "<style>"
        ".afterwork-container { font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important; font-size: 18.5px !important; line-height: 1.9 !important; color: #1e293b !important; letter-spacing: -0.2px !important; word-break: keep-all !important; overflow-wrap: break-word !important; }"
        ".afterwork-container p, .afterwork-container li, .afterwork-container div, .afterwork-container span { font-size: 18.5px !important; line-height: 1.9 !important; }"
        ".afterwork-container p { margin-bottom: 20px !important; }"
        ".afterwork-container ul, .afterwork-container ol { margin: 18px 0 24px 0 !important; padding-left: 22px !important; }"
        ".afterwork-container li { margin-bottom: 12px !important; }"
        ".afterwork-container h2 { font-size: 22.5px !important; line-height: 1.4 !important; font-weight: 800 !important; color: #0f172a !important; border-left: 6px solid #2563eb !important; background-color: #f8fafc !important; padding: 12px 16px !important; margin-top: 38px !important; margin-bottom: 18px !important; border-radius: 0 8px 8px 0 !important; }"
        ".afterwork-container h3 { font-size: 19.5px !important; line-height: 1.5 !important; font-weight: 700 !important; color: #1e3a8a !important; margin-top: 28px !important; margin-bottom: 12px !important; }"
        ".afterwork-container table { width: 100% !important; border-collapse: collapse !important; margin: 24px 0 !important; }"
        ".afterwork-container th, .afterwork-container td { font-size: 17px !important; line-height: 1.65 !important; padding: 12px 10px !important; border: 1px solid #cbd5e1 !important; }"
        ".afterwork-container th { background-color: #f1f5f9 !important; font-weight: 700 !important; color: #0f172a !important; width: 28% !important; }"
        "@media screen and (max-width: 768px) {"
        ".afterwork-container, .afterwork-container p, .afterwork-container li { font-size: 18.5px !important; line-height: 1.9 !important; }"
        ".afterwork-container h2 { font-size: 21px !important; padding: 11px 14px !important; margin-top: 34px !important; }"
        ".afterwork-container h3 { font-size: 19px !important; }"
        ".afterwork-container th, .afterwork-container td { font-size: 16.5px !important; padding: 10px 8px !important; }"
        ".afterwork-container th { width: 32% !important; }"
        "}"
        "</style>"
    )

    intro_box_html = (
        '<div style="margin-bottom: 28px; padding: 20px 22px; background-color: #eff6ff; border-left: 5px solid #3b82f6; border-radius: 0 12px 12px 0;">'
        '<p style="margin: 0 !important; font-size: 18.5px !important; line-height: 1.85 !important; color: #1e3a8a !important; font-weight: 600;">'
        f'👋 {FIXED_INTRO_TEXT}'
        '</p></div>'
    )

    safe_detail_url = clean_url(detail_url)
    footer_html = (
        '<div style="margin-top: 40px; padding: 24px 20px; background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 14px;">'
        '<h3 style="margin-top: 0 !important; color: #0f172a !important; font-size: 20px !important;">📌 공식 공고문 확인 및 온라인 신청 바로가기</h3>'
        '<p style="font-size: 17.5px !important; color: #334155 !important; line-height: 1.8 !important; margin-bottom: 22px !important;">'
        '지자체별 예산 소진 현황이나 세부 구비서류는 신청 시점에 따라 달라질 수 있어요. 아래 정부24 공식 안내 페이지에서 가장 정확한 최신 공고문을 확인하시고 혜택을 챙겨보세요!'
        '</p>'
        '<div style="text-align: center; margin: 24px 0;">'
        f'<a href="{safe_detail_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; font-weight: 800; padding: 15px 28px; border-radius: 10px; text-decoration: none; font-size: 18px !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);">'
        '👉 정부24 공식 상세안내 및 신청 페이지 이동'
        '</a></div>'
        '<div style="margin-top: 26px; padding: 18px 20px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;">'
        '<p style="margin: 0 !important; font-size: 18px !important; line-height: 1.85 !important; color: #0f172a !important;">'
        f'✨ {FIXED_OUTRO_TEXT}'
        '</p></div>'
        '<hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;" />'
        '<p style="font-size: 14.5px !important; color: #64748b !important; margin: 0 !important; line-height: 1.7 !important;">'
        '<b>[자료 및 실제 사진 출처 안내]</b><br />'
        '• 정책 데이터 출처: 행정안전부 보조금24 / 공공데이터포털(data.go.kr) 및 정부24(gov.kr) 공식 오픈 API (공공누리 제1유형 준수)<br />'
        '• 본문 사진 출처: Unsplash 실제 촬영 사진 무료 라이선스 제공 (각 사진 하단 촬영자 표기)'
        '</p></div>'
    )

    full_html = f"{responsive_style_html}\n<div class=\"afterwork-container\">\n{intro_box_html}\n{post_body}\n{footer_html}\n</div>"
    return post_title, full_html

def publish_to_blogger(title, body_html):
    print(f"🚀 [afterwork-pick] 블로그(ID: {blogger_id})에 '[혜택] 숨은 지원금' 라벨 부착 포스팅 발행 시작...")
    
    if not all([client_id, client_secret, blogger_id, refresh_token]):
        print("❌ 필수 인증 키 또는 블로그 ID가 누락되었습니다.")
        return False

    try:
        oauth_token_url = clean_url(SCHEME + "oauth2.googleapis.com/token")
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=oauth_token_url,
            client_id=client_id,
            client_secret=client_secret
        )
        service = build('blogger', 'v3', credentials=credentials, static_discovery=False)
        
        post_data = {
            'title': title,
            'content': body_html,
            'labels': ['[혜택] 숨은 지원금']
        }
        
        request = service.posts().insert(blogId=blogger_id, body=post_data, isDraft=False)
        response = request.execute()
        print(f"🎉 [afterwork-pick] 블로그 발행 완료! 글 URL: {response.get('url')}")
        return True
    except Exception as e:
        print(f"❌ 블로그 API 발행 실패: {e}")
        return False

if __name__ == "__main__":
    print("📡 [1단계] 기존 발행 기록을 확인하고 중복 없는 공식 데이터를 수집합니다...")
    history = load_history()
    
    official_facts, service_title, detail_url = fetch_from_data_go_kr(history)
    if not official_facts:
        official_facts, service_title, detail_url = fetch_from_korea_kr_official()
        
    if not official_facts:
        print("❌ 오늘 올릴 새로운 공식 데이터를 불러오지 못해 중단합니다.")
        exit(1)

    print(f"✅ 이번에 발행할 정책: {service_title}")
    print("✍️ [2단계] 깔끔하고 경쾌한 초안 작성 및 모바일 최적화 HTML 편집을 진행합니다...")
    draft = step1_generate_draft(official_facts)
    
    if draft:
        polished = step2_proofread_and_humanize(official_facts, draft)
        post_title, post_body = step3_finalize_post(
            polished if polished else draft,
            service_title,
            official_facts,
            detail_url
        )
        
        if post_title and post_body:
            pure_text_len = len(re.sub(r"<[^>]+>", "", post_body))
            print("\n" + "="*50)
            print(f"✨ [발행 예정 제목]: {post_title}")
            print(f"📏 [순수 본문 글자수]: 공백 포함 약 {pure_text_len}자 (HTML/CSS 제외)")
            print(f"🏷️ [부착될 라벨]: [혜택] 숨은 지원금")
            print("="*50 + "\n")
            
            is_success = publish_to_blogger(post_title, post_body)
            if is_success and service_title:
                save_history(service_title)
                print(f"💾 발행 내역 저장 완료 ({service_title})")
        else:
            print("❌ 생성된 본문이 없습니다.")
