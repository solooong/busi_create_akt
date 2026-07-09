# extract_text.py
import pdfplumber
import sys
import os

def extract_text_from_pdf(pdf_path, output_txt_path):
    """
    Извлекает весь текст из PDF и сохраняет в TXT файл.
    Сохраняет текст каждой страницы с разделителями.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                f.write(f"=== PDF файл: {pdf_path} ===\n")
                f.write(f"=== Количество страниц: {len(pdf.pages)} ===\n\n")
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    f.write(f"\n{'='*80}\n")
                    f.write(f"=== СТРАНИЦА {i+1} ===\n")
                    f.write(f"{'='*80}\n\n")
                    
                    if text:
                        f.write(text)
                    else:
                        f.write("(страница не содержит текста)\n")
                    
                    f.write(f"\n\n{'='*80}\n")
                    f.write(f"=== КОНЕЦ СТРАНИЦЫ {i+1} ===\n")
                    f.write(f"{'='*80}\n\n")
                
                # Также сохраняем отдельно первую и последние страницы
                f.write(f"\n\n{'#'*80}\n")
                f.write(f"=== ПЕРВАЯ СТРАНИЦА (отдельно) ===\n")
                f.write(f"{'#'*80}\n\n")
                if pdf.pages:
                    first_text = pdf.pages[0].extract_text()
                    f.write(first_text or "(нет текста)")
                
                f.write(f"\n\n{'#'*80}\n")
                f.write(f"=== ПОСЛЕДНИЕ 3 СТРАНИЦЫ ===\n")
                f.write(f"{'#'*80}\n\n")
                for i in range(max(0, len(pdf.pages)-3), len(pdf.pages)):
                    text = pdf.pages[i].extract_text()
                    f.write(f"\n--- Страница {i+1} ---\n")
                    f.write(text or "(нет текста)")
                    f.write("\n")
        
        print(f"✅ Текст сохранён в: {output_txt_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = input("Введите путь к PDF файлу: ").strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"❌ Файл не найден: {pdf_path}")
        sys.exit(1)
    
    output_path = pdf_path.rsplit('.', 1)[0] + '_extracted.txt'
    extract_text_from_pdf(pdf_path, output_path)