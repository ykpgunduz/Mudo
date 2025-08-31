# Python 3.11 slim imajını kullan
FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem paketlerini güncelle ve gerekli paketleri yükle
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Requirements dosyasını kopyala ve bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Gunicorn WSGI server'ını yükle (production için)
RUN pip install gunicorn

# Uygulama dosyalarını kopyala
COPY . .

# Flask uygulaması için port 5000'i aç
EXPOSE 5000

# Gunicorn ile uygulamayı çalıştır
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
