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

if not gemini_api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

# 2. 카테고리별 고화질 맞춤 이미지 및 공식 출처 DB
THEME_IMAGES = {
    "육아_출산": [
        {
            "url": "https://images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=1000&q=80",
            "alt": "아이와 함께하는 가정 지원 혜택 이미지",
            "credit": "출처: Unsplash (@dakotacorbin) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1542037104857-ffbb0b9155fb?auto=format&fit=crop&w=1000&q=80",
            "alt": "행복한 가족과 육아 지원 정책 사진",
            "credit": "출처: Unsplash (@natalie_pedigo) / 무료 라이선스 제공"
        }
    ],
    "청년_취업": [
        {
            "url": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1000&q=80",
            "alt": "청년 취업 및 직장인 역량 강화 지원 이미지",
            "credit": "출처: Unsplash (@brookecagle) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=1000&q=80",
            "alt": "노트북으로 지원금을 신청하는 모습",
            "credit": "출처: Unsplash (@andrewtneel) / 무료 라이선스 제공"
        }
    ],
    "주거_생활": [
        {
            "url": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=1000&q=80",
            "alt": "내 집 마련 및 주거 안정 지원금 관련 이미지",
            "credit": "출처: Unsplash (@tierramallorca) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1000&q=80",
            "alt": "가계 재정 및 주거비 계산 이미지",
            "credit": "출처: Unsplash (@kellysikkema) / 무료 라이선스 제공"
        }
    ],
    "의료_건강": [
        {
            "url": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1000&q=80",
            "alt": "건강검진 및 의료비 지원 혜택 이미지",
            "credit": "출처: Unsplash (@hush52) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1000&q=80",
            "alt": "의료 상담 및 보건 복지 서비스 이미지",
            "credit": "출처: Unsplash (@nationalcancerinstitute) / 무료 라이선스 제공"
        }
    ],
    "소상공인_기업": [
        {
            "url": "https://images.unsplash.com/photo-1556740758-90de374c12ad?auto=format&fit=crop&w=1000&q=80",
            "alt": "소상공인 및 중소기업 경영 지원금 이미지",
            "credit": "출처: Unsplash (@blakewisz) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1000&q=80",
            "alt": "사업 계획서 작성 및 정부 지원 신청 이미지",
            "credit": "출처: Unsplash (@homajob) / 무료 라이선스 제공"
        }
    ],
    "농어업_지역": [
        {
            "url": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=1000&q=80",
            "alt": "농어촌 및 지역 발전 정부 지원 정책 이미지",
            "credit": "출처: Unsplash (@goian) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=1000&q=80",
            "alt": "친환경 농어업 지원 혜택 관련 사진",
            "credit": "출처: Unsplash (@sippakorn) / 무료 라이선스 제공"
        }
    ],
    "일반_금융": [
        {
            "url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1000&q=80",
            "alt": "정부 지원금 및 생활 안정 자금 신청 이미지",
            "credit": "출처: Unsplash (@towfiqu999999) / 무료 라이선스 제공"
        },
        {
            "url": "https://images.unsplash.com/photo-1434626881859-194d67b2b86f?auto=format&fit=crop&w=1000&q=80",
            "alt": "온라인 서류 준비 및 신청 방법 안내 이미지",
            "credit": "출처: Unsplash (@firmbee) / 무료 라이선스 제공"
        }
    ]
}

def select_matching_images(text):
    if any(k in text for k in ["출산", "육아", "아동", "보육", "임신", "양육", "어린이", "유아", "첫만남"]):
        return THEME_IMAGES["육아_출산"]
    elif any(k in text for k in ["청년", "취업", "구직", "장학", "대학생", "일자리", "창업"]):
        return THEME_IMAGES["청년_취업"]
    elif any(k in text for k in ["주거", "전세", "월세", "주택", "임대", "이사", "보증금"]):
        return THEME_IMAGES["주거_생활"]
    elif any(k in text for k in ["의료", "건강", "치료", "병원", "검진", "진료", "장애", "돌봄", "요양"]):
        return THEME_IMAGES["의료_건강"]
    elif any(k in text for k in ["소상공인", "자영업", "중소기업", "사업자", "매출", "점포"]):
        return THEME_IMAGES["소상공인_기업"]
    elif any(k in text for k in ["농업", "어업", "농가", "어가", "어선", "양식", "축산", "임업", "귀농"]):
        return THEME_IMAGES["농어업_지역"]
    else:
        return THEME_IMAGES["일반_금융"]

