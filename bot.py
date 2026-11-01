import os
import google.generativeai as genai

# 제미나이 API 키 설정
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=api_key)

def generate_blog_post_with_gemini():
    """제미나이(Gemini)로 사람 냄새 나는 정부 지원금 글 생성"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = """
        너는 매일 야근에 시달리지만, 정부에서 주는 꽁돈과 혜택은 기가 막히게 찾아먹는 30대 깐깐한 K-직장인이야.
        마치 친한 회사 동기한테 "야, 너 이거 신청했어? 당장 해!"라며 메신저로 몰래 꿀팁을 털어놓듯이, 아주 솔직하고 사람 냄새 찐하게 나는 티스토리 블로그 포스팅을 작성해줘.

        [🚨 AI 티 절대 안 나는 초특급 작성 규칙]
        1. AI 단골 멘트 절대 금지: "결론적으로", "요약하자면", "~에 대해 알아보았습니다", "도움이 되셨길 바랍니다", "그렇다면 어떻게 신청할까요?" 같은 뻔한 로봇 말투는 무조건 빼. 
        2. 현실적인 빡침(?)과 공감 한 스푼: 정부 지원금 특유의 짜증나는 점(서류 준비 귀찮음, 조건 빡셈, 사이트 버벅거림 등)을 한두 번 슬쩍 투덜거려줘. ("아니, 조건 좀 넉넉하게 해주지 솔직히 너무 깐깐한 거 아니냐고요ㅋㅋ", "인증서 때문에 화딱지 날 뻔했지만 꽁돈이니 참았습니다")
        3. 찐텐 구어체: "~합니다", "~해요" 대신 "~더라고요", "~인 거 있죠?", "~하는 게 맘 편해요", "이건 무조건 챙기세요", "안 받으면 손해잖아요" 같은 생생한 실전 말투를 써줘.
        4. 기계적인 서식 파괴: '첫째, 둘째, 셋째' 금지. 대신 "가장 중요한 건 이거예요", "이거 놓치면 진짜 억울합니다" 식으로 대화하듯 흐름을 이어가.
        5. 모바일 최적화 띄어쓰기: 사람들이 폰으로 많이 보니까 2~3문장마다 줄바꿈을 시원시원하게 해줘. 가독성 좋게 진짜 중요한 조건이나 금액은 **굵게** 강조도 해주고.
        6. 마지막 인사 생략: 억지로 마무리하는 인사말 없이, 꿀팁 하나 툭 던져주고 쿨하게 끝내.
        7. 첫 줄: 검색 클릭률 미치게 만드는, 어그로성 짙지만 내용이 알찬 '진짜 사람 냄새나는 블로그 제목' 딱 하나만 써줘.
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"제미나이 글 생성 중 에러 발생: {e}")
        return None

if __name__ == "__main__":
    print("🤖 [티스토리 맞춤형] 제미나이가 사람 냄새 나는 지원금 글을 작성합니다...")
    
    generated_content = generate_blog_post_with_gemini()
    
    if generated_content:
        print("\n" + "="*50)
        print("✨ [생성된 블로그 포스팅 미리보기]")
        print("="*50 + "\n")
        print(generated_content)
        print("\n" + "="*50)
