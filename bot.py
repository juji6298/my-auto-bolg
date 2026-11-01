import os
import re
import json
import random
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import google.generativeai as genai

# 1. API 키 설정
gemini_api_key = os.environ.get("GEMINI_API_KEY")
public_data_key = os.environ.get("DATA_GO_KR_KEY")

if not gemini_api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

def get_working_model_name():
    """현재 API 키로 사용 가능한 최적의 제미나이 모델 자동 탐색"""
    candidate_models = []
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods and "gemini" in m.name:
                if not any(skip in m.name.lower() for skip in ["vision", "imagen", "veo", "tts", "audio", "embedding", "image"]):
                    candidate_models.append(m.name)
    except Exception as e:
        print(f"모델 목록 조회 중 에러: {e}")

    priority_models = [
        "models/gemini-3.8-flash",
        "models/gemini-3.0-flash",
        "models/gemini-2.5-pro",
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
    ]
    for pm in reversed(priority_models):
        if pm in candidate_models:
            candidate_models.remove(pm)
        candidate_models.insert(0, pm)
    return candidate_models

def fetch_from_data_go_kr():
    """[1순위] 공공데이터포털 보조금24 공식 오픈 API에서 팩트 수집"""
    if not public_data_key:
        return None
    try:
        encoded_key = urllib.parse.quote(public_data_key) if "%" not in public_data_key else public_data_key
        page = random.randint(1, 10)
        url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage=15&serviceKey={encoded_key}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        items = data.get("data", [])
        if not items:
            return None
            
        valid_items = [item for item in items if item.get("지원내용") and item.get("지원대상")]
        chosen = random.choice(valid_items if valid_items else items)
        
        fact_sheet = f"""
[대한민국 행정안전부 보조금24 공식 데이터]
- 정책(서비스)명: {chosen.get('서비스명', '정보 없음')}
- 소관기관명: {chosen.get('소관기관명', '정보 없음')}
- 지원유형: {chosen.get('지원유형', '정보 없음')}
- 서비스목적(요약): {chosen.get('서비스목적요약', '정보 없음')}
- 지원대상: {chosen.get('지원대상', '정보 없음')}
- 선정기준: {chosen.get('선정기준', '별도 명시 없음 (공고문 확인 필요)')}
- 지원내용(금액/혜택): {chosen.get('지원내용', '정보 없음')}
- 신청방법: {chosen.get('신청방법', '정보 없음')}
- 신청기한: {chosen.get('신청기한', '정보 없음')}
- 문의처: {chosen.get('문의처', '정부24 확인')}
- 정부24 공식 상세안내 링크: {chosen.get('상세조회URL', 'https://www.gov.kr')}
"""
        return fact_sheet.strip()
    except Exception as e:
        print(f"⚠️ 공공데이터포털 API 호출 중 에러: {e}")
        return None

def fetch_from_korea_kr_official():
    """[2순위 백업] 정부 공식 정책브리핑(korea.kr) RSS 수집"""
    url = "https://www.korea.kr/rss/policy.xml"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        items = root.findall('./channel/item')[:10]
        if not items:
            return None
        chosen = random.choice(items)
        title = chosen.find('title').text if chosen.find('title') is not None else ""
        desc = chosen.find('description').text if chosen.find('description') is not None else ""
        link = chosen.find('link').text if chosen.find('link') is not None else ""
        return f"[정부 공식 정책브리핑]\n- 제목: {title}\n- 내용: {desc}\n- 공식 링크: {link}"
    except Exception as e:
        print(f"⚠️ 정책브리핑 수집 에러: {e}")
        return None

def call_gemini(prompt, temperature=0.2):
    """모델 자동 순회 호출 함수"""
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
    """[1차 생성] 오차 0% 팩트 기반 초안 작성"""
    prompt = f"""
    아래 [정부 공식 원본 데이터]의 사실만을 100% 그대로 반영해서, 30대 직장인 블로거 말투로 정부 지원금 안내 초안을 작성해줘.
    원본에 없는 숫자나 조건은 절대 추측해서 적지 마.

    {source_facts}
    """
    return call_gemini(prompt, temperature=0.1)

