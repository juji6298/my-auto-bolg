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

def load_history():
    """기존에 발행했던 지원금 목록 불러오기"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_history(service_name):
    """새로 발행한 지원금 이름을 기록 파일에 추가"""
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
    """공공데이터 팩트 수집 (중복 검사 포함)"""
    if not public_data_key:
        return None, None
    try:
        encoded_key = urllib.parse.quote(public_data_key) if "%" not in public_data_key else public_data_key
        page = random.randint(1, 15)
        url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage=15&serviceKey={encoded_key}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        items = data.get("data", [])
        if not items:
            return None, None
            
        # 지원내용과 대상이 있으면서, 기존에 발행하지 않은(history_set에 없는) 항목만 필터링
        valid_items = [
            item for item in items 
            if item.get("지원내용") and item.get("지원대상") and item.get("서비스명", "") not in history_set
        ]
        
        if not valid_items:
            print(f"⚠️ {page}페이지의 모든 데이터가 이미 발행되었거나 조건에 맞지 않습니다.")
            return None, None
            
        chosen = random.choice(valid_items)
        service_name = chosen.get('서비스명', '정보 없음')
        
        fact_sheet = f"""
[대한민국 행정안전부 보조금24 공식 데이터]
- 서비스명: {service_name}
- 소관기관명: {chosen.get('소관기관명', '정보 없음')}
- 지원유형: {chosen.get('지원유형', '정보 없음')}
- 서비스목적요약: {chosen.get('서비스목적요약', '정보 없음')}
- 지원대상: {chosen.get('지원대상', '정보 없음')}
- 선정기준: {chosen.get('선정기준', '별도 명시 없음 (공고문 확인 필요)')}
- 지원내용: {chosen.get('지원내용', '정보 없음')}
- 신청방법: {chosen.get('신청방법', '정보 없음')}
- 신청기한: {chosen.get('신청기한', '정보 없음')}
- 문의처: {chosen.get('문의처', '정부24 확인')}
- 정부24 공식 링크: {chosen.get('상세조회URL', 'https://www.gov.kr')}
""".strip()
        return fact_sheet, service_name
    except Exception as e:
        print(f"공공데이터 API 호출 에러: {e}")
        return None, None

def fetch_from_korea_kr_official():
    url = "https://www.korea.kr/rss/policy.xml"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        items = root.findall('./channel/item')[:10]
        if not items:
            return None, None
        chosen = random.choice(items)
        title = chosen.find('title').text if chosen.find('title') is not None else ""
        desc = chosen.find('description').text if chosen.find('description') is not None else ""
        link = chosen.find('link').text if chosen.find('link') is not None else ""
        
        fact = f"[정부 정책브리핑]\n- 제목: {title}\n- 내용: {desc}\n- 링크: {link}"
        return fact, title
    except Exception as e:
        print(f"정책브리핑 수집 에러: {e}")
        return None, None

def call_gemini(prompt, temperature=0.2):
    models = get_working_model_name()
    config = {"temperature": temperature}
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
    아래 [정부 공식 데이터]를 바탕으로 '퇴근길에 3분 만에 읽는 알짜 정부 혜택' 콘셉트의 블로그 글 초안을 작성해줘.
    피곤한 퇴근길 지하철에서 스마트폰으로 슥슥 읽기 편하게 군더더기 없이 친절하고 직관적인 직장인 문체로 써.
    원본에 없는 수치나 자격조건은 절대 지어내지 마.

    [정부 공식 데이터]
    {source_facts}
    """
    return call_gemini(prompt, temperature=0.1)