def make_image_html(img_info):
    return f"""
<figure style="margin: 32px 0; text-align: center;">
  <img src="{img_info['url']}" alt="{img_info['alt']}" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />
  <figcaption style="margin-top: 10px; font-size: 15px !important; line-height: 1.5 !important; color: #475569 !important;">
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
        url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage=20&serviceKey={encoded_key}"
        
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
        detail_url = chosen.get('상세조회URL', 'https://www.gov.kr')
        
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
    url = "https://www.korea.kr/rss/policy.xml"
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
        link = chosen.find('link').text if chosen.find('link') is not None else "https://www.korea.kr"
        
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
    너는 정부 지원금 및 정책 분석 전문 칼럼니스트이자 파워 블로거야.
    아래 [정부 공식 데이터]를 바탕으로 독자가 블로그에 4~5분 이상 머물며 정독할 수 있도록 **공백 제외 최소 1,800자~2,500자 이상**의 깊이 있고 알찬 해설 글을 작성해줘.
    단순히 항목만 나열하면 절대 안 되며, 독자가 왜 이 혜택을 챙겨야 하는지, 실제 신청할 때 어떤 점을 주의해야 하는지 친절하고 상세하게 풀어서 설명해야 해.
    단, 원본 데이터에 있는 금액, 날짜, 전화번호 등 팩트 수치는 절대 왜곡하거나 지어내지 마.

    [정부 공식 데이터]
    {source_facts}

    [필수 포함 섹션 및 작성 가이드]
    1. 도입부 (최소 300자): 바쁜 일상 속에서 이런 지원금을 몰라서 놓치는 안타까운 현실을 짚어주고, 이 정책이 왜 실질적인 도움이 되는지 흥미로운 스토리텔링으로 시작할 것.
    2. 핵심 요약 정리: 바쁜 독자들을 위해 [지원대상 / 지원내용 / 신청기한 / 신청방법 / 문의처] 5가지 핵심 정보를 한눈에 볼 수 있게 정리할 것.
    3. 신청대상 및 선정기준 심층 분석 (최소 400자): 누가 받을 수 있는지 조건을 하나하나 쪼개서 쉽게 설명하고, 본인이 대상자인지 헷갈릴 때 확인하는 팁을 덧붙일 것.
    4. 지원내용 및 기대 효과 (최소 350자): 구체적으로 어떤 혜택을 받는지, 이를 통해 가계나 생활에 어떤 실질적 보탬이 되는지 체감할 수 있게 설명할 것.
    5. 신청기한 및 단계별 신청방법 완벽 가이드 (최소 450자): 신청기한을 강조하고, 온라인(정부24 등) 신청과 오프라인(주민센터/접수기관 방문) 신청 절차를 Step 1, Step 2, Step 3 순서로 초보자도 바로 따라 할 수 있게 안내할 것.
    6. 헛걸음 방지 필수 체크리스트 & 주의사항 (최소 300자): 서류 누락, 마감 기한 임박, 대리 신청 여부 등 실제 신청 시 자주 겪는 실수와 꿀팁 3가지를 정리할 것.
    7. 자주 묻는 질문 BEST 3 (FAQ): 독자들이 가장 궁금해할 만한 질문 3가지(Q1~Q3)와 명쾌한 답변(A1~A3)을 문답 형식으로 작성할 것.
    """
    return call_gemini(prompt, temperature=0.25)

