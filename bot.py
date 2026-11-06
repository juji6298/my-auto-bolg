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

# 3. 실시간 사진 검색 및 AI 문맥 일치 검수 시스템 (DB 미사용, 실시간 웹 검색)
def fetch_wikimedia_real_photos(query, limit=8):
    """위키미디어 공용 API를 통해 실시간으로 실제 사진(JPG/PNG)을 검색"""
    api_base = clean_url(SCHEME + "commons.wikimedia.org/w/api.php")
    # 비트맵(실제 사진)만 검색하고 AI/일러스트/아이콘 배제
    search_query = f"{query} filetype:bitmap -ai -illustration -vector -icon -logo -diagram -map"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search_query,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|dimensions|mime",
        "iiurlwidth": "1000",
        "format": "json"
    }
    url = api_base + "?" + urllib.parse.urlencode(params)
    results = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AfterworkPickBot/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            info_list = page_data.get("imageinfo", [])
            if not info_list:
                continue
            info = info_list[0]
            mime = info.get("mime", "")
            width = info.get("width", 0)
            height = info.get("height", 0)
            # 가로형 고화질 실제 사진(jpeg/png)만 필터링
            if mime not in ["image/jpeg", "image/png"] or width < 600 or width < height:
                continue
            img_url = clean_url(info.get("thumburl") or info.get("url", ""))
            if not img_url:
                continue
            ext = info.get("extmetadata", {})
            artist_raw = ext.get("Artist", {}).get("value", "Wikimedia Commons")
            artist = re.sub(r"<[^>]+>", "", artist_raw).strip()
            if len(artist) > 35:
                artist = "Wikimedia Commons"
            desc_raw = ext.get("ImageDescription", {}).get("value", "") or ext.get("ObjectName", {}).get("value", "")
            desc = re.sub(r"<[^>]+>", "", desc_raw).strip()[:120]
            title_clean = page_data.get("title", "").replace("File:", "")

            # AI 생성물이나 그래픽 관련 단어가 제목/설명에 있으면 철저히 제외
            check_str = (title_clean + " " + desc).lower()
            if any(bad in check_str for bad in ["ai generated", "midjourney", "stable diffusion", "dall-e", "illustration", "cartoon", "clipart", "icon", "logo", "vector", "coat of arms", "flag", "signature"]):
                continue

            results.append({
                "url": img_url,
                "title": title_clean,
                "desc": desc,
                "credit": f"출처: Wikimedia Commons ({artist})"
            })
    except Exception as e:
        print(f"실시간 사진 검색 중 에러 ({query}): {e}")
    return results

