#!/bin/bash

# Renkli output için
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Mudo Stock Uygulaması Deploy Scripti${NC}"
echo "========================================"

# Docker ve Docker Compose kontrolü
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker yüklü değil. Lütfen önce Docker'ı yükleyin.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose yüklü değil. Lütfen önce Docker Compose'u yükleyin.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Docker image'ı build ediliyor...${NC}"
docker-compose build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build başarılı!${NC}"
else
    echo -e "${RED}❌ Build başarısız!${NC}"
    exit 1
fi

echo -e "${YELLOW}🚀 Uygulama başlatılıyor...${NC}"
docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Uygulama başarıyla başlatıldı!${NC}"
    echo -e "${GREEN}🌐 Uygulama http://localhost:5000 adresinde çalışıyor${NC}"
    echo ""
    echo "Diğer komutlar:"
    echo "- Logları görmek için: docker-compose logs -f"
    echo "- Durdurmak için: docker-compose down"
    echo "- Yeniden başlatmak için: docker-compose restart"
else
    echo -e "${RED}❌ Uygulama başlatılamadı!${NC}"
    exit 1
fi