def step2_proofread_and_humanize(source_facts, draft_text):
    prompt = f"""
    너는 대한민국 상위 1% 블로그 편집장이야.
    아래 [1차 초안]을 [정부 공식 데이터]와 대조해 팩트를 검증하고, 독자가 모바일과 PC에서 4~5분 동안 눈이 편안하게 읽을 수 있는 **고품격 HTML 블로그 포스팅(최소 1,800자~2,500자 이상 유지)**으로 완성해줘.
    절대로 내용을 요약하거나 줄이지 말고, 1차 초안의 풍부한 분량과 디테일을 100% 살려야 해!

    [정부 공식 데이터]
    {source_facts}

    [1차 초안]
    {draft_text}

    [🛠️ 필수 편집 및 HTML 디자인 지침 (모바일 가독성 최우선)]
    1. **분량 유지 필수**: 본문 글자 수가 최소 1,800자 이상 되도록 각 문단을 풍부하고 깊이 있게 서술할 것.
    2. **자연스러운 인간 문체**: '결론적으로', '요약하자면', '지금까지 알아보았습니다' 같은 AI 상투어는 절대 쓰지 말고, 경험 많은 직장인 선배가 꼼꼼하게 알려주는 생생하고 친근한 문체를 사용할 것.
    3. **모바일에서도 큼직하고 시원한 글자 크기 적용**:
       - 마크다운 기호(`#`, `**`, ```)는 절대 쓰지 말 것.
       - 대소제목: `<h2 style="border-left: 6px solid #2563eb; background-color: #f8fafc; padding: 12px 16px; color: #0f172a; margin-top: 42px; margin-bottom: 20px; font-size: 24px; line-height: 1.4; font-weight: 800;">소제목</h2>`
       - 소소제목: `<h3 style="color: #1e3a8a; margin-top: 30px; margin-bottom: 14px; font-size: 20px; line-height: 1.5; font-weight: 700;">소제목</h3>`
       - 일반 문단: `<p style="line-height: 1.95; font-size: 19px; color: #1e293b; margin-bottom: 24px; word-break: keep-all;">`
       - 목록(리스트): `<ul>` 또는 `<ol>` 안의 각 항목은 `<li style="line-height: 1.95; font-size: 19px; color: #1e293b; margin-bottom: 14px; word-break: keep-all;">` 스타일을 반드시 적용할 것.
       - 핵심 강조 단어: `<b style="background-color: #fef08a; padding: 2px 6px; border-radius: 4px; color: #0f172a;">강조 내용</b>`
    4. **한눈에 보는 핵심 요약 표(`<table>`) 필수 포함**:
       - 도입부 다음에 아래와 같은 큼직한 인라인 CSS 표로 **신청대상, 지원내용, 신청기한, 신청방법, 문의처**를 정리할 것:
       `<table style="width:100%; border-collapse:collapse; margin:28px 0; font-size:17.5px; line-height:1.7;">`
       (표의 `<th>`는 `background-color:#f1f5f9; padding:14px 12px; border:1px solid #cbd5e1; width:28%; text-align:left; font-size:17.5px; color:#0f172a; font-weight:700;`, `<td>`는 `padding:14px 12px; border:1px solid #cbd5e1; font-size:17.5px; color:#1e293b;` 스타일 적용)
    5. **이미지 삽입 위치 마커 배치**:
       - 도입부 문단이 끝난 직후에 정확히 `[IMAGE_SLOT_1]` 이라는 글자를 한 줄 단독으로 넣을 것.
       - '신청기한 및 단계별 신청방법' 섹션 시작 직전에 정확히 `[IMAGE_SLOT_2]` 라는 글자를 한 줄 단독으로 넣을 것.
    6. **출력 형식**:
       - 첫 번째 줄에는 HTML 태그 없이 클릭을 유도하는 매력적인 **'블로그 제목'**만 한 줄로 출력할 것.
       - 두 번째 줄부터 곧바로 본문 HTML 코드를 출력할 것.
    """
    return call_gemini(prompt, temperature=0.35)

