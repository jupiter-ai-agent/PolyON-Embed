FROM python:3.11-slim

WORKDIR /app

# PyTorch CPU 버전 먼저 설치 (별도 인덱스 필요)
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# 나머지 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 모델 사전 다운로드 (이미지에 번들)
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
model = SentenceTransformer('intfloat/multilingual-e5-base'); \
model.save('/app/models/intfloat_multilingual-e5-base'); \
print('Model saved.') \
"

# 앱 소스
COPY app/ .

EXPOSE 4001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4001"]
