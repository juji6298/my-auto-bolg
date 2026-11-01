import os
import json
import random
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import google.generativeai as genai

# 1. API 키 설정
gemini_api_key = os.environ.get("GEMINI_API_KEY")
public_data_key = os.environ.get("DATA_GO_KR_KEY")  # 공공데이터포털(data.go.kr) 인증키

if not gemini_api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

def fetch_from_data_go_kr():
    """[1순위] 공공데이터포털(data.go.kr) 행정안전부 보조금24 공식 오픈 API에서 팩트 수집"""
    if not public_data_key:
        print("ℹ️ DATA_GO_KR_KEY가 아직 등록되지 않아 정부 공식 정책브리핑 데이터로 대체합니다.")
        return None

    try:
        # 최근 등록/수정된 현금·보조금 혜택 목록 조회
        encoded_key = urllib.parse.quote(public_data_key) if "%" not in public_data_key else public_data_key
        page = random.randint(1, 5)
        url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage=10&serviceKey={encoded_key}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        items = data.get("data", [])
        if not items:
            return None
            
        # 내용이 충실한 지원금 정책 1건 선택
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
        print(f"⚠️ 공공데이터포털 API 호출 중 에러 발생: {e}")
        return None

def fetch_from_korea_kr_official():
    """[2순위 백업] 대한민국 정부 공식 정책브리핑(korea.kr) RSS에서 정책 원문 수집"""
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
        pub_date = chosen.find('pubDate').text if chosen.find('pubDate') is not None else ""
        
        fact_sheet = f"""
[대한민국 정부 공식 정책브리핑 원문 데이터]
- 공식 발표 제목: {title}
- 발표 일시: {pub_date}
- 정부 발표 원문 내용: {desc}
- 공식 원문 링크: {link}
"""
        return fact_sheet.strip()
    except Exception as e:
        print(f"⚠️ 정부 정책브리핑 수집 중 에러 발생: {e}")
        return None

def generate_blog_post_with_gemini(source_facts):
    """공식 정부 팩트 시트만을 기반으로 오차 없이 사람 냄새 나는 블로그 글 생성"""
    prompt = f"""
    너는 정부에서 발표하는 공식 지원금과 정책을 한 치의 오차도 없이 정확하게 파헤쳐서 알려주는 30대 깐깐한 K-직장인 블로거야.
    반드시 아래 제공된 [정부 공식 원본 데이터]에 적힌 사실만을 바탕으로, 친한 회사 동기에게 꿀팁을 떠먹여 주듯 생생한 티스토리 블로그 포스팅을 작성해줘.

    {source_facts}

    [🚨 100% 팩트 고정(Fact-Lock) 절대 규칙 - 위반 시 실패 처리]
    1. 외부 지식 및 추측 절대 금지: 지원 금액, 나이, 소득 기준, 신청 기한, 신청 방법은 **오직 위 [정부 공식 원본 데이터]에 적힌 내용만** 그대로 사용해. 원본 데이터에 없는 숫자를 임의로 지어내거나 추측해서 적으면 절대 안 돼.
    2. 정보 부족 시 솔직한 안내: 만약 원본 데이터에 세부 서류나 구체적인 액수가 '공고문 참조' 등으로 되어 있다면, 억지로 지어내지 말고 "세부 서류나 지자체별 예산은 아래 공식 링크(정부24)에서 본인 조건으로 꼭 조회해 보세요!"라고 정확히 안내해.
    3. 공식 확인 링크 제공: 글 마지막 부분에 독자가 바로 확인할 수 있도록 원본 데이터의 '공식 상세안내 링크' 주소를 넣어줘.

    [🗣️ AI 티 절대 안 나는 문체 규칙]
    1. AI 상투어 금지: "결론적으로", "요약하자면", "~에 대해 알아보았습니다", "도움이 되셨길 바랍니다" 같은 로봇 말투는 절대 쓰지 마.
    2. 직장인 현실 말투: "~더라고요", "~인 거 있죠?", "~하는 게 속 편해요", "안 챙기면 진짜 손해잖아요" 같은 자연스러운 구어체를 쓰고, 조건이나 신청 절차가 까다로운 점은 현실적으로 한두 번 투덜거려줘.
    3. 모바일 가독성: 2~3문장마다 줄바꿈을 시원하게 해주고, 핵심 지원 대상·혜택·기한은 **굵게** 강조해줘.
    4. 첫 줄 제목: 첫 번째 줄에는 클릭하고 싶어지는 매력적인 블로그 제목 딱 하나만 적어줘.
    """

    # 사용 가능한 모델 자동 탐색
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
        "models/gemini-2.0-flash",
    ]
    for pm in reversed(priority_models):
        if pm in candidate_models:
            candidate_models.remove(pm)
        candidate_models.insert(0, pm)

    # 창의성(temperature)을 0.1로 극단적으로 낮춰 사실 왜곡 차단
    generation_config = {"temperature": 0.1}

    for model_name in candidate_models:
        try:
            print(f"🔄 [{model_name}] 모델로 팩트 고정 글 생성 시도 중...")
            model = genai.GenerativeModel(model_name, generation_config=generation_config)
            response = model.generate_content(prompt)
            if response and response.text:
                print(f"✅ [{model_name}] 모델로 글 생성 성공!")
                return response.text
        except Exception as e:
            print(f"⚠️ [{model_name}] 건너뜀 (사유: {e})")
            continue

    return None

if __name__ == "__main__":
    print("📡 [1단계] 정부 공식 지원금 데이터를 수집합니다...")
    
    # 1순위: 공공데이터포털 보조금24 API 시도 -> 없으면 2순위: 정부 공식 정책브리핑 RSS 수집
    official_facts = fetch_from_data_go_kr()
    if not official_facts:
        official_facts = fetch_from_korea_kr_official()
        
    if official_facts:
        print("\n" + "="*50)
        print("📋 [확보된 정부 공식 원본 데이터 (100% 팩트 기준)]")
        print("="*50)
        print(official_facts)
        print("="*50 + "\n")
        
        print("🤖 [2단계] 확보된 공식 팩트를 바탕으로 블로그 글을 작성합니다...")
        generated_content = generate_blog_post_with_gemini(official_facts)
        
        if generated_content:
            print("\n" + "="*50)
            print("✨ [완성된 블로그 포스팅 본문]")
            print("="*50 + "\n")
            print(generated_content)
            print("\n" + "="*50)
    else:
        print("❌ 공식 데이터를 가져오지 못해 글 생성을 중단합니다. (오류 정보 생성 원천 차단)")