def step2_proofread_and_humanize(source_facts, draft_text):
    """[2차 검수] 팩트 대조 + 오탈자 교정 + AI 탐지 회피 리라이팅"""
    prompt = f"""
    너는 10년 차 블로그 전문 편집장이자 AI 텍스트 탐지 회피 전문가야.
    아래 [1차 초안]을 [정부 공식 원본 데이터]와 대조하여 검수하고, 포털 사이트의 AI 탐지기에 절대 걸리지 않도록 완벽한 인간 문체로 교정해줘.

    [정부 공식 원본 데이터]
    {source_facts}

    [1차 초안]
    {draft_text}

    [🛠️ 필수 교정 및 AI 탐지 회피 지침]
    1. 팩트 완전 대조: 초안의 금액, 조건, 신청기한이 원본 데이터와 조금이라도 다르면 즉시 원본 기준으로 고쳐.
    2. 맞춤법 및 오탈자 완벽 교정: 어색한 조사, 띄어쓰기 오류, 오타, 번역투 문장을 자연스러운 한국어 구어체로 다듬어.
    3. 문장 길이 불규칙화 (Burstiness 적용): AI 탐지기를 피하기 위해 아주 짧은 문장("솔직히 이거 안 챙기면 손해죠.", "생각보다 간단하더라고요.")과 2~3줄짜리 설명 문장을 불규칙하게 섞어서 리듬감을 만들어.
    4. AI 상투어 완전 삭제: "결론적으로", "요약하자면", "지금까지 ~를 알아보았습니다", "첫째, 둘째", "도움이 되셨기를 바랍니다" 같은 표현은 흔적도 없이 지워.
    5. 마크다운 기호 금지 & HTML 서식 적용: 별표(**)나 샵(###) 같은 마크다운 기호를 쓰지 말고, 티스토리에 바로 붙여넣을 수 있게 소제목은 <h3>, 강조할 핵심 조건은 <b>, 문단 나눔은 <p>와 <br> 태그로 깔끔하게 감싸줘.
    6. 출력 형식:
       첫 번째 줄에는 태그 없이 '블로그 제목'만 딱 한 줄 적고,
       두 번째 줄부터 HTML 서식이 적용된 본문을 출력해.
    """
    return call_gemini(prompt, temperature=0.35)

def step3_hard_filter(text):
    """[3차 파이썬 필터] AI 잔여 기호 및 금지어 강제 제거"""
    # 마크다운 코드블록(```html 등) 및 잔여 별표(**) 제거
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = text.replace("```", "").replace("**", "")
    
    # AI 단골 마무리 멘트 강제 삭제
    banned_phrases = [
        "결론적으로", "요약하자면", "도움이 되셨기를 바랍니다", 
        "도움이 되셨길 바랍니다", "지금까지 알아보았습니다"
    ]
    for phrase in banned_phrases:
        text = text.replace(phrase, "")
        
    return text.strip()

if __name__ == "__main__":
    print("📡 [1단계] 정부 공식 데이터를 수집합니다...")
    official_facts = fetch_from_data_go_kr() or fetch_from_korea_kr_official()
    
    if not official_facts:
        print("❌ 공식 데이터를 가져오지 못해 중단합니다.")
        exit(1)

    print("✍️ [2단계] 1차 팩트 기반 초안을 작성합니다...")
    draft = step1_generate_draft(official_facts)
    
    if draft:
        print("🔍 [3단계] 자체 오탈자 교정 및 AI 탐지 회피(Humanizing) 검수를 진행합니다...")
        polished = step2_proofread_and_humanize(official_facts, draft)
        final_post = step3_hard_filter(polished if polished else draft)
        
        lines = [line.strip() for line in final_post.split('\n') if line.strip()]
        post_title = re.sub(r"<[^>]+>", "", lines[0]) # 제목에서 태그 제거
        post_body = "\n".join(lines[1:])
        
        print("\n" + "="*50)
        print(f"📌 [최종 검수 완료 제목]: {post_title}")
        print("="*50)
        print(post_body)
        print("="*50 + "\n")
