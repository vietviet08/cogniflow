import sys
import os
import json

# Đảm bảo thư mục api nằm trong python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import chromadb
    from app.core.config import get_settings
except ImportError as e:
    print(f"Lỗi: Không thể import cấu hình dự án hoặc chromadb. Hãy đảm bảo bạn đã kích hoạt virtual environment (.venv).")
    print(f"Chi tiết lỗi: {e}")
    sys.exit(1)

def inspect_chroma():
    settings = get_settings()
    host = settings.chroma_host
    port = settings.chroma_port
    
    print("="*60)
    print(f"KẾT NỐI TỚI CHROMADB TẠI: {host}:{port}")
    print("="*60)
    
    try:
        client = chromadb.HttpClient(host=host, port=port)
        collections = client.list_collections()
        
        if not collections:
            print("Không tìm thấy collection nào trong ChromaDB. Có thể bạn chưa tải lên/xử lý tài liệu nào.")
            return
            
        print(f"Tìm thấy {len(collections)} collections:")
        for idx, col in enumerate(collections, 1):
            count = col.count()
            print(f"{idx}. Tên Collection: {col.name}")
            print(f"   - Số lượng Vectors (Chunks): {count}")
            
            if count > 0:
                # Lấy 1 bản ghi mẫu để xem cấu trúc
                sample = col.peek(limit=1)
                print(f"   - Cấu trúc bản ghi mẫu:")
                
                # Check IDs
                ids = sample.get('ids')
                if ids and len(ids) > 0:
                    print(f"     + ID: {ids[0]}")
                
                # Check Embeddings
                embeddings = sample.get('embeddings')
                if embeddings is not None and len(embeddings) > 0 and embeddings[0] is not None:
                    try:
                        dim = len(embeddings[0])
                    except TypeError:
                        dim = "N/A"
                    print(f"     + Số chiều Vector (Dimension): {dim}")
                else:
                    print(f"     + Số chiều Vector (Dimension): N/A (Không có hoặc không lấy được)")
                
                # Check Metadatas
                metadatas = sample.get('metadatas')
                if metadatas and len(metadatas) > 0 and metadatas[0] is not None:
                    print(f"     + Metadata keys: {list(metadatas[0].keys())}")
                    print(f"     + Metadata sample: {json.dumps(metadatas[0], indent=7)}")
                else:
                    print(f"     + Metadata sample: Trống")
                
                # Check Documents
                documents = sample.get('documents')
                if documents and len(documents) > 0 and documents[0] is not None:
                    print(f"     + Nội dung text mẫu (200 ký tự đầu): \"{documents[0][:200]}...\"")
                else:
                    print(f"     + Nội dung text mẫu: Trống")
            print("-" * 60)
            
    except Exception as e:
        print(f"Lỗi kết nối tới ChromaDB: {e}")
        print("Hãy đảm bảo các container Docker (postgres và chroma) đang chạy.")
        print("Lệnh khởi động: docker compose -f infra/docker/docker-compose.local.yml up -d")

if __name__ == "__main__":
    inspect_chroma()