def search_and_verify_real_photos(service_title, post_title, official_facts):
    """
    1단계: 제미나이가 지원금 내용에 딱 맞는 실시간 사진 검색어 3개 생성
    2단계: 실시간 이미지 검색 API로 실제 사진 후보군 수집
    3단계: 제미나이가 후보 사진들의 정보를 읽고 문맥과 가장 잘 일치하는 실제 사진 2장 최종 선정
    """
    kw_prompt = (
        "아래 정부 지원금 내용과 문맥에 딱 맞는 실제 촬영 사진(Real Photo)을 해외/국내 오픈 포토 서버에서 실시간 검색하려고 해.\n"
        "AI 일러스트가 아닌 '실제 현실 사진'이 잘 검색되도록, 지원금의 핵심 대상이나 상황을 묘사하는 구체적인 영어 검색어 3개와 한국어 검색어 1개를 쉼표(,)로 구분해서 출력해줘.\n"
        "예시(육아): baby family mother, kindergarten child, Happy family with baby, 육아 가족\n"
        "예시(어업/양식): fishing boat sea, aquaculture fish farm, fisherman port, 어촌 어선\n"
        "예시(청년/직장): young office worker laptop, business meeting, job interview, 직장인 사무실\n\n"
        f"[정책명]: {service_title}\n"
        f"[블로그 제목]: {post_title}\n"
        f"[정책 요약]: {official_facts[:400]}\n\n"
        "설명 없이 검색어 4개만 쉼표로 구분해서 한 줄로 출력해."
    )
    kw_resp = call_gemini(kw_prompt, temperature=0.2)
    queries = []
    if kw_resp:
        queries = [q.strip() for q in kw_resp.split(",") if q.strip()]
    queries.extend(["South Korea daily life", "business office laptop"])

    candidates = []
    seen_urls = set()
    for q in queries[:5]:
        fetched = fetch_wikimedia_real_photos(q, limit=8)
        for item in fetched:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                candidates.append(item)
        if len(candidates) >= 12:
            break

    # 만약 특수 키워드로 사진이 부족하면 일상/오피스 실제 사진 추가 확보
    if len(candidates) < 2:
        for fallback_q in ["Seoul city people", "office desk notebook", "family lifestyle"]:
            for item in fetch_wikimedia_real_photos(fallback_q, limit=5):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    candidates.append(item)

    if len(candidates) <= 2:
        return candidates

    # 3단계: 후보 사진들 중 블로그 글 문맥과 가장 잘 맞고 실제 사진이 확실한 2장을 AI가 엄격히 심사
    cand_list_text = "\n".join(
        [f"{idx}. 파일명: {c['title']} | 설명: {c['desc']}" for idx, c in enumerate(candidates)]
    )
    verify_prompt = (
        "아래는 실시간으로 검색된 실제 사진 후보 목록이야.\n"
        "오늘 작성할 지원금 블로그 글의 문맥과 가장 자연스럽게 어울리는 실제 사진 2개의 번호를 골라줘.\n"
        "- 글의 주제와 동떨어진 사진, 인물 초상화(동상/옛날 흑백사진), 문서 스캔본, 로고는 절대 고르지 마.\n"
        "- 반드시 현재 지원금 내용과 가장 잘 들어맞는 생생한 실제 촬영 사진 2개를 골라야 해.\n\n"
        f"[지원금 정책명]: {service_title}\n"
        f"[블로그 제목]: {post_title}\n"
        f"[지원금 내용 요약]: {official_facts[:300]}\n\n"
        "[실시간 검색된 사진 후보 목록]\n"
        f"{cand_list_text}\n\n"
        "가장 문맥에 잘 맞는 사진 번호 2개만 쉼표로 구분해서 숫자만 출력해 (예: 0, 2)"
    )
    pick_resp = call_gemini(verify_prompt, temperature=0.0)
    chosen_photos = []
    if pick_resp:
        nums = re.findall(r"\d+", pick_resp)
        for n_str in nums:
            idx = int(n_str)
            if 0 <= idx < len(candidates) and candidates[idx] not in chosen_photos:
                chosen_photos.append(candidates[idx])
            if len(chosen_photos) == 2:
                break

    for c in candidates:
        if len(chosen_photos) >= 2:
            break
        if c not in chosen_photos:
            chosen_photos.append(c)

    print(f"🖼️ [실시간 사진 검색 및 문맥 검수 완료] 선정된 사진: {[p['title'] for p in chosen_photos[:2]]}")
    return chosen_photos[:2]

def make_image_html(img_info):
    """사진 설명은 완전히 제거하고 오직 출처만 깔끔하게 표시"""
    safe_url = clean_url(img_info["url"])
    return (
        '<figure style="margin: 24px 0; text-align: center;">'
        f'<img src="{safe_url}" alt="지원금 안내 참고 이미지" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />'
        '<figcaption style="margin-top: 6px; font-size: 13px !important; line-height: 1.4 !important; color: #94a3b8 !important;">'
        f'{img_info["credit"]}'
        '</figcaption></figure>'
    )

# 4. 정부 공식 데이터 수집
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
            f"- 지원유형: {chosen.get('지원유형', '현금/바우처/서비스 지원')}\n"
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

