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

# 1. 환경 변수 및 기본 설정
gemini_api_key = os.environ.get("GEMINI_API_KEY")
public_data_key = os.environ.get("DATA_GO_KR_KEY")
blogger_id = os.environ.get("BLOGGER_ID")
client_id = os.environ.get("GOOGLE_CLIENT_ID")
client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

HISTORY_FILE = "posted_history.txt"
SCHEME = "ht" + "tps" + "://"

if not gemini_api_key:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

def clean_url(u):
    if not u:
        return ""
    u = str(u).strip()
    # 마크다운 링크 기호가 섞여 들어온 경우 순수 URL만 추출
    if "](" in u and u.endswith(")"):
        u = u.split("](")[-1][:-1].strip()
