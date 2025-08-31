from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urlencode
import os

app = Flask(__name__, template_folder='.')

# Static dosyalar için route
@app.route('/<path:filename>')
def static_files(filename):
    """CSS, JS ve diğer static dosyaları serve etmek için"""
    if filename.endswith('.css') or filename.endswith('.js') or filename.endswith('.ico'):
        return send_from_directory('.', filename)
    return "File not found", 404

def scrape_mudo_stock(barcode):
    """Mudo API'sinden stok bilgilerini çeker"""
    try:
        # Mudo stok sorgulama URL'si
        url = f"http://mudonetapps.mudo.com.tr/StokSorgula/StokSorgula?kod={barcode}"
        
        # HTTP headers - gerçek tarayıcı gibi görünmek için
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        print(f"Sorgu URL: {url}")
        
        # HTTP isteği gönder
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        print(f"HTTP Status: {response.status_code}")
        print(f"Content Length: {len(response.text)}")
        
        # HTML içeriğini parse et
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Farklı yöntemlerle stok bilgilerini bulmaya çalış
        stock_data = []
        product_info = {}
        variants = []  # Yeni: Varyant bilgileri
        
        # 1. Ürün ismi ve başlık bilgisini al (Title'dan değil, ürün detaylarından)
        # Title bilgisini son çare olarak al
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.get_text().strip()
            if title_text and title_text != "MUDO - Stok Sorgula":
                product_info['title'] = title_text
        
        # Ürün ismini farklı yerlerden aramaya çalış
        product_name = None
        
        # 1. H1, H2, H3 başlıklarında ara
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text().strip()
            if text and len(text) > 5 and 'stok' not in text.lower() and 'mudo' not in text.lower():
                product_name = text
                break
        
        # 2. Script tag'lerinde ürün ismi ara
        if not product_name:
            scripts = soup.find_all('script', string=True)
            for script in scripts:
                script_content = script.string
                if script_content:
                    # "urunAdi" veya benzer pattern'leri ara
                    name_patterns = [
                        r'"urunAdi"\s*:\s*"([^"]+)"',
                        r'"productName"\s*:\s*"([^"]+)"',
                        r'"name"\s*:\s*"([^"]+)"',
                        r'urunAdi\s*=\s*"([^"]+)"'
                    ]
                    
                    for pattern in name_patterns:
                        match = re.search(pattern, script_content)
                        if match and len(match.group(1)) > 5:
                            product_name = match.group(1)
                            break
                    
                    if product_name:
                        break
        
        # 3. Ürün kodu ile birlikte ürün ismi çek
        if not product_name:
            # Tablolarda ürün ismini ara
            tables = soup.find_all('table')
            for table in tables:
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text().strip().lower()
                        value = cells[1].get_text().strip()
                        
                        if ('ürün ad' in label or 'model ad' in label or 'isim' in label) and len(value) > 5:
                            product_name = value
                            break
                
                if product_name:
                    break
        
        # Ürün ismini product_info'ya ekle
        if product_name:
            product_info['title'] = product_name
            print(f"🎯 Ürün ismi bulundu: {product_name}")
        else:
            print("⚠️ Ürün ismi bulunamadı, varsayılan başlık kullanılacak")
        
        # Ürün detay bilgilerini çek
        product_details = {}
        
        # Ürün bilgilerini içeren div/span/td elementlerini ara
        all_elements = soup.find_all(['div', 'span', 'td', 'p'])
        for element in all_elements:
            text = element.get_text().strip()
            
            # Ürün kodu pattern'i
            if re.search(r'ürün\s*no|model\s*no|ürün\s*kodu', text.lower()):
                # Bir sonraki elementi veya aynı elementteki kodu bul
                code_match = re.search(r'(\d{3}-\d-\d{3}-\d{2}-\d{3}|\d+)', text)
                if code_match:
                    product_details['product_code'] = code_match.group(1)
            
            # Fiyat bilgisi
            if re.search(r'₺|tl|lira|fiyat', text.lower()) and re.search(r'\d+', text):
                price_match = re.search(r'(\d+[.,]?\d*)\s*(?:₺|tl)', text)
                if price_match:
                    product_details['price'] = price_match.group(1).replace(',', '.') + ' TL'
            
            # Satış durumu
            if re.search(r'satış\s*durumu|durum', text.lower()):
                if 'açık' in text.lower():
                    product_details['sale_status'] = 'Satışta'
                elif 'kapalı' in text.lower():
                    product_details['sale_status'] = 'Satış Dışı'
            
            # İndirim oranı
            if '%' in text and re.search(r'\d+', text):
                discount_match = re.search(r'%\s*(\d+)', text)
                if discount_match:
                    product_details['discount'] = f"%{discount_match.group(1)} İndirim"
        
        # Form elementlerinden de bilgi çek
        inputs = soup.find_all('input')
        for inp in inputs:
            if inp.get('id') or inp.get('name'):
                field_name = (inp.get('id') or inp.get('name')).lower()
                value = inp.get('value', '').strip()
                
                if 'fiyat' in field_name and value and re.search(r'\d', value):
                    product_details['price'] = value + ' TL'
                elif 'kod' in field_name and value:
                    product_details['product_code'] = value
        
        # Tablo hücrelerinden ürün bilgilerini çek
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text().strip().lower()
                    value = cells[1].get_text().strip()
                    
                    if 'ürün no' in label or 'model no' in label:
                        product_details['product_code'] = value
                    elif 'fiyat' in label and value:
                        product_details['price'] = value
                    elif 'durum' in label or 'satış' in label:
                        product_details['sale_status'] = value
        
        product_info.update(product_details)
        
        print(f"🔍 Product Info Debug: {product_info}")
        print(f"🔍 Title: {product_info.get('title', 'YOK')}")
        
        # 2. Varyant tablosunu ara (Renk/Beden kombinasyonları)
        print("🎨 Varyant bilgileri aranıyor...")
        variant_tables = soup.find_all('table')
        for table in variant_tables:
            # Tablo başlıklarını kontrol et
            headers = table.find_all('th')
            header_texts = [th.get_text().strip().lower() for th in headers]
            
            # Varyant tablosu olup olmadığını kontrol et
            if any(keyword in ' '.join(header_texts) for keyword in ['renk', 'beden', 'mal no', 'barkod']):
                print("✅ Varyant tablosu bulundu!")
                rows = table.find_all('tr')[1:]  # İlk satır başlık
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:  # En az 4 sütun olmalı
                        try:
                            # Sütunları parse et
                            color = cells[0].get_text().strip() if len(cells) > 0 else ""
                            size = cells[1].get_text().strip() if len(cells) > 1 else ""
                            product_code = cells[2].get_text().strip() if len(cells) > 2 else ""
                            variant_barcode = cells[3].get_text().strip() if len(cells) > 3 else ""
                            
                            # Geçerli varyant mı kontrol et
                            if (color and size and variant_barcode and 
                                len(variant_barcode) >= 10 and variant_barcode.isdigit()):
                                
                                variants.append({
                                    'color': color,
                                    'size': size,
                                    'product_code': product_code,
                                    'barcode': variant_barcode,
                                    'display_name': f"{color} - {size}"
                                })
                                print(f"🎨 Varyant: {color} - {size} ({variant_barcode})")
                        except Exception as e:
                            print(f"⚠️ Varyant parse hatası: {e}")
                            continue
        
        # 3. Tablo içindeki stok bilgilerini ara
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    store_name = cells[0].get_text().strip()
                    stock_count = cells[1].get_text().strip()
                    
                    # Sayısal değer var mı kontrol et
                    if store_name and (re.search(r'\d+', stock_count) or 'stok' in stock_count.lower()):
                        stock_data.append({
                            'store': store_name,
                            'stock': stock_count
                        })
        
        # 4. Div elementlerindeki stok bilgilerini ara
        divs = soup.find_all('div')
        for div in divs:
            text = div.get_text().strip()
            # Mağaza adı ve stok sayısı pattern'leri
            patterns = [
                r'([A-Za-zÇĞıİÖŞÜçğıiöşü\s]+)[\s:]+(\d+)',
                r'([A-Za-zÇĞıİÖŞÜçğıiöşü\s]+)[\s:]+(\d+\s*adet)',
                r'([A-Za-zÇĞıİÖŞÜçğıiöşü\s]+)[\s:]+(\d+\s*stok)'
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    store_name = match.group(1).strip()
                    stock_count = match.group(2).strip()
                    if 2 < len(store_name) < 50:
                        stock_data.append({
                            'store': store_name,
                            'stock': stock_count
                        })
        
        # 5. Span elementlerindeki bilgileri ara
        spans = soup.find_all('span')
        store_names = []
        stock_counts = []
        
        for span in spans:
            text = span.get_text().strip()
            # Sadece sayı
            if re.match(r'^\d+$', text):
                stock_counts.append(text)
            # Mağaza ismi olabilecek metin
            elif 3 < len(text) < 50 and '©' not in text and 'http' not in text:
                store_names.append(text)
        
        # Mağaza isimleri ve stok sayılarını eşleştir
        min_length = min(len(store_names), len(stock_counts))
        for i in range(min_length):
            stock_data.append({
                'store': store_names[i],
                'stock': stock_counts[i]
            })
        
        # 6. Script taglerindeki JSON verilerini ara
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                script_content = script.string
                if any(keyword in script_content.lower() for keyword in ['stok', 'stock', 'magaza']):
                    print(f"İlgili script bulundu: {script_content[:200]}...")
                    
                    # JSON pattern'lerini ara
                    json_matches = re.findall(r'\{[^{}]*(?:"stok"|"stock"|"magaza")[^{}]*\}', script_content)
                    for match in json_matches:
                        try:
                            data = json.loads(match)
                            print(f"Script JSON data: {data}")
                        except json.JSONDecodeError:
                            continue
        
        # Duplicate'leri temizle ve gereksiz verileri filtrele
        unique_stock_data = []
        seen = set()
        
        # Gerçek mağaza isimlerini tanımlayalım (whitelist yaklaşımı)
        valid_store_patterns = [
            # City mağazaları
            r'.*city.*', r'.*vadistanbul.*', r'.*mall.*', r'.*avm.*', r'.*center.*',
            # Giyim mağazaları
            r'.*giyim.*', r'.*home.*', r'.*concept.*', r'.*marina.*', r'.*outlet.*',
            # Şehir isimleri içeren mağazalar
            r'.*istanbul.*', r'.*ankara.*', r'.*izmir.*', r'.*bursa.*', r'.*antalya.*',
            r'.*adana.*', r'.*trabzon.*', r'.*kayseri.*', r'.*samsun.*', r'.*gaziantep.*',
            r'.*malatya.*', r'.*eskişehir.*', r'.*bodrum.*', r'.*marmaris.*',
            # Belirli mağaza isimleri
            r'.*akmerkez.*', r'.*cevahir.*', r'.*carousel.*', r'.*palladium.*',
            r'.*nautilus.*', r'.*aqua.*', r'.*tema.*', r'.*nişantaşı.*', r'.*maslak.*',
            r'.*pendik.*', r'.*capitol.*', r'.*çanakkale.*', r'.*balıkesir.*',
            r'.*tekirdağ.*', r'.*bandırma.*', r'.*mersin.*', r'.*alanya.*'
        ]
        
        for item in stock_data:
            store_name = item['store'].lower().strip()
            stock_count = item['stock'].strip()
            
            # Önce whitelist kontrolü - gerçek mağaza ismi var mı?
            is_valid_store = False
            for pattern in valid_store_patterns:
                if re.search(pattern, store_name):
                    is_valid_store = True
                    break
            
            # Eğer geçerli mağaza ismi değilse, filtrelenecek veriler listesini kontrol et
            if not is_valid_store:
                continue
                
            # Stok sayısı kontrolü - sadece sayı içermeli
            if not re.search(r'\d+', stock_count) or len(stock_count) > 10:
                continue
                
            # Çok kısa veya çok uzun isimler
            if len(store_name) < 4 or len(store_name) > 60:
                continue
            
            # Duplicate kontrolü
            key = (store_name, stock_count)
            if key not in seen:
                seen.add(key)
                unique_stock_data.append(item)
        
        # Vadistanbul City (183) mağazasını öncelikli olarak ayır
        priority_store = None
        other_stores = []
        
        for item in unique_stock_data:
            store_name = item['store'].lower()
            # Vadistanbul City'yi farklı şekillerde arayalım
            if 'vadistanbul' in store_name and 'city' in store_name:
                priority_store = item
                # Mağaza adını temizle ve standardize et
                item['store'] = "Vadistanbul City (183)"
                item['is_priority'] = True
            else:
                # Diğer mağaza isimlerini de temizle
                clean_name = item['store'].strip()
                # Satır sonlarını ve gereksiz boşlukları temizle
                clean_name = re.sub(r'\s+', ' ', clean_name)
                item['store'] = clean_name
                other_stores.append(item)
        
        # Öncelikli mağazayı en başa koy
        final_stock_data = []
        if priority_store:
            final_stock_data.append(priority_store)
        final_stock_data.extend(other_stores)
        
        print(f"Filtrelenmiş veriler: Ham {len(stock_data)} -> Geçerli {len(unique_stock_data)} -> Final {len(final_stock_data)}")
        print(f"Vadistanbul City bulundu: {priority_store is not None}")
        print(f"Varyant sayısı: {len(variants)}")
        if final_stock_data:
            print(f"İlk 3 mağaza: {[item['store'] for item in final_stock_data[:3]]}")
        
        return {
            'success': True,
            'product_info': product_info,
            'stock_data': final_stock_data,
            'variants': variants,  # Yeni: Varyant bilgilerini ekle
            'priority_store': priority_store,
            'total_filtered': len(stock_data) - len(final_stock_data),
            'url': url
        }
        
    except requests.exceptions.RequestException as e:
        print(f"HTTP isteği hatası: {e}")
        return {
            'success': False,
            'error': f'HTTP isteği başarısız: {str(e)}',
            'url': url if 'url' in locals() else None
        }
    except Exception as e:
        print(f"Genel hata: {e}")
        return {
            'success': False,
            'error': f'Beklenmeyen hata: {str(e)}',
            'url': url if 'url' in locals() else None
        }

@app.route('/')
def index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/search', methods=['POST'])
def search():
    """Stok sorgulama endpoint'i"""
    try:
        # JSON verilerini al
        data = request.get_json()
        barcode = data.get('barcode')
        
        print(f"🔍 Stok sorgusu başlatılıyor: {barcode}")
        
        if not barcode:
            return jsonify({
                'success': False,
                'error': 'Barkod numarası gerekli',
                'stock_data': [],
                'variants': []
            })
        
        # Mudo'dan stok bilgilerini çek
        result = scrape_mudo_stock(str(barcode))
        
        if result['success']:
            stock_data = result.get('stock_data', [])
            variants = result.get('variants', [])
            
            print(f"✅ Sorgu başarılı: {len(stock_data)} mağaza, {len(variants)} varyant")
            
            return jsonify({
                'success': True,
                'stock_data': stock_data,
                'variants': variants,  # Yeni: Varyant bilgileri
                'product_info': result.get('product_info', {}),
                'priority_store': result.get('priority_store'),
                'debug_info': {
                    'url': result.get('url'),
                    'total_filtered': result.get('total_filtered', 0),
                    'variant_count': len(variants)
                }
            })
        else:
            print(f"❌ Sorgu başarısız: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Bilinmeyen hata'),
                'stock_data': [],
                'variants': [],
                'debug_info': {
                    'url': result.get('url')
                }
            })
        
    except Exception as e:
        print(f"❌ Endpoint hatası: {e}")
        return jsonify({
            'success': False,
            'error': f'Sunucu hatası: {str(e)}',
            'stock_data': [],
            'variants': []
        })

if __name__ == '__main__':
    # Development için
    app.run(debug=True, host='0.0.0.0', port=8083)