def step2_proofread_and_humanize(source_facts, draft_text):
    prompt = f"""
    너는 블로그 콘텐츠 에디터이자 AI 텍스트 탐지 회피 전문가야.
    아래 [1차 초안]을 [정부 공식 데이터]와 철저히 대조해 사실관계를 바로잡고, 포털 검색엔진에서 저품질로 분류되지 않도록 자연스러운 사람의 글 형태로 교정해줘.

    [정부 공식 데이터]
    {source_facts}

    [1차 초안]
    {draft_text}

    [필수 규칙]
    1. 팩트 검증: 금액, 지원 자격, 신청 기간이 원본과 다르면 100% 원본 기준으로 수정.
    2. AI 상투어 절대 금지: '결론적으로', '요약하자면', '도움이 되셨기를 바랍니다', '지금까지 알아보았습니다' 등 기계적 어구 모두 삭제.
    3. 리듬감(Burstiness): 짧고 직관적인 문장과 실질적인 팁 문장을 불규칙하게 배치하여 AI 특유의 획일적인 문장 길이를 없앨 것.
    4. HTML 서식 적용: 마크다운(#, **)을 쓰지 말고, 소제목은 <h3>, 강조는 <b>, 문단은 <p>, 줄바꿈은 <br> 태그 사용.
    5. 글 맨 하단에 "오늘도 퇴근길 혜택 픽을 읽어주셔서 감사합니다. 내일도 놓치기 아까운 지원금 소식으로 찾아뵙겠습니다." 형태의 1~2줄 마무리 문장 포함.
    6. 출력 규격: 첫 번째 줄에는 태그 없이 순수 텍스트로만 '블로그 포스팅 제목'을 출력하고, 두 번째 줄부터 본문 HTML을 출력할 것.
    """
    return call_gemini(prompt, temperature=0.35)

def step3_hard_filter(text):
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = text.replace("```", "").replace("**", "")
    banned_phrases = ["결론적으로", "요약하자면", "도움이 되셨기를 바랍니다", "도움이 되셨길 바랍니다", "지금까지 알아보았습니다"]
    for phrase in banned_phrases:
        text = text.replace(phrase, "")
    return text.strip()

def publish_to_blogger(title, body_html):
    print(f"🚀 [afterwork-pick] 블로그(ID: {blogger_id})에 포스팅 발행 시작...")
    
    if not all([client_id, client_secret, blogger_id, refresh_token]):
        print("❌ 필수 인증 키 또는 블로그 ID가 누락되었습니다.")
        return False

    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        service = build('blogger', 'v3', credentials=credentials)
        
        post_data = {
            'title': title,
            'content': body_html
        }
        
        request = service.posts().insert(blogId=blogger_id, body=post_data, isDraft=False)
        response = request.execute()
        print(f"🎉 [afterwork-pick] 블로그 발행 완료! 글 URL: {response.get('url')}")
        return True
    except Exception as e:
        print(f"❌ 블로그 API 발행 실패: {e}")
        return False

if __name__ == "__main__":
    print("📡 [1단계] 기존 발행 기록을 확인하고 중복 없는 데이터를 수집합니다...")
    history = load_history()
    
    official_facts, service_title = fetch_from_data_go_kr(history)
    if not official_facts:
        official_facts, service_title = fetch_from_korea_kr_official()
        
    if not official_facts:
        print("❌ 오늘 올릴 새로운 공식 데이터를 불러오지 못해 중단합니다.")
        exit(1)

    print(f"✅ 이번에 발행할 정책: {service_title}")
    print("✍️ [2단계] '퇴근길 픽' 스타일 초안 및 AI 탐지 회피 교정을 진행합니다...")
    draft = step1_generate_draft(official_facts)
    
    if draft:
        polished = step2_proofread_and_humanize(official_facts, draft)
        final_post = step3_hard_filter(polished if polished else draft)
        
        lines = [line.strip() for line in final_post.split('\n') if line.strip()]
        if lines:
            post_title = re.sub(r"<[^>]+>", "", lines[0])
            post_body = "\n".join(lines[1:])
            
            print("\n" + "="*50)
            print(f"✨ [발행 예정 제목]: {post_title}")
            print("="*50 + "\n")
            
            # 3단계 발행 진행 후 성공하면 히스토리에 저장
            is_success = publish_to_blogger(post_title, post_body)
            if is_success and service_title:
                save_history(service_title)
                print(f"💾 발행 내역 저장 완료 ({service_title})")
        else:
            print("❌ 생성된 본문이 없습니다.")
