# Mudo Stock Uygulaması - Production Guide

## 🚀 Sunucuda Deployment

### 1. Sunucu Gereksinimleri
- Ubuntu 20.04+ veya CentOS 7+
- Docker ve Docker Compose
- Nginx (reverse proxy için)
- SSL sertifikası (Let's Encrypt öneriliir)

### 2. Sunucuda Docker Kurulumu

```bash
# Ubuntu için Docker kurulumu
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker

# Kullanıcıyı docker grubuna ekle
sudo usermod -aG docker $USER
```

### 3. Projeyi Sunucuya Upload Etme

```bash
# Projeyi sunucuya kopyala (scp veya git kullanarak)
scp -r ./mudo-stock user@your-server:/var/www/mudo-stock

# Veya git ile
git clone your-repo-url /var/www/mudo-stock
```

### 4. Nginx Reverse Proxy Yapılandırması

`/etc/nginx/sites-available/mudo-stock` dosyası:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout ayarları (web scraping için önemli)
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 5. SSL Sertifikası (Let's Encrypt)

```bash
# Certbot kurulumu
sudo apt install certbot python3-certbot-nginx

# SSL sertifikası al
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 6. Deployment Komutları

```bash
# Sunucuda proje dizinine git
cd /var/www/mudo-stock

# Deploy script'ini çalıştır
./deploy.sh

# Veya manuel olarak
docker-compose up -d --build
```

### 7. Monitoring ve Maintenance

```bash
# Logları kontrol et
docker-compose logs -f

# Uygulamayı yeniden başlat
docker-compose restart

# Uygulamayı durdur
docker-compose down

# Image'ları temizle
docker system prune -a
```

### 8. Firewall Ayarları

```bash
# UFW firewall ayarları
sudo ufw allow 22      # SSH
sudo ufw allow 80      # HTTP
sudo ufw allow 443     # HTTPS
sudo ufw enable
```

### 9. Systemd Service (Otomatik Başlatma)

`/etc/systemd/system/mudo-stock.service`:

```ini
[Unit]
Description=Mudo Stock Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/var/www/mudo-stock
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# Service'i etkinleştir
sudo systemctl enable mudo-stock.service
sudo systemctl start mudo-stock.service
```

## 🔧 Yerel Test

Sunucuya deploy etmeden önce yerel olarak test edin:

```bash
# Yerel Docker test
./deploy.sh

# Tarayıcıda http://localhost:5000 adresini açın
```

## 📝 Notlar

- Web scraping işlemleri zaman alabilir, timeout değerlerini uygun şekilde ayarlayın
- Production'da debug modunu kapatın
- Log dosyalarını düzenli olarak temizleyin
- Backup stratejinizi belirleyin
