from __future__ import annotations
import os, re, io, json, math, csv, itertools, mimetypes
from pathlib import Path
import PyPDF2
import pdfminer
import docx
import bs4
import pandas
import PIL
import pytesseract
import chardet
import cv2
import tempfile
from PIL import Image
import numpy as np

class TextExctractor:
    @classmethod
    def detect_encoding(cls, raw_bytes: bytes) -> str:
        if chardet is None:
            return 'utf-8'
        try:
            res = chardet.detect(raw_bytes)
            enc = res.get('encoding') or 'utf-8'
            return enc
        except Exception:
            return 'utf-8'

    @classmethod
    def extract_text_generic(cls, path: Path) -> str:
        # попытка прочитать как текст с автоопределением кодировки
        try:
            raw = path.read_bytes()
            enc = cls.detect_encoding(raw)
            return raw.decode(enc, errors='ignore')
        except Exception:
            return ''
    
    @classmethod
    def extract_text_pdf(cls, path: Path) -> str:
        text = ''
        if pdfminer is not None:
            try:
                from pdfminer.high_level import extract_text as pdfminer_extract
                text = pdfminer_extract(str(path)) or ''
                if text:
                    return text
            except Exception:
                pass
        if PyPDF2 is not None:
            try:
                with open(path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        try:
                            text += page.extract_text() or ''
                        except Exception:
                            pass
                return text
            except Exception:
                pass
        return text

    @classmethod
    def extract_text_docx(cls, path: Path) -> str:
        if docx is None:
            return ''
        try:
            from docx import Document
            doc = Document(str(path))
            parts = []
            for p in doc.paragraphs:
                parts.append(p.text)
            for tbl in doc.tables:
                for row in tbl.rows:
                    parts.append(' \t '.join(cell.text for cell in row.cells))
            return '\n'.join(parts)
        except Exception:
            return ''

    @classmethod
    def extract_text_html(cls, path: Path) -> str:
        txt = cls.extract_text_generic(path)
        if bs4 is None:
            return txt
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(txt, 'lxml') if 'lxml' in str(bs4.builder.__dict__) else BeautifulSoup(txt, 'html.parser')
            return soup.get_text(' ')
        except Exception:
            return txt

    @classmethod
    def extract_text_rtf(cls, path: Path) -> str:
        raw = cls.extract_text_generic(path)
        # грубое снятие управляющих последовательностей RTF
        raw = re.sub(r'\\[a-zA-Z]+-?\d*\s?', ' ', raw)
        raw = re.sub(r'[{}]', ' ', raw)
        return re.sub(r'\s+', ' ', raw)

    @classmethod
    def extract_text_ipynb(path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding='utf-8', errors='ignore'))
            parts = []
            for cell in data.get('cells', []):
                src = cell.get('source', [])
                if isinstance(src, list):
                    parts.append(''.join(src))
                elif isinstance(src, str):
                    parts.append(src)
            return '\n'.join(parts)
        except Exception:
            return ''

    @classmethod
    def extract_text_xls(cls, path: Path) -> str:
        if pandas is None:
            return ''
        try:
            # для .xls нужен xlrd; для .xlsx (если попадётся) — openpyxl
            df = pandas.read_excel(str(path), header=None, dtype=str)
            return '\n'.join(' '.join(map(str, row.dropna().tolist())) for _, row in df.iterrows())
        except Exception:
            return ''

    @classmethod
    def extract_text_image(cls, path: Path) -> str:
        if PIL is None or pytesseract is None:
            return ''
        try:
            from PIL import Image
            img = Image.open(str(path))
            return pytesseract.image_to_string(img, lang='rus+eng')
        except Exception:
            return ''
    
    @classmethod
    def extract_text_doc(cls, path: Path) -> str:
        raw = cls.extract_text_generic(path)
        return raw

    @classmethod    
    def extract_text_video(cls, path: Path, frame_interval_sec: float = 0.5) -> str:
        if cv2 is None:
            print(f"OpenCV (cv2) не установлен")
            return ''
        
        cap = None
        all_texts = []
        
        try:
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                print(f"Не удалось открыть видео {path.name}")
                return ''
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            print(f"Обработка видео {path.name}: {duration:.1f} сек, {total_frames} кадров, {fps} fps")
            
            frame_step = max(1, int(fps * frame_interval_sec))
            
            frame_number = 0
            processed_frames = 0
            max_frames = 50
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                while processed_frames < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    if frame_number % frame_step == 0:
                        timestamp = frame_number / fps
                        
                        temp_image_path = temp_path / f"frame_{frame_number}.jpg"
                        cv2.imwrite(str(temp_image_path), frame)
                        
                        text = cls.extract_text_image(temp_image_path)
            
                        try:
                            temp_image_path.unlink()
                        except:
                            pass
                        
                        if text and len(text.strip()) > 10:
                            all_texts.append(f"[{timestamp:.1f}s] {text.strip()}")
                            print(f"Найден текст на кадре {processed_frames + 1} ({timestamp:.1f}s): {text[:50]}...")
                        
                        processed_frames += 1
                    
                    frame_number += 1
                    
                    if frame_number > 5000:
                        print(f"Достигнут лимит кадров ({frame_number}) для {path.name}")
                        break
            
            cap.release()
            
            if all_texts:
                result = '\n'.join(all_texts)
                print(f"Всего извлечено {len(result)} символов из {len(all_texts)} кадров видео {path.name}")
                return result
            else:
                print(f"Текст не найден в {path.name} (обработано {processed_frames} кадров)")
                cls.debug_save_frames(path, frame_step, max_frames=5)
                return ''
                
        except Exception as e:
            print(f"  ✗ Ошибка обработки видео {path.name}: {e}")
            import traceback
            traceback.print_exc()
            return ''
        finally:
            if cap:
                cap.release()

    @classmethod
    def debug_save_frames(cls, path: Path, frame_step: int, max_frames: int = 5):
        try:
            debug_dir = Path('debug_frames')
            debug_dir.mkdir(exist_ok=True)
            
            cap = cv2.VideoCapture(str(path))
            frame_number = 0
            saved = 0
            
            while saved < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_number % frame_step == 0:
                    frame_path = debug_dir / f"{path.stem}_frame_{saved}.jpg"
                    cv2.imwrite(str(frame_path), frame)
                    print(f"  → Сохранён кадр {saved+1} для отладки: {frame_path}")
                    saved += 1
                
                frame_number += 1
            
            cap.release()
            print(f"  → Сохранено {saved} кадров в папку {debug_dir}")
            print(f"  → Проверьте эти кадры вручную. Если текст виден, проблема в настройках OCR")
        except Exception as e:
            print(f"  → Ошибка сохранения кадров: {e}")

    @classmethod
    def extract_text_parquet(cls, path: Path) -> str:
        try:
            import pandas as pd
            df = pd.read_parquet(str(path))
            return df.to_string()
        except ImportError:
            return "Parquet support requires pandas and pyarrow"
        except Exception:
            return ''
        
    @classmethod
    def extract_text_markdown(cls, path: Path) -> str:
        text = cls.extract_text_generic(path)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        return text
    
    @classmethod
    def extract_text_tiff(cls, path: Path) -> str:
        if PIL is None or pytesseract is None:
            return ''
        try:
            from PIL import Image
            img = Image.open(str(path))
            text_parts = []
            try:
                while True:
                    text_parts.append(pytesseract.image_to_string(img, lang='rus+eng'))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
            return '\n'.join(text_parts)
        except Exception:
            return ''

    @classmethod
    def extract_text(cls, path):
        ext = path.suffix.lower().lstrip('.')
        try:
            if ext in {'mp4'}:
                return cls.extract_text_video(path, frame_interval_sec=0.5)
            elif ext == 'pdf':
                return cls.extract_text_pdf(path)
            elif ext == 'docx':
                return cls.extract_text_docx(path)
            elif ext in {'html', 'php'}:
                return cls.extract_text_html(path)
            elif ext == 'rtf':
                return cls.extract_text_rtf(path)
            elif ext == 'ipynb':
                return cls.extract_text_ipynb(path)
            elif ext == 'xls':
                return cls.extract_text_xls(path)
            elif ext in {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'}:
                return cls.extract_text_image(path)
            elif ext == 'doc':
                return cls.extract_text_doc(path)
            elif ext in {'parquet'}:
                return cls.extract_text_parquet(path)
            elif ext in {'md'}:
                return cls.extract_text_markdown(path)
            elif ext in {'tiff', 'tif'}:
                return cls.extract_text_tiff(path)
            else:
                return cls.extract_text_generic(path)
        except Exception as e:
            print(f"  ✗ Ошибка в extract_text для {path.name}: {e}")
            return ''
        