# 5. 모바일 최적화 경쾌한 글 작성 파이프라인
def step1_generate_draft(source_facts):
    prompt = (
        "너는 모바일 독자들을 위해 핵심만 쏙쏙 뽑아 경쾌하게 전달하는 '퇴근길 지원금 줍줍' 에디터야.\n"
        "독자들이 스마트폰으로 스크롤하며 지루하지 않게 1~2분 만에 후루룩 읽고 끝낼 수 있도록 "
        "공백 제외 1,000자~1,400자 내외로 군더더기 없이 아주 깔끔하고 경쾌하게 작성해줘.\n"
        "원본 데이터의 금액, 조건, 날짜, 전화번호 등 팩트는 절대 왜곡하거나 지어내지 마.\n\n"
        f"[정부 공식 데이터]\n{source_facts}\n\n"
        "[모바일 맞춤형 작성 지침 (매우 중요)]\n"
        "1. 지루함 절대 금지: 길고 빽빽한 설명은 과감히 쳐내고, 한 문단은 무조건 1~2문장으로 짧게 끊어 치고 빠지는 경쾌한 리듬으로 작성할 것.\n"
        "2. 밝고 산뜻한 말투: 친한 직장 동료가 꿀팁을 알려주듯 밝고 경쾌한 어조(~해요!, ~바로 챙겨보세요!, ~딱 정리해 드릴게요!)를 사용할 것.\n"
        "3. 첫인사/끝인사 생략: 상하단에 고정 인삿말과 맺음말이 자동으로 들어가니, 본문에서는 인사 없이 곧바로 '이 혜택, 왜 놓치면 아까울까요?' 같은 흥미로운 한마디로 시작할 것.\n\n"
        "[구성 순서]\n"
        "- 한 줄 훅(Hook) & 배경: 누구에게 왜 필요한 혜택인지 2~3문장으로 경쾌하게 시작\n"
        "- 10초 핵심 요약 표: 지원대상, 지원내용, 신청기한, 신청방법, 문의처\n"
        "- 지원대상 & 조건: 줄글 말고 글머리 기호로 한눈에 들어오게 정리\n"
        "- 지원 혜택 상세: 내가 실제로 받게 되는 혜택을 시원시원하게 정리\n"
        "- 3단계 신청방법: Step 1, Step 2, Step 3로 짧고 명쾌하게 안내\n"
        "- 신청 전 체크포인트 2가지: 헛걸음 막아주는 실전 꿀팁 2개만 짧게\n"
        "- 짧은 Q&A 2개: 가장 궁금해할 핵심 질문 2개와 한 줄 답변"
    )
    return call_gemini(prompt, temperature=0.3)