def step3_finalize_post(text, official_Facts_text, detail_url):
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = text.replace("```", "").replace("**", "")
    banned_phrases = ["결론적으로", "요약하자면", "도움이 되셨기를 바랍니다", "도움이 되셨길 바랍니다", "지금까지 알아보았습니다"]
    for phrase in banned_phrases:
        text = text.replace(phrase, "")
    text = text.strip()

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return None, None

    post_title = re.sub(r"<[^>]+>", "", lines[0]).strip()
    post_body = "\n".join(lines[1:])

    matched_images = select_matching_images(official_Facts_text + " " + post_title)
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

    responsive_style_html = """
<style>
  .afterwork-container {
    font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif !important;
    font-size: 18.5px !important;
    line-height: 1.95 !important;
    color: #1e293b !important;
    letter-spacing: -0.2px !important;
    word-break: keep-all !important;
    overflow-wrap: break-word !important;
  }
  .afterwork-container p,
  .afterwork-container li,
  .afterwork-container div,
  .afterwork-container span {
    font-size: 18.5px !important;
    line-height: 1.95 !important;
  }
  .afterwork-container p {
    margin-bottom: 24px !important;
  }
  .afterwork-container ul,
  .afterwork-container ol {
    margin: 20px 0 28px 0 !important;
    padding-left: 24px !important;
  }
  .afterwork-container li {
    margin-bottom: 14px !important;
  }
  .afterwork-container h2 {
    font-size: 24px !important;
    line-height: 1.45 !important;
    font-weight: 800 !important;
    color: #0f172a !important;
    border-left: 6px solid #2563eb !important;
    background-color: #f8fafc !important;
    padding: 14px 16px !important;
    margin-top: 44px !important;
    margin-bottom: 22px !important;
    border-radius: 0 8px 8px 0 !important;
  }
  .afterwork-container h3 {
    font-size: 20.5px !important;
    line-height: 1.5 !important;
    font-weight: 700 !important;
    color: #1e3a8a !important;
    margin-top: 32px !important;
    margin-bottom: 14px !important;
  }
  .afterwork-container table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 28px 0 !important;
  }
  .afterwork-container th,
  .afterwork-container td {
    font-size: 17.5px !important;
    line-height: 1.7 !important;
    padding: 14px 12px !important;
    border: 1px solid #cbd5e1 !important;
  }
  .afterwork-container th {
    background-color: #f1f5f9 !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    width: 28% !important;
  }
  @media screen and (max-width: 768px) {
    .afterwork-container,
    .afterwork-container p,
    .afterwork-container li {
      font-size: 19.5px !important;
      line-height: 2.0 !important;
    }
    .afterwork-container h2 {
      font-size: 22.5px !important;
      padding: 12px 14px !important;
      margin-top: 38px !important;
    }
    .afterwork-container h3 {
      font-size: 20px !important;
    }
    .afterwork-container th,
    .afterwork-container td {
      font-size: 17px !important;
      padding: 12px 10px !important;
    }
    .afterwork-container th {
      width: 32% !important;
    }
  }
</style>
""".strip()

    footer_html = f"""
<div style="margin-top: 44px; padding: 26px 22px; background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 14px;">
  <h3 style="margin-top: 0 !important; color: #0f172a !important; font-size: 21px !important;">📌 공식 공고문 확인 및 온라인 신청 바로가기</h3>
  <p style="font-size: 18px !important; color: #334155 !important; line-height: 1.85 !important; margin-bottom: 24px !important;">
    지자체별 예산 소진 현황이나 세부 구비서류는 신청 시점에 따라 업데이트될 수 있습니다. 아래 정부24 공식 안내 페이지를 통해 가장 정확한 최신 공고문을 확인하시고 혜택을 신청해 보세요!
  </p>
  <div style="text-align: center; margin: 28px 0;">
    <a href="{detail_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; font-weight: 800; padding: 16px 30px; border-radius: 10px; text-decoration: none; font-size: 18.5px !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);">
      👉 정부24 공식 상세안내 및 신청 페이지 이동
    </a>
  </div>
  <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 24px 0;" />
  <p style="font-size: 15px !important; color: #475569 !important; margin: 0 !important; line-height: 1.75 !important;">
    <b>[자료 및 이미지 출처 안내]</b><br />
    • 정책 데이터 출처: 행정안전부 보조금24 / 공공데이터포털(data.go.kr) 및 정부24(gov.kr) 공식 오픈 API (공공누리 제1유형 준수)<br />
    • 본문 이미지 출처: Unsplash 무료 상업적 라이선스 제공 (각 이미지 하단 저작자 표기)<br />
    • 오늘도 <b>퇴근길 혜택 픽</b>을 찾아주셔서 감사합니다. 내일도 놓치면 아까운 알짜 지원금 정보로 찾아뵙겠습니다!
  </p>
</div>
""".strip()

    full_html = f"""
{responsive_style_html}
<div class="afterwork-container">
{post_body}
{footer_html}
</div>
""".strip()

    return post_title, full_html

def publish_to_blogger(title, body_html):
    print(f"🚀 [afterwork-pick] 블로그(ID: {blogger_id})에 '[혜택] 숨은 지원금' 라벨 부착 포스팅 발행 시작...")
    
    if not all([client_id, client_secret, blogger_id, refresh_token]):
        print("❌ 필수 인증 키 또는 블로그 ID가 누락되었습니다.")
        return False

    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)",  # 👈 마크다운 기호 제거 완료!
            client_id=client_id,
            client_secret=client_secret
        )
        service = build('blogger', 'v3', credentials=credentials)
        
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
    print("✍️ [2단계] 심층 칼럼 초안 작성 및 모바일 최적화 HTML 교정을 진행합니다...")
    draft = step1_generate_draft(official_facts)
    
    if draft:
        polished = step2_proofread_and_humanize(official_facts, draft)
        post_title, post_body = step3_finalize_post(
            polished if polished else draft,
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