def step2_proofread_and_humanize(source_facts, draft_text):
    prompt = (
        "너는 모바일 가독성 끝판왕 블로그 편집장이야.\n"
        "아래 [1차 초안]을 [정부 공식 데이터]와 대조해 팩트를 점검하고, 스마트폰 화면에서 눈이 시원하고 술술 읽히는 "
        "경쾌한 HTML 포스팅으로 완성해줘.\n\n"
        f"[정부 공식 데이터]\n{source_facts}\n\n"
        f"[1차 초안]\n{draft_text}\n\n"
        "[필수 편집 및 HTML 스타일 지침]\n"
        "1. 모바일 속도감 최우선: 문단이 길어지면 무조건 나누고, 불릿 리스트(<ul>, <li>)를 적극 사용해 지루할 틈 없이 휙휙 읽히게 만들 것.\n"
        "2. 고정 인삿말/맺음말 중복 방지: 시스템에서 상하단에 인사를 자동 삽입하므로 본문 내에서는 인사말 없이 본론부터 시작해 Q&A로 산뜻하게 끝낼 것.\n"
        "3. AI 상투어 금지: 결론적으로, 요약하자면, 지금까지 알아보았습니다 같은 표현 절대 금지.\n"
        "4. 깔끔한 HTML 태그 적용 (샵이나 별표 같은 마크다운 기호는 절대 쓰지 말 것):\n"
        '   - 대소제목: <h2 style="border-left: 5px solid #2563eb; background-color: #f8fafc; padding: 10px 14px; color: #0f172a; margin-top: 32px; margin-bottom: 14px; font-size: 20px; line-height: 1.4; font-weight: 800;">소제목</h2>\n'
        '   - 소소제목: <h3 style="color: #1e3a8a; margin-top: 22px; margin-bottom: 10px; font-size: 18px; line-height: 1.4; font-weight: 700;">소제목</h3>\n'
        '   - 일반 문단: <p style="line-height: 1.8; font-size: 17.5px; color: #1e293b; margin-bottom: 16px; word-break: keep-all;">문단 내용</p>\n'
        '   - 목록(리스트): <ul> 또는 <ol> 안의 각 항목은 <li style="line-height: 1.8; font-size: 17.5px; color: #1e293b; margin-bottom: 10px; word-break: keep-all;">항목 내용</li> 적용.\n'
        '   - 핵심 강조: <b style="background-color: #fef08a; padding: 1px 5px; border-radius: 4px; color: #0f172a;">강조 단어</b>\n'
        "5. 10초 핵심 요약 표(<table>) 포함:\n"
        '   - 표 태그: <table style="width:100%; border-collapse:collapse; margin:20px 0; font-size:16px; line-height:1.6;">\n'
        '   - th 스타일: style="background-color:#f1f5f9; padding:10px; border:1px solid #cbd5e1; width:28%; text-align:left; font-size:16px; color:#0f172a; font-weight:700;"\n'
        '   - td 스타일: style="padding:10px; border:1px solid #cbd5e1; font-size:16px; color:#1e293b;"\n'
        "6. 이미지 삽입 마커 배치:\n"
        "   - 오프닝 문단 직후에 [IMAGE_SLOT_1] 을 한 줄 단독으로 넣을 것.\n"
        "   - 신청방법 섹션 시작 직전에 [IMAGE_SLOT_2] 를 한 줄 단독으로 넣을 것.\n"
        "7. 출력 형식:\n"
        "   - 첫 번째 줄에는 HTML 태그 없이 호기심을 자극하는 경쾌한 블로그 제목만 한 줄로 출력할 것.\n"
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

    # 실시간 웹 이미지 검색 및 문맥 일치 검수 실행
    matched_images = search_and_verify_real_photos(service_title, post_title, official_facts_text)
    img1_html = make_image_html(matched_images[0]) if len(matched_images) >= 1 else ""
    img2_html = make_image_html(matched_images[1]) if len(matched_images) >= 2 else ""

    if "[IMAGE_SLOT_1]" in post_body:
        post_body = post_body.replace("[IMAGE_SLOT_1]", img1_html)
    elif img1_html:
        post_body = img1_html + "\n" + post_body

    if "[IMAGE_SLOT_2]" in post_body:
        post_body = post_body.replace("[IMAGE_SLOT_2]", img2_html)
    elif img2_html:
        post_body = post_body + "\n" + img2_html

    responsive_style_html = (
        "<style>"
        ".afterwork-container { font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important; font-size: 17.5px !important; line-height: 1.8 !important; color: #1e293b !important; letter-spacing: -0.2px !important; word-break: keep-all !important; overflow-wrap: break-word !important; }"
        ".afterwork-container p, .afterwork-container li, .afterwork-container div, .afterwork-container span { font-size: 17.5px !important; line-height: 1.8 !important; }"
        ".afterwork-container p { margin-bottom: 16px !important; }"
        ".afterwork-container ul, .afterwork-container ol { margin: 14px 0 20px 0 !important; padding-left: 20px !important; }"
        ".afterwork-container li { margin-bottom: 10px !important; }"
        ".afterwork-container h2 { font-size: 20.5px !important; line-height: 1.4 !important; font-weight: 800 !important; color: #0f172a !important; border-left: 5px solid #2563eb !important; background-color: #f8fafc !important; padding: 10px 14px !important; margin-top: 32px !important; margin-bottom: 14px !important; border-radius: 0 8px 8px 0 !important; }"
        ".afterwork-container h3 { font-size: 18px !important; line-height: 1.4 !important; font-weight: 700 !important; color: #1e3a8a !important; margin-top: 24px !important; margin-bottom: 10px !important; }"
        ".afterwork-container table { width: 100% !important; border-collapse: collapse !important; margin: 20px 0 !important; }"
        ".afterwork-container th, .afterwork-container td { font-size: 16px !important; line-height: 1.6 !important; padding: 10px !important; border: 1px solid #cbd5e1 !important; }"
        ".afterwork-container th { background-color: #f1f5f9 !important; font-weight: 700 !important; color: #0f172a !important; width: 28% !important; }"
        "</style>"
    )

    intro_box_html = (
        '<div style="margin-bottom: 24px; padding: 18px 20px; background-color: #eff6ff; border-left: 5px solid #3b82f6; border-radius: 0 12px 12px 0;">'
        '<p style="margin: 0 !important; font-size: 17.5px !important; line-height: 1.75 !important; color: #1e3a8a !important; font-weight: 600;">'
        f'👋 {FIXED_INTRO_TEXT}'
        '</p></div>'
    )

    safe_detail_url = clean_url(detail_url)
    footer_html = (
        '<div style="margin-top: 34px; padding: 22px 18px; background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 14px;">'
        '<h3 style="margin-top: 0 !important; color: #0f172a !important; font-size: 18.5px !important;">📌 공식 공고문 확인 및 신청 바로가기</h3>'
        '<p style="font-size: 16.5px !important; color: #334155 !important; line-height: 1.7 !important; margin-bottom: 18px !important;">'
        '지자체별 예산 현황이나 세부 구비서류는 신청 시점에 따라 달라질 수 있어요. 아래 공식 페이지에서 최신 공고문을 바로 확인해 보세요!'
        '</p>'
        '<div style="text-align: center; margin: 20px 0;">'
        f'<a href="{safe_detail_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; font-weight: 800; padding: 14px 24px; border-radius: 10px; text-decoration: none; font-size: 17px !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);">'
        '👉 정부24 공식 상세안내 및 신청 이동'
        '</a></div>'
        '<div style="margin-top: 22px; padding: 16px 18px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;">'
        '<p style="margin: 0 !important; font-size: 17px !important; line-height: 1.75 !important; color: #0f172a !important;">'
        f'✨ {FIXED_OUTRO_TEXT}'
        '</p></div>'
        '<hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 16px 0;" />'
        '<p style="font-size: 13.5px !important; color: #64748b !important; margin: 0 !important; line-height: 1.6 !important;">'
        '• 정책 데이터 출처: 행정안전부 보조금24 / 공공데이터포털(data.go.kr) 및 정부24(gov.kr)<br />'
        '• 사진 출처: Wikimedia Commons (각 이미지 하단 출처 표기)'
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
    print("✍️ [2단계] 모바일 맞춤형 경쾌한 초안 작성 및 실시간 문맥 일치 사진 검색을 진행합니다...")
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
            print(f"📏 [순수 본문 글자수]: 공백 포함 약 {pure_text_len}자 (모바일 쾌속 독서 분량)")
            print(f"🏷️ [부착될 라벨]: [혜택] 숨은 지원금")
            print("="*50 + "\n")
            
            is_success = publish_to_blogger(post_title, post_body)
            if is_success and service_title:
                save_history(service_title)
                print(f"💾 발행 내역 저장 완료 ({service_title})")
        else:
            print("❌ 생성된 본문이 없습니다.")
